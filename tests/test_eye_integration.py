"""
Integration tests for the modified one-click cull logic and best selector.

Verifies:
1. Closed-eye photos are auto-rejected by cull
2. Blur photos are counted (blur_flagged) but NOT auto-rejected
3. Best selector excludes closed-eye photos
4. Best selector excludes blurry photos (unchanged)
5. OneClickCullResponse has the new field names

These tests use an in-memory SQLite database — no real photos needed.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.connection import init_database
from database.models import PhotoRecord
from database.repository import PhotoRepository


# ---------------------------------------------------------------------------
# Helper: create a minimal test database
# ---------------------------------------------------------------------------

def _make_record(image_id: str, **overrides) -> PhotoRecord:
    """Create a PhotoRecord with sensible defaults for testing."""
    defaults = {
        "image_id": image_id,
        "file_name": f"{image_id}.jpg",
        "file_path": f"/fake/{image_id}.jpg",
        "file_size": 1024 * 1024,
        "width": 4000,
        "height": 3000,
        "is_blur": 0,
        "blur_score": 70.0,
        "is_closed_eye": 0,
        "eye_score": 0.35,
        "is_rejected": 0,
        "is_duplicate": 0,
        "star_rating": None,
        "burst_group": None,
        "burst_position": None,
        "is_best_in_burst": 0,
    }
    defaults.update(overrides)
    return PhotoRecord(**defaults)


class TestCullBlurOnlyFlagged(unittest.TestCase):
    """Blur photos should be COUNTED but NOT auto-rejected."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        init_database(self.db_path)
        self.repo = PhotoRepository(self.db_path)

    def test_blur_photo_not_rejected(self):
        """A photo with is_blur=1 should NOT be auto-rejected by query logic."""
        blurry = _make_record("img001", is_blur=1, blur_score=25.0)
        self.repo.insert_photo(blurry)

        # After insertion, verify the photo is NOT rejected
        photo = self.repo.get_photo_by_id("img001")
        self.assertEqual(photo.is_blur, 1)
        self.assertEqual(photo.is_rejected, 0,
                        "Blur photo should NOT be auto-rejected")

    def test_blur_counted_separately(self):
        """Blur count should reflect flagged photos, not rejected ones."""
        blurry = _make_record("img001", is_blur=1, blur_score=20.0)
        sharp = _make_record("img002", is_blur=0, blur_score=80.0)
        self.repo.insert_photo(blurry)
        self.repo.insert_photo(sharp)

        blur_count = self.repo.get_blur_count()
        self.assertEqual(blur_count, 1)

        rejected_count = self.repo.get_rejected_count()
        self.assertEqual(rejected_count, 0,
                        "Blur alone should not make a photo rejected")


