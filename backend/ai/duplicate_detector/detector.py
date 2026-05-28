"""
PhotoFlow AI - Duplicate Detector

Computes perceptual hashes (phash) for duplicate image detection.
Uses the imagehash library with Pillow for phash computation.
"""

import io
import imagehash
from PIL import Image


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
