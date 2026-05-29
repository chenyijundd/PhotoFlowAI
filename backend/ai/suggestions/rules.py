"""
PhotoFlow AI — Suggestion Rules

Pure rule-based suggestion engine. Each rule evaluates a single photo
and returns a suggestion type or None.

Priority (first match wins):
  1. POSSIBLE_BEST  — sharpest non-rejected photo in a duplicate group
  2. POSSIBLE_BLUR  — photo is flagged as blurred
  3. POSSIBLE_DUPLICATE — photo belongs to a duplicate group

A photo receives at most ONE suggestion.
"""

from typing import Optional
from database.models import PhotoRecord


def evaluate_suggestion(
    photo: PhotoRecord,
    best_in_group: Optional[set] = None,
) -> Optional[str]:
    """
    Evaluate a single photo for AI suggestions.

    Args:
        photo: The photo record to evaluate.
        best_in_group: Optional set of image_ids that are the best shot
                       in their respective duplicate groups. If not provided,
                       POSSIBLE_BEST is skipped.

    Returns:
        A suggestion type string or None.
    """
    # Rule 1: POSSIBLE_BEST — best shot in duplicate group
    if best_in_group and photo.image_id in best_in_group:
        return "POSSIBLE_BEST"

    # Rule 2: POSSIBLE_BLUR — flagged as blurred
    if photo.is_blur == 1:
        return "POSSIBLE_BLUR"

    # Rule 3: POSSIBLE_DUPLICATE — part of a duplicate group
    if photo.duplicate_group is not None and photo.duplicate_group != "":
        return "POSSIBLE_DUPLICATE"

    return None


def compute_best_in_groups(photos: list[PhotoRecord]) -> set[str]:
    """
    For each duplicate group, find the photo with the highest blur_score
    that is NOT rejected. This photo is the "best shot" suggestion.

    Groups with only 1 photo or where all photos are rejected are skipped.
    """
    # Group photos by duplicate_group
    groups: dict[str, list[PhotoRecord]] = {}
    for p in photos:
        gid = p.duplicate_group
        if not gid:
            continue
        groups.setdefault(gid, []).append(p)

    best_ids: set[str] = set()

    for gid, members in groups.items():
        # Need at least 2 photos in group
        if len(members) < 2:
            continue

        # Filter: not rejected, has a blur_score
        candidates = [
            m for m in members
            if (m.is_rejected or 0) == 0 and m.blur_score is not None
        ]
        if not candidates:
            continue

        # Find the one with highest blur_score (sharpest)
        best = max(candidates, key=lambda m: m.blur_score or 0)
        best_ids.add(best.image_id)

    return best_ids