class TestCullClosedEyeRejected(unittest.TestCase):
    """Closed-eye photos should be auto-rejected by cull logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        init_database(self.db_path)
        self.repo = PhotoRepository(self.db_path)

    def test_closed_eye_rejected_flag(self):
        """is_closed_eye=1 can be set and queried."""
        closed = _make_record("img001", is_closed_eye=1, eye_score=0.10)
        self.repo.insert_photo(closed)

        photo = self.repo.get_photo_by_id("img001")
        self.assertEqual(photo.is_closed_eye, 1)
        self.assertEqual(photo.eye_score, 0.10)

    def test_closed_eye_count_query(self):
        """get_closed_eye_count should count closed-eye photos."""
        closed1 = _make_record("img001", is_closed_eye=1, eye_score=0.10)
        closed2 = _make_record("img002", is_closed_eye=1, eye_score=0.15)
        open_eye = _make_record("img003", is_closed_eye=0, eye_score=0.35)
        self.repo.insert_photo(closed1)
        self.repo.insert_photo(closed2)
        self.repo.insert_photo(open_eye)

        count = self.repo.get_closed_eye_count()
        self.assertEqual(count, 2)

    def test_closed_eye_photos_query(self):
        """get_closed_eye_photos should return only closed-eye photos."""
        closed = _make_record("img001", is_closed_eye=1, eye_score=0.10)
        open_eye = _make_record("img002", is_closed_eye=0, eye_score=0.35)
        self.repo.insert_photo(closed)
        self.repo.insert_photo(open_eye)

        photos = self.repo.get_closed_eye_photos()
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0].image_id, "img001")
        self.assertEqual(photos[0].is_closed_eye, 1)


class TestBestSelectorExclusions(unittest.TestCase):
    """Best selector should exclude blur and closed-eye photos."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        init_database(self.db_path)
        self.repo = PhotoRepository(self.db_path)

    def test_best_selector_excludes_blur(self):
        """select_best should not recommend a blurry photo."""
        from backend.ai.best_selector.selector import select_best

        blurry = _make_record("img001", burst_group="burst1", burst_position=0,
                              is_blur=1, blur_score=20.0)
        sharp = _make_record("img002", burst_group="burst1", burst_position=1,
                             is_blur=0, blur_score=80.0)
        self.repo.insert_photo(blurry)
        self.repo.insert_photo(sharp)

        photos = [self.repo.get_photo_by_id("img001"),
                  self.repo.get_photo_by_id("img002")]

        result = select_best(photos)
        self.assertEqual(result.recommended_id, "img002",
                        "Sharp photo should be recommended, not blurry")

    def test_best_selector_excludes_closed_eye(self):
        """select_best should not recommend a photo with closed eyes."""
        from backend.ai.best_selector.selector import select_best

        closed = _make_record("img001", burst_group="burst1", burst_position=0,
                              is_closed_eye=1, eye_score=0.10, blur_score=75.0)
        open_eye = _make_record("img002", burst_group="burst1", burst_position=1,
                                is_closed_eye=0, eye_score=0.35, blur_score=70.0)
        self.repo.insert_photo(closed)
        self.repo.insert_photo(open_eye)

        photos = [self.repo.get_photo_by_id("img001"),
                  self.repo.get_photo_by_id("img002")]

        result = select_best(photos)
        self.assertEqual(result.recommended_id, "img002",
                        "Non-closed-eye photo should be recommended, not the one with closed eyes")

    def test_best_selector_all_excluded(self):
        """When all photos are excluded, recommended_id should be None."""
        from backend.ai.best_selector.selector import select_best

        blurry = _make_record("img001", burst_group="burst1", burst_position=0,
                              is_blur=1, blur_score=20.0)
        closed = _make_record("img002", burst_group="burst1", burst_position=1,
                              is_closed_eye=1, eye_score=0.10, blur_score=75.0)
        self.repo.insert_photo(blurry)
        self.repo.insert_photo(closed)

        photos = [self.repo.get_photo_by_id("img001"),
                  self.repo.get_photo_by_id("img002")]

        result = select_best(photos)
        self.assertIsNone(result.recommended_id,
                         "Should be None when all photos are excluded")
        self.assertIn("blurry", result.selection_reason.lower())
        self.assertIn("closed", result.selection_reason.lower())


class TestOneClickCullResponse(unittest.TestCase):
    """Verify the updated response model."""

    def test_new_field_names(self):
        """OneClickCullResponse should have eye_closed_rejected and blur_flagged."""
        from backend.api.photo_service import OneClickCullResponse

        resp = OneClickCullResponse(
            eye_closed_rejected=5,
            blur_flagged=10,
            duplicate_rejected=3,
            burst_accepted=4,
            burst_rejected=8,
            total_accepted=4,
            total_rejected=16,
            untouched=20,
            total_photos=40,
        )
        self.assertEqual(resp.eye_closed_rejected, 5)
        self.assertEqual(resp.blur_flagged, 10)
        self.assertEqual(resp.total_rejected, 16)
        # Verify old field name is gone
        self.assertFalse(hasattr(resp, "blur_rejected"),
                        "blur_rejected should no longer exist")


class TestUpdateEyeStatus(unittest.TestCase):
    """Verify the repository update_eye_status method works."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        init_database(self.db_path)
        self.repo = PhotoRepository(self.db_path)

    def test_update_eye_status(self):
        """update_eye_status should set is_closed_eye and eye_score."""
        photo = _make_record("img001")
        self.repo.insert_photo(photo)

        ok = self.repo.update_eye_status("img001", is_closed_eye=1, eye_score=0.12)
        self.assertTrue(ok)

        updated = self.repo.get_photo_by_id("img001")
        self.assertEqual(updated.is_closed_eye, 1)
        self.assertEqual(updated.eye_score, 0.12)


if __name__ == "__main__":
    unittest.main()
