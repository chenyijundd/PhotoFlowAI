"""
PhotoFlow AI - Thumbnail Cache Utilities

Pure functions for thumbnail generation, path resolution, and cache checking.
Each function is self-contained for independent testing.
"""

import os
import logging
from pathlib import Path
from typing import Optional

from PIL import Image

from .models import ThumbnailResult

logger = logging.getLogger(__name__)

THUMBNAIL_MAX_SIZE: int = 200
THUMBNAIL_QUALITY: int = 85
THUMBNAIL_FORMAT: str = "JPEG"
THUMBNAIL_EXTENSION: str = ".jpg"


def ensure_cache_dir(cache_dir: str) -> str:
    """Create the cache directory if it does not exist. Returns the path."""
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def thumbnail_path_for(image_id: str, cache_dir: str) -> str:
    """Compute the expected thumbnail file path for a given image ID."""
    file_name = f"{image_id}{THUMBNAIL_EXTENSION}"
    return os.path.join(cache_dir, file_name)


def thumbnail_exists(image_id: str, cache_dir: str) -> bool:
    """Check whether a thumbnail for the given image ID is already cached."""
    return os.path.isfile(thumbnail_path_for(image_id, cache_dir))


def generate_single_thumbnail(
    source_path: str,
    image_id: str,
    cache_dir: str,
    max_size: int = THUMBNAIL_MAX_SIZE,
) -> ThumbnailResult:
    """
    Generate a thumbnail for a single image.

    The thumbnail is resized so its longest side is `max_size` pixels,
    maintaining the original aspect ratio. The image is never cropped
    or stretched.

    If the thumbnail already exists, it is returned immediately without
    re-generating.
    """
    # Return cached result immediately if available
    if thumbnail_exists(image_id, cache_dir):
        cached_path = thumbnail_path_for(image_id, cache_dir)
        return ThumbnailResult(
            image_id=image_id,
            source_path=source_path,
            thumbnail_path=cached_path,
            success=True,
        )

    # Validate source file
    if not os.path.isfile(source_path):
        return ThumbnailResult(
            image_id=image_id,
            source_path=source_path,
            success=False,
            error=f"Source file not found: {source_path}",
        )

    try:
        with Image.open(source_path) as img:
            # Convert RGBA/P modes to RGB for JPEG output
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # thumbnail() resizes so that no dimension exceeds max_size,
            # and always preserves aspect ratio. Never crops.
            img.thumbnail((max_size, max_size), Image.LANCZOS)

            # Ensure cache directory exists
            ensure_cache_dir(cache_dir)

            output_path = thumbnail_path_for(image_id, cache_dir)
            img.save(output_path, format=THUMBNAIL_FORMAT, quality=THUMBNAIL_QUALITY)

        return ThumbnailResult(
            image_id=image_id,
            source_path=source_path,
            thumbnail_path=output_path,
            success=True,
        )

    except Exception as exc:
        logger.warning("Failed to generate thumbnail for %s: %s", source_path, exc)
        return ThumbnailResult(
            image_id=image_id,
            source_path=source_path,
            success=False,
            error=str(exc),
        )
