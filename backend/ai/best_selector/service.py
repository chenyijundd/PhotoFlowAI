"""
PhotoFlow AI - Best Selector Batch Service

Orchestrates best-in-burst selection across all burst groups,
writing results to the ``is_best_in_burst`` database column.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .selector import select_best
from .models import BestSelection, BestSelectionSummary

if TYPE_CHECKING:
    from database.repository import PhotoRepository

logger = logging.getLogger("best_selector")

from backend.logging_config import setup_best_selector_logging

setup_best_selector_logging()


def select_best_for_all_bursts(repo: "PhotoRepository") -> BestSelectionSummary:
    """Run best-in-burst selection on every burst group in the database.

    Writes ``is_best_in_burst = 1`` for recommended photos and
    ``is_best_in_burst = 0`` for all other burst-group members.

    Args:
        repo: A ``PhotoRepository`` instance.

    Returns:
        A ``BestSelectionSummary`` with aggregate statistics.
    """
    logger.info("=== Best Selector Start ===")

    # ---- Get all burst groups ----
    group_ids = repo.get_burst_groups()
    total_groups = len(group_ids)
    logger.info("Burst groups to process: %d", total_groups)

    if total_groups == 0:
        logger.info("No burst groups found — nothing to do.")
        return BestSelectionSummary(total_groups=0)

    summary = BestSelectionSummary(total_groups=total_groups)
    group_sizes: list[int] = []

    for gid in group_ids:
        photos = repo.get_burst_group_photos(gid)
        selection = select_best(photos)

        # Write results to DB
        for r in selection.rankings:
            is_best = 1 if r.is_recommended else 0
            repo.update_best_in_burst(r.image_id, is_best)

        if selection.recommended_id:
            summary.recommended_count += 1
            group_sizes.append(len(selection.rankings))
            logger.info(
                "  %s: %s — %s  (candidates=%d)",
                gid,
                selection.recommended_id,
                selection.selection_reason,
                len(selection.rankings),
            )
        else:
            summary.no_candidate_count += 1
            logger.info("  %s: NO RECOMMENDATION — %s", gid, selection.selection_reason)

    if group_sizes:
        summary.avg_group_size = sum(group_sizes) / len(group_sizes)

    logger.info(
        "=== Best Selector Complete === "
        "groups=%d recommended=%d no_candidate=%d avg_candidates=%.1f",
        summary.total_groups,
        summary.recommended_count,
        summary.no_candidate_count,
        summary.avg_group_size,
    )

    return summary


def select_best_for_all_duplicates(repo: "PhotoRepository") -> int:
    """Run best-in-duplicate selection on every duplicate group.

    For each duplicate group, picks the photo with the highest
    ``blur_score`` and sets ``is_best_in_duplicate = 1``.
    All other members get ``is_best_in_duplicate = 0``.

    Photos excluded from consideration (rejected, blurry, closed-eye,
    or missing blur_score) are skipped and keep their existing flag.

    Args:
        repo: A ``PhotoRepository`` instance.

    Returns:
        The number of duplicate groups that received a recommendation.
    """
    logger.info("=== Duplicate Best Selector Start ===")

    dup_groups = repo.get_duplicate_groups()
    total_groups = len(dup_groups)
    logger.info("Duplicate groups to process: %d", total_groups)

    if total_groups == 0:
        logger.info("No duplicate groups found — nothing to do.")
        return 0

    recommended = 0

    for dg in dup_groups:
        group_id = dg["duplicate_group"]
        photos = repo.get_photos_by_duplicate_group(group_id)

        # Filter candidates (same criteria as burst best selector)
        candidates = [
            p for p in photos
            if p.is_rejected != 1
            and p.is_blur != 1
            and p.is_closed_eye != 1
            and p.blur_score is not None
        ]

        if not candidates:
            logger.info("  %s: NO RECOMMENDATION — all photos excluded", group_id)
            continue

        # Pick best by blur_score (higher = sharper)
        candidates.sort(key=lambda p: p.blur_score or 0, reverse=True)
        best = candidates[0]

        # Write results to DB
        for p in photos:
            is_best = 1 if p.image_id == best.image_id else 0
            repo.update_best_in_duplicate(p.image_id, is_best)

        recommended += 1
        logger.info(
            "  %s: %s — blur_score=%.1f (candidates=%d/%d)",
            group_id,
            best.image_id,
            best.blur_score or 0,
            len(candidates),
            len(photos),
        )

    logger.info(
        "=== Duplicate Best Selector Complete === groups=%d recommended=%d",
        total_groups,
        recommended,
    )

    return recommended
