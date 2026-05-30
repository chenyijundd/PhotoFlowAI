"""
PhotoFlow AI - AI API Service

Endpoints for AI-based photo analysis (blur detection, duplicate detection, etc.).

All detection tasks run in background threads. The start endpoint returns a
task_id immediately, and the frontend polls GET /api/ai/{type}-progress/{id}.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.ai.blur_detector.models import BlurDetectRequest
from backend.ai.blur_detector.service import start_blur_detection, get_blur_progress, cancel_blur_detection
from backend.ai.duplicate_detector.service import start_duplicate_detection, get_duplicate_progress, cancel_duplicate_detection
from backend.ai.suggestions.models import GenerateSuggestionsRequest, GenerateSuggestionsResponse
from backend.ai.suggestions.service import generate_suggestions
from database.repository import PhotoRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


# ---- Response models ----

class TaskStartResponse(BaseModel):
    task_id: str
    total: int


class ProgressResponse(BaseModel):
    task_id: str
    status: str  # "running" | "completed" | "cancelled" | "error"
    phase: str
    total: int
    progress: int
    current_file: str
    # Blur-specific
    blurred: int = 0
    # Duplicate-specific
    duplicate_groups: int = 0
    duplicate_count: int = 0
    failed: int = 0


# ---- Blur Detection ----

@router.post("/blur-detect", response_model=TaskStartResponse)
async def blur_detect_start(body: BlurDetectRequest):
    """Start blur detection in background. Returns task_id for polling."""
    try:
        repo = PhotoRepository()
        photo_ids = body.photo_ids
        if not photo_ids:
            all_photos = repo.get_all_photos()
            photo_ids = [p.image_id for p in all_photos]

        if not photo_ids:
            return TaskStartResponse(task_id="", total=0)

        task_id = start_blur_detection(photo_ids)
        return TaskStartResponse(task_id=task_id, total=len(photo_ids))
    except Exception as exc:
        logger.error("Blur detection start failed: %s", exc)
        raise HTTPException(status_code=500, detail="Blur detection start failed")


@router.get("/blur-progress/{task_id}", response_model=ProgressResponse)
async def blur_detect_progress(task_id: str):
    """Poll blur detection progress."""
    state = get_blur_progress(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    return ProgressResponse(
        task_id=state["task_id"],
        status=state["status"],
        phase=state.get("phase", ""),
        total=state.get("total", 0),
        progress=state.get("progress", 0),
        current_file=state.get("current_file", ""),
        blurred=state.get("blurred", 0),
        failed=state.get("failed", 0),
    )


@router.post("/blur-cancel/{task_id}")
async def blur_detect_cancel(task_id: str):
    """Cancel a running blur detection task."""
    ok = cancel_blur_detection(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
    return {"status": "cancelled"}


# ---- Duplicate Detection ----

@router.post("/duplicate-detect", response_model=TaskStartResponse)
async def duplicate_detect_start(body: BlurDetectRequest):
    """Start duplicate detection in background. Returns task_id for polling."""
    try:
        repo = PhotoRepository()
        photo_ids = body.photo_ids
        if not photo_ids:
            all_photos = repo.get_all_photos()
            photo_ids = [p.image_id for p in all_photos]

        if not photo_ids:
            return TaskStartResponse(task_id="", total=0)

        task_id = start_duplicate_detection(photo_ids)
        return TaskStartResponse(task_id=task_id, total=len(photo_ids))
    except Exception as exc:
        logger.error("Duplicate detection start failed: %s", exc)
        raise HTTPException(status_code=500, detail="Duplicate detection start failed")


@router.get("/duplicate-progress/{task_id}", response_model=ProgressResponse)
async def duplicate_detect_progress(task_id: str):
    """Poll duplicate detection progress."""
    state = get_duplicate_progress(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    return ProgressResponse(
        task_id=state["task_id"],
        status=state["status"],
        phase=state.get("phase", ""),
        total=state.get("total", 0),
        progress=state.get("progress", 0),
        current_file=state.get("current_file", ""),
        duplicate_groups=state.get("duplicate_groups", 0),
        duplicate_count=state.get("duplicate_count", 0),
        failed=state.get("failed", 0),
    )


@router.post("/duplicate-cancel/{task_id}")
async def duplicate_detect_cancel(task_id: str):
    """Cancel a running duplicate detection task."""
    ok = cancel_duplicate_detection(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
    return {"status": "cancelled"}


# ---- AI Suggestions ----

@router.post("/generate-suggestions", response_model=GenerateSuggestionsResponse)
async def generate_ai_suggestions(body: GenerateSuggestionsRequest = GenerateSuggestionsRequest()):
    """Generate rule-based AI suggestions for all (or specified) photos.

    Idempotent — re-running overwrites previous suggestions.
    """
    try:
        repo = PhotoRepository()
        result = generate_suggestions(
            photo_ids=body.photo_ids,
            repo=repo,
        )
        return GenerateSuggestionsResponse(
            processed=result["processed"],
            suggestions_generated=result["suggestions_generated"],
            suggestion_counts=result["suggestion_counts"],
        )
    except Exception as exc:
        logger.error("Suggestion generation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Suggestion generation failed")
