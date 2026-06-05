"""
PhotoFlow AI - Eye Detection Module (Real Implementation)

Uses MediaPipe Face Landmarker (Tasks API) to detect faces and
evaluate eye state via two complementary methods:

1. **BlendShapes** — MediaPipe's built-in ``EYE_BLINK_LEFT`` /
   ``EYE_BLINK_RIGHT`` scores (0-1).  High score = eye closed.
   This is the primary signal.

2. **Eye Aspect Ratio (EAR)** — computed from 6 periocular landmarks
   per eye.  Serves as a cross-check.

A photo is flagged as "eyes not open" if **any** detected face
has an eye-blink score above the threshold OR EAR below the
half-closed threshold.

Algorithm reference:
    Soukupová & Čech, 2016 — "Real-Time Eye Blink Detection
    using Facial Landmarks"

CLI usage:
    python -m backend.ai.eye_detection.cli --input ./photos
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
import urllib.request

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

MAX_IMAGE_DIM: int = 1024
"""
Images are downscaled so the long edge does not exceed this many pixels
before running MediaPipe.  Face detection accuracy is virtually unchanged
at 1024 px while inference time drops by 10–30× compared to a 24 MP original.

Set to *None* to disable downscaling (use full-resolution images).
"""

# ---------------------------------------------------------------------------
# MediaPipe model download
# ---------------------------------------------------------------------------

_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_MODEL_FILENAME = "face_landmarker_v2_with_blendshapes.task"
_MODEL_PATH = os.path.join(_MODEL_DIR, _MODEL_FILENAME)
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/latest/"
    "face_landmarker.task"
)

# ---------------------------------------------------------------------------
# MediaPipe Face Mesh — eye landmark indices (468-point topology)
# ---------------------------------------------------------------------------
# Left eye:  33 (outer) → 160, 158 (upper) → 133 (inner) → 153, 144 (lower)
# Right eye: 362 (outer) → 385, 387 (upper) → 263 (inner) → 373, 380 (lower)
LEFT_EYE_IDX: tuple[int, ...] = (33, 160, 158, 133, 153, 144)
RIGHT_EYE_IDX: tuple[int, ...] = (362, 385, 387, 263, 373, 380)

# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------

BLINK_SCORE_THRESHOLD: float = 0.55
"""
MediaPipe EYE_BLINK blendshape score above this **AND** EAR below
EAR_HALF_CLOSED_THRESHOLD → eye is flagged as closed.
Both signals must agree (AND logic) to minimise false positives
on naturally narrow eyes (Asian eye shapes, squinting from sunlight, smiling).
"""

EAR_CLOSED_THRESHOLD: float = 0.18
"""
EAR below this → eye is fully closed (Soukupová & Čech, 2016).
Used as the fallback when blendshapes are unavailable.
"""

EAR_HALF_CLOSED_THRESHOLD: float = 0.20
"""
EAR below this → candidate for closed-eye (must be confirmed by blendshape).
Set at 0.20 to catch partial blinks while requiring AND logic for precision.
"""

# ---------------------------------------------------------------------------
# Thread-local MediaPipe FaceLandmarker
# ---------------------------------------------------------------------------
# MediaPipe's Python FaceLandmarker is NOT thread-safe, so we cannot share
# a single instance across threads.  thread.local() gives each worker thread
# its own instance — created lazily on first use.
# ---------------------------------------------------------------------------

_thread_local = threading.local()


def _ensure_model() -> str:
    """Download the FaceLandmarker model if not already present.

    Returns the path to the model file.
    """
    os.makedirs(_MODEL_DIR, exist_ok=True)
    if not os.path.isfile(_MODEL_PATH):
        logger.info("Downloading FaceLandmarker model (~5 MB)...")
        print(f"[eye_detection] Downloading FaceLandmarker model to {_MODEL_PATH} ...")
        try:
            urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
            logger.info("Model downloaded: %s", _MODEL_PATH)
        except Exception as exc:
            logger.error("Failed to download model: %s", exc)
            raise RuntimeError(
                f"Failed to download FaceLandmarker model from {_MODEL_URL}\n"
                f"Please download it manually and place it at: {_MODEL_PATH}\n"
                f"Error: {exc}"
            )
    return _MODEL_PATH


def _get_face_landmarker():
    """Return a **thread-local** MediaPipe FaceLandmarker instance.

    Each worker thread gets its own instance (MediaPipe's Python API
    is not thread-safe for concurrent access to a single landmarker).
    The model is downloaded once; only the graph setup is per-thread.

    Blendshapes are enabled so we get EYE_BLINK_LEFT / EYE_BLINK_RIGHT
    scores.
    """
    if not hasattr(_thread_local, "landmarker") or _thread_local.landmarker is None:
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core import base_options as mp_base_options

        model_path = _ensure_model()

        base_opts = mp_base_options.BaseOptions(model_asset_path=model_path)
        opts = vision.FaceLandmarkerOptions(
            base_options=base_opts,
            num_faces=10,
            min_face_detection_confidence=0.5,
            output_face_blendshapes=True,  # ← EYE_BLINK scores
        )
        _thread_local.landmarker = vision.FaceLandmarker.create_from_options(opts)
    return _thread_local.landmarker


# ---------------------------------------------------------------------------
# EAR computation (cross-check against blendshapes)
# ---------------------------------------------------------------------------


def _ear_from_landmarks(
    landmarks: list,
    eye_indices: tuple[int, ...],
) -> float:
    """Compute Eye Aspect Ratio from a list of NormalizedLandmark objects.

    Args:
        landmarks: List of NormalizedLandmark for one face (478 points).
        eye_indices: The 6 landmark indices for the target eye.

    Returns:
        EAR value (0.0–~0.5).  Lower = more closed.
    """
    pts: list[tuple[float, float]] = []
    for idx in eye_indices:
        lm = landmarks[idx]
        pts.append((lm.x, lm.y))

    v1 = math.dist(pts[1], pts[5])  # p2 ↔ p6
    v2 = math.dist(pts[2], pts[4])  # p3 ↔ p5
    h = math.dist(pts[0], pts[3])   # p1 ↔ p4

    if h < 1e-6:
        return 0.0
    return (v1 + v2) / (2.0 * h)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_eyes(
    image_path: str,
    max_dim: int | None = MAX_IMAGE_DIM,
    blink_score_threshold: float | None = None,
    ear_closed_threshold: float | None = None,
    ear_half_closed_threshold: float | None = None,
) -> dict:
    """Analyse a single image for eye state.

    Detects all faces, evaluates eye state via blendshapes + EAR,
    and returns a detailed result dictionary.

    A photo is flagged as "eyes not open" if **any** detected face
    has BOTH:
    - EAR < EAR_HALF_CLOSED_THRESHOLD (eye shape appears narrow), AND
    - Blink score > BLINK_SCORE_THRESHOLD (blendshape confirms blink)

    If blendshapes are unavailable, falls back to EAR < EAR_CLOSED_THRESHOLD
    alone (more conservative, only catches fully closed eyes).

    Args:
        image_path: Absolute path to the image file.
        max_dim: If set, the image is downscaled so its long edge does not
            exceed this many pixels before MediaPipe inference.  This
            dramatically speeds up face detection with negligible accuracy
            loss.  Default: ``MAX_IMAGE_DIM`` (1024).  Pass ``None`` to
            use the original resolution.
        blink_score_threshold: Override for ``BLINK_SCORE_THRESHOLD``.
        ear_closed_threshold: Override for ``EAR_CLOSED_THRESHOLD``.
        ear_half_closed_threshold: Override for ``EAR_HALF_CLOSED_THRESHOLD``.

    Returns:
        A dict with keys: file, eyes_open, score, face_detected,
        num_faces, closed_count, per_face, processing_time_ms.

    Raises:
        FileNotFoundError: If the image cannot be decoded.
    """
    _blink = blink_score_threshold if blink_score_threshold is not None else BLINK_SCORE_THRESHOLD
    _ear_closed = ear_closed_threshold if ear_closed_threshold is not None else EAR_CLOSED_THRESHOLD
    _ear_half = ear_half_closed_threshold if ear_half_closed_threshold is not None else EAR_HALF_CLOSED_THRESHOLD
    t0 = time.perf_counter()

    # ---- Read image (OpenCV → PIL fallback for HEIC etc.) ----
    from backend.raw_preview.extractor import read_image_bgr
    img = read_image_bgr(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot decode image: {image_path}")

    h, w = img.shape[:2]

    # ---- Optional downscale for faster inference ----
    if max_dim is not None:
        long_edge = max(h, w)
        if long_edge > max_dim:
            scale = max_dim / long_edge
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # ---- MediaPipe expects RGB ----
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # ---- Run Face Landmarker ----
    import mediapipe as mp

    landmarker = _get_face_landmarker()

    # Create MediaPipe Image
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    # Run detection (the landmarker was configured with blendshapes enabled)
    result = landmarker.detect(mp_image)

    elapsed = (time.perf_counter() - t0) * 1000.0

    # ---- No faces → treat as "eyes open" (not a portrait) ----
    if not result.face_landmarks:
        return {
            "file": image_path,
            "eyes_open": True,
            "score": 1.0,
            "face_detected": False,
            "num_faces": 0,
            "closed_count": 0,
            "per_face": [],
            "processing_time_ms": round(elapsed, 1),
        }

    # ---- Evaluate each face ----
    all_min_ears: list[float] = []
    closed_count = 0
    per_face: list[dict] = []

    for i, face_landmarks in enumerate(result.face_landmarks):
        left_ear = _ear_from_landmarks(face_landmarks, LEFT_EYE_IDX)
        right_ear = _ear_from_landmarks(face_landmarks, RIGHT_EYE_IDX)
        min_ear = min(left_ear, right_ear)

        # Determine if eyes are closed
        # Primary: EAR threshold
        ear_says_closed = min_ear < _ear_half

        # Blendshapes cross-check (if available)
        blink_left = None
        blink_right = None
        blend_says_closed = False
        has_blendshapes = False
        if result.face_blendshapes and i < len(result.face_blendshapes):
            blends = result.face_blendshapes[i]
            for b in blends:
                if b.index == 9:   # EYE_BLINK_LEFT
                    blink_left = b.score
                elif b.index == 10:  # EYE_BLINK_RIGHT
                    blink_right = b.score
            if blink_left is not None and blink_right is not None:
                has_blendshapes = True
                blend_says_closed = (
                    blink_left > _blink
                    or blink_right > _blink
                )

        # Final verdict: AND logic — both signals must agree
        if has_blendshapes:
            is_closed = ear_says_closed and blend_says_closed
        else:
            # Fallback: no blendshapes available → use stricter EAR-only check
            is_closed = min_ear < _ear_closed
        if is_closed:
            closed_count += 1

        all_min_ears.append(min_ear)
        per_face.append({
            "face_index": i,
            "left_ear": round(left_ear, 4),
            "right_ear": round(right_ear, 4),
            "min_ear": round(min_ear, 4),
            "blink_left": round(blink_left, 4) if blink_left is not None else None,
            "blink_right": round(blink_right, 4) if blink_right is not None else None,
            "ear_closed": ear_says_closed,
            "blend_closed": blend_says_closed,
            "is_closed": is_closed,
        })

    # ---- Overall verdict ----
    overall_min_ear = min(all_min_ears) if all_min_ears else 1.0
    eyes_open = closed_count == 0

    return {
        "file": image_path,
        "eyes_open": eyes_open,
        "score": round(overall_min_ear, 4),
        "face_detected": True,
        "num_faces": len(result.face_landmarks),
        "closed_count": closed_count,
        "per_face": per_face,
        "processing_time_ms": round(elapsed, 1),
    }


def detect_eyes_batch(
    image_paths: list[str],
    max_dim: int | None = MAX_IMAGE_DIM,
    blink_score_threshold: float | None = None,
    ear_closed_threshold: float | None = None,
    ear_half_closed_threshold: float | None = None,
) -> list[dict]:
    """Run ``detect_eyes`` on every path in *image_paths*.

    Returns a list of result dicts in the same order.
    Errors are caught per-image and returned as dicts with an
    ``"error"`` key so the batch never halts.

    Args:
        image_paths: List of absolute image paths.
        max_dim: Passed through to ``detect_eyes``.  Default: 1024.
        blink_score_threshold: Passed through to ``detect_eyes``.
        ear_closed_threshold: Passed through to ``detect_eyes``.
        ear_half_closed_threshold: Passed through to ``detect_eyes``.
    """
    results: list[dict] = []
    for path in image_paths:
        try:
            results.append(detect_eyes(
                path, max_dim=max_dim,
                blink_score_threshold=blink_score_threshold,
                ear_closed_threshold=ear_closed_threshold,
                ear_half_closed_threshold=ear_half_closed_threshold,
            ))
        except Exception as exc:
            results.append({
                "file": path,
                "error": str(exc),
            })
    return results
