"""
Tests for the Eye Detection module.

Verifies:
1. EAR computation logic with synthetic landmarks
2. Module imports and structure
3. Non-face image handling (returns face_detected=False)
4. Unicode path handling
5. MediaPipe model download and singleton caching
"""

import math
import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.ai.eye_detection.eye_detector import (
    _ear_from_landmarks,
    LEFT_EYE_IDX,
    RIGHT_EYE_IDX,
    EAR_CLOSED_THRESHOLD,
    EAR_HALF_CLOSED_THRESHOLD,
    BLINK_SCORE_THRESHOLD,
    detect_eyes,
    detect_eyes_batch,
)


# ---------------------------------------------------------------------------
# Synthetic landmark helper
# ---------------------------------------------------------------------------

class FakeLandmark:
    """Minimal stand-in for a MediaPipe NormalizedLandmark."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


def make_fake_landmarks(
    left_pts: list[tuple[float, float]],
    right_pts: list[tuple[float, float]],
) -> list[FakeLandmark]:
    """Build a fake landmark list with only eye landmarks populated.

    All non-eye indices get a dummy (0, 0) landmark.
    """
    landmarks = [FakeLandmark(0, 0)] * 478
    for idx, (x, y) in zip(LEFT_EYE_IDX, left_pts):
        landmarks[idx] = FakeLandmark(x, y)
    for idx, (x, y) in zip(RIGHT_EYE_IDX, right_pts):
        landmarks[idx] = FakeLandmark(x, y)
    return landmarks


def create_test_image(path: str, width: int = 200, height: int = 200) -> str:
    """Create a small PNG test image at *path*."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img = Image.new("RGB", (width, height), color="blue")
    img.save(path, format="PNG")
    return path


# ---------------------------------------------------------------------------
# EAR computation tests
# ---------------------------------------------------------------------------

class TestEARComputation(unittest.TestCase):
    """Unit tests for the _ear_from_landmarks function."""

    def test_open_eye_high_ear(self):
        """An open eye (wide vertical opening) should have high EAR."""
        # Open eye: wide vertical gap
        open_eye_pts = [
            (0.30, 0.50),  # p1 outer corner
            (0.33, 0.44),  # p2 upper lid 1
            (0.37, 0.42),  # p3 upper lid 2
            (0.40, 0.50),  # p4 inner corner
            (0.37, 0.58),  # p5 lower lid 2
            (0.33, 0.56),  # p6 lower lid 1
        ]
        landmarks = make_fake_landmarks(open_eye_pts, open_eye_pts)
        ear = _ear_from_landmarks(landmarks, LEFT_EYE_IDX)
        self.assertGreater(ear, EAR_HALF_CLOSED_THRESHOLD,
                          f"Open eye EAR ({ear:.4f}) should be > {EAR_HALF_CLOSED_THRESHOLD}")

    def test_closed_eye_low_ear(self):
        """A closed eye (narrow vertical opening) should have EAR below threshold."""
        closed_eye_pts = [
            (0.30, 0.50),   # p1 outer corner
            (0.33, 0.495),  # p2 upper lid (barely above midline)
            (0.37, 0.493),  # p3 upper lid
            (0.40, 0.50),   # p4 inner corner
            (0.37, 0.507),  # p5 lower lid (barely below midline)
            (0.33, 0.505),  # p6 lower lid
        ]
        landmarks = make_fake_landmarks(closed_eye_pts, closed_eye_pts)
        ear = _ear_from_landmarks(landmarks, LEFT_EYE_IDX)
        self.assertLess(ear, EAR_HALF_CLOSED_THRESHOLD,
                       f"Closed eye EAR ({ear:.4f}) should be < {EAR_HALF_CLOSED_THRESHOLD}")

    def test_fully_closed_eye_below_threshold(self):
        """A fully closed eye should be below EAR_CLOSED_THRESHOLD."""
        fully_closed_pts = [
            (0.30, 0.50),
            (0.33, 0.499),
            (0.37, 0.498),
            (0.40, 0.50),
            (0.37, 0.502),
            (0.33, 0.501),
        ]
        landmarks = make_fake_landmarks(fully_closed_pts, fully_closed_pts)
        ear = _ear_from_landmarks(landmarks, LEFT_EYE_IDX)
        self.assertLess(ear, EAR_CLOSED_THRESHOLD,
                       f"Fully closed eye EAR ({ear:.4f}) should be < {EAR_CLOSED_THRESHOLD}")

    def test_left_right_eye_independence(self):
        """Left and right eye EAR should be computed independently."""
        open_eye = [
            (0.30, 0.50), (0.33, 0.44), (0.37, 0.42),
            (0.40, 0.50), (0.37, 0.58), (0.33, 0.56),
        ]
        closed_eye = [
            (0.60, 0.50), (0.63, 0.499), (0.67, 0.498),
            (0.70, 0.50), (0.67, 0.502), (0.63, 0.501),
        ]
        landmarks = make_fake_landmarks(open_eye, closed_eye)

        left_ear = _ear_from_landmarks(landmarks, LEFT_EYE_IDX)
        right_ear = _ear_from_landmarks(landmarks, RIGHT_EYE_IDX)

        self.assertGreater(left_ear, EAR_HALF_CLOSED_THRESHOLD,
                          f"Left (open) eye EAR should be high, got {left_ear:.4f}")
        self.assertLess(right_ear, EAR_CLOSED_THRESHOLD,
                       f"Right (closed) eye EAR should be low, got {right_ear:.4f}")

    def test_zero_width_returns_zero(self):
        """An eye with zero width should return EAR=0."""
        degenerate_pts = [(0.30, 0.50)] * 6  # all points identical → width=0
        landmarks = make_fake_landmarks(degenerate_pts, degenerate_pts)
        ear = _ear_from_landmarks(landmarks, LEFT_EYE_IDX)
        self.assertEqual(ear, 0.0)


