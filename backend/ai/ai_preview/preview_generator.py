"""
PhotoFlow AI — 800 px AI Preview Generator

Produces and caches JPEG previews whose long edge does not exceed
800 pixels.  These previews are large enough that Laplacian variance
correlates strongly with full-resolution sharpness, yet small enough
to load 50–100× faster than a 24 MP HEIC/RAW original.

Usage::

    from backend.ai.ai_preview.preview_generator import (
        get_preview_path, ensure_preview,
    )

    path = ensure_preview(image_id, readable_source_path)
    # → ``cache/ai_previews/<image_id>.jpg`` (created if missing)
"""

from __future__ import annotations

import logging
import os

import cv2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

PREVIEW_MAX_SIZE: int = 800
"""Long edge of generated previews (px).  Aspect ratio is preserved."""

PREVIEW_JPEG_QUALITY: int = 85
"""JPEG quality for saved previews (0–100)."""

_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
PREVIEW_DIR: str = os.path.join(_PROJECT_ROOT, "cache", "ai_previews")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_preview_path(image_id: str) -> str:
    """Return the expected on-disk path for *image_id*'s AI preview."""
    return os.path.join(PREVIEW_DIR, f"{image_id}.jpg")


def _generate_preview(image_id: str, source_path: str) -> str:
    """Generate an 800 px JPEG preview and return its path.

    The source image is read via ``read_image_bgr`` (OpenCV → PIL
    fallback) so HEIC, RAW previews, and standard formats are all
    supported.

    Raises:
        FileNotFoundError: If *source_path* cannot be decoded.
    """
    from backend.raw_preview.extractor import read_image_bgr

    img = read_image_bgr(source_path)
    if img is None:
        raise FileNotFoundError(f"Cannot decode image for preview: {source_path}")

    h, w = img.shape[:2]
    long_edge = max(h, w)
    if long_edge > PREVIEW_MAX_SIZE:
        scale = PREVIEW_MAX_SIZE / long_edge
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    preview_path = get_preview_path(image_id)
    cv2.imwrite(preview_path, img, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_JPEG_QUALITY])

    logger.debug("Generated 800 px AI preview: %s → %s", source_path, preview_path)
    return preview_path


def ensure_preview(image_id: str, source_path: str) -> str:
    """Return the AI preview path, generating it if necessary.

    This is a cache-or-create wrapper: if the preview already exists
    on disk it is returned immediately (no re-generation).  Otherwise
    it is generated from *source_path* and cached for future calls.

    Args:
        image_id: Unique image identifier (used as the cache key).
        source_path: Path to the **readable** source image (full
            original or RAW preview JPEG).

    Returns:
        Absolute path to the 800 px JPEG preview.
    """
    preview_path = get_preview_path(image_id)
    if os.path.isfile(preview_path):
        return preview_path
    return _generate_preview(image_id, source_path)
