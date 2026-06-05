"""
Tests for the Image Scanner module.

Uses dynamically generated test images (via Pillow) to verify:
- Directory scanning
- File filtering
- Metadata extraction
- Corrupted file handling
- Large directory compatibility
"""

import json
import os
import sys
import subprocess
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.image_loader.models import PhotoInfo, ScanResult
from backend.image_loader.utils import (
    is_supported_format,
    scan_photos,
    collect_scan,
    safe_get_image_size,
    generate_file_id,
)


def create_test_image(path: str, width: int = 100, height: int = 80,
                      fmt: str = "JPEG") -> str:
    """Generate a small test image at the given path. Returns the path."""
    img = Image.new("RGB", (width, height), color="red")
    img.save(path, format=fmt)
    return path


class TestIsSupportedFormat(unittest.TestCase):
    """Tests for file format filtering."""

    def test_supported_extensions(self):
        self.assertTrue(is_supported_format("photo.jpg"))
        self.assertTrue(is_supported_format("photo.jpeg"))
        self.assertTrue(is_supported_format("photo.png"))
        self.assertTrue(is_supported_format("photo.JPG"))
        self.assertTrue(is_supported_format("photo.JPEG"))

    def test_unsupported_extensions(self):
        self.assertFalse(is_supported_format("photo.gif"))
        self.assertFalse(is_supported_format("photo.webp"))
        self.assertFalse(is_supported_format("photo.tiff"))
        self.assertFalse(is_supported_format("photo.bmp"))
        self.assertFalse(is_supported_format("photo.raw"))
        self.assertFalse(is_supported_format("notes.txt"))
        self.assertFalse(is_supported_format("photo"))


