"""
PhotoFlow AI - Photo Detail API Service

Endpoints for fetching individual photo metadata and serving
full-size original images to the frontend preview panel.
"""

import os
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database.repository import PhotoRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["detail"])


class StarUpdateRequest(BaseModel):
    star_rating: int


@router.get("/photo/{image_id}")
async def get_photo_detail(image_id: str):
    """Return metadata for a single photo."""
    try:
        repo = PhotoRepository()
        p = repo.get_photo_by_id(image_id)
    except Exception as exc:
        logger.error("Failed to query photo %s: %s", image_id, exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    if p is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Build thumbnail path for the response
    thumbnail_path = None
    try:
        from backend.thumbnail_cache.cache_manager import DEFAULT_CACHE_DIR
        thumb_file = os.path.join(DEFAULT_CACHE_DIR, f"{image_id}.jpg")
        if os.path.isfile(thumb_file):
            thumbnail_path = thumb_file
    except Exception:
        pass

    return {
        "image_id": p.image_id,
        "file_name": p.file_name,
        "file_path": p.file_path,
        "width": p.width,
        "height": p.height,
        "file_size": p.file_size,
        "created_time": p.created_time or "",
        "thumbnail_path": thumbnail_path,
        "star_rating": p.star_rating,
        "blur_score": p.blur_score,
        "is_blur": p.is_blur,
        "is_rejected": p.is_rejected,
        "is_duplicate": p.is_duplicate,
        "duplicate_group": p.duplicate_group,
    }


@router.patch("/photo/{image_id}/star")
async def update_photo_star(image_id: str, body: StarUpdateRequest):
    """Update the star rating for a photo (0 or 1)."""
    if body.star_rating not in (0, 1):
        raise HTTPException(status_code=400, detail="star_rating must be 0 or 1")

    try:
        repo = PhotoRepository()
        p = repo.get_photo_by_id(image_id)
    except Exception as exc:
        logger.error("Failed to query photo %s: %s", image_id, exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    if p is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    repo.update_star_rating(image_id, body.star_rating)
    return {"status": "ok", "image_id": image_id, "star_rating": body.star_rating}


class RejectUpdateRequest(BaseModel):
    is_rejected: int


@router.patch("/photo/{image_id}/reject")
async def update_photo_reject(image_id: str, body: RejectUpdateRequest):
    """Update the reject status for a photo (0 or 1)."""
    if body.is_rejected not in (0, 1):
        raise HTTPException(status_code=400, detail="is_rejected must be 0 or 1")

    try:
        repo = PhotoRepository()
        p = repo.get_photo_by_id(image_id)
    except Exception as exc:
        logger.error("Failed to query photo %s: %s", image_id, exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    if p is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    repo.update_reject_status(image_id, body.is_rejected)
    return {"status": "ok", "image_id": image_id, "is_rejected": body.is_rejected}


@router.get("/fullsize/{image_id}")
async def get_fullsize_image(image_id: str):
    """Serve the original full-size image file identified by image_id."""
    try:
        repo = PhotoRepository()
        p = repo.get_photo_by_id(image_id)
    except Exception as exc:
        logger.error("Failed to query photo %s: %s", image_id, exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    if p is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    if not os.path.isfile(p.file_path):
        logger.warning("Original file not found on disk: %s", p.file_path)
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    return FileResponse(p.file_path, media_type="image/jpeg")
