"""
PhotoFlow AI — Suggestion Service

Orchestrates suggestion generation across photos.
Processes photos in batches to avoid loading all into memory at once.
"""

import logging
from typing import Optional

from database.repository import PhotoRepository
from .models import SuggestionResult
from .rules import evaluate_suggestion

logger = logging.getLogger("photoflow")

BATCH_SIZE = 200


def generate_suggestions(
    photo_ids: Optional[list[str]] = None,
    repo: Optional[PhotoRepository] = None,
) -> dict:
    """
    Generate AI suggestions for all photos (or a subset).

    This is idempotent — re-running overwrites previous suggestions.

    Args:
        photo_ids: Optional list of specific photo IDs. If None, all photos.
        repo: PhotoRepository instance.

    Returns:
        { "processed": int, "suggestions_generated": int, "suggestion_counts": dict }
    """
    if repo is None:
        repo = PhotoRepository()

    # Get photos to process
    if photo_ids:
        all_photos = []
        for pid in photo_ids:
            p = repo.get_photo_by_id(pid)
            if p:
                all_photos.append(p)
    else:
        all_photos = repo.get_all_photos()

    total = len(all_photos)
    if total == 0:
        return {
            "processed": 0,
            "suggestions_generated": 0,
            "suggestion_counts": {},
        }

    # Evaluate suggestions in batches
    suggestion_counts: dict[str, int] = {}
    updates = []
    processed = 0

    for i in range(0, total, BATCH_SIZE):
        batch = all_photos[i : i + BATCH_SIZE]

        for photo in batch:
            suggestion = evaluate_suggestion(photo)
            processed += 1

            if suggestion:
                suggestion_counts[suggestion] = suggestion_counts.get(suggestion, 0) + 1

            updates.append({
                "image_id": photo.image_id,
                "ai_suggestion": suggestion,
            })

        # Write batch to database
        if updates:
            repo.update_photos_batch(updates)
            logger.info(
                "Suggestions batch %d/%d: %d processed",
                min(i + BATCH_SIZE, total), total, len(updates),
            )
            updates.clear()

    logger.info(
        "Suggestions complete: %d processed, %d generated — %s",
        processed,
        sum(suggestion_counts.values()),
        suggestion_counts,
    )

    return {
        "processed": processed,
        "suggestions_generated": sum(suggestion_counts.values()),
        "suggestion_counts": suggestion_counts,
    }
