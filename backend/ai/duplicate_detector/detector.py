"""
PhotoFlow AI - Duplicate Detector

Computes perceptual hashes (phash / dhash) for duplicate image detection.
Uses the imagehash library with Pillow for hash computation.

As of Task 1 optimization:
  - compute_dhash_int()  returns a **64-bit integer** (not ImageHash object)
    that is used for multi-index hashing — much faster lookup and comparison.
  - hamming_distance_int()  uses Python's native int.bit_count()  (POPCNT
    instruction on x86) for single-cycle Hamming distance.
"""

import io
import imagehash
from PIL import Image


# ---------------------------------------------------------------------------
# Legacy phash API (kept for backward compatibility)
# ---------------------------------------------------------------------------


def compute_phash(image_path: str) -> imagehash.ImageHash:
    """Compute perceptual hash (phash) for an image.

    Uses open() + BytesIO to handle Unicode file paths on Windows,
    then passes bytes to Pillow for decoding.

    Args:
        image_path: Absolute path to the original image file.

    Returns:
        ImageHash object (64-bit hash) for Hamming Distance comparison.

    Raises:
        FileNotFoundError: If the image cannot be read or decoded.
    """
    with open(image_path, "rb") as f:
        buf = io.BytesIO(f.read())
    img = Image.open(buf)
    img = img.convert("RGB")
    return imagehash.phash(img)


def hamming_distance(hash_a: imagehash.ImageHash, hash_b: imagehash.ImageHash) -> int:
    """Compute Hamming Distance between two perceptual hashes.

    Args:
        hash_a: First ImageHash.
        hash_b: Second ImageHash.

    Returns:
        Integer Hamming distance (number of differing bits).
    """
    return hash_a - hash_b


# ---------------------------------------------------------------------------
# Optimised dHash API (64-bit integer — used by multi-index hashing)
# ---------------------------------------------------------------------------


def _load_image_rgb(image_path: str) -> Image.Image:
    """Load an image file as an RGB Pillow Image.

    Uses open() + BytesIO to handle Unicode paths on Windows.
    """
    with open(image_path, "rb") as f:
        buf = io.BytesIO(f.read())
    img = Image.open(buf)
    return img.convert("RGB")


def compute_dhash_int(image_path: str, hash_size: int = 8) -> int:
    """Compute **difference hash** (dHash) as a 64-bit integer.

    dHash works by comparing adjacent pixels horizontally:
      1. Resize to *(hash_size + 1) × hash_size*  (default 9×8).
      2. Convert to greyscale.
      3. For each row: if pixel[x] < pixel[x+1] → 1, else → 0.
      4. Pack the resulting boolean matrix into a single 64-bit integer.

    The integer representation allows **multi-index hashing** — the
    64-bit value is split into segments for sub-linear candidate lookup.

    dHash is ~3× faster to compute than phash (no DCT step) and
    slightly more robust to subtle brightness changes.

    Args:
        image_path: Absolute path to the original image file.
        hash_size: Side length of the hash (default 8 → 64 bits).

    Returns:
        64-bit integer where bit 63 is the first row, first column.
    """
    img = _load_image_rgb(image_path)
    dh = imagehash.dhash(img, hash_size=hash_size)
    bits = dh.hash.flatten()
    val = 0
    for b in bits:
        val = (val << 1) | (1 if b else 0)
    return val


def hamming_distance_int(a: int, b: int) -> int:
    """Compute Hamming distance between two 64-bit integers.

    Uses Python's ``int.bit_count()`` which maps to the POPCNT
    instruction on x86 — single-cycle throughput on modern CPUs.

    Args:
        a, b: 64-bit hash integers.

    Returns:
        Number of differing bits (0–64).
    """
    return (a ^ b).bit_count()
