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
from .models import BlurDetectionResult, BlurDetectionSummary

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
    chunk: list[tuple[str, str, float | None, str | None]],
) -> list[tuple[str, bool, float, int, str | None]]:
    """Process a chunk of photos in a worker process.

    Each worker imports ``calculate_blur_v2`` independently so there
    is no shared state between processes.

    If a *thumbnail_path* is provided and the thumbnail exists, a fast
    pre‑screen (global Laplacian on the small cached JPEG) may skip
    loading the full‑resolution image entirely — a 50–100× speedup
    for obviously sharp or obviously blurry photos.

    Args:
        chunk: List of ``(image_id, readable_path, threshold, thumbnail_path)``
            tuples.  *thumbnail_path* may be None.

    Returns:
        List of ``(image_id, success, final_score, is_blur, error_msg)``.
    """
    # Late import — worker processes need their own module references
    from backend.ai.blur_detector_v2.detector import calculate_blur_v2 as _calc

    results: list[tuple[str, bool, float, int, str | None]] = []
    for image_id, readable_path, threshold, thumbnail_path in chunk:
        try:
            final_score, is_blur, _patch_scores, _proc_ms, _w, _t = _calc(
                readable_path,
                threshold=threshold,
                thumbnail_path=thumbnail_path,
            )
            results.append((image_id, True, final_score, is_blur, None))
        except Exception as exc:
            results.append((image_id, False, 0.0, 0, str(exc)))
    return results


def _run_blur_loop_v2(
    task_id: str,
    photo_ids: list[str],
    threshold: float | None,
    skip_ids: set[str] | None = None,
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

    # ---- Separate skip vs process ----
    to_process: list[tuple[str, str, float | None, str | None]] = []
    skipped_count = 0

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

        thumb = photo.thumbnail_path if photo.thumbnail_path and os.path.isfile(photo.thumbnail_path) else None
        to_process.append((image_id, photo.readable_path, threshold, thumb))

    process_count = len(to_process)
    if process_count == 0:
        if state["status"] == "running":
            state["status"] = "completed"
        state["current_file"] = ""
        state["phase"] = ""
        logger.info("=== Blur Detection V2 Complete (nothing to process) ===")
        return

    # ---- Chunk the work ----
    # Each worker gets ~2 chunks to keep all cores fed (pipeline effect)
    chunk_count = max_workers * 2
    chunk_size = max(1, process_count // chunk_count)
    chunks: list[list[tuple[str, str, float | None, str | None]]] = []
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

                # ---- Write results to DB (single-threaded) ----
                for image_id, success, final_score, is_blur, error_msg in chunk_results:
                    if success:
                        repo.update_blur_status(
                            image_id, is_blur=is_blur,
                            blur_score=round(final_score, 2),
                        )
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
) -> str:
    """Start v2 blur detection in a background thread. Returns task_id.

    Args:
        photo_ids: List of image_id values to process.
        threshold: Optional override for the blur threshold.
        skip_ids: Optional set of image_id values to skip (e.g. closed-eye photos).
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
        args=(task_id, photo_ids, threshold, skip_ids),
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

    logger.info("=== Blur Detection V2 Start === total=%d", total)

    for idx, image_id in enumerate(photo_ids, 1):
        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            summary.errors += 1
            logger.warning("[%d/%d] %s SKIPPED: not found in DB", idx, total, image_id)
            continue

        t0 = time.perf_counter()
        try:
            thumb = photo.thumbnail_path if photo.thumbnail_path and os.path.isfile(photo.thumbnail_path) else None
            final_score, is_blur, patch_scores, proc_ms, weighted_score, top_median = (
                calculate_blur_v2(photo.readable_path, threshold=threshold, thumbnail_path=thumb)
            )
            repo.update_blur_status(
                image_id,
                is_blur=is_blur,
                blur_score=round(final_score, 2),
            )

            if is_blur:
                summary.blurred += 1
            else:
                summary.clear += 1

            summary.scores.append(final_score)
            times.append(proc_ms)

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
