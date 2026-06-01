"""
PhotoFlow AI - Burst Grouper Data Models
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BurstGroup:
    """A single burst / continuous-shooting group."""

    group_id: str
    """Unique group identifier, e.g. ``burst_0001``."""

    photo_ids: list[str] = field(default_factory=list)
    """``image_id`` values of photos in this group, in chronological order."""

    photo_count: int = 0
    """Number of photos in the group (derived from *photo_ids*)."""

    start_time: str | None = None
    """ISO-8601 timestamp of the earliest photo in the group."""

    end_time: str | None = None
    """ISO-8601 timestamp of the latest photo in the group."""

    duration_seconds: float = 0.0
    """Wall-clock span from *start_time* to *end_time* in seconds."""

    def __post_init__(self) -> None:
        if self.photo_count == 0:
            self.photo_count = len(self.photo_ids)


@dataclass
class BurstGroupSummary:
    """Aggregated summary of a burst-grouping run."""

    total_photos: int = 0
    """Total number of photos considered for grouping."""

    burst_groups_count: int = 0
    """Number of distinct burst groups detected."""

    photos_in_bursts: int = 0
    """Total photos that belong to *any* burst group."""

    photos_not_in_bursts: int = 0
    """Total photos that are not part of any burst group."""

    skipped_no_time: int = 0
    """Photos skipped because ``created_time`` was missing or unparseable."""

    group_sizes: list[int] = field(default_factory=list)
    """Size of each burst group (for distribution analysis)."""
