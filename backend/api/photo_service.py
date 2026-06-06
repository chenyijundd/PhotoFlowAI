"""
PhotoFlow AI - Photo API Service

REST API endpoints for retrieving photo data from the SQLite database.
Used by the Electron frontend to display the photo grid.
"""

import asyncio
import json
import logging
import os
import queue
import threading
import uuid
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from database.repository import PhotoRepository

logger = logging.getLogger(__name__)

# Default cache directory (matches thumbnail_cache default)
from backend.env import get_data_dir

DEFAULT_CACHE_DIR = os.path.join(get_data_dir(), "cache", "thumbnails")

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


@router.get("/photos/blur/count")
async def get_blur_count():
    """Return the count of blur photos."""
    try:
        repo = PhotoRepository()
        count = repo.get_blur_count()
        return {"count": count}
    except Exception as exc:
        logger.error("Failed to query blur count: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


@router.get("/photos/closed-eye")
async def get_closed_eye_photos(
    limit: int = Query(100, ge=1, le=1000, description="Number of photos to return"),
    offset: int = Query(0, ge=0, description="Number of photos to skip"),
):
    """Retrieve photos with closed/half-closed eyes (is_closed_eye == 1)."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_closed_eye_photos()
    except Exception as exc:
        logger.error("Failed to query closed-eye photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    return _build_photo_list_response(all_photos, offset, limit)


@router.get("/photos/closed-eye/count")
async def get_closed_eye_count():
    """Return the count of closed-eye photos."""
    try:
        repo = PhotoRepository()
        count = repo.get_closed_eye_count()
        return {"count": count}
    except Exception as exc:
        logger.error("Failed to query closed-eye count: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


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
            "eye_score": p.eye_score,
            "is_closed_eye": p.is_closed_eye,
            "is_rejected": p.is_rejected,
            "is_duplicate": p.is_duplicate,
            "duplicate_group": p.duplicate_group,
            "raw_jpeg_pair_id": p.raw_jpeg_pair_id,
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


@router.get("/photos/counts")
async def get_all_counts():
    """Return all filter counts in a single request — basic + AI category.

    Single-pass DB scan over all photos avoids N+1 HTTP round trips
    and N+1 SQLite queries.  The frontend filter bar receives all 12
    counts in one response.
    """
    try:
        repo = PhotoRepository()
        all_photos = repo.get_all_photos()
        all_count = len(all_photos)

        starred = 0
        rejected = 0
        unprocessed = 0
        blur_count = 0
        closed_eye_count = 0
        duplicate_count = 0
        best_count = 0
        burst_groups: set[str] = set()
        burst_photo_count = 0

        for p in all_photos:
            # ---- Basic status ----
            if p.star_rating is not None and p.star_rating >= 1:
                starred += 1
            elif p.is_rejected == 1:
                rejected += 1
            else:
                unprocessed += 1

            # ---- AI category counts ----
            if p.is_blur == 1:
                blur_count += 1
            if p.is_closed_eye == 1:
                closed_eye_count += 1
            if p.is_duplicate == 1:
                duplicate_count += 1
            if p.is_best_in_burst == 1 or p.is_best_in_duplicate == 1:
                best_count += 1
            if p.burst_group is not None:
                burst_groups.add(p.burst_group)
                burst_photo_count += 1

        # Clean = total - (photos with any AI issue or in any group)
        clean_count = all_count - (
            blur_count + closed_eye_count + duplicate_count
            + burst_photo_count
        )
        # Compensate double-counting: a photo can have multiple flags.
        # We count photos that have at least one issue/belonging.
        flagged_ids: set[str] = set()
        for p in all_photos:
            if p.is_blur == 1 or p.is_closed_eye == 1 or p.is_duplicate == 1:
                flagged_ids.add(p.image_id)
            if p.burst_group is not None:
                flagged_ids.add(p.image_id)
        clean_count = all_count - len(flagged_ids)

        # ---- Trash count (separate query since all_photos only returns non-deleted) ----
        trash_count = repo.get_trashed_count()

        return {
            "all": all_count,
            "starred": starred,
            "unprocessed": unprocessed,
            "rejected": rejected,
            "trash_count": trash_count,
            "blur_count": blur_count,
            "closed_eye_count": closed_eye_count,
            "duplicate_count": duplicate_count,
            "burst_group_count": len(burst_groups),
            "burst_photo_count": burst_photo_count,
            "best_count": best_count,
            "clean_count": clean_count,
        }
    except Exception as exc:
        logger.error("Failed to query counts: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


@router.get("/photos/bursts")
async def get_burst_groups_list():
    """Return a summary list of all burst groups."""
    try:
        repo = PhotoRepository()
        group_ids = repo.get_burst_groups()
        result = []
        for gid in group_ids:
            photos = repo.get_burst_group_photos(gid)
            result.append({
                "group_id": gid,
                "photo_count": len(photos),
                "photo_ids": [p.image_id for p in photos],
            })
        return {"burst_groups": result, "total": len(result)}
    except Exception as exc:
        logger.error("Failed to query burst groups: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


@router.get("/photos/burst/{group_id}")
async def get_burst_group_photos_endpoint(group_id: str):
    """Retrieve all photos in a specific burst group, ordered by burst_position."""
    try:
        repo = PhotoRepository()
        photos = repo.get_burst_group_photos(group_id)
    except Exception as exc:
        logger.error("Failed to query burst group photos: %s", exc)
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
            "eye_score": p.eye_score,
            "is_closed_eye": p.is_closed_eye,
            "is_rejected": p.is_rejected,
            "is_duplicate": p.is_duplicate,
            "duplicate_group": p.duplicate_group,
            "burst_group": p.burst_group,
            "burst_position": p.burst_position,
            "raw_jpeg_pair_id": p.raw_jpeg_pair_id,
        })

    return {"photos": result, "group_id": group_id, "total": len(result)}


@router.get("/photos/bursts/count")
async def get_burst_count():
    """Return the count of distinct burst groups."""
    try:
        repo = PhotoRepository()
        count = repo.get_burst_group_count()
        return {"count": count}
    except Exception as exc:
        logger.error("Failed to query burst count: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


@router.get("/photos/unprocessed")
async def get_unprocessed_photos(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Retrieve unprocessed photos (not starred, not rejected)."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_unprocessed_photos()
    except Exception as exc:
        logger.error("Failed to query unprocessed photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    return _build_photo_list_response(all_photos, offset, limit)


@router.get("/photos/unprocessed/count")
async def get_unprocessed_count():
    """Return the count of unprocessed photos."""
    try:
        repo = PhotoRepository()
        count = repo.get_unprocessed_count()
        return {"count": count}
    except Exception as exc:
        logger.error("Failed to query unprocessed count: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


@router.get("/photos/best")
async def get_best_photos(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Retrieve photos marked as best-in-burst (is_best_in_burst == 1)."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_best_photos()
    except Exception as exc:
        logger.error("Failed to query best photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    return _build_photo_list_response(all_photos, offset, limit)


@router.get("/photos/best/count")
async def get_best_count():
    """Return the count of best-in-burst photos."""
    try:
        repo = PhotoRepository()
        count = repo.get_burst_best_count()
        return {"count": count}
    except Exception as exc:
        logger.error("Failed to query best count: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")


@router.get("/photos/burst")
async def get_burst_photos(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Retrieve photos that belong to any burst group, sorted by burst_group then burst_position."""
    try:
        repo = PhotoRepository()
        all_photos = repo.get_all_photos()
        burst_photos = [p for p in all_photos if p.burst_group is not None]
        # Sort by burst_group (连拍组) then burst_position (组内帧序)
        burst_photos.sort(key=lambda p: (p.burst_group or "", p.burst_position or 0))
    except Exception as exc:
        logger.error("Failed to query burst photos: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")

    return _build_photo_list_response(burst_photos, offset, limit)


@router.get("/thumbnails/{filename}")
async def get_thumbnail(filename: str):
    """Serve a thumbnail image file by filename (e.g. abc123.jpg)."""
    cache_dir = _get_cache_dir()
    # Basic path traversal protection
    safe_name = os.path.basename(filename)
    path = os.path.join(cache_dir, safe_name)

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Access-Control-Allow-Origin": "*"},
    )


