"""
PhotoFlow AI - AI API Service

Endpoints for AI-based photo analysis (blur detection, duplicate detection, etc.).
"""

import logging
import os

from fastapi import APIRouter, HTTPException

from backend.ai.blur_detector.models import BlurDetectRequest, BlurDetectResponse
from backend.ai.blur_detector.service import run_blur_detection
from backend.ai.duplicate_detector.models import DuplicateDetectRequest, DuplicateDetectResponse
from backend.ai.duplicate_detector.service import run_duplicate_detection
from backend.ai.suggestions.models import GenerateSuggestionsRequest, GenerateSuggestionsResponse
from backend.ai.suggestions.service import generate_suggestions
from database.repository import PhotoRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Log file paths
LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "logs",
)
BLUR_LOG_PATH = os.path.join(LOG_DIR, "blur_detection.log")
DUPLICATE_LOG_PATH = os.path.join(LOG_DIR, "duplicate_detection.log")


@router.post("/blur-detect", response_model=BlurDetectResponse)
async def blur_detect(body: BlurDetectRequest):
    """Run blur detection on specified photo IDs, or all photos if not specified."""
    try:
        repo = PhotoRepository()
        # If no photo_ids provided, process ALL photos in the database
        photo_ids = body.photo_ids
        if not photo_ids:
            all_photos = repo.get_all_photos()
            photo_ids = [p.image_id for p in all_photos]

        if not photo_ids:
            return BlurDetectResponse(processed=0, blurred=0)

        processed, blurred = run_blur_detection(
            photo_ids,
            repo,
            log_path=BLUR_LOG_PATH,
        )
        return BlurDetectResponse(processed=processed, blurred=blurred)
    except Exception as exc:
        logger.error("Blur detection failed: %s", exc)
        raise HTTPException(status_code=500, detail="Blur detection failed")


@router.post("/duplicate-detect", response_model=DuplicateDetectResponse)
async def duplicate_detect(body: DuplicateDetectRequest):
    """Run duplicate detection on specified photo IDs, or all photos if not specified."""
    try:
        repo = PhotoRepository()
        # If no photo_ids provided, process ALL photos in the database
        photo_ids = body.photo_ids
        if not photo_ids:
            all_photos = repo.get_all_photos()
            photo_ids = [p.image_id for p in all_photos]

        if not photo_ids:
            return DuplicateDetectResponse(processed=0, duplicate_groups=0, duplicates=0)

        processed, duplicate_groups, duplicates = run_duplicate_detection(
            photo_ids,
            repo,
            log_path=DUPLICATE_LOG_PATH,
        )
        return DuplicateDetectResponse(
            processed=processed,
            duplicate_groups=duplicate_groups,
            duplicates=duplicates,
        )
    except Exception as exc:
        logger.error("Duplicate detection failed: %s", exc)
        raise HTTPException(status_code=500, detail="Duplicate detection failed")


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
