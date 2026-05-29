"""
PhotoFlow AI - Photo API Service

REST API endpoints for retrieving photo data from the SQLite database.
Used by the Electron frontend to display the photo grid.
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

from database.repository import PhotoRepository

logger = logging.getLogger(__name__)

# Default cache directory (matches thumbnail_cache default)
DEFAULT_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "cache",
    "thumbnails",
)

router = APIRouter(prefix="/api", tags=["photos"])


def _get_cache_dir() -> str:
    """Resolve the thumbnail cache directory, falling back to default."""
    try:
        from backend.thumbnail_cache.cache_manager import DEFAULT_CACHE_DIR as CACHE_DIR
        return CACHE_DIR
    except ImportError:
        return DEFAULT_CACHE_DIR


def _build_thumbnail_url(image_id: str) -> Optional[str]:
    """Build a thumbnail URL if the thumbnail file exists."""
    cache_dir = _get_cache_dir()
    thumb_path = os.path.join(cache_dir, f"{image_id}.jpg")
    if os.path.isfile(thumb_path):
        return f"/api/thumbnails/{image_id}.jpg"
    return None


@router.get("/photos")
async def get_photos(
    limit: int = Query(100, ge=1, le=1000, description="Number of photos to return"),
    offset: int = Query(0, ge=0, description="Number of photos to skip"),
):
    """Retrieve photos from the database with pagination."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_all_photos()
    except Exception as exc:
        logger.error("Failed to query photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    page = all_photos[offset:offset + limit]

    result = []
    for p in page:
        thumbnail_url = _build_thumbnail_url(p.image_id)
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
            "is_rejected": p.is_rejected,
            "is_duplicate": p.is_duplicate,
            "duplicate_group": p.duplicate_group,
            "ai_suggestion": p.ai_suggestion,
        })

    return {
        "total": len(all_photos),
        "limit": limit,
        "offset": offset,
        "photos": result,
    }


def _build_photo_list_response(photos, offset, limit):
    """Build a paginated photo list response with blur fields."""
    page = photos[offset:offset + limit]
    result = []
    for p in page:
        thumbnail_url = _build_thumbnail_url(p.image_id)
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
            "is_rejected": p.is_rejected,
            "is_duplicate": p.is_duplicate,
            "duplicate_group": p.duplicate_group,
        })
    return {
        "total": len(photos),
        "limit": limit,
        "offset": offset,
        "photos": result,
    }


@router.get("/photos/starred")
async def get_starred_photos(
    limit: int = Query(100, ge=1, le=1000, description="Number of photos to return"),
    offset: int = Query(0, ge=0, description="Number of photos to skip"),
):
    """Retrieve starred photos (star_rating == 1) with pagination."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_starred_photos()
    except Exception as exc:
        logger.error("Failed to query starred photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    return _build_photo_list_response(all_photos, offset, limit)


@router.get("/photos/blur")
async def get_blur_photos(
    limit: int = Query(100, ge=1, le=1000, description="Number of photos to return"),
    offset: int = Query(0, ge=0, description="Number of photos to skip"),
):
    """Retrieve blur photos (is_blur == 1) with pagination."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_blur_photos()
    except Exception as exc:
        logger.error("Failed to query blur photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    return _build_photo_list_response(all_photos, offset, limit)


@router.get("/photos/rejected")
async def get_rejected_photos(
    limit: int = Query(100, ge=1, le=1000, description="Number of photos to return"),
    offset: int = Query(0, ge=0, description="Number of photos to skip"),
):
    """Retrieve rejected photos (is_rejected == 1) with pagination."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_rejected_photos()
    except Exception as exc:
        logger.error("Failed to query rejected photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    return _build_photo_list_response(all_photos, offset, limit)


@router.get("/photos/rejected/count")
async def get_rejected_count():
    """Return the count of rejected photos."""
    try:
        repo = PhotoRepository()
        count = repo.get_rejected_count()
        return {"count": count}
    except Exception as exc:
        logger.error("Failed to query rejected count: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


@router.get("/photos/duplicate")
async def get_duplicate_photos(
    limit: int = Query(100, ge=1, le=1000, description="Number of photos to return"),
    offset: int = Query(0, ge=0, description="Number of photos to skip"),
):
    """Retrieve duplicate photos (is_duplicate == 1) with pagination."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_duplicate_photos()
    except Exception as exc:
        logger.error("Failed to query duplicate photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    return _build_photo_list_response(all_photos, offset, limit)


@router.get("/photos/duplicate/count")
async def get_duplicate_count():
    """Return the count of duplicate photos."""
    try:
        repo = PhotoRepository()
        count = repo.get_duplicate_count()
        return {"count": count}
    except Exception as exc:
        logger.error("Failed to query duplicate count: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


@router.get("/photos/duplicate/group/{group_id}")
async def get_photos_by_duplicate_group(group_id: str):
    """Retrieve all photos in a specific duplicate group."""
    try:
        repo = PhotoRepository()
        photos = repo.get_photos_by_duplicate_group(group_id)
    except Exception as exc:
        logger.error("Failed to query photos by duplicate group: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    result = []
    for p in photos:
        thumbnail_url = _build_thumbnail_url(p.image_id)
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
            "is_rejected": p.is_rejected,
            "is_duplicate": p.is_duplicate,
            "duplicate_group": p.duplicate_group,
        })

    return {"photos": result, "group_id": group_id, "total": len(result)}


@router.get("/photos/starred/count")
async def get_starred_count():
    """Return the count of starred photos."""
    try:
        repo = PhotoRepository()
        count = repo.get_starred_count()
        return {"count": count}
    except Exception as exc:
        logger.error("Failed to query starred count: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


@router.get("/photos/suggested")
async def get_suggested_photos(
    limit: int = Query(100, ge=1, le=1000, description="Number of photos to return"),
    offset: int = Query(0, ge=0, description="Number of photos to skip"),
):
    """Retrieve photos with AI suggestions (ai_suggestion IS NOT NULL)."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_suggested_photos()
    except Exception as exc:
        logger.error("Failed to query suggested photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    return _build_photo_list_response(all_photos, offset, limit)


@router.get("/photos/suggested/count")
async def get_suggested_count():
    """Return the count of photos with AI suggestions."""
    try:
        repo = PhotoRepository()
        count = repo.get_suggested_count()
        return {"count": count}
    except Exception as exc:
        logger.error("Failed to query suggested count: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


@router.get("/thumbnails/{filename}")
async def get_thumbnail(filename: str):
    """Serve a thumbnail image file by filename (e.g. abc123.jpg)."""
    cache_dir = _get_cache_dir()
    # Basic path traversal protection
    safe_name = os.path.basename(filename)
    path = os.path.join(cache_dir, safe_name)

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    return FileResponse(path, media_type="image/jpeg")
