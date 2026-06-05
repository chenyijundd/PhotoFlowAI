"""
PhotoFlow AI - Burst Grouper Batch Service

Orchestrates burst grouping across all photos in the database,
writing results back to the ``burst_group`` and ``burst_position``
columns.

Supports both synchronous execution (``run_burst_grouping``) and
background-thread execution with progress polling
(``start_burst_grouping`` / ``get_burst_progress`` / ``cancel_burst_grouping``).
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import TYPE_CHECKING, Optional

from .grouper import group_by_time_gap
from .models import BurstGroupSummary

if TYPE_CHECKING:
    from database.repository import PhotoRepository

logger = logging.getLogger("burst_grouping")

from backend.logging_config import setup_burst_grouping_logging

setup_burst_grouping_logging()

# ---------------------------------------------------------------------------
# In-memory task registry (same pattern as blur detection)
# ---------------------------------------------------------------------------

_tasks: dict[str, dict] = {}
_lock = threading.Lock()


def _run_burst_loop(
    task_id: str,
    repo: "PhotoRepository",
    gap_seconds: float | None,
    min_burst_size: int | None = None,
) -> None:
    """Run burst grouping in a background thread, updating shared state."""
    state = _tasks.get(task_id)
    if not state:
        return

    state["phase"] = "正在检测连拍分组"
    logger.info("=== Burst Grouping Start === gap=%.1f min_size=%s", gap_seconds or 2.0, min_burst_size)

    try:
        summary = run_burst_grouping(repo, gap_seconds=gap_seconds, min_burst_size=min_burst_size)

        state["burst_groups"] = summary.burst_groups_count
        state["photos_in_bursts"] = summary.photos_in_bursts
        state["progress"] = summary.total_photos
        state["total"] = summary.total_photos
        state["status"] = "completed"
        logger.info("=== Burst Grouping Complete === groups=%d", summary.burst_groups_count)
    except Exception as exc:
        state["status"] = "error"
        state["phase"] = f"分组失败: {exc}"
        logger.error("Burst grouping %s FAILED: %s", task_id, exc)

    state["phase"] = ""
    state["current_file"] = ""


def start_burst_grouping(
    repo: "PhotoRepository",
    gap_seconds: float | None = None,
    min_burst_size: int | None = None,
) -> str:
    """Start burst grouping in a background thread. Returns task_id."""
    task_id = uuid.uuid4().hex[:8]

    state = {
        "task_id": task_id,
        "status": "running",
        "phase": "正在检测连拍分组",
        "total": 0,
        "progress": 0,
        "burst_groups": 0,
        "photos_in_bursts": 0,
        "failed": 0,
        "current_file": "",
        "cancelled": False,
    }
    with _lock:
        _tasks[task_id] = state

    t = threading.Thread(
        target=_run_burst_loop,
        args=(task_id, repo, gap_seconds, min_burst_size),
        daemon=True,
    )
    t.start()
    return task_id


def get_burst_progress(task_id: str) -> Optional[dict]:
    """Get current progress of a burst grouping task."""
    return _tasks.get(task_id)


def cancel_burst_grouping(task_id: str) -> bool:
    """Cancel a running burst grouping task."""
    state = _tasks.get(task_id)
    if state and state["status"] == "running":
        state["cancelled"] = True
        return True
    return False


def run_burst_grouping(
    repo: "PhotoRepository",
    gap_seconds: float | None = None,
    min_burst_size: int | None = None,
) -> BurstGroupSummary:
    """Run burst grouping on every photo in the database.

    Args:
        repo: A ``PhotoRepository`` instance.
        gap_seconds: Override the default gap threshold.  *None* uses
            the module default (2.0 s).
        min_burst_size: Override ``MIN_BURST_SIZE``.

    Returns:
        A ``BurstGroupSummary`` with aggregate statistics.
    """
    logger.info("=== Burst Grouping Start === gap=%.1f min_size=%s", gap_seconds or 2.0, min_burst_size)

    # ---- Fetch all photos ----
    all_photos = repo.get_all_photos()
    total = len(all_photos)
    logger.info("Total photos in DB: %d", total)

    # ---- Convert to dicts for the pure grouper function ----
    photo_dicts: list[dict] = []
    skipped_no_time = 0
    for p in all_photos:
        if not p.created_time:
            skipped_no_time += 1
            continue
        photo_dicts.append(
            {"image_id": p.image_id, "created_time": p.created_time}
        )

    # ---- Group ----
    groups = group_by_time_gap(photo_dicts, gap_seconds=gap_seconds, min_burst_size=min_burst_size)

    # ---- Write results to DB (batch transaction — 1 commit instead of N) ----
    photos_in_bursts = 0
    group_sizes: list[int] = []

    with repo.batch_transaction():
        for group in groups:
            group_sizes.append(group.photo_count)
            for pos, image_id in enumerate(group.photo_ids):
                repo.update_burst_group(
                    image_id,
                    burst_group=group.group_id,
                    burst_position=pos,
                )
            photos_in_bursts += group.photo_count

    photos_not_in_bursts = total - photos_in_bursts - skipped_no_time

    summary = BurstGroupSummary(
        total_photos=total,
        burst_groups_count=len(groups),
        photos_in_bursts=photos_in_bursts,
        photos_not_in_bursts=photos_not_in_bursts,
        skipped_no_time=skipped_no_time,
        group_sizes=group_sizes,
    )

    logger.info(
        "=== Burst Grouping Complete === "
        "groups=%d photos_in_bursts=%d skipped_no_time=%d",
        summary.burst_groups_count,
        summary.photos_in_bursts,
        summary.skipped_no_time,
    )

    # Log distribution
    if group_sizes:
        logger.info(
            "Group size distribution: min=%d max=%d avg=%.1f",
            min(group_sizes),
            max(group_sizes),
            sum(group_sizes) / len(group_sizes),
        )
        for g in groups:
            logger.info(
                "  %s: %d photos | %s → %s (%.1fs)",
                g.group_id,
                g.photo_count,
                g.start_time,
                g.end_time,
                g.duration_seconds,
            )

    return summary