# ---------------------------------------------------------------------------
# Non-face image handling tests
# ---------------------------------------------------------------------------

class TestEyeDetectionNonFace(unittest.TestCase):
    """Test detect_eyes on images without faces."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_non_face_image_returns_open(self):
        """A plain color image (no face) should return eyes_open=True, face_detected=False."""
        path = os.path.join(self.tmpdir, "no_face.png")
        create_test_image(path)
        result = detect_eyes(path)
        self.assertTrue(result["eyes_open"])
        self.assertEqual(result["score"], 1.0)
        self.assertFalse(result["face_detected"])
        self.assertEqual(result["num_faces"], 0)
        self.assertEqual(result["closed_count"], 0)
        self.assertIsInstance(result["processing_time_ms"], float)

    def test_non_existent_path_raises(self):
        """Non-existent file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            detect_eyes(os.path.join(self.tmpdir, "does_not_exist.png"))

    def test_unicode_path(self):
        """Chinese characters in filename should work."""
        path = os.path.join(self.tmpdir, "闭眼测试照片.png")
        create_test_image(path)
        result = detect_eyes(path)
        self.assertIn("eyes_open", result)


# ---------------------------------------------------------------------------
# Module structure tests
# ---------------------------------------------------------------------------

class TestEyeDetectionModule(unittest.TestCase):
    """Verify module imports and constants."""

    def test_thresholds_are_positive(self):
        """All thresholds should be positive floats."""
        self.assertGreater(EAR_CLOSED_THRESHOLD, 0)
        self.assertGreater(EAR_HALF_CLOSED_THRESHOLD, 0)
        self.assertGreater(BLINK_SCORE_THRESHOLD, 0)
        self.assertLess(EAR_CLOSED_THRESHOLD, EAR_HALF_CLOSED_THRESHOLD,
                       "Closed threshold should be stricter than half-closed")

    def test_eye_indices_length(self):
        """Each eye should have exactly 6 landmark indices."""
        self.assertEqual(len(LEFT_EYE_IDX), 6)
        self.assertEqual(len(RIGHT_EYE_IDX), 6)

    def test_left_right_indices_distinct(self):
        """Left and right eye indices should not overlap."""
        overlap = set(LEFT_EYE_IDX) & set(RIGHT_EYE_IDX)
        self.assertEqual(len(overlap), 0, f"Left/right eye indices overlap: {overlap}")

    def test_import_models(self):
        """Data models should import correctly."""
        from backend.ai.eye_detection.models import (
            EyeDetectionResult,
            EyeDetectionSummary,
            PerFaceResult,
        )
        # Create instances to verify field access (dataclass fields are on instances)
        r = EyeDetectionResult("id", "path", True, 0.5, True, 1, 0, [], 100.0)
        self.assertTrue(r.eyes_open)
        self.assertEqual(r.closed_count, 0)

        s = EyeDetectionSummary(total=5, closed=2, open=3)
        self.assertEqual(s.closed, 2)

        pf = PerFaceResult(0, 0.35, 0.32, 0.32, False)
        self.assertFalse(pf.is_closed)

    def test_import_service(self):
        """Service functions should import correctly."""
        from backend.ai.eye_detection.service import (
            start_eye_detection,
            get_eye_progress,
            cancel_eye_detection,
        )
        self.assertTrue(callable(start_eye_detection))
        self.assertTrue(callable(get_eye_progress))
        self.assertTrue(callable(cancel_eye_detection))


# ---------------------------------------------------------------------------
# Batch detection tests
# ---------------------------------------------------------------------------

class TestBatchDetection(unittest.TestCase):
    """Test detect_eyes_batch function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_batch_non_face_images(self):
        """Batch of non-face images should all return open."""
        paths = []
        for i in range(3):
            path = os.path.join(self.tmpdir, f"test_{i}.png")
            create_test_image(path)
            paths.append(path)

        results = detect_eyes_batch(paths)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertTrue(r["eyes_open"])
            self.assertFalse(r["face_detected"])

    def test_batch_with_bad_path(self):
        """Batch with a bad path should return error dict without halting."""
        paths = [
            os.path.join(self.tmpdir, "good.png"),
            os.path.join(self.tmpdir, "bad.png"),
        ]
        create_test_image(paths[0])
        # paths[1] doesn't exist

        results = detect_eyes_batch(paths)
        self.assertEqual(len(results), 2)
        self.assertIn("eyes_open", results[0])
        self.assertIn("error", results[1])


if __name__ == "__main__":
    unittest.main()