class TestSafeGetImageSize(unittest.TestCase):
    """Tests for safe image dimension reading."""

    def test_valid_image(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            path = f.name
        try:
            create_test_image(path, 640, 480)
            w, h = safe_get_image_size(path)
            self.assertEqual(w, 640)
            self.assertEqual(h, 480)
        finally:
            os.unlink(path)

    def test_corrupted_file(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"this is not a valid image file")
            path = f.name
        try:
            w, h = safe_get_image_size(path)
            self.assertEqual(w, 0)
            self.assertEqual(h, 0)
        finally:
            os.unlink(path)

    def test_non_image_file(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"<html>not an image</html>")
            path = f.name
        try:
            w, h = safe_get_image_size(path)
            self.assertEqual(w, 0)
            self.assertEqual(h, 0)
        finally:
            os.unlink(path)


class TestGenerateFileId(unittest.TestCase):
    """Tests for stable file ID generation."""

    def test_id_is_string(self):
        img_dir = tempfile.mkdtemp()
        path = os.path.join(img_dir, "test.jpg")
        create_test_image(path)
        try:
            file_id = generate_file_id(path, img_dir)
            self.assertIsInstance(file_id, str)
            self.assertEqual(len(file_id), 12)
        finally:
            os.unlink(path)
            os.rmdir(img_dir)

    def test_id_is_stable(self):
        img_dir = tempfile.mkdtemp()
        path = os.path.join(img_dir, "test.jpg")
        create_test_image(path)
        try:
            id1 = generate_file_id(path, img_dir)
            id2 = generate_file_id(path, img_dir)
            self.assertEqual(id1, id2)
        finally:
            os.unlink(path)
            os.rmdir(img_dir)

    def test_different_files_different_ids(self):
        img_dir = tempfile.mkdtemp()
        path1 = os.path.join(img_dir, "a.jpg")
        path2 = os.path.join(img_dir, "b.jpg")
        create_test_image(path1)
        create_test_image(path2)
        try:
            id1 = generate_file_id(path1, img_dir)
            id2 = generate_file_id(path2, img_dir)
            self.assertNotEqual(id1, id2)
        finally:
            os.unlink(path1)
            os.unlink(path2)
            os.rmdir(img_dir)


class TestScanPhotos(unittest.TestCase):
    """Tests for directory scanning."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        for root, _dirs, files in os.walk(self.test_dir, topdown=False):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in _dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(self.test_dir)

    def test_scan_empty_directory(self):
        results = list(scan_photos(self.test_dir))
        self.assertEqual(len(results), 0)

    def test_scan_single_image(self):
        create_test_image(os.path.join(self.test_dir, "test.jpg"))
        results = list(scan_photos(self.test_dir))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file_name, "test.jpg")
        self.assertEqual(results[0].width, 100)
        self.assertEqual(results[0].height, 80)

    def test_scan_multiple_formats(self):
        create_test_image(os.path.join(self.test_dir, "a.jpg"))
        create_test_image(os.path.join(self.test_dir, "b.jpeg"))
        create_test_image(os.path.join(self.test_dir, "c.png"), fmt="PNG")
        results = list(scan_photos(self.test_dir))
        self.assertEqual(len(results), 3)

    def test_skip_non_image_files(self):
        create_test_image(os.path.join(self.test_dir, "photo.jpg"))
        with open(os.path.join(self.test_dir, "notes.txt"), "w") as f:
            f.write("not an image")
        with open(os.path.join(self.test_dir, "data.gif"), "w") as f:
            f.write("fake gif")
        results = list(scan_photos(self.test_dir))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file_name, "photo.jpg")

    def test_skip_corrupted_images(self):
        create_test_image(os.path.join(self.test_dir, "good.jpg"))
        with open(os.path.join(self.test_dir, "bad.jpg"), "wb") as f:
            f.write(b"not a real image")
        results = list(scan_photos(self.test_dir))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file_name, "good.jpg")

    def test_recursive_scan(self):
        sub_dir = os.path.join(self.test_dir, "subfolder")
        os.makedirs(sub_dir)
        create_test_image(os.path.join(self.test_dir, "root.jpg"))
        create_test_image(os.path.join(sub_dir, "nested.png"), fmt="PNG")
        results = list(scan_photos(self.test_dir))
        self.assertEqual(len(results), 2)

    def test_photo_info_fields(self):
        path = os.path.join(self.test_dir, "test.jpg")
        create_test_image(path, 1920, 1080)
        results = list(scan_photos(self.test_dir))
        self.assertEqual(len(results), 1)
        p = results[0]
        self.assertIsInstance(p.id, str)
        self.assertEqual(p.file_name, "test.jpg")
        self.assertEqual(p.file_path, path)
        self.assertGreater(p.file_size, 0)
        self.assertIsInstance(p.created_time, str)
        self.assertEqual(p.width, 1920)
        self.assertEqual(p.height, 1080)

    def test_to_dict(self):
        path = os.path.join(self.test_dir, "test.jpg")
        create_test_image(path)
        results = list(scan_photos(self.test_dir))
        d = results[0].to_dict()
        expected_keys = {"id", "file_name", "file_path", "file_size",
                         "created_time", "width", "height"}
        self.assertEqual(set(d.keys()), expected_keys)

    def test_scan_result_model(self):
        result = ScanResult(total_count=0, photos=[], errors=[])
        d = result.to_dict()
        self.assertIn("total_count", d)
        self.assertIn("photos", d)
        self.assertIn("errors", d)


class TestLargeDirectoryCompatibility(unittest.TestCase):
    """Verify generator behavior does not load everything in memory."""

    def test_generator_lazy_evaluation(self):
        """Verify that scan_photos returns a generator (not a list)."""
        gen = scan_photos(tempfile.mkdtemp())
        self.assertTrue(hasattr(gen, "__next__"))


class TestCLI(unittest.TestCase):
    """Tests for CLI entry point."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        create_test_image(os.path.join(self.test_dir, "img1.jpg"))
        create_test_image(os.path.join(self.test_dir, "img2.png"), fmt="PNG")

    def tearDown(self):
        for f in os.listdir(self.test_dir):
            os.unlink(os.path.join(self.test_dir, f))
        os.rmdir(self.test_dir)

    def test_cli_returns_json(self):
        result = subprocess.run(
            [sys.executable, "-m", "backend.image_loader.image_scanner",
             "--input", self.test_dir],
            capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("total_count", data)
        self.assertEqual(data["total_count"], 2)
        self.assertEqual(len(data["photos"]), 2)

    def test_cli_pretty_output(self):
        result = subprocess.run(
            [sys.executable, "-m", "backend.image_loader.image_scanner",
             "--input", self.test_dir, "--pretty"],
            capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("\n", result.stdout)

    def test_cli_limit(self):
        create_test_image(os.path.join(self.test_dir, "img3.jpg"))
        result = subprocess.run(
            [sys.executable, "-m", "backend.image_loader.image_scanner",
             "--input", self.test_dir, "--limit", "1"],
            capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["photos"]), 1)

    def test_cli_invalid_directory(self):
        result = subprocess.run(
            [sys.executable, "-m", "backend.image_loader.image_scanner",
             "--input", "Z:/nonexistent"],
            capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
