"""
PhotoFlow AI - Thumbnail Cache Manager

Orchestrates scanning images via image_loader and generating thumbnails.
Provides batch processing (sequential, no multi-threading in V1).

Performance (Task 14):
   - Cache validation: respects source file mtime to auto-regen stale thumbnails
"""

import os
import logging
from typing import List

from backend.image_loader.utils import scan_photos

from .models import ThumbnailResult
from .utils import generate_single_thumbnail, ensure_cache_dir, thumbnail_exists, is_thumbnail_stale

logger = logging.getLogger(__name__)

from backend.env import get_data_dir

DEFAULT_CACHE_DIR = os.path.join(get_data_dir(), "cache", "thumbnails")


class CacheManager:
    """Manages thumbnail cache operations."""

    def __init__(self, cache_dir: str = None):
        self.cache_dir = ensure_cache_dir(cache_dir or DEFAULT_CACHE_DIR)
        self._generated_count = 0
        self._cached_count = 0
        self._error_count = 0
        self._regenerated_count = 0  # Track re-generated (stale cache) separately

    @property
    def summary(self) -> dict:
        return {
            "cache_dir": self.cache_dir,
            "generated": self._generated_count,
            "regenerated": self._regenerated_count,
            "cached": self._cached_count,
            "errors": self._error_count,
        }

    def process_image(self, source_path: str, image_id: str) -> ThumbnailResult:
        """
        Generate a thumbnail for a single image.

        If the thumbnail is already cached and the source file hasn't been
        modified since, returns the cached result without re-generating.
        If the source was modified after caching, auto-re-generates.
        """
        from .utils import thumbnail_path_for

        if thumbnail_exists(image_id, self.cache_dir):
            # Check if the cached thumbnail is still fresh
            if not is_thumbnail_stale(image_id, self.cache_dir, source_path):
                self._cached_count += 1
                return ThumbnailResult(
                    image_id=image_id,
                    source_path=source_path,
                    thumbnail_path=thumbnail_path_for(image_id, self.cache_dir),
                    success=True,
                )
            else:
                # Stale cache — will regenerate below
                logger.info(
                    "Thumbnail stale for %s (source modified), regenerating...",
                    source_path,
                )
                self._regenerated_count += 1

        result = generate_single_thumbnail(
            source_path=source_path,
            image_id=image_id,
            cache_dir=self.cache_dir,
        )

        if result.success:
            if self._regenerated_count == 0 or result.image_id != image_id:
                pass  # already counted in regenerated or it was a fresh generate
            if self._generated_count == 0:
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
