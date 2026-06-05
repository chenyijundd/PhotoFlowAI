"""
PhotoFlow AI - Thumbnail Cache Utilities

Pure functions for thumbnail generation, path resolution, and cache checking.
Each function is self-contained for independent testing.

Performance (Task 14):
   - Cache validation: checks source file mtime vs thumbnail mtime
   - Auto-regen when source is newer than cached thumbnail
"""

import os
import logging
from pathlib import Path

from PIL import Image

# Register HEIC/HEIF support with Pillow (one-time, at import)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

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


def is_thumbnail_stale(
    image_id: str,
    cache_dir: str,
    source_path: str,
) -> bool:
    """
    Check whether a cached thumbnail is stale.

    A thumbnail is stale if the source image file has been modified
    after the thumbnail was generated.

    Returns True if the thumbnail should be regenerated.
    """
    thumb_path = thumbnail_path_for(image_id, cache_dir)
    if not os.path.isfile(thumb_path):
        return True  # No thumbnail at all → needs generation

    if not os.path.isfile(source_path):
        return False  # Source missing — can't validate, keep thumbnail

    try:
        source_mtime = os.path.getmtime(source_path)
        thumb_mtime = os.path.getmtime(thumb_path)
        return source_mtime > thumb_mtime
    except OSError:
        return False  # Can't stat files — keep existing thumbnail


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

    If the thumbnail already exists and is not stale, it is returned
    immediately without re-generating.
    """
    # Check if thumbnail exists and is fresh
    if thumbnail_exists(image_id, cache_dir) and not is_thumbnail_stale(
        image_id, cache_dir, source_path
    ):
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

        logger.debug("Generated thumbnail for %s → %s", source_path, output_path)
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
