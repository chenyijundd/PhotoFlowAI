"""
PhotoFlow AI - RAW Preview Extractor

Extracts the embedded full-size JPEG preview from RAW camera files.
Most cameras embed a high-quality JPEG inside the RAW container —
we extract it once and use it for all downstream processing.

Supported formats (by extension, case-insensitive):
    .CR2  — Canon
    .CR3  — Canon (newer)
    .NEF  — Nikon
    .ARW  — Sony
    .DNG  — Adobe / Leica / DJI / smartphone
    .ORF  — Olympus / OM System
    .RAF  — Fujifilm
    .RW2  — Panasonic
    .PEF  — Pentax
    .SRW  — Samsung
    .RAW  — generic (may fail if not supported by LibRaw)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported RAW extensions (lowercase, without dot)
# ---------------------------------------------------------------------------

RAW_EXTENSIONS: frozenset = frozenset({
    "cr2", "cr3",   # Canon
    "nef", "nrw",   # Nikon
    "arw", "srf",   # Sony
    "dng",          # Adobe / Leica / DJI / smartphone
    "orf",          # Olympus / OM System
    "raf",          # Fujifilm
    "rw2",          # Panasonic
    "pef",          # Pentax
    "srw",          # Samsung
    "raw",          # generic (LibRaw-dependent)
})

# Default cache directory for extracted previews
from backend.env import get_data_dir

DEFAULT_PREVIEW_DIR = os.path.join(get_data_dir(), "cache", "raw_previews")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_raw_file(file_path: str) -> bool:
    """Return True if the file extension matches a supported RAW format."""
    ext = Path(file_path).suffix.lower().lstrip(".")
    return ext in RAW_EXTENSIONS


def preview_path_for(image_id: str, cache_dir: str | None = None) -> str:
    """Return the expected preview file path for a given image ID."""
    _dir = cache_dir or DEFAULT_PREVIEW_DIR
    return os.path.join(_dir, f"{image_id}.jpg")


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------


def extract_preview(
    raw_path: str,
    image_id: str,
    cache_dir: str | None = None,
) -> Optional[str]:
    """Extract the embedded JPEG preview from a RAW file and save it to disk.

    Args:
        raw_path: Absolute path to the RAW file.
        image_id: Stable image ID (used for the output filename).
        cache_dir: Directory for extracted previews.  Defaults to
            ``cache/raw_previews/``.

    Returns:
        Absolute path to the saved JPEG, or *None* if extraction failed.
        Returns the existing path (without re-extracting) if the preview
        is already cached.

    Raises:
        FileNotFoundError: If *raw_path* does not exist.
    """
    _dir = cache_dir or DEFAULT_PREVIEW_DIR
    os.makedirs(_dir, exist_ok=True)

    output_path = preview_path_for(image_id, _dir)

    # ---- Already extracted — skip ----
    if os.path.isfile(output_path):
        logger.debug("RAW preview already cached: %s", output_path)
        return output_path

    if not os.path.isfile(raw_path):
        raise FileNotFoundError(f"RAW file not found: {raw_path}")

    # ---- Extract via rawpy ----
    try:
        import rawpy

        with rawpy.imread(raw_path) as raw:
            thumb = raw.extract_thumb()

        if thumb.format == rawpy.ThumbFormat.JPEG:
            # Most cameras: full-size JPEG preview
            with open(output_path, "wb") as f:
                f.write(thumb.data)
            logger.info(
                "Extracted JPEG preview (%d bytes) from %s → %s",
                len(thumb.data), os.path.basename(raw_path), output_path,
            )
            return output_path

        elif thumb.format == rawpy.ThumbFormat.BITMAP:
            # Some cameras / DNG files: uncompressed bitmap
            # Convert to JPEG ourselves
            from PIL import Image
            import numpy as np

            # thumb.data is a numpy array (H, W, 3) RGB
            img = Image.fromarray(thumb.data.astype("uint8"), "RGB")
            img.save(output_path, "JPEG", quality=95)
            logger.info(
                "Converted bitmap preview from %s → %s",
                os.path.basename(raw_path), output_path,
            )
            return output_path

        else:
            logger.warning(
                "Unsupported thumbnail format %s in %s",
                thumb.format, raw_path,
            )
            return None

    except Exception as exc:
        logger.error("Failed to extract preview from %s: %s", raw_path, exc)
        return None


def get_raw_dimensions(raw_path: str) -> tuple[int, int]:
    """Read the full-resolution dimensions from a RAW file header.

    Does NOT decode pixel data — only reads the metadata header.
    For cameras with masked border pixels (e.g. Canon), the visible
    (user-facing) size is used.

    Returns:
        (width, height) or (0, 0) on failure.
    """
    try:
        import rawpy

        with rawpy.imread(raw_path) as raw:
            # raw.sizes returns a namedtuple: (width, height, iwidth, iheight)
            # Use visible size (what the photographer sees)
            w, h = raw.sizes.width, raw.sizes.height
            return w, h if w and h else raw.sizes.iwidth, raw.sizes.iheight
    except Exception as exc:
        logger.warning("Failed to read dimensions from %s: %s", raw_path, exc)
        return (0, 0)




def read_image_bgr(image_path: str):
    """Read an image as a BGR numpy array (OpenCV format).

    Tries OpenCV ``imdecode`` first (fast, native).  If that fails
    (e.g. HEIC on Windows where the codec is unavailable), falls
    back to PIL/Pillow conversion.

    Args:
        image_path: Path to the image file (any format Pillow supports).

    Returns:
        BGR numpy array (H, W, 3), or None if all readers fail.
    """
    import cv2
    import numpy as np

    # ---- Fast path: OpenCV ----
    data = np.fromfile(image_path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is not None:
        return img

    # ---- Fallback: PIL → numpy (HEIC, WebP, etc.) ----
    try:
        from PIL import Image
        pil_img = Image.open(image_path).convert("RGB")
        rgb = np.array(pil_img)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except Exception:
        logger.warning("All readers failed for: %s", image_path)
        return None
