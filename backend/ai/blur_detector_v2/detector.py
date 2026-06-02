"""
PhotoFlow AI - Blur Detector V2 (Content-Aware)

Multi-patch Laplacian Variance with centre-weighted scoring.

Problem with v1 (global Laplacian):
    Photos with large smooth areas — bokeh backgrounds, white walls, sky —
    get low variance scores and are falsely flagged as blurry.

Solution:
    1. Divide the image into an N×N grid of patches.
    2. Score each patch independently with Laplacian variance.
    3. Apply centre weighting: patches near the centre (where the subject
       usually sits) contribute more to the score.
    4. Take the median of the top 50 % patches — this effectively ignores
       smooth background regions and focuses on patches that actually
       contain detail.
    5. Combine the centre-weighted average (40 %) with the top‑median
       (60 %) for the final score.

This approach correctly identifies sharp subjects even when most of
the frame is soft (bokeh, plain backdrop).
"""

from __future__ import annotations

import logging
import math
import os
import time
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger("blur_detection_v2")

# ---------------------------------------------------------------------------
# Tunable constants (exposed at module level for future configuration UI)
# ---------------------------------------------------------------------------

PATCH_GRID: int = 4
"""Number of patches per side.  4 → 16 patches total."""

BLUR_THRESHOLD: float = 25.0
"""
Photos with a final score *below* this value are classified as blurry.

Calibrated through real‑world testing.  The multi‑patch + top‑median
approach produces scores that are naturally concentrated on the sharpest
regions; 25.0 was found to be the sweet spot that catches genuinely
blurry photos while letting bokeh / plain‑background shots through.
"""

CENTRE_WEIGHT_TOP_FRACTION: float = 0.5
"""
Fraction of patches (sorted by score) included in the top‑median
calculation.  0.5 means "top 50 % patches".
"""

WEIGHTED_WEIGHT: float = 0.4
"""Weight of the centre‑weighted average in the final score (0–1)."""

TOP_MEDIAN_WEIGHT: float = 0.6
"""Weight of the top‑patches median in the final score (0–1)."""

# ---- Thumbnail pre-screening thresholds ----
# These are intentionally conservative — only the extremes (obviously
# sharp / obviously blurry) are fast-pathed.  Borderline photos fall
# through to the full multi-patch analysis.

THUMB_SHARP_THRESHOLD: float = 120.0
"""
Global Laplacian variance on the **thumbnail** above this →
photo is classified as **sharp** without loading the full image.

Conservative default: only very high scores skip full analysis.
"""

THUMB_BLUR_THRESHOLD: float = 8.0
"""
Global Laplacian variance on the **thumbnail** below this →
photo is classified as **blurry** without loading the full image.

Conservative default: only very low scores skip full analysis.
"""

THUMB_SCALE_GUARD: float = 0.85
"""
If the thumbnail score falls between *THUMB_BLUR_THRESHOLD* and
*THUMB_SHARP_THRESHOLD*, the photo is **borderline** — we fall
through to the full multi-patch analysis for an accurate verdict.

Setting this fraction higher makes the pre-screen more aggressive
(more photos fast-pathed) but risks false classifications.
"""


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------


