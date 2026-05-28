"""
PhotoFlow AI - Thumbnail Cache Manager

Orchestrates scanning images via image_loader and generating thumbnails.
Provides batch processing (sequential, no multi-threading in V1).
"""

import os
import logging
from typing import List

from backend.image_loader.utils import scan_photos

from .models import ThumbnailResult
from .utils import generate_single_thumbnail, ensure_cache_dir

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "cache",
    "thumbnails",
)


class CacheManager:
    """Manages thumbnail cache operations."""

    def __init__(self, cache_dir: str = None):
        self.cache_dir = ensure_cache_dir(cache_dir or DEFAULT_CACHE_DIR)
        self._generated_count = 0
        self._cached_count = 0
        self._error_count = 0

    @property
    def summary(self) -> dict:
        return {
            "cache_dir": self.cache_dir,
            "generated": self._generated_count,
            "cached": self._cached_count,
            "errors": self._error_count,
        }

    def process_image(self, source_path: str, image_id: str) -> ThumbnailResult:
        """
        Generate a thumbnail for a single image.

        If the thumbnail is already cached, returns the cached result
        without re-generating.
        """
        from .utils import thumbnail_exists

        if thumbnail_exists(image_id, self.cache_dir):
            from .utils import thumbnail_path_for

            self._cached_count += 1
            return ThumbnailResult(
                image_id=image_id,
                source_path=source_path,
                thumbnail_path=thumbnail_path_for(image_id, self.cache_dir),
                success=True,
            )

        result = generate_single_thumbnail(
            source_path=source_path,
            image_id=image_id,
            cache_dir=self.cache_dir,
        )

        if result.success:
            self._generated_count += 1
        else:
            self._error_count += 1

        return result

    def process_directory(self, input_dir: str) -> List[ThumbnailResult]:
        """
        Scan a directory and generate thumbnails for all supported images.

        Iterates via the image_loader generator so that 5000+ images
        are not loaded into memory at once.
        """
        results: List[ThumbnailResult] = []

        for photo in scan_photos(input_dir):
            result = self.process_image(photo.file_path, photo.id)
            results.append(result)

        return results
