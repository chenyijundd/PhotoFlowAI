"""
PhotoFlow AI - Image Scanner Utilities

Provides directory scanning, file filtering, and metadata extraction.
Each function is self-contained for independent testing.
"""

import os
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from PIL import Image

# Register HEIC/HEIF support with Pillow (one-time, at import)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # pillow-heif not installed — HEIC files will be skipped

from .models import PhotoInfo
from backend.raw_preview.extractor import RAW_EXTENSIONS, is_raw_file, get_raw_dimensions

# Supported image formats (lowercase, without dot)
SUPPORTED_FORMATS: frozenset = frozenset({"jpg", "jpeg", "png", "heic", "heif"}).union(RAW_EXTENSIONS)


def is_supported_format(file_path: str) -> bool:
    """Check whether a file has a supported image extension."""
    ext = Path(file_path).suffix.lower().lstrip(".")
    return ext in SUPPORTED_FORMATS


def generate_file_id(file_path: str, input_dir: str = "") -> str:
    """Generate a stable unique ID from the absolute file path."""
    _ = input_dir  # kept for backward compatibility
    return hashlib.md5(file_path.encode("utf-8")).hexdigest()[:12]


def safe_get_image_size(file_path: str) -> tuple[int, int]:
    """
    Safely read image dimensions.

    For regular images, uses Pillow's lazy header parsing.
    For RAW files, uses rawpy to read the metadata header.

    Returns (width, height) or (0, 0) if the file is corrupted or
    cannot be read. Does NOT load full pixel data into memory.
    """
    # RAW files: use rawpy metadata (fast, no pixel decode)
    if is_raw_file(file_path):
        return get_raw_dimensions(file_path)

    # Regular images: use Pillow
    try:
        with Image.open(file_path) as img:
            return img.size
    except Exception:
        return (0, 0)


def get_file_created_time(file_path: str) -> str:
    """
    Get the file creation time as an ISO-8601 string.

    Falls back to modification time if creation time is not available
    (e.g., on some Unix systems).
    """
    stat = os.stat(file_path)
    timestamp = stat.st_ctime if hasattr(stat, "st_ctime") else stat.st_mtime
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.isoformat()


def scan_photos(input_dir: str) -> Generator[Optional[PhotoInfo], None, None]:
    """
    Recursively scan a directory for supported image files.

    This is a generator so that callers can process images one at a time
    without loading all metadata into memory at once.
    """
    for root, _dirs, files in os.walk(input_dir):
        for file_name in sorted(files):
            file_path = os.path.join(root, file_name)

            # Skip files with unsupported extensions early
            if not is_supported_format(file_path):
                continue

            # Skip symlinks and other non-regular files
            if not os.path.isfile(file_path):
                continue

            file_size = 0
            created_time = ""
            width = 0
            height = 0

            try:
                file_size = os.path.getsize(file_path)
                created_time = get_file_created_time(file_path)
                width, height = safe_get_image_size(file_path)
            except OSError:
                # Unreadable file — yield nothing for this entry
                continue

            # If Pillow could not read the image, treat as corrupted
            if width == 0 or height == 0:
                continue

            # Generate a stable ID from the relative path
            photo_id = generate_file_id(file_path, input_dir)

            yield PhotoInfo(
                id=photo_id,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                created_time=created_time,
                width=width,
                height=height,
            )


def collect_scan(input_dir: str) -> list[PhotoInfo]:
    """
    Convenience wrapper that materializes a full scan into a list.

    For 5000+ images, prefer using scan_photos() as a generator
    to avoid holding all results in memory simultaneously.
    """
    return list(scan_photos(input_dir))
