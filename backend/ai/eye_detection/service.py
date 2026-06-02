"""
PhotoFlow AI - Eye Detection Batch Service

Orchestrates eye detection across a list of photos.
Uses ThreadPoolExecutor for parallel processing — MediaPipe's C++
inference releases the GIL, so threads achieve near-process-level
parallelism without the memory overhead of forking.

Each worker thread gets its own MediaPipe FaceLandmarker instance
(thread-local storage).  Images are downscaled to 1024 px before
inference for an additional 10–30× speedup per photo.

Background-thread support (start / progress / cancel) mirrors
the blur-detector-v2 service pattern so the frontend can poll
for real-time updates.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .eye_detector import detect_eyes, MAX_IMAGE_DIM
from .models import EyeDetectionSummary

logger = logging.getLogger("eye_detection")

# Ensure rotating log handler is set up
from backend.logging_config import setup_eye_detection_logging

setup_eye_detection_logging()

# ---------------------------------------------------------------------------
# In-memory task registry
# ---------------------------------------------------------------------------

_tasks: dict[str, dict] = {}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Worker function (module-level for ThreadPoolExecutor)
# ---------------------------------------------------------------------------


def _process_eye_chunk(
    chunk: list[tuple[str, str]],
) -> list[tuple[str, bool, float, int, str | None]]:
    """Process a chunk of photos in a worker thread.

    Each worker thread gets its own MediaPipe FaceLandmarker via
    thread-local storage.  Images are downscaled to *MAX_IMAGE_DIM*
    (1024 px) before inference.

    Args:
        chunk: List of ``(image_id, readable_path)`` tuples.

    Returns:
        List of ``(image_id, success, eye_score, is_closed_eye, error_msg)``.
    """
    from backend.ai.eye_detection.eye_detector import detect_eyes as _detect

    results: list[tuple[str, bool, float, int, str | None]] = []
    for image_id, readable_path in chunk:
        try:
            result = _detect(readable_path, max_dim=MAX_IMAGE_DIM)
            is_closed_eye = 0 if result["eyes_open"] else 1
            eye_score = float(result["score"])
            results.append((image_id, True, eye_score, is_closed_eye, None))
        except Exception as exc:
            results.append((image_id, False, 0.0, 0, str(exc)))
    return results


# ---------------------------------------------------------------------------
# Background detection loop
# ---------------------------------------------------------------------------


def _worker_count() -> int:
    """Return a sensible ThreadPoolExecutor worker count."""
    cpu = os.cpu_count() or 4
    return max(2, min(cpu, 8))  # MediaPipe is CPU-bound, cap at 8


def _run_eye_loop(task_id: str, photo_ids: list[str]) -> None:
    """Run eye detection in a background thread with parallel workers.

    Pipeline:
      1. Collect all valid (non-None) photos from the DB.
      2. Split into chunks and distribute across worker threads.
      3. Each worker loads the image, downscales, runs MediaPipe.
      4. Main thread writes results to SQLite (single-threaded).
    """
    from database.repository import PhotoRepository

    repo = PhotoRepository()

    state = _tasks.get(task_id)
    if not state:
        return

    total = len(photo_ids)
    state["total"] = total
    state["phase"] = "Step 1/5: 闭眼检测 — 并行处理中"
    workers = _worker_count()

    logger.info(
        "=== Eye Detection Start === total=%d workers=%d", total, workers,
    )

    # ---- Collect photos to process ----
    to_process: list[tuple[str, str]] = []  # (image_id, readable_path)
    skipped_db = 0

    for image_id in photo_ids:
        if state["cancelled"]:
            state["status"] = "cancelled"
            logger.info(
                "Eye detection %s cancelled before start", task_id,
            )
            return

        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            state["failed"] += 1
            state["processed"] += 1
            skipped_db += 1
            continue

        to_process.append((image_id, photo.readable_path))

    process_count = len(to_process)
    if process_count == 0:
        if state["status"] == "running":
            state["status"] = "completed"
        state["current_file"] = ""
        state["phase"] = ""
        logger.info("=== Eye Detection Complete (nothing to process) ===")
        return

    # ---- Chunk the work ----
    chunk_count = workers * 2  # 2 chunks per worker for pipeline effect
    chunk_size = max(1, process_count // chunk_count)
    chunks: list[list[tuple[str, str]]] = []
    for i in range(0, process_count, chunk_size):
        chunks.append(to_process[i : i + chunk_size])

    logger.info(
        "Eye: %d photos to process → %d chunks (size ~%d) × %d workers",
        process_count, len(chunks), chunk_size, workers,
    )

    # ---- Parallel processing ----
    t_start = time.time()
    completed_chunks = 0

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_chunk = {
                executor.submit(_process_eye_chunk, chunk): idx
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
                        "Eye detection %s cancelled at %d/%d processed",
                        task_id, state["processed"], total,
                    )
                    return

                try:
                    chunk_results = future.result()
                except Exception as exc:
                    logger.error("Eye chunk failed entirely: %s", exc)
                    state["failed"] += chunk_size  # approximate
                    state["processed"] += chunk_size
                    state["progress"] = state["processed"]
                    continue

                # ---- Write results to DB (single-threaded) ----
                for image_id, success, eye_score, is_closed_eye, error_msg in chunk_results:
                    if success:
                        repo.update_eye_status(
                            image_id,
                            is_closed_eye=is_closed_eye,
                            eye_score=round(eye_score, 4),
                        )
                        state["processed"] += 1
                        if is_closed_eye:
                            state["closed"] += 1
                    else:
                        state["failed"] += 1
                        state["processed"] += 1
                        logger.warning(
                            "Eye: %s failed in worker: %s", image_id, error_msg,
                        )

                completed_chunks += 1
                state["progress"] = state["processed"]
                # Update current_file to last image_id in this chunk
                if chunk_results:
                    state["current_file"] = chunk_results[-1][0]

                # Log progress every 10 chunks or at the end
                if completed_chunks % 10 == 0 or completed_chunks == len(chunks):
                    elapsed = time.time() - t_start
                    rate = state["processed"] / elapsed if elapsed > 0 else 0
                    logger.info(
                        "Eye progress: %d/%d processed, %d closed, "
                        "%.1f photos/sec, %d/%d chunks done",
                        state["processed"], total, state.get("closed", 0),
                        rate, completed_chunks, len(chunks),
                    )

    except Exception as exc:
        logger.error("Eye ThreadPoolExecutor error: %s", exc)
        state["failed"] += process_count - max(0, state["processed"] - skipped_db)
        state["processed"] = total

    if state["status"] == "running":
        state["status"] = "completed"
    state["current_file"] = ""
    state["phase"] = ""

    elapsed_total = time.time() - t_start
    logger.info(
        "=== Eye Detection Complete === "
        "processed=%d closed=%d failed=%d elapsed=%.1fs",
        state["processed"], state.get("closed", 0), state["failed"], elapsed_total,
    )


# ---------------------------------------------------------------------------
# Public API (unchanged signatures for backward compatibility)
# ---------------------------------------------------------------------------


def start_eye_detection(photo_ids: list[str]) -> str:
    """Start eye detection in a background thread. Returns task_id."""
    task_id = uuid.uuid4().hex[:8]

    state = {
        "task_id": task_id,
        "status": "running",
        "phase": "Step 1/5: 闭眼检测 — 并行处理中",
        "total": 0,
        "processed": 0,
        "closed": 0,
        "failed": 0,
        "progress": 0,
        "current_file": "",
        "cancelled": False,
    }
    with _lock:
        _tasks[task_id] = state

    t = threading.Thread(
        target=_run_eye_loop,
        args=(task_id, photo_ids),
        daemon=True,
    )
    t.start()
    return task_id


def get_eye_progress(task_id: str) -> Optional[dict]:
    """Get current progress of an eye detection task."""
    return _tasks.get(task_id)


def cancel_eye_detection(task_id: str) -> bool:
    """Cancel a running eye detection task."""
    state = _tasks.get(task_id)
    if state and state["status"] == "running":
        state["cancelled"] = True
        return True
    return False


def detect_eyes_batch_sync(
    photo_ids: list[str],
    repo,
) -> EyeDetectionSummary:
    """Run eye detection on every photo in *photo_ids* synchronously.

    Each photo's ``eye_score`` and ``is_closed_eye`` columns are updated
    in the database immediately after detection.

    Args:
        photo_ids: List of ``image_id`` values to process.
        repo: A ``PhotoRepository`` instance for DB lookups / writes.

    Returns:
        An ``EyeDetectionSummary`` with aggregate statistics.
    """
    total = len(photo_ids)
    summary = EyeDetectionSummary(total=total)
    times: list[float] = []

    logger.info("=== Eye Detection Batch Start === total=%d", total)

    for idx, image_id in enumerate(photo_ids, 1):
        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            summary.errors += 1
            logger.warning(
                "[%d/%d] %s SKIPPED: not found in DB", idx, total, image_id,
            )
            continue

        t0 = time.perf_counter()
        try:
            result = detect_eyes(photo.readable_path, max_dim=MAX_IMAGE_DIM)

            is_closed_eye = 0 if result["eyes_open"] else 1
            eye_score = result["score"]

            repo.update_eye_status(
                image_id,
                is_closed_eye=is_closed_eye,
                eye_score=round(eye_score, 4),
            )

            if is_closed_eye:
                summary.closed += 1
            elif not result["face_detected"]:
                summary.no_face += 1
            else:
                summary.open += 1

            summary.scores.append(eye_score)

            elapsed = (time.perf_counter() - t0) * 1000.0
            times.append(elapsed)

            faces_info = ""
            if result["face_detected"]:
                faces_info = (
                    f"faces={result['num_faces']} "
                    f"closed={result['closed_count']}"
                )
            else:
                faces_info = "no_face"

            logger.info(
                "[%d/%d] %s | is_closed=%d score=%.4f %s (%.1fms)",
                idx, total, image_id, is_closed_eye, eye_score,
                faces_info, elapsed,
            )

        except Exception as exc:
            summary.errors += 1
            elapsed = (time.perf_counter() - t0) * 1000.0
            times.append(elapsed)
            logger.error(
                "[%d/%d] %s FAILED: %s (%.1fms)",
                idx, total, image_id, exc, elapsed,
            )

    if times:
        summary.avg_time_ms = sum(times) / len(times)

    logger.info(
        "=== Eye Detection Batch Complete === "
        "total=%d closed=%d open=%d no_face=%d errors=%d avg=%.1fms",
        summary.total, summary.closed, summary.open,
        summary.no_face, summary.errors, summary.avg_time_ms,
    )

    return summary
