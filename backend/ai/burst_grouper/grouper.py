"""
PhotoFlow AI - Burst Grouper Core Algorithm

Groups photos by EXIF / file creation time using a simple time-gap
threshold.  When the interval between consecutive (time-sorted) photos
is ≤ *gap_seconds*, they are considered part of the same burst —
typically a continuous-shooting sequence of the same scene.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import BurstGroup

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

BURST_GAP_SECONDS: float = 2.0
"""Maximum interval (seconds) between consecutive photos in the same burst."""

MIN_BURST_SIZE: int = 2
"""A burst must contain at least this many photos.  Singles are ignored."""


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------


def group_by_time_gap(
    photos: list[dict[str, Any]],
    gap_seconds: float | None = None,
    min_burst_size: int | None = None,
) -> list[BurstGroup]:
    """Group *photos* into bursts using a simple time-gap threshold.

    The algorithm:
        1. Sorts photos by ``created_time``.
        2. Iterates through the sorted list; whenever the gap between the
           current photo and the previous one exceeds *gap_seconds*, a new
           burst group is started.
        3. Groups with fewer than *min_burst_size* members are discarded.

    Args:
        photos: A list of dicts, each containing at least:

            * ``image_id``: ``str`` — unique photo identifier
            * ``created_time``: ``str | None`` — ISO‑8601 timestamp (may be
              ``None`` or empty; such photos are skipped)
        gap_seconds: Override ``BURST_GAP_SECONDS``.  If *None*, the
            module default is used.
        min_burst_size: Override ``MIN_BURST_SIZE``.  If *None*, the
            module default is used.

    Returns:
        A list of ``BurstGroup`` objects, ordered chronologically.
        Each group is assigned a sequential ID (``burst_0001``, …).
    """
    _gap = gap_seconds if gap_seconds is not None else BURST_GAP_SECONDS
    _min_size = min_burst_size if min_burst_size is not None else MIN_BURST_SIZE

    # ---- Step 1 & 2: filter + sort by created_time ----
    parsed: list[tuple[str, datetime]] = []
    for p in photos:
        ts = p.get("created_time")
        if not ts:
            continue  # skip photos with no timestamp
        try:
            # Handle both timezone-aware and naive ISO strings
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
        parsed.append((p["image_id"], dt))

    parsed.sort(key=lambda item: item[1])

    if not parsed:
        return []

    # ---- Step 3: sliding-window grouping ----
    raw_groups: list[list[tuple[str, datetime]]] = []
    current_burst: list[tuple[str, datetime]] = [parsed[0]]

    for i in range(1, len(parsed)):
        prev_dt = parsed[i - 1][1]
        curr_dt = parsed[i][1]
        delta = (curr_dt - prev_dt).total_seconds()

        if delta <= _gap:
            current_burst.append(parsed[i])
        else:
            raw_groups.append(current_burst)
            current_burst = [parsed[i]]

    raw_groups.append(current_burst)  # the last one

    # ---- Step 4 & 5 & 6: filter min size, assign IDs, build result ----
    groups: list[BurstGroup] = []
    group_idx = 0

    for raw in raw_groups:
        if len(raw) < _min_size:
            continue

        group_idx += 1
        ids = [item[0] for item in raw]
        dts = [item[1] for item in raw]
        start = dts[0].isoformat()
        end = dts[-1].isoformat()
        duration = (dts[-1] - dts[0]).total_seconds()

        groups.append(
            BurstGroup(
                group_id=f"burst_{group_idx:04d}",
                photo_ids=ids,
                photo_count=len(ids),
                start_time=start,
                end_time=end,
                duration_seconds=duration,
            )
        )

    return groups
