"""
PhotoFlow AI - Best Selector Data Models
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RankedPhoto:
    """A single photo's ranking within a burst group."""

    image_id: str
    rank: int
    blur_score: float | None
    file_size: int
    file_name: str = ""
    is_recommended: bool = False


@dataclass
class BestSelection:
    """Best-photo recommendation for a single burst group."""

    group_id: str
    """Burst group ID, e.g. ``burst_0042``."""

    recommended_id: str | None = None
    """``image_id`` of the recommended photo, or *None* if no candidate."""

    selection_reason: str = ""
    """Human-readable explanation of the selection."""

    rankings: list[RankedPhoto] = field(default_factory=list)
    """All valid candidates, ranked best-to-worst."""


@dataclass
class BestSelectionSummary:
    """Aggregated summary of a best-selection run."""

    total_groups: int = 0
    """Number of burst groups processed."""

    recommended_count: int = 0
    """Number of groups that received a recommendation."""

    no_candidate_count: int = 0
    """Number of groups where all photos were excluded."""

    skipped_no_blur: int = 0
    """Groups skipped because no photo had a blur_score."""

    avg_group_size: float = 0.0
    """Average number of candidates per group (after filtering)."""
