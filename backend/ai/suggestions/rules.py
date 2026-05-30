"""
PhotoFlow AI — Suggestion Rules

Pure rule-based suggestion engine. Each rule evaluates a single photo
and returns a suggestion type or None.

Priority (first match wins):
  1. POSSIBLE_BEST       — non-rejected, non-blur, blur_score > threshold
  2. POSSIBLE_BLUR       — photo is flagged as blurred
  3. POSSIBLE_DUPLICATE  — photo belongs to a duplicate group

A photo receives at most ONE suggestion.
"""

from typing import Optional
from database.models import PhotoRecord

# BEST V2 threshold: Laplacian variance above this = clearly sharp
BEST_SHARPNESS_THRESHOLD: float = 200.0


def evaluate_suggestion(photo: PhotoRecord) -> Optional[str]:
    """
    Evaluate a single photo for AI suggestions.

    BEST V2 rule:
      - Non-rejected (is_rejected == 0)
      - Non-blur (is_blur == 0)
      - blur_score > BEST_SHARPNESS_THRESHOLD

    Returns:
        A suggestion type string or None.
    """
    rejected = (photo.is_rejected or 0) == 1
    blurry = (photo.is_blur or 0) == 1
    score = photo.blur_score

    # Rule 1: POSSIBLE_BEST — non-rejected, non-blur, clearly sharp
    if not rejected and not blurry and score is not None and score > BEST_SHARPNESS_THRESHOLD:
        return "POSSIBLE_BEST"

    # Rule 2: POSSIBLE_BLUR — flagged as blurred
    if blurry:
        return "POSSIBLE_BLUR"

    # Rule 3: POSSIBLE_DUPLICATE — part of a duplicate group
    if photo.duplicate_group is not None and photo.duplicate_group != "":
        return "POSSIBLE_DUPLICATE"

    return None