def _quick_laplacian_on_thumbnail(thumbnail_path: str) -> float | None:
    """Compute global Laplacian variance on a cached thumbnail.

    The thumbnail is a small JPEG (~400 px) that loads in < 1 ms.
    Laplacian variance is strongly correlated across resolutions, so
    a sharp full‑size image will also have a high score on the thumbnail.

    Returns:
        Laplacian variance (float), or *None* if the thumbnail cannot
        be read (missing / corrupted).
    """
    if not thumbnail_path or not os.path.isfile(thumbnail_path):
        return None
    gray = cv2.imread(thumbnail_path, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return None
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def calculate_blur_v2(
    image_path: str,
    *,
    threshold: float | None = None,
    patch_grid: int | None = None,
    thumbnail_path: str | None = None,
) -> Tuple[float, int, list[float], float, float, float]:
    """Analyse a single image for blur using multi‑patch Laplacian variance.

    If *thumbnail_path* points to an existing cached thumbnail, a fast
    pre‑screen is performed first:
      - Score > ``THUMB_SHARP_THRESHOLD`` → sharp (skip full image)
      - Score < ``THUMB_BLUR_THRESHOLD``  → blurry (skip full image)
      - Otherwise → borderline → fall through to full analysis

    Args:
        image_path: Absolute path to the original image file.
        threshold: Override ``BLUR_THRESHOLD``.  If *None*, the module
            default is used.
        patch_grid: Override ``PATCH_GRID``.  If *None*, the module
            default is used.
        thumbnail_path: Optional path to a pre‑generated thumbnail
            (~400 px JPEG).  When provided, a fast pre‑screen may
            skip loading the full‑resolution image.

    Returns:
        (blur_score, is_blur, patch_scores, processing_time_ms,
         weighted_score, top_median_score) where:

        * *blur_score* — final composite score (higher = sharper)
        * *is_blur* — 1 if *blur_score* < threshold, else 0
        * *patch_scores* — per‑patch Laplacian variance values
          (length = *patch_grid*²)
        * *processing_time_ms* — wall‑clock time for this image
        * *weighted_score* — centre‑weighted average of all patch scores
        * *top_median_score* — median of the top‑50 % patches
    """
    t0 = time.perf_counter()

    _threshold = threshold if threshold is not None else BLUR_THRESHOLD
    _grid = patch_grid if patch_grid is not None else PATCH_GRID

    # ---- Step 0: fast thumbnail pre‑screen ----
    thumb_score = _quick_laplacian_on_thumbnail(thumbnail_path)
    if thumb_score is not None:
        if thumb_score > THUMB_SHARP_THRESHOLD:
            elapsed = (time.perf_counter() - t0) * 1000.0
            # Thumbnail is clearly sharp — skip full image
            logger.debug(
                "Blur V2 fast-path SHARP: thumbnail_score=%.1f > %.0f",
                thumb_score, THUMB_SHARP_THRESHOLD,
            )
            return (
                thumb_score, 0, [thumb_score], elapsed,
                thumb_score, thumb_score,
            )
        elif thumb_score < THUMB_BLUR_THRESHOLD:
            elapsed = (time.perf_counter() - t0) * 1000.0
            # Thumbnail is clearly blurry — skip full image
            logger.debug(
                "Blur V2 fast-path BLUR: thumbnail_score=%.1f < %.0f",
                thumb_score, THUMB_BLUR_THRESHOLD,
            )
            is_blur = 1 if thumb_score < _threshold else 0
            return (
                thumb_score, is_blur, [thumb_score], elapsed,
                thumb_score, thumb_score,
            )
        # else: borderline — fall through to full analysis

    # ---- Step 1: read image (OpenCV → PIL fallback for HEIC etc.) ----
    from backend.raw_preview.extractor import read_image_bgr
    img = read_image_bgr(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot decode image: {image_path}")

    h, w = img.shape[:2]

    # ---- Step 2: convert to grayscale ----
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ---- Step 3: divide into patches ----
    patch_h = h // _grid
    patch_w = w // _grid

    if patch_h < 1 or patch_w < 1:
        # Image is too small for the grid — fall back to global variance
        score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        elapsed = (time.perf_counter() - t0) * 1000.0
        is_blur = 1 if score < _threshold else 0
        return score, is_blur, [score], elapsed, score, score

    patch_scores: list[float] = []

    # Image centre coordinates (used for distance weighting)
    cx = w / 2.0
    cy = h / 2.0
    # Normalisation factor: maximum possible distance from centre to corner
    max_dist = math.sqrt(cx * cx + cy * cy)

    # ---- Step 4 & 5: score each patch + centre weight ----
    weights: list[float] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for row in range(_grid):
        y1 = row * patch_h
        y2 = y1 + patch_h if row < _grid - 1 else h
        patch_cy = (y1 + y2) / 2.0

        for col in range(_grid):
            x1 = col * patch_w
            x2 = x1 + patch_w if col < _grid - 1 else w
            patch_cx = (x1 + x2) / 2.0

            # Extract patch
            patch = gray[y1:y2, x1:x2]
            score = float(cv2.Laplacian(patch, cv2.CV_64F).var())
            patch_scores.append(score)

            # Centre distance weight
            dx = patch_cx - cx
            dy = patch_cy - cy
            distance = math.sqrt(dx * dx + dy * dy)
            norm_distance = distance / max_dist if max_dist > 0 else 0.0
            weight = 1.0 / (1.0 + norm_distance)

            weights.append(weight)
            weighted_sum += score * weight
            weight_total += weight

    # ---- Step 6: centre-weighted average ----
    weighted_score = weighted_sum / weight_total if weight_total > 0 else 0.0

    # ---- Step 7: top-50 % median ----
    sorted_scores = sorted(patch_scores, reverse=True)
    top_count = max(1, int(len(sorted_scores) * CENTRE_WEIGHT_TOP_FRACTION))
    top_scores = sorted_scores[:top_count]
    top_median = float(np.median(top_scores))

    # ---- Step 8: composite final score ----
    final_score = (
        weighted_score * WEIGHTED_WEIGHT + top_median * TOP_MEDIAN_WEIGHT
    )

    # ---- Step 9: classify ----
    is_blur = 1 if final_score < _threshold else 0

    elapsed = (time.perf_counter() - t0) * 1000.0
    return final_score, is_blur, patch_scores, elapsed, weighted_score, top_median
