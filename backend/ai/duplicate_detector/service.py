"""
PhotoFlow AI - Duplicate Detection Service

Orchestrates duplicate detection across a list of photos using
perceptual hashing (phash) and Hamming Distance comparison.

Runs in a background thread with progress tracking — frontend polls
GET /api/ai/duplicate-progress/{task_id} for real-time updates.
"""

import logging
import threading
import time
import uuid
from typing import Optional

from .detector import compute_phash, hamming_distance
from backend.logging_config import setup_duplicate_logging

DUPLICATE_THRESHOLD = 5

logger = logging.getLogger("duplicate_detection")
setup_duplicate_logging()

# In-memory task registry
_tasks: dict[str, dict] = {}
_lock = threading.Lock()


class UnionFind:
    """Union-Find / Disjoint Set Union data structure."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.size[rx] < self.size[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        self.size[rx] += self.size[ry]


def _run_duplicate_loop(task_id: str, photo_ids: list[str], skip_ids: set[str] | None = None):
    """Run duplicate detection in background thread, updating shared state.

    Args:
        task_id: Unique task identifier for progress polling.
        photo_ids: List of image_id values to process.
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

    # Phase 1: Compute phashes
    state["phase"] = "正在检测重复照片"
    phashes: list[tuple[str, int, object]] = []

    for idx, image_id in enumerate(photo_ids, 1):
        if state["cancelled"]:
            state["status"] = "cancelled"
            logger.info("Duplicate detection %s cancelled at %d/%d", task_id, state["processed"], total)
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
            ph = compute_phash(photo.readable_path)
            elapsed = time.time() - t0
            phashes.append((image_id, len(phashes), ph))
            state["processed"] += 1
            logger.info("[%d/%d] %s | phash=%s (%.3fs)", idx, total, image_id, str(ph), elapsed)
        except Exception as exc:
            state["failed"] += 1
            logger.error("[%d/%d] %s FAILED: %s", idx, total, image_id, exc)

        state["progress"] = state["processed"]
        state["current_file"] = photo.file_name or image_id

    if state["cancelled"]:
        return

    # Phase 2: Pairwise comparison
    n = len(phashes)
    if n > 1:
        state["phase"] = "正在检测重复照片"
        state["progress"] = 0
        state["processed"] = 0
        state["current_file"] = f"比对 {n} 张照片..."

        uf = UnionFind(n)

        for i in range(n):
            if state["cancelled"]:
                state["status"] = "cancelled"
                return
            for j in range(i + 1, n):
                dist = hamming_distance(phashes[i][2], phashes[j][2])
                if dist <= DUPLICATE_THRESHOLD:
                    uf.union(i, j)
            state["progress"] = i + 1
            state["processed"] = i + 1

        # Phase 3: Assign groups
        state["phase"] = "正在写入结果"

        root_to_indices: dict[int, list[int]] = {}
        for i in range(n):
            root = uf.find(i)
            root_to_indices.setdefault(root, []).append(i)

        group_num = 0
        duplicate_groups = 0
        duplicate_count = 0

        for indices in root_to_indices.values():
            if state["cancelled"]:
                state["status"] = "cancelled"
                return
            if len(indices) <= 1:
                # Clear duplicate flags for singletons
                i = indices[0]
                image_id = phashes[i][0]
                repo.update_duplicate_status(image_id, is_duplicate=0, duplicate_group=None)
                continue
            group_num += 1
            group_id = f"dup_{group_num:04d}"
            for i in indices:
                image_id = phashes[i][0]
                repo.update_duplicate_status(image_id, is_duplicate=1, duplicate_group=group_id)
            duplicate_groups += 1
            duplicate_count += len(indices)

        state["duplicate_groups"] = duplicate_groups
        state["duplicate_count"] = duplicate_count

    if state["status"] == "running":
        state["status"] = "completed"
    state["current_file"] = ""
    state["phase"] = ""
    state["progress"] = state["total"]

    logger.info("=== Duplicate Detection Complete ===")


def start_duplicate_detection(photo_ids: list[str], skip_ids: set[str] | None = None) -> str:
    """Start duplicate detection in a background thread. Returns task_id.

    Args:
        photo_ids: List of image_id values to process.
        skip_ids: Optional set of image_id values to skip (e.g. closed-eye photos).
    """
    task_id = uuid.uuid4().hex[:8]

    state = {
        "task_id": task_id,
        "status": "running",
        "phase": "正在检测重复照片",
        "total": 0,
        "processed": 0,
        "failed": 0,
        "duplicate_groups": 0,
        "duplicate_count": 0,
        "progress": 0,
        "current_file": "",
        "cancelled": False,
    }
    with _lock:
        _tasks[task_id] = state

    t = threading.Thread(target=_run_duplicate_loop, args=(task_id, photo_ids, skip_ids), daemon=True)
    t.start()
    return task_id


def get_duplicate_progress(task_id: str) -> Optional[dict]:
    """Get current progress of a duplicate detection task."""
    return _tasks.get(task_id)


def cancel_duplicate_detection(task_id: str) -> bool:
    """Cancel a running duplicate detection task."""
    state = _tasks.get(task_id)
    if state and state["status"] == "running":
        state["cancelled"] = True
        return True
    return False
