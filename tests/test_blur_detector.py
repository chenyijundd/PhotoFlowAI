"""
Tests for the Blur Detector module.

Verifies that calculate_blur works with Unicode file paths
(Chinese, Japanese, spaces, emoji) on all platforms.
"""

import json
import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.ai.blur_detector.detector import calculate_blur, BLUR_THRESHOLD


def create_test_image(path: str, width: int = 200, height: int = 200) -> str:
    """Create a small PNG test image at *path*."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new("RGB", (width, height), color="blue")
    img.save(path, format="PNG")
    return path


class TestBlurDetector(unittest.TestCase):
    """Test that calculate_blur handles various path encodings."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _test_path(self, filename: str):
        """Helper: create an image at *filename* and run calculate_blur on it."""
        filepath = os.path.join(self.tmpdir, filename)
        create_test_image(filepath)
        score, is_blur = calculate_blur(filepath)
        # A solid-blue PNG should be sharp (high Laplacian variance expected)
        self.assertIsInstance(score, float)
        self.assertIn(is_blur, (0, 1))

    def test_ascii_path(self):
        """Baseline: plain ASCII path works."""
        self._test_path("test_image.png")

    def test_chinese_path(self):
        """Chinese characters in filename."""
        self._test_path("生成模糊人像照片阈值100.png")

    def test_japanese_path(self):
        """Japanese characters in filename."""
        self._test_path("ぼやけた写真.png")

    def test_space_path(self):
        """Spaces in filename."""
        self._test_path("test image with spaces.png")

    def test_emoji_path(self):
        """Emoji in filename."""
        self._test_path("📷😊 blur test.png")

    def test_mixed_unicode_path(self):
        """Mixed Chinese, Japanese, spaces, and emoji."""
        self._test_path("测试 テスト 😊 blur.png")

    def test_non_existent_path(self):
        """Non-existent file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            calculate_blur(os.path.join(self.tmpdir, "does_not_exist.png"))

    def test_invalid_file(self):
        """File that exists but is not an image raises FileNotFoundError."""
        bad_path = os.path.join(self.tmpdir, "not_an_image.txt")
        with open(bad_path, "w") as f:
            f.write("this is not image data")
        with self.assertRaises(FileNotFoundError):
            calculate_blur(bad_path)

    def test_blur_threshold_sharp(self):
        """A high-contrast synthetic image scores above threshold."""
        path = os.path.join(self.tmpdir, "sharp.png")
        # Create a checkerboard pattern (high contrast → high Laplacian variance)
        img = Image.new("L", (200, 200), color=128)
        for y in range(0, 200, 10):
            for x in range(0, 200, 10):
                if (x // 10 + y // 10) % 2 == 0:
                    for dy in range(10):
                        for dx in range(10):
                            img.putpixel((x + dx, y + dy), 255)
        img = img.convert("RGB")
        img.save(path, format="PNG")
        score, is_blur = calculate_blur(path)
        self.assertGreater(score, BLUR_THRESHOLD,
                           f"Sharp checkerboard should score above {BLUR_THRESHOLD}, got {score}")
        self.assertEqual(is_blur, 0)


# ==============================================================================
# V2 Blur Detector Cache Tests (改进建议 §5 — patch_scores 缓存)
# ==============================================================================

from backend.ai.blur_detector_v2.detector import (
    build_patch_scores_cache,
    judge_from_cache,
    BLUR_THRESHOLD,
    WEIGHTED_WEIGHT,
    TOP_MEDIAN_WEIGHT,
)
from database.repository import PhotoRepository
from database.models import PhotoRecord


class TestPatchScoresCache(unittest.TestCase):
    """Unit tests for build_patch_scores_cache and judge_from_cache."""

    def test_build_cache_produces_valid_json(self):
        """Cache JSON should be valid and contain w, t, s keys."""
        patch_scores = [10.0, 20.0, 30.0, 40.0]
        weighted = 25.0
        top_median = 35.0
        result = build_patch_scores_cache(patch_scores, weighted, top_median)
        data = json.loads(result)
        self.assertIn("w", data)
        self.assertIn("t", data)
        self.assertIn("s", data)
        self.assertAlmostEqual(data["w"], 25.0)
        self.assertAlmostEqual(data["t"], 35.0)
        self.assertEqual(len(data["s"]), 4)

    def test_build_cache_rounds_values(self):
        """Cache values should be rounded to 4 decimal places."""
        patch_scores = [1.0 / 3.0]
        weighted = 1.0 / 3.0
        top_median = 2.0 / 3.0
        result = build_patch_scores_cache(patch_scores, weighted, top_median)
        data = json.loads(result)
        # 1/3 ≈ 0.3333 (rounded to 4 places)
        self.assertAlmostEqual(data["w"], 0.3333, places=4)

    def test_judge_from_cache_default_threshold(self):
        """Re-judge correctly reproduces the composite score."""
        patch_scores = [40.0] * 16  # all sharp
        weighted = 40.0
        top_median = 40.0
        cache = build_patch_scores_cache(patch_scores, weighted, top_median)

        # Composite: 40 * 0.4 + 40 * 0.6 = 40
        score, is_blur = judge_from_cache(cache, BLUR_THRESHOLD)
        expected = weighted * WEIGHTED_WEIGHT + top_median * TOP_MEDIAN_WEIGHT
        self.assertAlmostEqual(score, expected)
        self.assertEqual(is_blur, 0)  # 40 > 25, not blurry

    def test_judge_from_cache_blurry_with_low_scores(self):
        """Low scores below threshold → classified as blurry."""
        patch_scores = [5.0] * 16
        weighted = 5.0
        top_median = 5.0
        cache = build_patch_scores_cache(patch_scores, weighted, top_median)

        score, is_blur = judge_from_cache(cache, BLUR_THRESHOLD)
        self.assertEqual(is_blur, 1)  # 5 < 25, blurry

    def test_judge_from_cache_threshold_change(self):
        """Changing threshold flips the blur verdict."""
        # Scores right at 50 — above default threshold (25) but below 60
        patch_scores = [50.0] * 16
        weighted = 50.0
        top_median = 50.0
        cache = build_patch_scores_cache(patch_scores, weighted, top_median)

        # Composite = 50 * 0.4 + 50 * 0.6 = 50
        _, is_blur_25 = judge_from_cache(cache, 25.0)
        self.assertEqual(is_blur_25, 0, "Score 50 > threshold 25 → NOT blurry")

        _, is_blur_60 = judge_from_cache(cache, 60.0)
        self.assertEqual(is_blur_60, 1, "Score 50 < threshold 60 → blurry")

    def test_judge_from_cache_very_high_threshold(self):
        """With a very high threshold, even sharp photos become 'blurry'."""
        patch_scores = [80.0] * 16
        weighted = 80.0
        top_median = 80.0
        cache = build_patch_scores_cache(patch_scores, weighted, top_median)

        # Composite = 80
        _, is_blur = judge_from_cache(cache, 100.0)
        self.assertEqual(is_blur, 1, "Score 80 < threshold 100 → blurry")

    def test_judge_from_cache_malformed_json_raises(self):
        """Corrupt cache data should raise ValueError."""
        with self.assertRaises((ValueError, json.JSONDecodeError, KeyError)):
            judge_from_cache("this is not json", BLUR_THRESHOLD)

        with self.assertRaises((ValueError, json.JSONDecodeError, KeyError)):
            judge_from_cache("{}", BLUR_THRESHOLD)  # missing keys

        with self.assertRaises((ValueError, json.JSONDecodeError, KeyError)):
            judge_from_cache('{"w": 1}', BLUR_THRESHOLD)  # missing 't'

    def test_judge_from_cache_returns_consistent_score(self):
        """Multiple calls with same inputs return identical results."""
        patch_scores = [12.5, 38.2, 45.1, 17.8] * 4  # 16 patches
        weighted = 28.4
        top_median = 36.75
        cache = build_patch_scores_cache(patch_scores, weighted, top_median)

        score1, blur1 = judge_from_cache(cache, 30.0)
        score2, blur2 = judge_from_cache(cache, 30.0)
        self.assertEqual(score1, score2)
        self.assertEqual(blur1, blur2)


class TestPatchScoresRepository(unittest.TestCase):
    """Integration tests: store and retrieve patch_scores via PhotoRepository."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.repo = PhotoRepository(db_path=self.db_path)
        self.repo.init_database()

    def tearDown(self):
        import gc
        gc.collect()
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except PermissionError:
                pass

    def _insert_test_photo(self, image_id: str = "cache001") -> None:
        """Insert a minimal photo record for testing."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        photo = PhotoRecord(
            image_id=image_id,
            file_name="test.jpg",
            file_path="/tmp/test.jpg",
            width=800,
            height=600,
            file_size=1024,
            created_at=now,
            updated_at=now,
        )
        self.repo.insert_photo(photo)

    def test_store_and_retrieve_cache(self):
        """patch_scores should round-trip through the database."""
        self._insert_test_photo("cache001")
        cache = build_patch_scores_cache([10.0] * 16, 20.0, 30.0)
        self.repo.update_patch_scores("cache001", cache)

        photo = self.repo.get_photo_by_id("cache001")
        self.assertIsNotNone(photo.patch_scores)
        data = json.loads(photo.patch_scores)
        self.assertAlmostEqual(data["w"], 20.0)
        self.assertAlmostEqual(data["t"], 30.0)

    def test_clear_cache(self):
        """Setting patch_scores to None should clear the column."""
        self._insert_test_photo("cache002")
        cache = build_patch_scores_cache([10.0] * 16, 20.0, 30.0)
        self.repo.update_patch_scores("cache002", cache)
        self.repo.update_patch_scores("cache002", None)

        photo = self.repo.get_photo_by_id("cache002")
        self.assertIsNone(photo.patch_scores)

    def test_cache_independent_of_blur_status(self):
        """patch_scores are independent of the blur threshold/verdict."""
        self._insert_test_photo("cache003")
        cache = build_patch_scores_cache([50.0] * 16, 50.0, 50.0)
        self.repo.update_patch_scores("cache003", cache)

        # Update blur status with different thresholds — cache should persist
        self.repo.update_blur_status("cache003", is_blur=0, blur_score=50.0)
        photo = self.repo.get_photo_by_id("cache003")
        self.assertIsNotNone(photo.patch_scores, "Cache should survive blur_status updates")

        self.repo.update_blur_status("cache003", is_blur=1, blur_score=50.0)
        photo = self.repo.get_photo_by_id("cache003")
        self.assertIsNotNone(photo.patch_scores, "Cache should survive re-analysis")

    def test_no_cache_for_new_photo(self):
        """Newly inserted photos should have no patch_scores."""
        self._insert_test_photo("cache004")
        photo = self.repo.get_photo_by_id("cache004")
        self.assertIsNone(photo.patch_scores)




if __name__ == "__main__":
    unittest.main()
