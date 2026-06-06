"""
PhotoFlow AI - Trash Service

Soft-delete (move to trash), restore, and permanent-delete operations
for photos.  Permanent deletion moves photo files to the system recycle
bin (send2trash), cleans up thumbnail / RAW-preview caches, repairs
related entities (burst groups, duplicate groups, RAW+JPEG pairs), and
removes the database record.
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database.repository import PhotoRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["trash"])

# ---- Lazily import send2trash so the module loads even if it's missing ----
try:
    import send2trash as _send2trash
    _HAS_SEND2TRASH = True
except ImportError:
    _HAS_SEND2TRASH = False
    logger.warning(
        "send2trash is not installed — photos will be permanently removed "
        "via os.remove() instead of being moved to the system recycle bin. "
        "Run: pip install send2trash"
    )

# ---- Cache directories ----
from backend.env import get_data_dir

_THUMBNAIL_CACHE_DIR = os.path.join(get_data_dir(), "cache", "thumbnails")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class BatchTrashRequest(BaseModel):
    photo_ids: list[str]


class BatchRestoreRequest(BaseModel):
    photo_ids: list[str]


class PermDeleteResponse(BaseModel):
    status: str
    deleted_ids: list[str]
    files_trashed: int
    thumbnails_removed: int
    error: Optional[str] = None


class TrashCountResponse(BaseModel):
    count: int


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------

def _delete_file_safe(file_path: str) -> bool:
    """Move *file_path* to the system recycle bin (or os.remove as fallback).

    Returns True if the file was successfully removed from its original
    location.
    """
    try:
        if not os.path.isfile(file_path):
            return False
        if _HAS_SEND2TRASH:
            _send2trash.send2trash(file_path)
        else:
            os.remove(file_path)
        return True
    except Exception as exc:
        logger.warning("Failed to delete file %s: %s", file_path, exc)
        return False


def _delete_thumbnail_cache(image_id: str) -> bool:
    """Remove the cached thumbnail for *image_id*."""
    thumb_path = os.path.join(_THUMBNAIL_CACHE_DIR, f"{image_id}.jpg")
    if os.path.isfile(thumb_path):
        try:
            os.remove(thumb_path)
            return True
        except OSError as exc:
            logger.warning("Failed to remove thumbnail %s: %s", thumb_path, exc)
    return False


# ---------------------------------------------------------------------------
# Entity-repair helpers (called BEFORE deleting DB records)
# ---------------------------------------------------------------------------

def _repair_burst_group(repo: PhotoRepository, group_id: str) -> None:
    """Re-number burst positions and re-select best-in-burst after removing members."""
    remaining = repo.get_burst_group_photos(group_id)
    if not remaining:
        return
    # Re-number positions sequentially
    for i, photo in enumerate(remaining):
        repo.update_burst_group(photo.image_id, group_id, i + 1)
    # If the previous best was deleted, pick a new best by blur_score
    if not any(p.is_best_in_burst == 1 for p in remaining):
        scored = [p for p in remaining if p.blur_score is not None]
        if scored:
            best = max(scored, key=lambda p: p.blur_score or 0)
        else:
            best = remaining[0]
        repo.update_best_in_burst(best.image_id, 1)


def _repair_duplicate_group(repo: PhotoRepository, group_id: str) -> None:
    """Update duplicate-group metadata after removing members.

    If fewer than 2 members remain, the group is dissolved (members'
    is_duplicate cleared).  Otherwise, if the best-in-duplicate was
    deleted, a new best is selected.
    """
    remaining = repo.get_photos_by_duplicate_group(group_id)
    if len(remaining) < 2:
        # Dissolve the group
        for p in remaining:
            repo.update_duplicate_status(p.image_id, 0, None)
        return
    # Re-select best if needed
    if not any(p.is_best_in_duplicate == 1 for p in remaining):
        scored = [p for p in remaining if p.blur_score is not None]
        if scored:
            best = max(scored, key=lambda p: p.blur_score or 0)
        else:
            best = remaining[0]
        repo.update_best_in_duplicate(best.image_id, 1)


def _repair_raw_jpeg_pair(repo: PhotoRepository, pair_id: str, exclude_id: str) -> None:
    """Clear raw_jpeg_pair_id for remaining pair members.

    Called before deleting *exclude_id*.  If only one member remains
    after exclusion, its pair_id is also cleared (a pair needs >= 2).
    """
    remaining = [
        p for p in repo.get_photos_by_raw_jpeg_pair(pair_id)
        if p.image_id != exclude_id
    ]
    if len(remaining) <= 1:
        for p in remaining:
            repo.update_raw_jpeg_pair(p.image_id, None)
        return
    # More than one remain — just clear the deleted one's ref.
    # The remaining pair is still valid; no action needed on others.


# ---------------------------------------------------------------------------
# Permanent-delete business logic
# ---------------------------------------------------------------------------

def permanent_delete_photo(
    image_id: str,
    include_paired: bool = True,
) -> PermDeleteResponse:
    """Permanently delete a photo and (optionally) its RAW+JPEG paired photos.

    Requirements that must be satisfied before calling:
    * The photo must already be soft-deleted (deleted_at IS NOT NULL).

    Steps (per photo):
      1. Move original file to system recycle bin (send2trash).
      2. Move RAW preview file (if any) to recycle bin.
      3. Remove cached thumbnail.
      4. Repair burst / duplicate / RAW+JPEG pair entities.
      5. Remove database record.
    """
    repo = PhotoRepository()
    photo = repo.get_photo_by_id(image_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Safety gate: only allow permanent delete from trash
    if not photo.deleted_at:
        raise HTTPException(
            status_code=400,
            detail="请先将照片移入回收站，再执行彻底删除",
        )

    # Collect all image_ids to delete
    delete_ids = [image_id]
    if include_paired and photo.raw_jpeg_pair_id:
        paired = repo.get_paired_photo_ids(image_id)
        if paired:
            logger.info(
                "Permanent delete: including %d paired photo(s) for %s",
                len(paired), image_id,
            )
            delete_ids.extend(paired)

    files_trashed = 0
    thumbnails_removed = 0

    for pid in delete_ids:
        p = repo.get_photo_by_id(pid)
        if not p:
            continue

        # ---- Entity repair (BEFORE deleting the DB row) ----
        if p.burst_group:
            _repair_burst_group(repo, p.burst_group)
        if p.duplicate_group:
            _repair_duplicate_group(repo, p.duplicate_group)
        if p.raw_jpeg_pair_id:
            _repair_raw_jpeg_pair(repo, p.raw_jpeg_pair_id, pid)

        # ---- File cleanup ----
        # Move original to trash
        if _delete_file_safe(p.file_path):
            files_trashed += 1

        # Move RAW preview to trash (if different from original)
        if p.raw_preview_path and p.raw_preview_path != p.file_path:
            if _delete_file_safe(p.raw_preview_path):
                files_trashed += 1

        # Remove thumbnail
        if _delete_thumbnail_cache(pid):
            thumbnails_removed += 1

        # ---- Remove DB record ----
        repo.delete_photo(pid)

    logger.info(
        "Permanent delete: %d photo(s), %d file(s) trashed, %d thumbnail(s) removed",
        len(delete_ids), files_trashed, thumbnails_removed,
    )

    return PermDeleteResponse(
        status="ok",
        deleted_ids=delete_ids,
        files_trashed=files_trashed,
        thumbnails_removed=thumbnails_removed,
    )


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.post("/photo/{image_id}/trash")
async def trash_photo(image_id: str):
    """Soft-delete a photo — move to trash (set deleted_at)."""
    try:
        repo = PhotoRepository()
        p = repo.get_photo_by_id(image_id)
    except Exception as exc:
        logger.error("Failed to query photo %s: %s", image_id, exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    if p is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    if p.deleted_at is not None:
        return {"status": "ok", "image_id": image_id, "deleted": False,
                "message": "Photo already in trash"}

    repo.soft_delete_photo(image_id)
    return {"status": "ok", "image_id": image_id, "deleted": True}


@router.post("/photo/{image_id}/restore")
async def restore_photo(image_id: str):
    """Restore a photo from trash (clear deleted_at)."""
    try:
        repo = PhotoRepository()
        p = repo.get_photo_by_id(image_id)
    except Exception as exc:
        logger.error("Failed to query photo %s: %s", image_id, exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    if p is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    if p.deleted_at is None:
        return {"status": "ok", "image_id": image_id, "restored": False,
                "message": "Photo is not in trash"}

    repo.restore_photo(image_id)
    return {"status": "ok", "image_id": image_id, "restored": True}


@router.post("/photos/batch-trash")
async def batch_trash(body: BatchTrashRequest):
    """Batch soft-delete — move multiple photos to trash."""
    if not body.photo_ids:
        return {"updated": 0}

    try:
        repo = PhotoRepository()
        updated = repo.soft_delete_photos_batch(body.photo_ids)
        logger.info("Batch trash: %d photos", updated)
        return {"updated": updated}
    except Exception as exc:
        logger.error("Batch trash failed: %s", exc)
        raise HTTPException(status_code=500, detail="Batch trash failed")


@router.post("/photos/batch-restore")
async def batch_restore(body: BatchRestoreRequest):
    """Batch restore — restore multiple photos from trash."""
    if not body.photo_ids:
        return {"updated": 0}

    try:
        repo = PhotoRepository()
        updated = repo.restore_photos_batch(body.photo_ids)
        logger.info("Batch restore: %d photos", updated)
        return {"updated": updated}
    except Exception as exc:
        logger.error("Batch restore failed: %s", exc)
        raise HTTPException(status_code=500, detail="Batch restore failed")


@router.delete("/photo/{image_id}/permanent", response_model=PermDeleteResponse)
async def permanent_delete_endpoint(
    image_id: str,
    include_paired: bool = Query(True, description="Also delete paired RAW/JPG files"),
):
    """Permanently delete a photo that is in the trash.

    Moves files to system recycle bin, cleans caches, repairs related
    entities, and removes the database record.
    """
    try:
        return permanent_delete_photo(image_id, include_paired=include_paired)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Permanent delete failed for %s: %s", image_id, exc)
        raise HTTPException(status_code=500, detail="Permanent delete failed")


@router.get("/photos/trashed")
async def get_trashed_photos(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Retrieve soft-deleted photos with pagination."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_trashed_photos()
    except Exception as exc:
        logger.error("Failed to query trashed photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    page = all_photos[offset:offset + limit]
    result = []
    for p in page:
        # Build thumbnail URL
        thumbnail_url = None
        thumb_path = os.path.join(_THUMBNAIL_CACHE_DIR, f"{p.image_id}.jpg")
        if os.path.isfile(thumb_path):
            thumbnail_url = f"/api/thumbnails/{p.image_id}.jpg"

        result.append({
            "image_id": p.image_id,
            "file_name": p.file_name,
            "file_path": p.file_path,
            "thumbnail_url": thumbnail_url,
            "width": p.width,
            "height": p.height,
            "file_size": p.file_size,
            "star_rating": p.star_rating,
            "blur_score": p.blur_score,
            "is_blur": p.is_blur,
            "eye_score": p.eye_score,
            "is_closed_eye": p.is_closed_eye,
            "is_rejected": p.is_rejected,
            "is_duplicate": p.is_duplicate,
            "duplicate_group": p.duplicate_group,
            "burst_group": p.burst_group,
            "burst_position": p.burst_position,
            "is_best_in_burst": p.is_best_in_burst,
            "is_best_in_duplicate": p.is_best_in_duplicate,
            "raw_jpeg_pair_id": p.raw_jpeg_pair_id,
            "deleted_at": p.deleted_at,
        })

    return {
        "total": len(all_photos),
        "limit": limit,
        "offset": offset,
        "photos": result,
    }


@router.get("/photos/trashed/count", response_model=TrashCountResponse)
async def get_trashed_count():
    """Return the count of soft-deleted photos."""
    try:
        repo = PhotoRepository()
        count = repo.get_trashed_count()
        return {"count": count}
    except Exception as exc:
        logger.error("Failed to query trashed count: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")
