"""
PhotoFlow AI - Blur Detector V2 Batch Service

Orchestrates v2 blur detection across a list of photos.
Uses ProcessPoolExecutor for parallel processing — N cores ≈ N× speedup.

Each worker process independently handles a chunk of photos:
opens OpenCV, reads the image, computes Laplacian variance, and
returns results.  The main thread aggregates results and writes
to SQLite (single-threaded to avoid lock conflicts).

Background-thread support (start / progress / cancel) mirrors
the v1 service pattern so the frontend can poll for real-time
updates.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import TYPE_CHECKING, Optional

from .detector import calculate_blur_v2
from .models import BlurDetectionSummary

if TYPE_CHECKING:
    from database.repository import PhotoRepository

logger = logging.getLogger("blur_detection_v2")

from backend.logging_config import setup_blur_v2_logging

setup_blur_v2_logging()

# ---------------------------------------------------------------------------
# In-memory task registry (same pattern as v1)
# ---------------------------------------------------------------------------

_tasks: dict[str, dict] = {}
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Parallel worker (module-level for ProcessPoolExecutor pickling)
# ---------------------------------------------------------------------------


def _process_blur_chunk(
    chunk: list[tuple[str, str, str | None, float | None, float | None, float | None]],
) -> list[tuple[str, bool, float, int, str | None, str | None]]:
    """Process a chunk of photos in a worker process.  (See module docstring.)

    Args:
        chunk: List of ``(image_id, readable_path, preview_path,
            threshold, preview_sharp_threshold, preview_blur_threshold)``.
            Each threshold may be ``None`` (use module default).

    Returns:
        List of ``(image_id, success, final_score, is_blur, error_msg,
        patch_scores_json)``.
    """
    from backend.ai.blur_detector_v2.detector import (
        calculate_blur_v2 as _calc,
        quick_blur_check,
        PREVIEW_SHARP_THRESHOLD,
        PREVIEW_BLUR_THRESHOLD,
        build_patch_scores_cache,
    )
    from backend.ai.ai_preview.preview_generator import ensure_preview

    results: list[tuple[str, bool, float, int, str | None, str | None]] = []
    for image_id, readable_path, preview_path, threshold, prev_sharp, prev_blur in chunk:
        try:
            # ---- Tier 1: ensure 800 px AI preview ----
            if preview_path is None:
                from backend.ai.ai_preview.preview_generator import get_preview_path as _gpp
                preview_path = _gpp(image_id)
            preview_path = ensure_preview(image_id, readable_path)

            # ---- Tier 2: quick Laplacian on 800 px preview ----
            quick_score, verdict = quick_blur_check(
                preview_path,
                sharp_threshold=prev_sharp,
                blur_threshold=prev_blur,
            )

            _ps = prev_sharp if prev_sharp is not None else PREVIEW_SHARP_THRESHOLD
            _pb = prev_blur if prev_blur is not None else PREVIEW_BLUR_THRESHOLD
            if verdict == "sharp":
                safe_score = max(quick_score, float(_ps))
                results.append((image_id, True, safe_score, 0, None, None))
                continue
            elif verdict == "blur":
                safe_score = min(quick_score, float(_pb))
                results.append((image_id, True, safe_score, 1, None, None))
                continue

            # ---- Tier 3: borderline — full multi-patch analysis ----
            final_score, is_blur, patch_scores, _proc_ms, weighted_score, top_median = _calc(
                readable_path, threshold=threshold,
            )
            # Cache intermediate scores so re-analysis with a different
            # threshold can skip the expensive Laplacian computation.
            cache_json = build_patch_scores_cache(patch_scores, weighted_score, top_median)
            results.append((image_id, True, final_score, is_blur, None, cache_json))
        except Exception as exc:
            results.append((image_id, False, 0.0, 0, str(exc), None))
    return results


def _run_blur_loop_v2(
    task_id: str,
    photo_ids: list[str],
    threshold: float | None,
    skip_ids: set[str] | None = None,
    preview_sharp_threshold: float | None = None,
    preview_blur_threshold: float | None = None,
) -> None:
    """Run v2 blur detection in a background thread, updating shared state.

    Uses ProcessPoolExecutor for parallel processing:
    - Photos are split into chunks and distributed across worker processes.
    - Each worker calls ``calculate_blur_v2`` independently.
    - SQLite writes happen ONLY in this (main) thread to avoid lock conflicts.
    - N CPU cores → close to N× speedup on the blur step.

    Args:
        task_id: Unique task identifier for progress polling.
        photo_ids: List of image_id values to process.
        threshold: Optional override for the blur threshold.
        skip_ids: Optional set of image_id values to skip (counted toward
            progress but not actually processed).  Used for closed-eye photos
            that have already been flagged as unfixable.
        preview_sharp_threshold: Optional override for PREVIEW_SHARP_THRESHOLD.
        preview_blur_threshold: Optional override for PREVIEW_BLUR_THRESHOLD.
    """
    from database.repository import PhotoRepository

    repo = PhotoRepository()

    state = _tasks.get(task_id)
    if not state:
        return

    _skip = skip_ids or set()

    total = len(photo_ids)
    state["total"] = total
    state["phase"] = "正在检测模糊照片 (V2 精准 · 并行)"

    # ---- Determine worker count ----
    cpu_count = os.cpu_count() or 4
    max_workers = max(2, min(cpu_count, 8))  # at least 2, at most 8
    logger.info(
        "=== Blur Detection V2 Start === total=%d threshold=%s skip=%d workers=%d",
        total, threshold, len(_skip), max_workers,
    )

    # ---- Separate skip vs process, checking patch_scores cache ----
    from backend.ai.ai_preview.preview_generator import get_preview_path
    from backend.ai.blur_detector_v2.detector import (
        judge_from_cache,
        BLUR_THRESHOLD,
    )

    to_process: list[tuple[str, str, str | None, float | None, float | None, float | None]] = []
    cached_photos: list[tuple[str, str]] = []  # (image_id, patch_scores_json)
    skipped_count = 0

    _effective_threshold = threshold if threshold is not None else BLUR_THRESHOLD

    for image_id in photo_ids:
        if state["cancelled"]:
            state["status"] = "cancelled"
            logger.info("Blur detection V2 %s cancelled before start", task_id)
            return

        if image_id in _skip:
            skipped_count += 1
            state["processed"] += 1
            state["progress"] = state["processed"]
            state["current_file"] = image_id
            continue

        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            state["failed"] += 1
            state["processed"] += 1
            state["progress"] = state["processed"]
            continue

        # ---- Cache fast-path: if this photo already has cached patch_scores,
        #      we can re-judge without touching the image file (改进建议 §5) ----
        if photo.patch_scores:
            cached_photos.append((image_id, photo.patch_scores))
        else:
            to_process.append((image_id, photo.readable_path, get_preview_path(image_id), threshold, preview_sharp_threshold, preview_blur_threshold))

    # ---- Step A: Re-judge cached photos in main thread (milliseconds each) ----
    if cached_photos:
        logger.info(
            "Blur V2: %d photos have cached patch_scores — re-judging with threshold=%.1f",
            len(cached_photos), _effective_threshold,
        )
        with repo.batch_transaction():
            for image_id, cache_json in cached_photos:
                if state["cancelled"]:
                    break
                try:
                    final_score, is_blur = judge_from_cache(cache_json, _effective_threshold)
                    repo.update_blur_status(
                        image_id, is_blur=is_blur,
                        blur_score=round(final_score, 2),
                    )
                    state["processed"] += 1
                    state["current_file"] = image_id
                    if is_blur:
                        state["blurred"] += 1
                except Exception as exc:
                    # Corrupted cache — clear it and add to worker queue
                    logger.warning(
                        "Blur V2: %s cache corrupted (%s), will recompute",
                        image_id, exc,
                    )
                    repo.update_patch_scores(image_id, None)
                    photo = repo.get_photo_by_id(image_id)
                    if photo:
                        to_process.append(
                            (image_id, photo.readable_path, get_preview_path(image_id), threshold)
                        )
        state["progress"] = state["processed"]
        logger.info(
            "Blur V2: cache re-judge complete — %d processed, %d blurred",
            len(cached_photos), state["blurred"],
        )

    process_count = len(to_process)
    if process_count == 0:
        if state["status"] == "running":
            state["status"] = "completed"
        state["current_file"] = ""
        state["phase"] = ""
        logger.info("=== Blur Detection V2 Complete (nothing to process) ===")
        return

    # ---- Chunk the (uncached) work ----
    # Each worker gets ~2 chunks to keep all cores fed (pipeline effect)
    chunk_count = max_workers * 2
    chunk_size = max(1, process_count // chunk_count)
    chunks: list[list[tuple[str, str, str | None, float | None]]] = []
    for i in range(0, process_count, chunk_size):
        chunks.append(to_process[i:i + chunk_size])

    logger.info(
        "Blur V2: %d photos to process → %d chunks (size ~%d) × %d workers",
        process_count, len(chunks), chunk_size, max_workers,
    )

    # ---- Parallel processing ----
    t_start = time.time()
    completed_in_chunks = 0

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {
                executor.submit(_process_blur_chunk, chunk): idx
                for idx, chunk in enumerate(chunks)
            }

            for future in as_completed(future_to_chunk):
                if state["cancelled"]:
                    # Shutdown executor, cancel pending futures
                    for f in future_to_chunk:
                        f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    state["status"] = "cancelled"
                    logger.info(
                        "Blur detection V2 %s cancelled at %d/%d processed",
                        task_id, state["processed"], total,
                    )
                    return

                try:
                    chunk_results = future.result()
                except Exception as exc:
                    logger.error("Blur V2 chunk failed entirely: %s", exc)
                    state["failed"] += chunk_size  # approximate
                    state["processed"] += chunk_size
                    state["progress"] = state["processed"]
                    continue

                # ---- Write results to DB (single-threaded, batched per chunk) ----
                with repo.batch_transaction():
                    for image_id, success, final_score, is_blur, error_msg, cache_json in chunk_results:
                        if success:
                            repo.update_blur_status(
                                image_id, is_blur=is_blur,
                                blur_score=round(final_score, 2),
                            )
                            # Persist intermediate scores for future
                            # re-analysis with a different threshold
                            # (改进建议 §5 — patch_scores 缓存)
                            if cache_json:
                                repo.update_patch_scores(image_id, cache_json)
                            state["processed"] += 1
                            if is_blur:
                                state["blurred"] += 1
                        else:
                            state["failed"] += 1
                            state["processed"] += 1
                            logger.warning(
                                "Blur V2: %s failed in worker: %s", image_id, error_msg,
                            )

                completed_in_chunks += 1
                state["progress"] = state["processed"]
                # Update current_file to last processed image_id in this chunk
                if chunk_results:
                    state["current_file"] = chunk_results[-1][0]

                # Log progress every 10 chunks or at the end
                if completed_in_chunks % 10 == 0 or completed_in_chunks == len(chunks):
                    elapsed = time.time() - t_start
                    rate = state["processed"] / elapsed if elapsed > 0 else 0
                    logger.info(
                        "Blur V2 progress: %d/%d processed, %d blurred, "
                        "%.1f photos/sec, %d/%d chunks done",
                        state["processed"], total, state["blurred"],
                        rate, completed_in_chunks, len(chunks),
                    )

    except Exception as exc:
        logger.error("Blur V2 ProcessPoolExecutor error: %s", exc)
        state["failed"] += (process_count - (state["processed"] - skipped_count))
        state["processed"] = total

    if state["status"] == "running":
        state["status"] = "completed"
    state["current_file"] = ""
    state["phase"] = ""

    elapsed_total = time.time() - t_start
    logger.info(
        "=== Blur Detection V2 Complete === "
        "processed=%d blurred=%d failed=%d elapsed=%.1fs",
        state["processed"], state["blurred"], state["failed"], elapsed_total,
    )


def start_blur_detection_v2(
    photo_ids: list[str],
    threshold: float | None = None,
    skip_ids: set[str] | None = None,
    preview_sharp_threshold: float | None = None,
    preview_blur_threshold: float | None = None,
) -> str:
    """Start v2 blur detection in a background thread. Returns task_id.

    Args:
        photo_ids: List of image_id values to process.
        threshold: Optional override for the blur threshold.
        skip_ids: Optional set of image_id values to skip (e.g. closed-eye photos).
        preview_sharp_threshold: Optional override for PREVIEW_SHARP_THRESHOLD.
        preview_blur_threshold: Optional override for PREVIEW_BLUR_THRESHOLD.
    """
    task_id = uuid.uuid4().hex[:8]

    state = {
        "task_id": task_id,
        "status": "running",
        "phase": "正在检测模糊照片 (V2 精准)",
        "total": 0,
        "processed": 0,
        "blurred": 0,
        "failed": 0,
        "progress": 0,
        "current_file": "",
        "cancelled": False,
    }
    with _lock:
        _tasks[task_id] = state

    t = threading.Thread(
        target=_run_blur_loop_v2,
        args=(task_id, photo_ids, threshold, skip_ids, preview_sharp_threshold, preview_blur_threshold),
        daemon=True,
    )
    t.start()
    return task_id


def get_blur_progress_v2(task_id: str) -> Optional[dict]:
    """Get current progress of a v2 blur detection task."""
    return _tasks.get(task_id)


def cancel_blur_detection_v2(task_id: str) -> bool:
    """Cancel a running v2 blur detection task."""
    state = _tasks.get(task_id)
    if state and state["status"] == "running":
        state["cancelled"] = True
        return True
    return False


def detect_blur_batch(
    photo_ids: list[str],
    repo: "PhotoRepository",
    *,
    threshold: float | None = None,
) -> BlurDetectionSummary:
    """Run v2 blur detection on every photo in *photo_ids* synchronously.

    Each photo's ``blur_score`` and ``is_blur`` columns are updated
    in the database immediately after detection.

    Args:
        photo_ids: List of ``image_id`` values to process.
        repo: A ``PhotoRepository`` instance for DB lookups / writes.
        threshold: Optional override for the blur threshold.

    Returns:
        A ``BlurDetectionSummary`` with aggregate statistics.
    """
    total = len(photo_ids)
    summary = BlurDetectionSummary(total=total)
    times: list[float] = []

    from backend.ai.blur_detector_v2.detector import (
        judge_from_cache,
        build_patch_scores_cache,
        BLUR_THRESHOLD,
    )

    logger.info("=== Blur Detection V2 Start === total=%d", total)

    for idx, image_id in enumerate(photo_ids, 1):
        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            summary.errors += 1
            logger.warning("[%d/%d] %s SKIPPED: not found in DB", idx, total, image_id)
            continue

        t0 = time.perf_counter()
        try:
            # ---- Cache fast-path (改进建议 §5) ----
            if photo.patch_scores:
                final_score, is_blur = judge_from_cache(
                    photo.patch_scores,
                    threshold if threshold is not None else BLUR_THRESHOLD,
                )
                proc_ms = (time.perf_counter() - t0) * 1000.0
                # Re-use cached scores — just update the verdict
                repo.update_blur_status(
                    image_id,
                    is_blur=is_blur,
                    blur_score=round(final_score, 2),
                )
            else:
                final_score, is_blur, patch_scores, proc_ms, weighted_score, top_median = (
                    calculate_blur_v2(photo.readable_path, threshold=threshold)
                )
                repo.update_blur_status(
                    image_id,
                    is_blur=is_blur,
                    blur_score=round(final_score, 2),
                )
                # Cache intermediate scores for future re-analysis
                cache_json = build_patch_scores_cache(
                    patch_scores, weighted_score, top_median,
                )
                repo.update_patch_scores(image_id, cache_json)

            if is_blur:
                summary.blurred += 1
            else:
                summary.clear += 1

            summary.scores.append(final_score)
            times.append(proc_ms)

            if photo.patch_scores:
                logger.info(
                    "[%d/%d] %s | final=%.2f is_blur=%d (%.1fms) [from cache]",
                    idx, total, image_id, final_score, is_blur, proc_ms,
                )
            else:
                logger.info(
                    "[%d/%d] %s | final=%.2f is_blur=%d (%.1fms)  "
                    "w_avg=%.2f top_med=%.2f  "
                    "composition: final = w_avg*0.4 + top_med*0.6  "
                    "patches=%s",
                    idx,
                    total,
                    image_id,
                    final_score,
                    is_blur,
                    proc_ms,
                    weighted_score,
                    top_median,
                    [round(s, 1) for s in patch_scores],
            )

        except Exception as exc:
            summary.errors += 1
            elapsed = (time.perf_counter() - t0) * 1000.0
            times.append(elapsed)
            logger.error(
                "[%d/%d] %s FAILED: %s (%.1fms)",
                idx,
                total,
                image_id,
                exc,
                elapsed,
            )

    if times:
        summary.avg_time_ms = sum(times) / len(times)

    logger.info(
        "=== Blur Detection V2 Complete === "
        "total=%d blurred=%d clear=%d errors=%d avg=%.1fms",
        summary.total,
        summary.blurred,
        summary.clear,
        summary.errors,
        summary.avg_time_ms,
    )

    return summary
