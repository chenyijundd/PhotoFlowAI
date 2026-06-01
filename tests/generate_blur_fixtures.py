#!/usr/bin/env python3
"""
Generate synthetic test images for blur detector v2 validation.

Creates three test photos under tests/fixtures/:

  a) bokeh_portrait.jpg   — sharp centre circle, blurred surround (simulated bokeh)
  b) true_blur.jpg        — Gaussian‑blurred photo (genuinely blurry)
  c) plain_bg_sharp.jpg   — sharp small subject on a plain white background
"""

import os
import sys

import cv2
import numpy as np

_THIS_FILE = os.path.abspath(__file__)
# Go up from tests/generate_blur_fixtures.py → project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_FILE))
OUT_DIR = os.path.join(_PROJECT_ROOT, "tests", "fixtures")

SIZE = (800, 600)


def _ensure_dir() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def create_bokeh_portrait() -> str:
    """
    Simulate a portrait with sharp centre and blurred background.

    The centre circle contains high‑frequency texture (sharp),
    while the surrounding area is low‑pass filtered (soft bokeh).
    """
    # Start with a noise texture (gives Laplacian something to detect)
    np.random.seed(42)
    img = np.random.randint(0, 256, (*SIZE[::-1], 3), dtype=np.uint8)

    # Create a circular mask for the "subject"
    h, w = SIZE[::-1]
    cx, cy = w // 2, h // 2
    radius = 150
    Y, X = np.ogrid[:h, :w]
    mask = ((X - cx) ** 2 + (Y - cy) ** 2) <= radius**2
    mask_3ch = np.stack([mask, mask, mask], axis=-1)

    # Sharp centre: leave noise as‑is (high variance)
    # Blurred surround: apply Gaussian blur
    blurred = cv2.GaussianBlur(img, (31, 31), 15)

    result = np.where(mask_3ch, img, blurred)

    path = os.path.join(OUT_DIR, "bokeh_portrait.jpg")
    cv2.imwrite(path, result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return path


def create_true_blur() -> str:
    """
    Create a genuinely blurry photo (Gaussian blur over the whole image).
    """
    np.random.seed(99)
    img = np.random.randint(0, 256, (*SIZE[::-1], 3), dtype=np.uint8)

    # Add some structure (circles) before blurring so it's not pure noise
    h, w = SIZE[::-1]
    cv2.circle(img, (w // 3, h // 2), 80, (200, 100, 50), -1)
    cv2.circle(img, (2 * w // 3, h // 2), 80, (50, 150, 200), -1)
    cv2.rectangle(img, (w // 4, h // 4), (3 * w // 4, 3 * h // 4), (100, 200, 100), 3)

    # Heavy blur
    blurred = cv2.GaussianBlur(img, (41, 41), 20)

    path = os.path.join(OUT_DIR, "true_blur.jpg")
    cv2.imwrite(path, blurred, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return path


def create_plain_bg_sharp() -> str:
    """
    Sharp subject on a plain white background.

    The subject (centre region) contains high‑frequency detail;
    the rest of the frame is solid white.
    """
    h, w = SIZE[::-1]
    # Start with white background
    img = np.full((h, w, 3), 240, dtype=np.uint8)

    # Draw a sharp textured subject in the centre
    np.random.seed(7)
    cx, cy = w // 2, h // 2
    subject_w, subject_h = 200, 200
    x1 = cx - subject_w // 2
    y1 = cy - subject_h // 2
    x2 = x1 + subject_w
    y2 = y1 + subject_h

    # Fill the subject area with detailed texture
    texture = np.random.randint(0, 256, (subject_h, subject_w, 3), dtype=np.uint8)
    # Add some lines/edges for Laplacian to detect
    cv2.line(texture, (10, 100), (190, 100), (0, 0, 0), 2)
    cv2.line(texture, (100, 10), (100, 190), (0, 0, 0), 2)
    cv2.circle(texture, (100, 100), 50, (0, 0, 0), 2)
    cv2.rectangle(texture, (30, 30), (170, 170), (0, 0, 0), 2)

    img[y1:y2, x1:x2] = texture

    path = os.path.join(OUT_DIR, "plain_bg_sharp.jpg")
    cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return path


def main() -> None:
    _ensure_dir()
    print(f"Writing test fixtures to: {OUT_DIR}\n")

    for name, creator in [
        ("bokeh_portrait.jpg", create_bokeh_portrait),
        ("true_blur.jpg", create_true_blur),
        ("plain_bg_sharp.jpg", create_plain_bg_sharp),
    ]:
        path = creator()
        size_kb = os.path.getsize(path) / 1024
        print(f"  OK {name}  ({size_kb:.0f} KB)")

    print(f"\nDone. Run with:")
    print(f"  python backend/ai/blur_detector_v2/cli.py --input \"{OUT_DIR}\"")


if __name__ == "__main__":
    main()
