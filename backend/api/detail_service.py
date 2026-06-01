"""
PhotoFlow AI - Photo Detail API Service

Endpoints for fetching individual photo metadata and serving
full-size original images to the frontend preview panel.
"""

import os
import io
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from database.repository import PhotoRepository

# Ensure HEIC/HEIF support is registered before any PIL operations
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

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

    # Build burst_total for the frontend display
    burst_total = None
    if p.burst_group:
        burst_total = repo.get_burst_group_size(p.burst_group)

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
        "eye_score": p.eye_score,
        "is_closed_eye": p.is_closed_eye,
        "is_rejected": p.is_rejected,
        "is_duplicate": p.is_duplicate,
        "duplicate_group": p.duplicate_group,
        "burst_group": p.burst_group,
        "burst_position": p.burst_position,
        "burst_total": burst_total,
        "is_best_in_burst": p.is_best_in_burst,
        "is_best_in_duplicate": p.is_best_in_duplicate,
    }


@router.patch("/photo/{image_id}/star")
async def update_photo_star(image_id: str, body: StarUpdateRequest):
    """Update the star rating for a photo (0 or 1).

    When starring (1), auto-clears is_rejected so the photo moves
    from 废片 to 已选.  Star and reject are mutually exclusive.
    """
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

    repo.update_star_rating(image_id, body.star_rating, is_manual=True)
    # When starring, clear reject so the photo only appears in 已选
    if body.star_rating == 1 and p.is_rejected == 1:
        repo.update_reject_status(image_id, 0, is_manual=True)
    return {"status": "ok", "image_id": image_id, "star_rating": body.star_rating}


class RejectUpdateRequest(BaseModel):
    is_rejected: int


@router.patch("/photo/{image_id}/reject")
async def update_photo_reject(image_id: str, body: RejectUpdateRequest):
    """Update the reject status for a photo (0 or 1).

    When rejecting (1), auto-clears star_rating so the photo moves
    from 已选 to 废片.  Star and reject are mutually exclusive.
    """
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

    repo.update_reject_status(image_id, body.is_rejected, is_manual=True)
    # When rejecting, clear star so the photo only appears in 废片
    if body.is_rejected == 1 and p.star_rating is not None and p.star_rating >= 1:
        repo.update_star_rating(image_id, 0, is_manual=True)
    return {"status": "ok", "image_id": image_id, "is_rejected": body.is_rejected}


class BatchUpdateRequest(BaseModel):
    photo_ids: list[str]
    star_rating: int | None = None  # 0 or 1, set to update star
    is_rejected: int | None = None  # 0 or 1, set to update reject


@router.post("/photos/batch-update")
async def batch_update(body: BatchUpdateRequest):
    """Update star_rating and/or is_rejected for multiple photos at once.

    At least one of star_rating or is_rejected must be provided.
    All updates run in a single transaction.
    Applies mutual-exclusion: star=1 clears reject; reject=1 clears star.
    """
    if body.star_rating is None and body.is_rejected is None:
        raise HTTPException(status_code=400, detail="star_rating or is_rejected required")

    if body.star_rating is not None and body.star_rating not in (0, 1):
        raise HTTPException(status_code=400, detail="star_rating must be 0 or 1")

    if body.is_rejected is not None and body.is_rejected not in (0, 1):
        raise HTTPException(status_code=400, detail="is_rejected must be 0 or 1")

    if not body.photo_ids:
        return {"updated": 0}

    try:
        repo = PhotoRepository()
        updated = 0
        with repo.batch_transaction():
            for image_id in body.photo_ids:
                p = repo.get_photo_by_id(image_id)
                if p is None:
                    continue

                if body.star_rating is not None:
                    repo.update_star_rating(image_id, body.star_rating, is_manual=True)
                    # Mutual exclusion: star → clear reject
                    if body.star_rating == 1 and p.is_rejected == 1:
                        repo.update_reject_status(image_id, 0, is_manual=True)

                if body.is_rejected is not None:
                    repo.update_reject_status(image_id, body.is_rejected, is_manual=True)
                    # Mutual exclusion: reject → clear star
                    if body.is_rejected == 1 and p.star_rating is not None and p.star_rating >= 1:
                        repo.update_star_rating(image_id, 0, is_manual=True)

                updated += 1

        logger.info("Batch update: %d photos (star=%s, reject=%s)",
                     updated, body.star_rating, body.is_rejected)
        return {"updated": updated}
    except Exception as exc:
        logger.error("Batch update failed: %s", exc)
        raise HTTPException(status_code=500, detail="Batch update failed")


@router.get("/fullsize/{image_id}")
async def get_fullsize_image(image_id: str):
    """Serve the full-size image file identified by image_id.

    For formats that browsers can display (JPEG, PNG), the file is
    served directly.  For HEIC and other conversion-required formats,
    the image is transcoded to JPEG on-the-fly.
    """
    try:
        repo = PhotoRepository()
        p = repo.get_photo_by_id(image_id)
    except Exception as exc:
        logger.error("Failed to query photo %s: %s", image_id, exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    if p is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    readable = p.readable_path
    if not os.path.isfile(readable):
        logger.warning("Readable file not found on disk: %s (raw: %s)", readable, p.file_path)
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    # Formats the browser can display natively — serve directly
    ext = os.path.splitext(readable)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        media_type = {
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(ext, "image/jpeg")
        logger.info("[FULLSIZE] Direct serve %s (ext=%s) for %s", readable, ext, image_id)
        return FileResponse(
            readable,
            media_type=media_type,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    # HEIC, RAW previews, and other formats — convert to JPEG on-the-fly
    try:
        from PIL import Image
        from starlette.responses import Response as StarletteResponse

        logger.info("[FULLSIZE] Converting %s (ext=%s) for %s", readable, ext, image_id)
        with Image.open(readable) as img:
            logger.info("[FULLSIZE] Opened: format=%s mode=%s size=%s", img.format, img.mode, img.size)
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=92)

        data = buf.getvalue()
        logger.info("[FULLSIZE] OK %s → JPEG %d bytes", image_id, len(data))
        return StarletteResponse(
            content=data,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Content-Length": str(len(data)),
            },
        )
    except Exception as exc:
        logger.error("[FULLSIZE] FAIL %s: %s", image_id, exc)
        raise HTTPException(status_code=415, detail="Unsupported image format")