# ---------------------------------------------------------------------------
# One-Click Cull (comprehensive: blur + duplicate + burst)
# ---------------------------------------------------------------------------


class OneClickCullResponse(BaseModel):
    eye_closed_rejected: int = 0
    blur_flagged: int = 0
    duplicate_rejected: int = 0      # non-best duplicates rejected
    duplicate_best_kept: int = 0     # best-in-duplicate photos kept (not rejected)
    burst_accepted: int = 0
    burst_rejected: int = 0
    clean_accepted: int = 0          # non-burst clean photos auto-starred
    total_accepted: int = 0
    total_rejected: int = 0
    untouched: int = 0
    total_photos: int = 0


class CullProgressResponse(BaseModel):
    task_id: str
    status: str = "running"
    phase: str = ""
    total: int = 0
    progress: int = 0
    # Final result (populated when status == "completed")
    result: Optional[OneClickCullResponse] = None
    error: Optional[str] = None


# In-memory task store for cull progress
_cull_tasks: dict[str, dict] = {}
_cull_lock = threading.Lock()
_cull_event_queues: dict[str, queue.Queue] = {}


def _push_cull_event(task_id: str, event_type: str, data: dict):
    """Push an SSE event into the cull task's event queue (thread-safe)."""
    q = _cull_event_queues.get(task_id)
    if q is not None:
        try:
            q.put({"event": event_type, "data": data})
        except Exception:
            logger.debug("Failed to push cull SSE event '%s' to queue", event_type, exc_info=True)


