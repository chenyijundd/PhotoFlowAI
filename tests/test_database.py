"""
Tests for the Database module (SQLite Image Index System).

Tests connection management, repository CRUD operations, and CLI.
All tests use temporary databases to avoid polluting the real one.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.connection import DatabaseConnection, init_database, get_default_db_path
from database.models import PhotoRecord, PHOTO_COLUMNS
from database.repository import PhotoRepository


def create_test_image(path: str, width: int = 100, height: int = 100) -> str:
    """Generate a small test image for CLI tests. Returns the path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new("RGB", (width, height), color="blue")
    img.save(path, format="JPEG")
    return path


def make_photo(
    image_id: str = "test001",
    file_name: str = "test.jpg",
    file_path: str = "/tmp/test.jpg",
    **kwargs,
) -> PhotoRecord:
    """Helper to create a PhotoRecord with sensible defaults."""
    return PhotoRecord(
        image_id=image_id,
        file_name=file_name,
        file_path=file_path,
        width=kwargs.pop("width", 800),
        height=kwargs.pop("height", 600),
        file_size=kwargs.pop("file_size", 1024),
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        **kwargs,
    )


class TestDatabaseConnection(unittest.TestCase):
    """Tests for DatabaseConnection context manager and init_database."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()

    def tearDown(self):
        import gc
        gc.collect()
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except PermissionError:
                pass

    def test_init_creates_photos_table(self):
        init_database(self.db_path)
        with DatabaseConnection(self.db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = [r["name"] for r in tables]
            self.assertIn("photos", table_names)

    def test_init_creates_correct_columns(self):
        init_database(self.db_path)
        with DatabaseConnection(self.db_path) as conn:
            cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(photos)").fetchall()
            }
            self.assertIn("image_id", cols)
            self.assertIn("file_name", cols)
            self.assertIn("file_path", cols)
            self.assertIn("blur_score", cols)
            self.assertIn("is_blur", cols)
            self.assertIn("is_rejected", cols)
            self.assertIn("is_duplicate", cols)
            self.assertIn("duplicate_group", cols)
            self.assertIn("star_rating", cols)
            self.assertIn("created_at", cols)
            self.assertIn("updated_at", cols)

    def test_init_is_idempotent(self):
        init_database(self.db_path)
        init_database(self.db_path)
        with DatabaseConnection(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table' AND name='photos'"
            ).fetchone()["cnt"]
            self.assertEqual(count, 1)

    def test_connection_auto_commits(self):
        init_database(self.db_path)
        with DatabaseConnection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO photos (image_id, file_name, file_path) VALUES (?, ?, ?)",
                ("auto001", "test.jpg", "/test.jpg"),
            )
        with DatabaseConnection(self.db_path) as conn:
            row = conn.execute(
                "SELECT image_id FROM photos WHERE image_id = ?", ("auto001",)
            ).fetchone()
            self.assertIsNotNone(row)

    def test_connection_rolls_back_on_error(self):
        init_database(self.db_path)
        try:
            with DatabaseConnection(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO photos (image_id, file_name, file_path) VALUES (?, ?, ?)",
                    ("err001", "test.jpg", "/test.jpg"),
                )
                raise ValueError("simulated error")
        except ValueError:
            pass
        with DatabaseConnection(self.db_path) as conn:
            row = conn.execute(
                "SELECT image_id FROM photos WHERE image_id = ?", ("err001",)
            ).fetchone()
            self.assertIsNone(row)

    def test_get_default_db_path_returns_expected(self):
        path = get_default_db_path()
        self.assertTrue(path.endswith("photoflow.db"))
        self.assertIn("database", path)


class TestPhotoRecord(unittest.TestCase):
    """Tests for PhotoRecord data model."""

    def test_to_dict_omits_none(self):
        r = PhotoRecord(
            image_id="abc",
            file_name="test.jpg",
            file_path="/test.jpg",
            width=100,
            height=200,
        )
        d = r.to_dict()
        self.assertIn("image_id", d)
        self.assertIn("file_name", d)
        self.assertNotIn("thumbnail_path", d)
        self.assertNotIn("blur_score", d)

    def test_to_row_values_length(self):
        r = make_photo()
        vals = r.to_row_values()
        self.assertEqual(len(vals), len(PHOTO_COLUMNS))

    def test_from_row_roundtrip(self):
        import sqlite3
        r = make_photo(image_id="rt001", file_name="roundtrip.jpg")
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE photos (image_id TEXT PRIMARY KEY, file_name TEXT, file_path TEXT, "
            "thumbnail_path TEXT, file_size INTEGER, width INTEGER, height INTEGER, "
            "created_time TEXT, blur_score REAL, eye_score REAL, duplicate_group TEXT, "
            "is_blur INTEGER, is_closed_eye INTEGER, is_duplicate INTEGER, "
            "is_rejected INTEGER, "
            "star_rating INTEGER, created_at TEXT, updated_at TEXT)"
        )
        conn.execute(
            "INSERT INTO photos (image_id, file_name, file_path, width, height, "
            "file_size, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("rt001", "roundtrip.jpg", "/rt.jpg", 800, 600, 1024, "2024-01-01", "2024-01-01"),
        )
        row = conn.execute("SELECT * FROM photos WHERE image_id = 'rt001'").fetchone()
        recovered = PhotoRecord.from_row(row)
        self.assertEqual(recovered.image_id, "rt001")
        self.assertEqual(recovered.file_name, "roundtrip.jpg")
        self.assertEqual(recovered.width, 800)
        conn.close()

    def test_column_names_and_placeholders(self):
        cols = PhotoRecord.column_names()
        self.assertIn("image_id", cols)
        self.assertIn("file_name", cols)
        ph = PhotoRecord.placeholders()
        self.assertEqual(len(ph.split(", ")), len(PHOTO_COLUMNS))


class TestPhotoRepository(unittest.TestCase):
    """Tests for PhotoRepository CRUD operations."""

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

    def test_insert_photo_single(self):
        p = make_photo(image_id="ins001", file_name="single.jpg")
        result = self.repo.insert_photo(p)
        self.assertTrue(result)

    def test_insert_photo_skip_duplicate(self):
        p = make_photo(image_id="dup001", file_name="dup.jpg")
        self.repo.insert_photo(p)
        p2 = make_photo(image_id="dup001", file_name="dup_other.jpg")
        result = self.repo.insert_photo(p2)
        self.assertFalse(result)

    def test_insert_photos_batch(self):
        photos = [
            make_photo(image_id=f"batch{i:03d}", file_name=f"batch{i}.jpg")
            for i in range(10)
        ]
        count = self.repo.insert_photos(photos)
        self.assertEqual(count, 10)

    def test_insert_photos_with_duplicates(self):
        photos = [
            make_photo(image_id="dup_batch", file_name="a.jpg"),
            make_photo(image_id="dup_batch", file_name="b.jpg"),
            make_photo(image_id="unique", file_name="c.jpg"),
        ]
        count = self.repo.insert_photos(photos)
        self.assertEqual(count, 2)

    def test_insert_photos_empty_list(self):
        count = self.repo.insert_photos([])
        self.assertEqual(count, 0)

    def test_get_all_photos(self):
        photos = [
            make_photo(image_id=f"all{i:03d}", file_name=f"file{i}.jpg")
            for i in range(5)
        ]
        self.repo.insert_photos(photos)
        results = self.repo.get_all_photos()
        self.assertEqual(len(results), 5)

    def test_get_all_photos_empty(self):
        results = self.repo.get_all_photos()
        self.assertEqual(results, [])

    def test_get_photo_by_id_found(self):
        p = make_photo(image_id="find001", file_name="find.jpg")
        self.repo.insert_photo(p)
        found = self.repo.get_photo_by_id("find001")
        self.assertIsNotNone(found)
        self.assertEqual(found.file_name, "find.jpg")

    def test_get_photo_by_id_not_found(self):
        found = self.repo.get_photo_by_id("nonexistent")
        self.assertIsNone(found)

    def test_get_photo_by_id_returns_all_fields(self):
        p = make_photo(
            image_id="fields001",
            file_name="fields.jpg",
            file_path="/path/fields.jpg",
            file_size=2048,
            width=1920,
            height=1080,
        )
        self.repo.insert_photo(p)
        found = self.repo.get_photo_by_id("fields001")
        self.assertEqual(found.file_size, 2048)
        self.assertEqual(found.width, 1920)
        self.assertEqual(found.height, 1080)

    def test_update_blur_status(self):
        p = make_photo(image_id="blur001")
        self.repo.insert_photo(p)
        updated = self.repo.update_blur_status("blur001", is_blur=1, blur_score=0.85)
        self.assertTrue(updated)
        found = self.repo.get_photo_by_id("blur001")
        self.assertEqual(found.is_blur, 1)
        self.assertEqual(found.blur_score, 0.85)

    def test_update_blur_status_nonexistent(self):
        updated = self.repo.update_blur_status("nobody", is_blur=1)
        self.assertFalse(updated)

    def test_update_eye_status(self):
        p = make_photo(image_id="eye001")
        self.repo.insert_photo(p)
        updated = self.repo.update_eye_status("eye001", is_closed_eye=1, eye_score=0.92)
        self.assertTrue(updated)
        found = self.repo.get_photo_by_id("eye001")
        self.assertEqual(found.is_closed_eye, 1)
        self.assertEqual(found.eye_score, 0.92)

    def test_update_duplicate_status(self):
        p = make_photo(image_id="dupgrp001")
        self.repo.insert_photo(p)
        updated = self.repo.update_duplicate_status(
            "dupgrp001", is_duplicate=1, duplicate_group="group_a"
        )
        self.assertTrue(updated)
        found = self.repo.get_photo_by_id("dupgrp001")
        self.assertEqual(found.is_duplicate, 1)
        self.assertEqual(found.duplicate_group, "group_a")

    def test_update_star_rating(self):
        p = make_photo(image_id="star001")
        self.repo.insert_photo(p)
        updated = self.repo.update_star_rating("star001", 5)
        self.assertTrue(updated)
        found = self.repo.get_photo_by_id("star001")
        self.assertEqual(found.star_rating, 5)

    def test_update_updates_timestamp(self):
        p = make_photo(image_id="ts001")
        self.repo.insert_photo(p)
        before = self.repo.get_photo_by_id("ts001").updated_at
        self.repo.update_star_rating("ts001", 3)
        after = self.repo.get_photo_by_id("ts001").updated_at
        self.assertNotEqual(before, after)


class TestCLI(unittest.TestCase):
    """Tests for CLI entry point."""

    def setUp(self):
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.db_tmp.name
        self.db_tmp.close()
        self.img_dir = tempfile.mkdtemp()

    def tearDown(self):
        import gc
        gc.collect()
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except PermissionError:
                pass
        if os.path.exists(self.img_dir):
            import shutil
            shutil.rmtree(self.img_dir, ignore_errors=True)

    def _run_cli(self, *args) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            "-m",
            "database.db_manager",
            *args,
        ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )

    def test_cli_init(self):
        result = self._run_cli("--init", "--db-path", self.db_path)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "ok")
        self.assertIn("db_path", data)

    def test_cli_import(self):
        create_test_image(os.path.join(self.img_dir, "photo1.jpg"))
        create_test_image(os.path.join(self.img_dir, "photo2.jpg"))
        result = self._run_cli(
            "--import", self.img_dir,
            "--db-path", self.db_path,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["imported"], 2)
        self.assertEqual(data["total_scanned"], 2)

    def test_cli_import_dedup(self):
        create_test_image(os.path.join(self.img_dir, "photo.jpg"))
        result = self._run_cli(
            "--import", self.img_dir,
            "--db-path", self.db_path,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["imported"], 1)
        result = self._run_cli(
            "--import", self.img_dir,
            "--db-path", self.db_path,
        )
        data = json.loads(result.stdout)
        # Second import finds the same files but skips due to image_id conflict
        self.assertEqual(data["imported"], 0)

    def test_cli_no_args_shows_help(self):
        result = self._run_cli()
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
