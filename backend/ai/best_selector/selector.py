"""
PhotoFlow AI - Best-in-Burst Selector Algorithm

Multi-criteria ranking for picking the best photo from a burst group:

1. Exclude rejected (is_rejected == 1) photos
2. Exclude blurry (is_blur == 1) photos
3. Exclude closed-eye (is_closed_eye == 1) photos
4. Rank remaining by blur_score descending (sharper = better)
5. Tie-break on file_size if scores are within 10 %
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import BestSelection, RankedPhoto

if TYPE_CHECKING:
    from database.models import PhotoRecord

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

BLUR_TIE_PCT: float = 0.10
"""If two photos' blur_scores differ by < 10 %, they are considered tied."""

SIZE_TIE_PCT: float = 0.20
"""If two photos' file_sizes differ by < 20 %, they are considered tied."""


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------


def select_best(
    photos: list["PhotoRecord"],
    blur_tie_pct: float | None = None,
    size_tie_pct: float | None = None,
) -> BestSelection:
    """Pick the best photo from a burst group.

    Args:
        photos: All ``PhotoRecord`` objects in a single burst group.

    Returns:
        A ``BestSelection`` with the recommended photo and full ranking.
        If no candidate survives filtering, ``recommended_id`` is *None*.
    """
    _blur_tie = blur_tie_pct if blur_tie_pct is not None else BLUR_TIE_PCT
    _size_tie = size_tie_pct if size_tie_pct is not None else SIZE_TIE_PCT

    if not photos:
        return BestSelection(
            group_id="",
            recommended_id=None,
            selection_reason="NO_RECOMMENDATION: empty group",
        )

    group_id = photos[0].burst_group or "unknown"

    # ---- Step 1, 2 & 3: filter ----
    candidates: list[PhotoRecord] = []
    for p in photos:
        if p.is_rejected == 1:
            continue
        if p.is_blur == 1:
            continue
        if p.is_closed_eye == 1:
            continue
        if p.blur_score is None:
            continue  # no blur data → can't rank
        candidates.append(p)

    if not candidates:
        return BestSelection(
            group_id=group_id,
            recommended_id=None,
            selection_reason="NO_RECOMMENDATION: all photos rejected, blurry, closed-eye, or unscored",
        )

    # ---- Step 3: rank by blur_score descending ----
    candidates.sort(key=lambda p: p.blur_score or 0, reverse=True)

    # ---- Step 4 & 5: tie-breaking ----
    # Use the top photo's blur_score as the reference
    best_blur = candidates[0].blur_score or 0

    # Find all photos within BLUR_TIE_PCT of the best
    if best_blur > 0:
        tie_group = [
            p
            for p in candidates
            if (p.blur_score or 0) >= best_blur * (1.0 - _blur_tie)
        ]
    else:
        tie_group = candidates

    # Within the tie group, sort by file_size descending
    tie_group.sort(key=lambda p: p.file_size, reverse=True)
    best_size = tie_group[0].file_size

    # If sizes are also close, use resolution
    if best_size > 0:
        resolution_tie = [
            p
            for p in tie_group
            if p.file_size >= best_size * (1.0 - _size_tie)
        ]
    else:
        resolution_tie = tie_group

    resolution_tie.sort(key=lambda p: p.width * p.height, reverse=True)
    best = resolution_tie[0]

    # ---- Build reason ----
    if len(tie_group) == 1 or best == candidates[0]:
        reason = f"最清晰 (blur_score: {best.blur_score:.1f})"
    elif best.file_size > tie_group[0].file_size:
        reason = f"最清晰且细节最丰富 (blur_score: {best.blur_score:.1f}, {best.file_size:,}B)"
    else:
        reason = f"最清晰且分辨率最高 (blur_score: {best.blur_score:.1f}, {best.width}x{best.height})"

    # ---- Build rankings ----
    rankings: list[RankedPhoto] = []
    for rank, p in enumerate(candidates, 1):
        rankings.append(
            RankedPhoto(
                image_id=p.image_id,
                rank=rank,
                blur_score=p.blur_score,
                file_size=p.file_size,
                file_name=p.file_name,
                is_recommended=(p.image_id == best.image_id),
            )
        )

    return BestSelection(
        group_id=group_id,
        recommended_id=best.image_id,
        selection_reason=reason,
        rankings=rankings,
    )