class TaskStartResponse(BaseModel):
    task_id: str
    total: int


def _run_cull_all(task_id: str, event_queue: queue.Queue | None = None):
    """Run the full 5-step cull in background, updating progress as we go.

    Cascade order (matches AI analysis pipeline):
      Step 1: Auto-reject closed-eye photos (L1: fatal, unfixable).
      Step 2: Count blur photos (L2: quality issue — FLAGGED only, NOT auto-rejected).
              Blur is left for the photographer to decide on manually.
      Step 3: Burst groups — accept best-in-burst, reject rest.
              Photos already rejected (closed-eye) are skipped.
      Step 4: Duplicate groups — pick best, reject rest.
              Photos already in burst groups or rejected are skipped.
      Step 5: Clean remaining photos — auto-star photos that have no issues
              and weren't already processed.

    **Manual override protection**: Photos with manually_operated_at set
    (photographer hand-touched star or reject) are skipped in ALL steps.
    AI never overrides a human decision.

    If *event_queue* is provided, SSE events are pushed at step boundaries
    and progress checkpoints for real-time streaming to the frontend.
    """
    _push = lambda evt, data: _push_cull_event(task_id, evt, data) if event_queue else None

    state = _cull_tasks.get(task_id)
    if not state:
        return

    repo = PhotoRepository()
    all_photos = repo.get_all_photos()

    if not all_photos:
        state["status"] = "completed"
        state["result"] = OneClickCullResponse(total_photos=0)
        return

    # ---- Pre-cull reset: clear previous non-manual cull results ----
    # Ensures a re-analysis + re-cull produces correct results even when
    # a previous cull was run without analysis data and starred everything.
    # Photos with manually_operated_at (hand-picked by the photographer)
    # are always preserved — AI never overrides a human decision.
    stars_reset, rejects_reset = repo.reset_cull_results()
    if stars_reset or rejects_reset:
        logger.info(
            "one-click-cull: reset %d non-manual star(s), %d non-manual reject(s)",
            stars_reset, rejects_reset,
        )
        # Reload photos so in-memory state matches the reset database
        all_photos = repo.get_all_photos()

    total_photos = len(all_photos)
    starred_ids = {p.image_id for p in all_photos if p.star_rating is not None and p.star_rating >= 1}

    # Photos the photographer has manually adjusted (starred or rejected by hand).
    # These must be left untouched — AI should never override a human decision.
    manually_operated_ids = {p.image_id for p in all_photos if p.manually_operated_at is not None}

    eye_closed_rejected = 0
    blur_flagged = 0
    duplicate_rejected = 0
    duplicate_best_kept = 0
    burst_accepted = 0
    burst_rejected = 0
    clean_accepted = 0

    processed: set[str] = set()

    # ---- Step 1: Reject closed-eye photos (L1: fatal) ----
    state["phase"] = "步骤 1/5: 闭眼照片"
    _push("step_start", {"step": "eye_reject", "phase": "步骤 1/5: 闭眼照片", "total": total_photos})
    scanned = 0
    with repo.batch_transaction():
        for p in all_photos:
            if state.get("cancelled"):
                state["status"] = "cancelled"
                _push("task_cancelled", {})
                return
            scanned += 1
            if scanned % 50 == 0:
                state["progress"] = scanned
                state["total"] = total_photos
                _push("progress", {"step": "eye_reject", "phase": "步骤 1/5: 闭眼照片", "progress": scanned, "total": total_photos})
            if p.image_id in starred_ids or p.image_id in manually_operated_ids:
                continue
            if p.is_closed_eye == 1 and p.is_rejected != 1:
                repo.update_reject_status(p.image_id, 1)
                eye_closed_rejected += 1
                processed.add(p.image_id)
    state["progress"] = total_photos
    _push("progress", {"step": "eye_reject", "phase": "步骤 1/5: 闭眼照片", "progress": total_photos, "total": total_photos})
    _push("step_complete", {"step": "eye_reject", "eye_closed_rejected": eye_closed_rejected})

    # ---- Step 2: Count blur photos (L2: flagged, NOT auto-rejected) ----
    state["phase"] = "步骤 2/5: 模糊标记"
    _push("step_start", {"step": "blur_flag", "phase": "步骤 2/5: 模糊标记", "total": total_photos})
    blur_flagged = sum(
        1 for p in all_photos
        if p.is_blur == 1 and p.is_rejected != 1
        and p.image_id not in starred_ids
        and p.image_id not in manually_operated_ids
    )
    state["progress"] = total_photos
    _push("progress", {"step": "blur_flag", "phase": "步骤 2/5: 模糊标记", "progress": total_photos, "total": total_photos})
    _push("step_complete", {"step": "blur_flag", "blur_flagged": blur_flagged})

    # ---- Step 3: Burst groups — accept best, reject rest ----
    # Photos already rejected (closed-eye) are skipped.
    # Burst takes priority over duplicate per cascade design.
    group_ids = repo.get_burst_groups()
    total_burst = sum(len(repo.get_burst_group_photos(gid)) for gid in group_ids) if group_ids else 0
    step3_base = total_photos
    step3_total = step3_base + total_burst

    state["phase"] = "步骤 3/5: 连拍组"
    state["progress"] = step3_base
    state["total"] = step3_total
    _push("step_start", {"step": "burst_cull", "phase": "步骤 3/5: 连拍组", "total": step3_total})
    burst_processed_cnt = 0
    with repo.batch_transaction():
        for gid in group_ids:
            if state.get("cancelled"):
                state["status"] = "cancelled"
                _push("task_cancelled", {})
                return
            group_photos = repo.get_burst_group_photos(gid)
            for p in group_photos:
                burst_processed_cnt += 1
                if burst_processed_cnt % 20 == 0:
                    state["progress"] = step3_base + burst_processed_cnt
                    state["total"] = step3_total
                    _push("progress", {"step": "burst_cull", "phase": "步骤 3/5: 连拍组", "progress": state["progress"], "total": state["total"]})
                if p.image_id in starred_ids or p.image_id in manually_operated_ids:
                    continue
                # Skip already rejected photos (closed-eye)
                if p.image_id in processed:
                    continue
                # Safety: exclude closed-eye from burst best recommendation
                if p.is_closed_eye == 1:
                    continue
                if p.is_best_in_burst == 1:
                    if p.star_rating != 1:
                        repo.update_star_rating(p.image_id, 1)
                        burst_accepted += 1
                        processed.add(p.image_id)
                else:
                    if p.is_rejected != 1:
                        repo.update_reject_status(p.image_id, 1)
                        burst_rejected += 1
                        processed.add(p.image_id)
    state["progress"] = step3_total if total_burst else step3_base
    state["total"] = step3_total if total_burst else step3_base
    _push("progress", {"step": "burst_cull", "phase": "步骤 3/5: 连拍组", "progress": state["progress"], "total": state["total"]})
    _push("step_complete", {"step": "burst_cull", "burst_accepted": burst_accepted, "burst_rejected": burst_rejected})

    # ---- Step 4: Duplicate groups — keep best, reject rest ----
    # Skip photos already processed (closed-eye rejected, burst handled).
    state["phase"] = "步骤 4/5: 重复照片"
    state["progress"] = state["progress"]
    dup_groups = repo.get_duplicate_groups()
    dup_scanned = 0
    dup_total = sum(dg["cnt"] for dg in dup_groups) if dup_groups else 0
    step4_base = state["progress"]
    step4_total = step4_base + dup_total
    state["total"] = step4_total
    _push("step_start", {"step": "dup_cull", "phase": "步骤 4/5: 重复照片", "total": step4_total})
    with repo.batch_transaction():
        for dg in dup_groups:
            if state.get("cancelled"):
                state["status"] = "cancelled"
                _push("task_cancelled", {})
                return
            group_photos = repo.get_photos_by_duplicate_group(dg["duplicate_group"])
            # Exclude already processed (closed-eye rejected, burst handled),
            # starred, and manually operated photos.
            candidates = [
                p for p in group_photos
                if p.image_id not in processed
                and p.image_id not in starred_ids
                and p.image_id not in manually_operated_ids
            ]
            if len(candidates) <= 1:
                dup_scanned += len(group_photos)
                continue
            # Find the best-in-duplicate (set by analyse phase)
            best = next((p for p in candidates if p.is_best_in_duplicate == 1), None)
            if best is None:
                # Fallback: pick by blur_score (shouldn't happen if analyse ran)
                candidates.sort(key=lambda p: p.blur_score or 0, reverse=True)
                best = candidates[0]
            duplicate_best_kept += 1
            # Reject the rest
            for p in candidates:
                dup_scanned += 1
                if dup_scanned % 20 == 0:
                    state["progress"] = step4_base + dup_scanned
                    state["total"] = step4_total
                    _push("progress", {"step": "dup_cull", "phase": "步骤 4/5: 重复照片", "progress": state["progress"], "total": state["total"]})
                if p.image_id == best.image_id:
                    if p.star_rating != 1:
                        repo.update_star_rating(p.image_id, 1)
                        processed.add(p.image_id)
                    continue
                if p.is_rejected != 1:
                    repo.update_reject_status(p.image_id, 1)
                    duplicate_rejected += 1
                    processed.add(p.image_id)
    state["progress"] = step4_total if dup_total else step4_base
    state["total"] = step4_total if dup_total else step4_base
    _push("progress", {"step": "dup_cull", "phase": "步骤 4/5: 重复照片", "progress": state["progress"], "total": state["total"]})
    _push("step_complete", {"step": "dup_cull", "duplicate_rejected": duplicate_rejected, "duplicate_best_kept": duplicate_best_kept})

    # ---- Step 5: Clean remaining photos — auto-star ----
    # Only stars photos that have NO detection issues AND haven't been
    # decided before.  Must skip:
    #   - Already processed (starred / rejected this run)
    #   - Manually operated (photographer hand-touched)
    #   - Already rejected from a previous cull (is_rejected == 1)
    #   - Belongs to a burst group (handled in Step 3)
    #   - Belongs to a duplicate group (handled in Step 4)
    state["phase"] = "步骤 5/5: 干净照片"
    state["progress"] = state["progress"]
    state["total"] = total_photos * 3  # rough scale for the final scan
    _push("step_start", {"step": "clean_star", "phase": "步骤 5/5: 干净照片", "total": total_photos})
    scanned = 0
    with repo.batch_transaction():
        for p in all_photos:
            if state.get("cancelled"):
                state["status"] = "cancelled"
                _push("task_cancelled", {})
                return
            scanned += 1
            if scanned % 50 == 0:
                state["progress"] = state["progress"] + scanned
                _push("progress", {"step": "clean_star", "phase": "步骤 5/5: 干净照片", "progress": scanned, "total": total_photos})
            if p.image_id in starred_ids or p.image_id in processed or p.image_id in manually_operated_ids:
                continue
            # Already rejected (by previous cull or this run) — keep decision
            if p.is_rejected == 1:
                continue
            # Already in a burst or duplicate group — handled by Steps 3 / 4
            if p.burst_group is not None or p.duplicate_group is not None:
                continue
            # Blur photos stay for manual review
            if p.is_blur == 1:
                continue
            # Safety: skip closed-eye (should already be in processed)
            if p.is_closed_eye == 1:
                continue
            repo.update_star_rating(p.image_id, 1)
            clean_accepted += 1
            processed.add(p.image_id)

    _push("step_complete", {"step": "clean_star", "clean_accepted": clean_accepted})

    # ---- Final tally ----
    total_accepted = burst_accepted + duplicate_best_kept + clean_accepted
    total_rejected = eye_closed_rejected + duplicate_rejected + burst_rejected
    untouched = sum(
        1 for p in all_photos
        if p.image_id not in starred_ids
        and p.image_id not in processed
        and p.image_id not in manually_operated_ids
    )

    result = OneClickCullResponse(
        eye_closed_rejected=eye_closed_rejected,
        blur_flagged=blur_flagged,
        duplicate_rejected=duplicate_rejected,
        duplicate_best_kept=duplicate_best_kept,
        burst_accepted=burst_accepted,
        burst_rejected=burst_rejected,
        clean_accepted=clean_accepted,
        total_accepted=total_accepted,
        total_rejected=total_rejected,
        untouched=untouched,
        total_photos=total_photos,
    )

    logger.info(
        "one-click-cull: eye=%d blur_flagged=%d dup_rej=%d dup_best=%d "
        "burst_acc=%d burst_rej=%d clean_acc=%d untouched=%d total=%d",
        eye_closed_rejected, blur_flagged, duplicate_rejected, duplicate_best_kept,
        burst_accepted, burst_rejected, clean_accepted, untouched, total_photos,
    )

    state["status"] = "completed"
    state["phase"] = "选片完成"
    state["progress"] = state["total"]
    state["result"] = result

    _push("task_complete", {
        "eye_closed_rejected": eye_closed_rejected,
        "blur_flagged": blur_flagged,
        "duplicate_rejected": duplicate_rejected,
        "duplicate_best_kept": duplicate_best_kept,
        "burst_accepted": burst_accepted,
        "burst_rejected": burst_rejected,
        "clean_accepted": clean_accepted,
        "total_accepted": total_accepted,
        "total_rejected": total_rejected,
        "untouched": untouched,
        "total_photos": total_photos,
    })


