"""
PhotoFlow AI - Burst Batch Operations API

Endpoints for bulk accept / reject operations on burst groups.
All operations are idempotent and log to ``logs/batch_operations.log``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.repository import PhotoRepository

router = APIRouter(prefix="/api/burst", tags=["burst"])

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("batch_operations")

from backend.logging_config import setup_batch_operations_logging
setup_batch_operations_logging()

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class BurstOpResponse(BaseModel):
    group_id: str
    accepted: int = 0
    rejected: int = 0
    unchanged: int = 0


class BulkOpResponse(BaseModel):
    groups_processed: int
    total_accepted: int = 0
    total_rejected: int = 0
    total_unchanged: int = 0


# ---------------------------------------------------------------------------
# Per-group operations
# ---------------------------------------------------------------------------


def _validate_group(repo: PhotoRepository, group_id: str) -> list:
    """Return group photos or raise 404."""
    photos = repo.get_burst_group_photos(group_id)
    if not photos:
        raise HTTPException(status_code=404, detail=f"Burst group not found: {group_id}")
    return photos


@router.post("/{group_id}/accept-best", response_model=BurstOpResponse)
async def accept_best_in_burst(group_id: str):
    """Accept the recommended photo (star) and reject the rest in a burst group."""
    repo = PhotoRepository()
    photos = _validate_group(repo, group_id)

    accepted = 0
    rejected = 0
    unchanged = 0

    for p in photos:
        if p.is_best_in_burst == 1:
            if p.star_rating != 1:
                repo.update_star_rating(p.image_id, 1, is_manual=True)
                accepted += 1
            else:
                unchanged += 1
        else:
            if p.is_rejected != 1:
                repo.update_reject_status(p.image_id, 1, is_manual=True)
                rejected += 1
            else:
                unchanged += 1

    logger.info(
        "accept-best %s: accepted=%d rejected=%d unchanged=%d",
        group_id, accepted, rejected, unchanged,
    )
    return BurstOpResponse(
        group_id=group_id,
        accepted=accepted,
        rejected=rejected,
        unchanged=unchanged,
    )


@router.post("/{group_id}/accept-all", response_model=BurstOpResponse)
async def accept_all_in_burst(group_id: str):
    """Star all photos in a burst group."""
    repo = PhotoRepository()
    photos = _validate_group(repo, group_id)

    accepted = 0
    unchanged = 0

    for p in photos:
        if p.star_rating != 1:
            repo.update_star_rating(p.image_id, 1, is_manual=True)
            accepted += 1
        else:
            unchanged += 1

    logger.info(
        "accept-all %s: accepted=%d unchanged=%d",
        group_id, accepted, unchanged,
    )
    return BurstOpResponse(
        group_id=group_id,
        accepted=accepted,
        rejected=0,
        unchanged=unchanged,
    )


@router.post("/{group_id}/reject-all", response_model=BurstOpResponse)
async def reject_all_in_burst(group_id: str):
    """Reject all photos in a burst group."""
    repo = PhotoRepository()
    photos = _validate_group(repo, group_id)

    rejected = 0
    unchanged = 0

    for p in photos:
        if p.is_rejected != 1:
            repo.update_reject_status(p.image_id, 1, is_manual=True)
            rejected += 1
        else:
            unchanged += 1

    logger.info(
        "reject-all %s: rejected=%d unchanged=%d",
        group_id, rejected, unchanged,
    )
    return BurstOpResponse(
        group_id=group_id,
        accepted=0,
        rejected=rejected,
        unchanged=unchanged,
    )


# ---------------------------------------------------------------------------
# Bulk (all-groups) operations
# ---------------------------------------------------------------------------


@router.post("/accept-all-best", response_model=BulkOpResponse)
async def accept_all_best():
    """Accept the best photo in *every* burst group; reject the rest."""
    repo = PhotoRepository()
    group_ids = repo.get_burst_groups()

    total_accepted = 0
    total_rejected = 0
    total_unchanged = 0

    for gid in group_ids:
        photos = repo.get_burst_group_photos(gid)
        for p in photos:
            if p.is_best_in_burst == 1:
                if p.star_rating != 1:
                    repo.update_star_rating(p.image_id, 1, is_manual=True)
                    total_accepted += 1
                else:
                    total_unchanged += 1
            else:
                if p.is_rejected != 1:
                    repo.update_reject_status(p.image_id, 1, is_manual=True)
                    total_rejected += 1
                else:
                    total_unchanged += 1

    logger.info(
        "accept-all-best: groups=%d accepted=%d rejected=%d unchanged=%d",
        len(group_ids), total_accepted, total_rejected, total_unchanged,
    )
    return BulkOpResponse(
        groups_processed=len(group_ids),
        total_accepted=total_accepted,
        total_rejected=total_rejected,
        total_unchanged=total_unchanged,
    )


@router.post("/reject-all-rest", response_model=BulkOpResponse)
async def reject_all_rest():
    """Reject all non-recommended photos across all burst groups.

    Recommended photos (is_best_in_burst == 1) are left untouched.
    """
    repo = PhotoRepository()
    group_ids = repo.get_burst_groups()

    total_rejected = 0
    total_unchanged = 0

    for gid in group_ids:
        photos = repo.get_burst_group_photos(gid)
        for p in photos:
            if p.is_best_in_burst != 1:
                if p.is_rejected != 1:
                    repo.update_reject_status(p.image_id, 1, is_manual=True)
                    total_rejected += 1
                else:
                    total_unchanged += 1
            else:
                total_unchanged += 1  # leave recommended photos alone

    logger.info(
        "reject-all-rest: groups=%d rejected=%d unchanged=%d",
        len(group_ids), total_rejected, total_unchanged,
    )
    return BulkOpResponse(
        groups_processed=len(group_ids),
        total_accepted=0,
        total_rejected=total_rejected,
        total_unchanged=total_unchanged,
    )
