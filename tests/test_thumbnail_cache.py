"""
Tests for the Thumbnail Cache module.

Uses dynamically generated test images (via Pillow) to verify:
- Single thumbnail generation
- Aspect ratio preservation
- Cache hit (skip re-generation)
- Corrupted file handling
- Batch directory processing
- CLI output
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.thumbnail_cache.models import ThumbnailResult
from backend.thumbnail_cache.utils import (
    ensure_cache_dir,
    thumbnail_path_for,
    thumbnail_exists,
    generate_single_thumbnail,
)
from backend.thumbnail_cache.cache_manager import CacheManager


def create_test_image(
    path: str, width: int = 800, height: int = 600, fmt: str = "JPEG"
) -> str:
    """Generate a small test image. Returns the path."""
    img = Image.new("RGB", (width, height), color="blue")
    img.save(path, format=fmt)
    return path


def rmtree(path: str) -> None:
    """Remove a directory tree safely."""
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)


class TestThumbnailResult(unittest.TestCase):
    """Tests for ThumbnailResult data model."""

    def test_to_dict_keys(self):
        r = ThumbnailResult(
            image_id="abc123",
            source_path="/a.jpg",
            thumbnail_path="/thumb/abc123.jpg",
            success=True,
        )
        d = r.to_dict()
        self.assertIn("image_id", d)
        self.assertIn("source_path", d)
        self.assertIn("thumbnail_path", d)
        self.assertIn("success", d)

    def test_failure_result(self):
        r = ThumbnailResult(
            image_id="abc123",
            source_path="/missing.jpg",
            success=False,
            error="File not found",
        )
        self.assertFalse(r.success)
        self.assertIsNotNone(r.error)


class TestThumbnailPathUtils(unittest.TestCase):
    """Tests for path and cache checking utilities."""

    def setUp(self):
        self.cache_dir = tempfile.mkdtemp()

    def tearDown(self):
        rmtree(self.cache_dir)

    def test_ensure_cache_dir_creates(self):
        nested = os.path.join(self.cache_dir, "a", "b", "c")
        result = ensure_cache_dir(nested)
        self.assertEqual(result, nested)
        self.assertTrue(os.path.isdir(nested))

    def test_thumbnail_path_ends_with_jpg(self):
        path = thumbnail_path_for("abc123", self.cache_dir)
        self.assertTrue(path.endswith(".jpg"))

    def test_thumbnail_path_contains_id(self):
        path = thumbnail_path_for("abc123", self.cache_dir)
        self.assertIn("abc123", path)

    def test_thumbnail_exists_false_when_missing(self):
        self.assertFalse(thumbnail_exists("nonexistent", self.cache_dir))

    def test_thumbnail_exists_true_when_present(self):
        path = thumbnail_path_for("exists", self.cache_dir)
        Path(path).touch()
        self.assertTrue(thumbnail_exists("exists", self.cache_dir))


class TestGenerateSingleThumbnail(unittest.TestCase):
    """Tests for single thumbnail generation."""

    def setUp(self):
        self.img_dir = tempfile.mkdtemp()
        self.cache_dir = tempfile.mkdtemp()

    def tearDown(self):
        rmtree(self.img_dir)
        rmtree(self.cache_dir)

    def _make_image(
        self, name: str = "src.jpg", w: int = 800, h: int = 600
    ) -> str:
        path = os.path.join(self.img_dir, name)
        create_test_image(path, w, h)
        return path

    def test_generates_thumbnail_file(self):
        src = self._make_image()
        result = generate_single_thumbnail(src, "img001", self.cache_dir)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.thumbnail_path)
        self.assertTrue(os.path.isfile(result.thumbnail_path))

    def test_thumbnail_max_size_200(self):
        src = self._make_image(w=3000, h=2000)
        result = generate_single_thumbnail(src, "size_test", self.cache_dir)
        with Image.open(result.thumbnail_path) as thumb:
            w, h = thumb.size
            self.assertLessEqual(max(w, h), 200)
            self.assertAlmostEqual(w / h, 3 / 2, delta=0.02)

    def test_maintains_aspect_ratio_portrait(self):
        src = self._make_image(w=1000, h=2000)
        result = generate_single_thumbnail(src, "portrait", self.cache_dir)
        with Image.open(result.thumbnail_path) as thumb:
            w, h = thumb.size
            self.assertLessEqual(max(w, h), 200)
            self.assertAlmostEqual(w / h, 1 / 2, delta=0.02)

    def test_maintains_aspect_ratio_square(self):
        src = self._make_image(w=1000, h=1000)
        result = generate_single_thumbnail(src, "square", self.cache_dir)
        with Image.open(result.thumbnail_path) as thumb:
            w, h = thumb.size
            self.assertLessEqual(max(w, h), 200)
            self.assertAlmostEqual(w / h, 1.0, delta=0.02)

    def test_no_crop(self):
        """Verify that all original content area is preserved in thumbnail."""
        src = self._make_image(w=400, h=200)
        result = generate_single_thumbnail(src, "nocrop", self.cache_dir)
        with Image.open(result.thumbnail_path) as thumb:
            w, h = thumb.size
            self.assertLessEqual(w, 200)
            self.assertLessEqual(h, 200)
            if w == 200:
                self.assertEqual(h, 100)
            elif h == 200:
                self.assertEqual(w, 400)

    def test_skip_if_cached(self):
        src = self._make_image()
        r1 = generate_single_thumbnail(src, "cached", self.cache_dir)
        r2 = generate_single_thumbnail(src, "cached", self.cache_dir)
        self.assertTrue(r2.success)
        self.assertEqual(r2.thumbnail_path, r1.thumbnail_path)

    def test_corrupted_file_does_not_crash(self):
        bad_path = os.path.join(self.img_dir, "bad.jpg")
        with open(bad_path, "wb") as f:
            f.write(b"\x00\x00\x00\x00\x00\x00\x00\x00")
        result = generate_single_thumbnail(bad_path, "bad", self.cache_dir)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_missing_file_does_not_crash(self):
        result = generate_single_thumbnail(
            "/nonexistent/path.jpg", "missing", self.cache_dir
        )
        self.assertFalse(result.success)

    def test_rgba_to_rgb_conversion(self):
        """RGBA images should be converted to RGB for JPEG output."""
        path = os.path.join(self.img_dir, "rgba.png")
        img = Image.new("RGBA", (100, 200), (255, 0, 0, 128))
        img.save(path, format="PNG")
        result = generate_single_thumbnail(path, "rgba_test", self.cache_dir)
        self.assertTrue(result.success)
        with Image.open(result.thumbnail_path) as thumb:
            self.assertEqual(thumb.mode, "RGB")

    def test_output_is_jpeg(self):
        src = self._make_image(w=400, h=300)
        result = generate_single_thumbnail(src, "fmt_test", self.cache_dir)
        with Image.open(result.thumbnail_path) as thumb:
            self.assertEqual(thumb.format, "JPEG")


class TestCacheManager(unittest.TestCase):
    """Tests for CacheManager batch processing."""

    def setUp(self):
        self.img_dir = tempfile.mkdtemp()
        self.cache_dir = tempfile.mkdtemp()
        self.manager = CacheManager(cache_dir=self.cache_dir)

    def tearDown(self):
        rmtree(self.img_dir)
        rmtree(self.cache_dir)

    def test_process_image_generates_thumbnail(self):
        src = os.path.join(self.img_dir, "source.jpg")
        create_test_image(src, 800, 600)
        result = self.manager.process_image(src, "test_img")
        self.assertTrue(result.success)
        self.assertTrue(os.path.isfile(result.thumbnail_path))

    def test_summary_counts(self):
        src1 = os.path.join(self.img_dir, "a.jpg")
        src2 = os.path.join(self.img_dir, "b.jpg")
        create_test_image(src1, 100, 100)
        create_test_image(src2, 200, 200)

        self.manager.process_image(src1, "id_a")
        self.manager.process_image(src2, "id_b")

        summary = self.manager.summary
        self.assertEqual(summary["generated"], 2)
        self.assertEqual(summary["cached"], 0)
        self.assertEqual(summary["errors"], 0)

    def test_cached_count_increments_on_repeat(self):
        src = os.path.join(self.img_dir, "repeat.jpg")
        create_test_image(src, 100, 100)
        self.manager.process_image(src, "repeat_id")
        self.manager.process_image(src, "repeat_id")
        summary = self.manager.summary
        self.assertEqual(summary["cached"], 1)
        self.assertEqual(summary["generated"], 1)

    def test_error_count_for_corrupted(self):
        bad = os.path.join(self.img_dir, "bad.jpg")
        with open(bad, "wb") as f:
            f.write(b"\x00")
        self.manager.process_image(bad, "bad_id")
        summary = self.manager.summary
        self.assertEqual(summary["errors"], 1)

    def test_process_directory_with_temp_images(self):
        img_dir = tempfile.mkdtemp()
        try:
            create_test_image(os.path.join(img_dir, "a.jpg"), 100, 100)
            create_test_image(os.path.join(img_dir, "b.png"), 200, 200, fmt="PNG")
            sub_dir = os.path.join(img_dir, "sub")
            os.makedirs(sub_dir)
            create_test_image(os.path.join(sub_dir, "c.jpeg"), 300, 300)

            results = self.manager.process_directory(img_dir)
            self.assertEqual(len(results), 3)
            for r in results:
                self.assertTrue(r.success)

            summary = self.manager.summary
            self.assertEqual(summary["generated"], 3)
        finally:
            rmtree(img_dir)


class TestCLI(unittest.TestCase):
    """Tests for CLI entry point."""

    def setUp(self):
        self.img_dir = tempfile.mkdtemp()
        self.cache_dir = tempfile.mkdtemp()
        create_test_image(os.path.join(self.img_dir, "photo1.jpg"), 400, 300)
        create_test_image(os.path.join(self.img_dir, "photo2.png"), 500, 500, fmt="PNG")

    def tearDown(self):
        rmtree(self.img_dir)
        rmtree(self.cache_dir)

    def _run_cli(self, *extra_args) -> dict:
        cmd = [
            sys.executable,
            "-m",
            "backend.thumbnail_cache.thumbnail_generator",
            "--input",
            self.img_dir,
            "--cache-dir",
            self.cache_dir,
            *extra_args,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        return json.loads(result.stdout)

    def test_cli_returns_summary_and_results(self):
        data = self._run_cli()
        self.assertIn("summary", data)
        self.assertIn("results", data)
        self.assertEqual(data["summary"]["generated"], 2)

    def test_cli_cached_on_second_run(self):
        self._run_cli()
        data = self._run_cli()
        self.assertEqual(data["summary"]["generated"], 0)
        self.assertEqual(data["summary"]["cached"], 2)

    def test_cli_missing_directory(self):
        cmd = [
            sys.executable,
            "-m",
            "backend.thumbnail_cache.thumbnail_generator",
            "--input",
            "Z:/does_not_exist",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