@router.post("/photos/cull-all")
async def one_click_cull_start():
    """Start a one-click cull task in the background.

    Returns a task_id for polling via GET /api/photos/cull-progress/{task_id}
    or streaming via GET /api/photos/cull-stream/{task_id} (SSE).
    """
    # Pre-check: refuse cull if no photos have been analysed yet.
    # Without analysis data (closed_eye, blur, burst, duplicate), the cull
    # algorithm would star every photo indiscriminately (Step 5).
    repo = PhotoRepository()
    unanalyzed = repo.get_unanalyzed_count()
    all_photos = repo.get_all_photos()
    total = len(all_photos)
    if total > 0 and unanalyzed == total:
        raise HTTPException(
            status_code=400,
            detail="尚未执行智能分析，无法选片。请先点击「智能分析」完成 AI 检测。",
        )

    task_id = uuid.uuid4().hex[:8]
    state = {
        "task_id": task_id,
        "status": "running",
        "phase": "准备中...",
        "total": 0,
        "progress": 0,
        "cancelled": False,
    }
    with _cull_lock:
        _cull_tasks[task_id] = state
        _cull_event_queues[task_id] = queue.Queue()

    t = threading.Thread(
        target=_run_cull_all,
        args=(task_id, _cull_event_queues[task_id]),
        daemon=True,
    )
    t.start()
    return {"task_id": task_id, "total": 0}


