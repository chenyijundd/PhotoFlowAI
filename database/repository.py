"""
PhotoFlow AI - Photo Repository

Repository pattern for photo database operations.
All methods take a db_path parameter (defaulting to None for auto-detect)
to support dependency injection and testing.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

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

    def clear_all(self) -> int:
        """Delete all photo records from the database.

        Returns the number of deleted rows.
        """
        with DatabaseConnection(self.db_path) as conn:
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
        with DatabaseConnection(self.db_path) as conn:
            before = conn.total_changes
            conn.execute(sql, photo.to_row_values())
            return conn.total_changes > before

    def insert_photos(self, photos: List[PhotoRecord]) -> int:
        """Batch insert multiple photo records.

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
        with DatabaseConnection(self.db_path) as conn:
            before = conn.total_changes
            conn.executemany(sql, values_list)
            return conn.total_changes - before

    def get_all_photos(self) -> List[PhotoRecord]:
        """Retrieve all photo records ordered by file_name."""
        with DatabaseConnection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_starred_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with star_rating == 1, ordered by file_name."""
        with DatabaseConnection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE star_rating = 1 ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_blur_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with is_blur == 1, ordered by file_name."""
        with DatabaseConnection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE is_blur = 1 ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_starred_count(self) -> int:
        """Return the count of photos with star_rating == 1."""
        with DatabaseConnection(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE star_rating = 1"
            ).fetchone()
            return row[0] if row else 0

    def get_photo_by_id(self, image_id: str) -> Optional[PhotoRecord]:
        """Retrieve a single photo record by image_id.

        Returns None if not found.
        """
        with DatabaseConnection(self.db_path) as conn:
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

    def get_rejected_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with is_rejected == 1, ordered by file_name."""
        with DatabaseConnection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE is_rejected = 1 ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_duplicate_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with is_duplicate == 1, ordered by file_name."""
        with DatabaseConnection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE is_duplicate = 1 ORDER BY file_name"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_duplicate_count(self) -> int:
        """Return the count of photos with is_duplicate == 1."""
        with DatabaseConnection(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE is_duplicate = 1"
            ).fetchone()
            return row[0] if row else 0

    def get_duplicate_groups(self) -> List[dict]:
        """Return duplicate groups with their member count and sample photo IDs."""
        with DatabaseConnection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT duplicate_group, COUNT(*) as cnt, GROUP_CONCAT(image_id) as members "
                "FROM photos WHERE is_duplicate = 1 AND duplicate_group IS NOT NULL "
                "GROUP BY duplicate_group ORDER BY duplicate_group"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_photos_by_duplicate_group(self, group_id: str) -> List[PhotoRecord]:
        """Retrieve all photos in a specific duplicate group, ordered by file_name."""
        with DatabaseConnection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE duplicate_group = ? ORDER BY file_name",
                (group_id,),
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_rejected_count(self) -> int:
        """Return the count of photos with is_rejected == 1."""
        with DatabaseConnection(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE is_rejected = 1"
            ).fetchone()
            return row[0] if row else 0

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
        with DatabaseConnection(self.db_path) as conn:
            cursor = conn.execute(sql, values)
            return cursor.rowcount > 0
