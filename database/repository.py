"""
PhotoFlow AI - Photo Repository

Repository pattern for photo database operations.
All methods take a db_path parameter (defaulting to None for auto-detect)
to support dependency injection and testing.

Performance (Task 14):
   - batch_update(): performs multiple updates in a single transaction
   - batch_insert_photos(): existing method, documented as batch tx
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Callable

from .connection import DatabaseConnection, init_database
from .models import PHOTO_COLUMNS, PhotoRecord

logger = logging.getLogger(__name__)


class PhotoRepository:
    """Repository for photo CRUD operations using the Repository pattern."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def init_database(self) -> str:
        """Initialize the database schema. Returns the database path."""
        return init_database(self.db_path)

    @contextmanager
    def batch_transaction(self):
        """
        Context manager for batch operations within a single transaction.

        Usage:
            with repo.batch_transaction():
                repo.update_star_rating(id1, 1)
                repo.update_reject_status(id2, 1)

        All operations within the block are committed atomically.
        On exception, everything is rolled back.
        """
        conn = DatabaseConnection(self.db_path)
        db = conn.__enter__()
        try:
            # Temporarily replace the per-call connection with our shared one
            old_get_conn = getattr(self, "_batch_conn", None)
            self._batch_conn = db
            yield
            conn.__exit__(None, None, None)
        except Exception:
            conn.__exit__(*sys.exc_info())
            raise
        finally:
            self._batch_conn = old_get_conn

    def _get_conn(self):
        """Return either the batch connection or a new one."""
        batch = getattr(self, "_batch_conn", None)
        if batch is not None:
            return _NoOpConnection(batch)
        return DatabaseConnection(self.db_path)

    def clear_all(self) -> int:
        """Delete all photo records from the database.

        Returns the number of deleted rows.
        """
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM photos")
            return cursor.rowcount

    def insert_photo(self, photo: PhotoRecord) -> bool:
        """Insert a single photo record.

        If image_id already exists, the insertion is silently skipped.
        Returns True if a new row was inserted, False if skipped.
        """
        if photo.created_at is None:
            photo.created_at = datetime.now(timezone.utc).isoformat()
        if photo.updated_at is None:
            photo.updated_at = photo.created_at

        sql = (
            f"INSERT OR IGNORE INTO photos ({PhotoRecord.column_names()}) "
            f"VALUES ({PhotoRecord.placeholders()})"
        )
        with self._get_conn() as conn:
            before = conn.total_changes
            conn.execute(sql, photo.to_row_values())
            return conn.total_changes > before

    def insert_photos(self, photos: List[PhotoRecord]) -> int:
        """Batch insert multiple photo records in a single transaction.

        Silently skips duplicates (image_id conflict).
        Returns the number of rows actually inserted.
        """
        now = datetime.now(timezone.utc).isoformat()
        values_list: List[tuple] = []
        for p in photos:
            if p.created_at is None:
                p.created_at = now
            if p.updated_at is None:
                p.updated_at = now
            values_list.append(p.to_row_values())

        if not values_list:
            return 0

        sql = (
            f"INSERT OR IGNORE INTO photos ({PhotoRecord.column_names()}) "
            f"VALUES ({PhotoRecord.placeholders()})"
        )
        with self._get_conn() as conn:
            before = conn.total_changes
            conn.executemany(sql, values_list)
            return conn.total_changes - before

    def get_all_photos(self) -> List[PhotoRecord]:
        """Retrieve all photo records ordered by file_name."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_starred_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with star_rating == 1, ordered by file_name."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE star_rating = 1 ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_blur_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with is_blur == 1, ordered by file_name."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE is_blur = 1 ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_starred_count(self) -> int:
        """Return the count of photos with star_rating == 1."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE star_rating = 1"
            ).fetchone()
            return row[0] if row else 0

    def get_photo_by_id(self, image_id: str) -> Optional[PhotoRecord]:
        """Retrieve a single photo record by image_id.

        Returns None if not found.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE image_id = ?",
                (image_id,),
            ).fetchone()
            return PhotoRecord.from_row(row) if row is not None else None

    def update_blur_status(
        self,
        image_id: str,
        is_blur: int,
        blur_score: Optional[float] = None,
    ) -> bool:
        """Update the blur detection status for a photo.

        Returns True if a row was updated.
        """
        return self._update_fields(
            image_id,
            is_blur=is_blur,
            blur_score=blur_score,
        )

    def update_eye_status(
        self,
        image_id: str,
        is_closed_eye: int,
        eye_score: Optional[float] = None,
    ) -> bool:
        """Update the eye closure status for a photo.

        Returns True if a row was updated.
        """
        return self._update_fields(
            image_id,
            is_closed_eye=is_closed_eye,
            eye_score=eye_score,
        )

    def update_duplicate_status(
        self,
        image_id: str,
        is_duplicate: int,
        duplicate_group: Optional[str] = None,
    ) -> bool:
        """Update the duplicate detection status for a photo.

        Returns True if a row was updated.
        """
        return self._update_fields(
            image_id,
            is_duplicate=is_duplicate,
            duplicate_group=duplicate_group,
        )

    def update_star_rating(self, image_id: str, star_rating: int) -> bool:
        """Update the star rating for a photo.

        Returns True if a row was updated.
        """
        return self._update_fields(image_id, star_rating=star_rating)

    def update_reject_status(self, image_id: str, is_rejected: int) -> bool:
        """Update the reject status for a photo.

        Returns True if a row was updated.
        """
        return self._update_fields(image_id, is_rejected=is_rejected)

    def update_photos_batch(
        self,
        updates: List[Dict[str, Any]],
    ) -> int:
        """
        Batch update multiple photos in a single transaction.

        Each dict in `updates` must contain:
            - 'image_id': str
            - other fields to update (star_rating, is_rejected, etc.)

        Returns the total number of rows updated.

        Example:
            repo.update_photos_batch([
                {'image_id': 'abc', 'star_rating': 1},
                {'image_id': 'def', 'is_rejected': 1, 'is_blur': 0},
            ])
        """
        if not updates:
            return 0

        total_updated = 0
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            for update in updates:
                image_id = update.pop("image_id", None)
                if not image_id or not update:
                    continue

                set_fields = {k: v for k, v in update.items() if v is not None}
                if not set_fields:
                    continue

                set_fields["updated_at"] = now
                set_clause = ", ".join(f"{k} = ?" for k in set_fields)
                values = tuple(set_fields.values()) + (image_id,)
                sql = f"UPDATE photos SET {set_clause} WHERE image_id = ?"

                cursor = conn.execute(sql, values)
                total_updated += cursor.rowcount

        return total_updated

    def get_rejected_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with is_rejected == 1, ordered by file_name."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE is_rejected = 1 ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_duplicate_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with is_duplicate == 1, ordered by file_name."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE is_duplicate = 1 ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_duplicate_count(self) -> int:
        """Return the count of photos with is_duplicate == 1."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE is_duplicate = 1"
            ).fetchone()
            return row[0] if row else 0

    def get_duplicate_groups(self) -> List[dict]:
        """Return duplicate groups with their member count and sample photo IDs."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT duplicate_group, COUNT(*) as cnt, GROUP_CONCAT(image_id) as members "
                "FROM photos WHERE is_duplicate = 1 AND duplicate_group IS NOT NULL "
                "GROUP BY duplicate_group ORDER BY duplicate_group"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_photos_by_duplicate_group(self, group_id: str) -> List[PhotoRecord]:
        """Retrieve all photos in a specific duplicate group, ordered by file_name."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE duplicate_group = ? ORDER BY file_name",
                (group_id,),
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_rejected_count(self) -> int:
        """Return the count of photos with is_rejected == 1."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE is_rejected = 1"
            ).fetchone()
            return row[0] if row else 0

    # ---- AI Suggestion methods ----

    def get_suggested_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with ai_suggestion IS NOT NULL, ordered by file_name."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE ai_suggestion IS NOT NULL ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_suggested_count(self) -> int:
        """Return the count of photos with ai_suggestion IS NOT NULL."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE ai_suggestion IS NOT NULL"
            ).fetchone()
            return row[0] if row else 0

    def update_suggestion(self, image_id: str, suggestion: Optional[str]) -> bool:
        """Update the ai_suggestion field for a photo. Pass None to clear."""
        return self._update_fields(image_id, ai_suggestion=suggestion)

    def _update_fields(self, image_id: str, **fields) -> bool:
        """Generic field updater. Builds SET clause from keyword arguments.

        Automatically updates the updated_at timestamp.
        """
        if not fields:
            return False

        set_fields = {k: v for k, v in fields.items() if v is not None}
        if not set_fields:
            return False

        set_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in set_fields)
        values = tuple(set_fields.values()) + (image_id,)

        sql = f"UPDATE photos SET {set_clause} WHERE image_id = ?"
        with self._get_conn() as conn:
            cursor = conn.execute(sql, values)
            return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Helper: No-op connection wrapper for batch transaction reuse
# ---------------------------------------------------------------------------

import sys as _sys


class _NoOpConnection:
    """
    Wraps an already-open sqlite3.Connection so it can be used as a
    context manager without opening/closing/committing.
    """

    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, *args):
        # Don't commit/close — the batch_transaction context manages that
        return False
