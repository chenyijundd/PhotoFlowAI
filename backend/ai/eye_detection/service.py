"""
PhotoFlow AI - Eye Detection Batch Service

Orchestrates eye detection across a list of photos.
Processes images sequentially (one at a time) so that large
originals are never all held in memory simultaneously.

Errors on individual photos are logged and tallied but never
halt the batch.

Background-thread support (start / progress / cancel) mirrors
the blur-detector-v2 service pattern so the frontend can poll
for real-time updates.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Optional

from .eye_detector import detect_eyes, EAR_HALF_CLOSED_THRESHOLD
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


def _run_eye_loop(task_id: str, photo_ids: list[str]) -> None:
    """Run eye detection in a background thread, updating shared state."""
    from database.repository import PhotoRepository

    repo = PhotoRepository()

    state = _tasks.get(task_id)
    if not state:
        return

    total = len(photo_ids)
    state["total"] = total
    state["phase"] = "正在检测闭眼照片"
    logger.info("=== Eye Detection Start === total=%d", total)

    for idx, image_id in enumerate(photo_ids, 1):
        if state["cancelled"]:
            state["status"] = "cancelled"
            logger.info(
                "Eye detection %s cancelled at %d/%d",
                task_id, state["processed"], total,
            )
            break

        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            state["failed"] += 1
            continue

        t0 = time.time()
        try:
            result = detect_eyes(photo.readable_path)

            is_closed_eye = 0 if result["eyes_open"] else 1
            eye_score = result["score"]

            repo.update_eye_status(
                image_id,
                is_closed_eye=is_closed_eye,
                eye_score=round(eye_score, 4),
            )

            state["processed"] += 1
            if is_closed_eye:
                state["closed"] += 1

            elapsed = time.time() - t0
            faces_info = ""
            if result["face_detected"]:
                faces_info = (
                    f"faces={result['num_faces']} "
                    f"closed={result['closed_count']} "
                    f"min_ear={eye_score:.4f}"
                )
            else:
                faces_info = "no_face"

            logger.info(
                "[%d/%d] %s | is_closed=%d score=%.4f %s (%.3fs)",
                idx, total, image_id, is_closed_eye, eye_score,
                faces_info, elapsed,
            )

        except Exception as exc:
            state["failed"] += 1
            logger.error("[%d/%d] %s FAILED: %s", idx, total, image_id, exc)

        state["progress"] = state["processed"]
        state["current_file"] = photo.file_name or image_id

    if state["status"] == "running":
        state["status"] = "completed"
    state["current_file"] = ""
    state["phase"] = ""

    logger.info(
        "=== Eye Detection Complete === "
        "total=%d processed=%d closed=%d failed=%d",
        total, state["processed"], state.get("closed", 0), state["failed"],
    )


def start_eye_detection(photo_ids: list[str]) -> str:
    """Start eye detection in a background thread. Returns task_id."""
    task_id = uuid.uuid4().hex[:8]

    state = {
        "task_id": task_id,
        "status": "running",
        "phase": "正在检测闭眼照片",
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
            result = detect_eyes(photo.readable_path)

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
