"""
PhotoFlow AI - Blur Detector V2 Batch Service

Orchestrates v2 blur detection across a list of photos.
Processes images sequentially (one at a time) so that large
originals are never all held in memory simultaneously.

Errors on individual photos are logged and tallied but never
halt the batch.

Background-thread support (start / progress / cancel) mirrors
the v1 service pattern so the frontend can poll for real-time
updates.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
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


def _run_blur_loop_v2(
    task_id: str,
    photo_ids: list[str],
    threshold: float | None,
    skip_ids: set[str] | None = None,
) -> None:
    """Run v2 blur detection in a background thread, updating shared state.

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
    state["phase"] = "正在检测模糊照片 (V2 精准)"
    logger.info("=== Blur Detection V2 Start === total=%d threshold=%s skip=%d", total, threshold, len(_skip))

    for idx, image_id in enumerate(photo_ids, 1):
        if state["cancelled"]:
            state["status"] = "cancelled"
            logger.info("Blur detection V2 %s cancelled at %d/%d", task_id, state["processed"], total)
            break

        # ---- Skip photos already flagged as closed-eye ----
        if image_id in _skip:
            state["processed"] += 1
            state["progress"] = state["processed"]
            state["current_file"] = image_id
            continue

        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            state["failed"] += 1
            continue

        t0 = time.time()
        try:
            final_score, is_blur, patch_scores, proc_ms, weighted_score, top_median = (
                calculate_blur_v2(photo.readable_path, threshold=threshold)
            )
            elapsed = time.time() - t0

            repo.update_blur_status(image_id, is_blur=is_blur, blur_score=round(final_score, 2))

            state["processed"] += 1
            if is_blur:
                state["blurred"] += 1

            logger.info(
                "[%d/%d] %s | final=%.2f is_blur=%d (%.3fs)  "
                "w_avg=%.2f top_med=%.2f  "
                "composition: final = w_avg*0.4 + top_med*0.6  "
                "patches=%s",
                idx, total, image_id, final_score, is_blur, elapsed,
                weighted_score, top_median,
                [round(s, 1) for s in patch_scores],
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

    logger.info("=== Blur Detection V2 Complete ===")


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
            final_score, is_blur, patch_scores, proc_ms, weighted_score, top_median = (
                calculate_blur_v2(photo.readable_path, threshold=threshold)
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
