"""
PhotoFlow AI - Blur Detection Service

Orchestrates blur detection across a list of photos.
Processes images sequentially to avoid loading all originals at once.

Runs in a background thread with progress tracking — frontend polls
GET /api/ai/blur-progress/{task_id} for real-time updates.
"""

import logging
import threading
import time
import uuid
from typing import Optional

from .detector import calculate_blur
from backend.logging_config import setup_blur_logging

logger = logging.getLogger("blur_detection")
setup_blur_logging()

# In-memory task registry
_tasks: dict[str, dict] = {}
_lock = threading.Lock()


def _run_blur_loop(task_id: str, photo_ids: list[str]):
    """Run blur detection in background thread, updating shared state."""
    from database.repository import PhotoRepository
    repo = PhotoRepository()

    state = _tasks.get(task_id)
    if not state:
        return

    total = len(photo_ids)
    state["total"] = total
    state["phase"] = "正在检测模糊照片"
    logger.info("=== Blur Detection Start ===")

    for idx, image_id in enumerate(photo_ids, 1):
        if state["cancelled"]:
            state["status"] = "cancelled"
            logger.info("Blur detection %s cancelled at %d/%d", task_id, state["processed"], total)
            break

        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            state["failed"] += 1
            continue

        t0 = time.time()
        try:
            score, is_blur = calculate_blur(photo.file_path)
            elapsed = time.time() - t0

            repo.update_blur_status(image_id, is_blur=is_blur, blur_score=score)

            state["processed"] += 1
            if is_blur:
                state["blurred"] += 1

            logger.info("[%d/%d] %s | score=%.2f is_blur=%d (%.3fs)", idx, total, image_id, score, is_blur, elapsed)
        except Exception as exc:
            state["failed"] += 1
            logger.error("[%d/%d] %s FAILED: %s", idx, total, image_id, exc)

        state["progress"] = state["processed"]
        state["current_file"] = photo.file_name or image_id

    if state["status"] == "running":
        state["status"] = "completed"
    state["current_file"] = ""
    state["phase"] = ""

    logger.info("=== Blur Detection Complete ===")


def start_blur_detection(photo_ids: list[str]) -> str:
    """Start blur detection in a background thread. Returns task_id."""
    task_id = uuid.uuid4().hex[:8]

    state = {
        "task_id": task_id,
        "status": "running",
        "phase": "正在检测模糊照片",
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

    t = threading.Thread(target=_run_blur_loop, args=(task_id, photo_ids), daemon=True)
    t.start()
    return task_id


def get_blur_progress(task_id: str) -> Optional[dict]:
    """Get current progress of a blur detection task."""
    return _tasks.get(task_id)


def cancel_blur_detection(task_id: str) -> bool:
    """Cancel a running blur detection task."""
    state = _tasks.get(task_id)
    if state and state["status"] == "running":
        state["cancelled"] = True
        return True
    return False