@router.get("/photos/cull-progress/{task_id}", response_model=CullProgressResponse)
async def one_click_cull_progress(task_id: str):
    """Poll the progress of a one-click cull task (legacy — prefer SSE for new clients)."""
    state = _cull_tasks.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    return CullProgressResponse(
        task_id=state["task_id"],
        status=state["status"],
        phase=state.get("phase", ""),
        total=state.get("total", 0),
        progress=state.get("progress", 0),
        result=state.get("result"),
        error=state.get("error"),
    )


@router.get("/photos/cull-stream/{task_id}")
async def cull_stream(task_id: str):
    """SSE endpoint — stream cull progress events in real time.

    Events emitted:
      - step_start    {step, phase, total}
      - progress      {step, phase, progress, total}
      - step_complete {step, ...counts}
      - task_complete {result}
      - task_cancelled {}
    """
    event_queue = _cull_event_queues.get(task_id)

    if event_queue is None:
        with _cull_lock:
            if _cull_tasks.get(task_id) and task_id not in _cull_event_queues:
                _cull_event_queues[task_id] = queue.Queue()
        event_queue = _cull_event_queues.get(task_id)

    if event_queue is None:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        loop = asyncio.get_running_loop()
        try:
            while True:
                try:
                    event = await loop.run_in_executor(None, lambda: event_queue.get(timeout=1.0))
                    yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                    if event["event"] in ("task_complete", "task_cancelled", "task_error"):
                        break
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _cull_event_queues.pop(task_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/photos/cull-cancel/{task_id}")
async def cull_cancel(task_id: str):
    """Cancel a running cull task."""
    state = _cull_tasks.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    if state.get("status") != "running":
        raise HTTPException(status_code=400, detail="Task is not running")
    state["cancelled"] = True
    _push_cull_event(task_id, "task_cancelled", {})
    return {"status": "cancelling"}
