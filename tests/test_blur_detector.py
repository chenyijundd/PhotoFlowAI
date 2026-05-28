"""
Tests for the Blur Detector module.

Verifies that calculate_blur works with Unicode file paths
(Chinese, Japanese, spaces, emoji) on all platforms.
"""

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


if __name__ == "__main__":
    unittest.main()
