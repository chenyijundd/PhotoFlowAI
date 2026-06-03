"""
PhotoFlow AI - Duplicate Detector

Computes perceptual hashes (phash / dhash) and SSIM for duplicate image detection.
Uses the imagehash library with Pillow for hash computation.

As of Task 1 optimization:
  - compute_dhash_int()  returns a **64-bit integer** (not ImageHash object)
    that is used for multi-index hashing — much faster lookup and comparison.
  - hamming_distance_int()  uses Python's native int.bit_count()  (POPCNT
    instruction on x86) for single-cycle Hamming distance.
  - compute_ssim()  provides the final structural similarity verification
    for candidate pairs that pass the Hamming pre-filter, eliminating
    false positives from hash-only comparison.
"""

import io
import numpy as np
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


# ---------------------------------------------------------------------------
# SSIM — Structural Similarity Index (final arbiter for duplicate detection)
# ---------------------------------------------------------------------------

# Cached import check (module level, done once)
_has_scipy: bool | None = None


def _check_scipy() -> bool:
    """Lazy-check whether scipy.ndimage is available (cached)."""
    global _has_scipy
    if _has_scipy is None:
        try:
            import scipy.ndimage  # noqa: F401
            _has_scipy = True
        except ImportError:
            _has_scipy = False
    return _has_scipy


def _integral_box_filter(arr: np.ndarray, size: int) -> np.ndarray:
    """Fast 2D box filter via integral image (pure numpy, vectorised).

    Uses the integral-image trick: the sum over any rectangle can be
    computed with 4 array lookups — O(1) per output pixel, independent
    of window size.  This is ~50× faster than a double-loop per-pixel
    approach for 256×256 images.

    Args:
        arr: 2D float64 array.
        size: Window size (odd integer, e.g. 7).

    Returns:
        Filtered array of same shape as *arr*.
    """
    r = size // 2
    area = float(size * size)

    # Reflect-pad to handle edges
    padded = np.pad(arr, ((r, r), (r, r)), mode="reflect")

    # 2D integral image
    integral = np.cumsum(np.cumsum(padded, axis=0), axis=1)

    h, w = arr.shape
    # Corners for the sliding window
    top = integral[:h, :w]
    bottom = integral[size:, size:]
    left = integral[:h, size:]
    right = integral[size:, :w]

    return (bottom + top - left - right) / area


def compute_ssim(
    image_path_a: str,
    image_path_b: str,
    target_size: tuple[int, int] = (256, 256),
    window_size: int = 7,
    k1: float = 0.01,
    k2: float = 0.03,
) -> float:
    """Compute SSIM between two images as the final duplicate verification.

    SSIM measures perceptual similarity by comparing luminance, contrast,
    and structure independently.  Unlike dHash (which only captures
    coarse 8×8 edge patterns), SSIM detects subtle differences that a
    hash collision might miss — eliminating false positives.

    **Performance**:
      - Images are resized to *target_size* (default 256×256).  This is
        sufficient for SSIM accuracy and costs ~3 ms per pair when scipy
        is available, ~15 ms with the pure-numpy fallback.
      - Only called for candidate pairs that pass the Hamming pre-filter,
        so the total cost is bounded — typically 1 000–5 000 SSIM calls
        per 5 000-photo analysis.

    Formula (Wang et al. 2004):
        SSIM(x, y) = (2μxμy + C1)(2σxy + C2) / ((μx² + μy² + C1)(σx² + σy² + C2))

    Args:
        image_path_a: Path to the first image.
        image_path_b: Path to the second image.
        target_size: (width, height) to resize images to before comparison.
        window_size: Side length of the local averaging window (odd).
        k1, k2: Stabilisation constants (default 0.01, 0.03 per the paper).

    Returns:
        SSIM score in [0.0, 1.0].  1.0 = structurally identical.
        Returns 0.0 on any read/decode/processing error.
    """
    try:
        # Load both images as greyscale arrays
        with open(image_path_a, "rb") as f:
            buf_a = io.BytesIO(f.read())
        with open(image_path_b, "rb") as f:
            buf_b = io.BytesIO(f.read())

        img_a = Image.open(buf_a).convert("L").resize(target_size)
        img_b = Image.open(buf_b).convert("L").resize(target_size)

        arr_a = np.array(img_a, dtype=np.float64)
        arr_b = np.array(img_b, dtype=np.float64)
    except Exception:
        return 0.0

    # SSIM stabilisation constants
    L = 255.0
    c1 = (k1 * L) ** 2
    c2 = (k2 * L) ** 2

    if _check_scipy():
        from scipy.ndimage import uniform_filter

        mu_a = uniform_filter(arr_a, size=window_size)
        mu_b = uniform_filter(arr_b, size=window_size)

        mu_aa = mu_a * mu_a
        mu_bb = mu_b * mu_b
        mu_ab = mu_a * mu_b

        sigma_aa = uniform_filter(arr_a * arr_a, size=window_size) - mu_aa
        sigma_bb = uniform_filter(arr_b * arr_b, size=window_size) - mu_bb
        sigma_ab = uniform_filter(arr_a * arr_b, size=window_size) - mu_ab
    else:
        # Pure-numpy integral-image fallback
        mu_a = _integral_box_filter(arr_a, window_size)
        mu_b = _integral_box_filter(arr_b, window_size)

        mu_aa = mu_a * mu_a
        mu_bb = mu_b * mu_b
        mu_ab = mu_a * mu_b

        sigma_aa = _integral_box_filter(arr_a * arr_a, window_size) - mu_aa
        sigma_bb = _integral_box_filter(arr_b * arr_b, window_size) - mu_bb
        sigma_ab = _integral_box_filter(arr_a * arr_b, window_size) - mu_ab

    # SSIM map → mean
    ssim_map = ((2.0 * mu_ab + c1) * (2.0 * sigma_ab + c2)) / (
        (mu_aa + mu_bb + c1) * (sigma_aa + sigma_bb + c2)
    )

    return float(np.mean(ssim_map))
