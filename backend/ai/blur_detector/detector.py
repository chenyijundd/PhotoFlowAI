"""
PhotoFlow AI - Blur Detector

Uses Laplacian Variance to detect blurry images.
Threshold-based classification with a hardcoded threshold of 100.
"""

import cv2
import numpy as np

BLUR_THRESHOLD = 100.0


def calculate_blur(image_path: str) -> tuple[float, int]:
    """Analyze a single image for blur using Laplacian Variance.

    Args:
        image_path: Absolute path to the original image file.

    Returns:
        (blur_score, is_blur) where:
        - blur_score: Laplacian variance value (higher = sharper)
        - is_blur: 1 if blur_score < BLUR_THRESHOLD, else 0
    """
    data = np.fromfile(image_path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot decode image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    is_blur = 1 if score < BLUR_THRESHOLD else 0

    return score, is_blur
