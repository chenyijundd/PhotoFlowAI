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

import math
import time
from typing import Tuple

import cv2
import numpy as np

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

# ---------------------------------------------------------------------------
# NOTE: 400 px thumbnail pre-screening was considered and rejected.
#
# 400 px thumbnails are ~0.3 % of a 24 MP original.  At that scale:
#   - Slight focus misses (< 2 mm DoF) are invisible (blur radius < 1 px).
#   - JPEG compression artefacts add spurious high-frequency noise that
#     inflates Laplacian variance → false "sharp" readings.
#   - Pillow's thumbnail() applies anti-alias down-sampling which further
#     masks genuine softness.
#
# A future approach: generate dedicated **800 px AI previews** during
# import.  800 px is large enough that Laplacian variance correlates
# strongly with full-resolution sharpness (see 改进建议 §2), while
# still loading 50–100× faster than a 24 MP HEIC.  These previews
# would also benefit eye detection (skip HEIC decode entirely for
# photos without a RAW preview).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------


def calculate_blur_v2(
    image_path: str,
    *,
    threshold: float | None = None,
    patch_grid: int | None = None,
) -> Tuple[float, int, list[float], float, float, float]:
    """Analyse a single image for blur using multi‑patch Laplacian variance.

    Args:
        image_path: Absolute path to the original image file.
        threshold: Override ``BLUR_THRESHOLD``.  If *None*, the module
            default is used.
        patch_grid: Override ``PATCH_GRID``.  If *None*, the module
            default is used.

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
