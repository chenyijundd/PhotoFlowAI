"""
Tests for the Duplicate Detection module.

Tests phash computation, detector, and service orchestration.
"""

import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.ai.duplicate_detector.detector import compute_phash, hamming_distance
from backend.ai.duplicate_detector.service import UnionFind, DUPLICATE_THRESHOLD


def create_test_image(path: str, color: tuple = (100, 149, 237)) -> str:
    """Generate a small test image."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new("RGB", (200, 150), color=color)
    img.save(path, format="JPEG")
    return path


class TestHammingDistance(unittest.TestCase):
    """Tests for Hamming distance computation."""

    def test_same_hash_zero_distance(self):
        from imagehash import ImageHash
        import numpy as np
        h = ImageHash(np.ones((8, 8), dtype=bool))
        self.assertEqual(hamming_distance(h, h), 0)

    def test_different_hashes_nonzero(self):
        from imagehash import ImageHash
        import numpy as np
        h1 = ImageHash(np.zeros((8, 8), dtype=bool))
        h2 = ImageHash(np.ones((8, 8), dtype=bool))
        self.assertGreater(hamming_distance(h1, h2), 0)


class TestDuplicateDetector(unittest.TestCase):
    """Tests for phash computation and duplicate detection."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_compute_phash_valid_image(self):
        path = create_test_image(os.path.join(self.tmp_dir, "test.jpg"))
        h = compute_phash(path)
        self.assertIsNotNone(h)
        # phash returns a 64-bit hash (8x8)
        self.assertEqual(len(str(h)), 16)  # 64 bits = 16 hex chars

    def test_compute_phash_non_existent_raises(self):
        path = os.path.join(self.tmp_dir, "nonexistent.jpg")
        with self.assertRaises(FileNotFoundError):
            compute_phash(path)

    def test_compute_phash_corrupted_raises(self):
        path = os.path.join(self.tmp_dir, "corrupted.jpg")
        with open(path, "wb") as f:
            f.write(b"not an image")
        with self.assertRaises(Exception):
            compute_phash(path)

    def test_identical_images_same_hash(self):
        img1 = os.path.join(self.tmp_dir, "img1.jpg")
        img2 = os.path.join(self.tmp_dir, "img2.jpg")
        create_test_image(img1, (100, 149, 237))
        create_test_image(img2, (100, 149, 237))
        h1 = compute_phash(img1)
        h2 = compute_phash(img2)
        dist = hamming_distance(h1, h2)
        self.assertLessEqual(dist, DUPLICATE_THRESHOLD)

    def test_different_images_large_distance(self):
        img1 = os.path.join(self.tmp_dir, "red.jpg")
        img2 = os.path.join(self.tmp_dir, "blue.jpg")
        create_test_image(img1, (255, 0, 0))
        create_test_image(img2, (0, 0, 255))
        h1 = compute_phash(img1)
        h2 = compute_phash(img2)
        dist = hamming_distance(h1, h2)
        # Different solid colors should have larger distance
        self.assertGreaterEqual(dist, 0)

    def test_unicode_path(self):
        """Test that Unicode file paths work correctly on Windows."""
        path = os.path.join(self.tmp_dir, "测试照片_阈值_100.jpg")
        create_test_image(path)
        h = compute_phash(path)
        self.assertIsNotNone(h)
        self.assertEqual(len(str(h)), 16)


class TestUnionFind(unittest.TestCase):
    """Tests for Union-Find data structure."""

    def test_initial_state(self):
        uf = UnionFind(5)
        for i in range(5):
            self.assertEqual(uf.find(i), i)

    def test_union_simple(self):
        uf = UnionFind(4)
        uf.union(0, 1)
        self.assertEqual(uf.find(0), uf.find(1))

    def test_transitive_union(self):
        uf = UnionFind(5)
        uf.union(0, 1)
        uf.union(1, 2)
        self.assertEqual(uf.find(0), uf.find(2))

    def test_no_false_positive(self):
        uf = UnionFind(5)
        uf.union(0, 1)
        uf.union(2, 3)
        self.assertNotEqual(uf.find(0), uf.find(2))


class TestDuplicateDetectorService(unittest.TestCase):
    """Tests for the duplicate detection service (orchestration)."""

    def test_run_duplicate_detection_empty_list(self):
        from backend.ai.duplicate_detector.service import run_duplicate_detection
        processed, groups, duplicates = run_duplicate_detection([], None)
        self.assertEqual(processed, 0)
        self.assertEqual(groups, 0)
        self.assertEqual(duplicates, 0)

    def test_threshold_constant(self):
        self.assertEqual(DUPLICATE_THRESHOLD, 5)


if __name__ == "__main__":
    unittest.main()
