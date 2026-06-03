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
        """Retrieve all photo records ordered by created_time (拍摄时间)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos ORDER BY created_time"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_starred_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with star_rating == 1.

        Sorted by manually_operated_at DESC (manually starred first),
        then by created_time (拍摄时间) for AI-starred photos.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE star_rating = 1 "
                "ORDER BY manually_operated_at DESC NULLS LAST, created_time"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_blur_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with is_blur == 1, sorted by blur_score DESC (worst first)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE is_blur = 1 "
                "ORDER BY blur_score DESC, created_time"
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

    def update_star_rating(self, image_id: str, star_rating: int, is_manual: bool = False) -> bool:
        """Update the star rating for a photo.

        When star_rating == 1, is_rejected is automatically cleared to 0
        so that star and reject are always mutually exclusive.

        When is_manual=True, also records manually_operated_at so the photo
        sorts to the top of the 已选 tab.
        """
        fields = {"star_rating": star_rating}
        if star_rating == 1:
            fields["is_rejected"] = 0
        if is_manual:
            fields["manually_operated_at"] = datetime.now(timezone.utc).isoformat()
        return self._update_fields(image_id, **fields)

    def update_reject_status(self, image_id: str, is_rejected: int, is_manual: bool = False) -> bool:
        """Update the reject status for a photo.

        When is_rejected == 1, star_rating is automatically cleared to 0
        so that star and reject are always mutually exclusive.

        When is_manual=True, also records manually_operated_at so the photo
        sorts to the top of the 废片 tab.
        """
        fields = {"is_rejected": is_rejected}
        if is_rejected == 1:
            fields["star_rating"] = 0
        if is_manual:
            fields["manually_operated_at"] = datetime.now(timezone.utc).isoformat()
        return self._update_fields(image_id, **fields)

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
        """Retrieve rejected photos that are NOT starred, ordered by manually_operated_at then created_time.

        Starred photos always belong to the 已选 tab — they are excluded
        from the 废片 view even if is_rejected=1.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos "
                "WHERE is_rejected = 1 AND (star_rating IS NULL OR star_rating != 1) "
                "ORDER BY manually_operated_at DESC NULLS LAST, created_time"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_duplicate_photos(self) -> List[PhotoRecord]:
        """Retrieve all photos with is_duplicate == 1, grouped by duplicate_group then file_name."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE is_duplicate = 1 "
                "ORDER BY duplicate_group, file_name"
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

    def get_blur_count(self) -> int:
        """Return the count of photos with is_blur == 1."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE is_blur = 1"
            ).fetchone()
            return row[0] if row else 0

    def get_rejected_count(self) -> int:
        """Return the count of rejected photos that are NOT starred.

        Starred photos belong to 已选, not 废片.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos "
                "WHERE is_rejected = 1 AND (star_rating IS NULL OR star_rating != 1)"
            ).fetchone()
            return row[0] if row else 0

    # ---- Burst group methods ----

    def update_burst_group(
        self,
        image_id: str,
        burst_group: str,
        burst_position: int,
    ) -> bool:
        """Set the burst_group and burst_position for a photo.

        Returns True if a row was updated.
        """
        return self._update_fields(
            image_id,
            burst_group=burst_group,
            burst_position=burst_position,
        )

    def clear_burst_group(self, image_id: str) -> bool:
        """Remove a photo from its burst group (set burst_group and burst_position to NULL).

        Returns True if a row was updated.
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE photos SET burst_group = NULL, burst_position = NULL,"
                " updated_at = ? WHERE image_id = ?",
                (datetime.now(timezone.utc).isoformat(), image_id),
            )
            return cursor.rowcount > 0

    def delete_photo(self, image_id: str) -> bool:
        """Delete a photo record from the database.

        Returns True if a row was deleted.
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM photos WHERE image_id = ?", (image_id,)
            )
            return cursor.rowcount > 0

    def get_burst_group_photos(self, group_id: str) -> list:
        """Retrieve all photos in a specific burst group, ordered by burst_position."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos "
                "WHERE burst_group = ? ORDER BY burst_position",
                (group_id,),
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_burst_groups(self) -> list[str]:
        """Return all distinct burst_group IDs."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT burst_group FROM photos "
                "WHERE burst_group IS NOT NULL ORDER BY burst_group"
            ).fetchall()
            return [r[0] for r in rows]

    def get_burst_group_count(self) -> int:
        """Return the number of distinct burst groups."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT burst_group) FROM photos "
                "WHERE burst_group IS NOT NULL"
            ).fetchone()
            return row[0] if row else 0

    def get_burst_group_size(self, group_id: str) -> int:
        """Return the number of photos in a specific burst group."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE burst_group = ?",
                (group_id,),
            ).fetchone()
            return row[0] if row else 0

    # ---- Best-in-burst / Best-in-duplicate methods ----

    def update_best_in_burst(self, image_id: str, is_best: int) -> bool:
        """Set the is_best_in_burst flag for a photo (1 = recommended, 0 = not).

        Returns True if a row was updated.
        """
        return self._update_fields(image_id, is_best_in_burst=is_best)

    def update_best_in_duplicate(self, image_id: str, is_best: int) -> bool:
        """Set the is_best_in_duplicate flag for a photo (1 = recommended, 0 = not).

        Returns True if a row was updated.
        """
        return self._update_fields(image_id, is_best_in_duplicate=is_best)

    def get_best_photos(self) -> list:
        """Retrieve all best-recommended photos (burst OR duplicate best).

        Returns photos where is_best_in_burst == 1 OR is_best_in_duplicate == 1,
        ordered by is_best_in_burst DESC (burst best first), then created_time.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos "
                "WHERE is_best_in_burst = 1 OR is_best_in_duplicate = 1 "
                "ORDER BY is_best_in_burst DESC, created_time"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_burst_best_count(self) -> int:
        """Return the count of recommended photos (burst best + duplicate best)."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos "
                "WHERE is_best_in_burst = 1 OR is_best_in_duplicate = 1"
            ).fetchone()
            return row[0] if row else 0

    # ---- Unprocessed photos (not starred, not rejected) ----

    # ---- Closed-eye methods ----

    def get_closed_eye_photos(self) -> list:
        """Retrieve all photos with is_closed_eye == 1, sorted by eye_score ASC (worst first)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos WHERE is_closed_eye = 1 "
                "ORDER BY eye_score ASC, created_time"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_closed_eye_count(self) -> int:
        """Return the count of photos with is_closed_eye == 1."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE is_closed_eye = 1"
            ).fetchone()
            return row[0] if row else 0

    # ---- Unprocessed photos ----

    def get_unprocessed_photos(self) -> list:
        """Retrieve photos that are neither starred nor rejected, ordered by created_time."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos "
                "WHERE (star_rating IS NULL OR star_rating != 1) "
                "AND is_rejected != 1 ORDER BY created_time"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_unprocessed_count(self) -> int:
        """Return the count of unprocessed photos."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos "
                "WHERE (star_rating IS NULL OR star_rating != 1) "
                "AND is_rejected != 1"
            ).fetchone()
            return row[0] if row else 0

    def get_unanalyzed_photos(self) -> list:
        """Retrieve photos that have never been analysed (analyzed_at IS NULL),
        ordered by created_time."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos "
                "WHERE analyzed_at IS NULL ORDER BY created_time"
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_unanalyzed_count(self) -> int:
        """Return the count of unanalyzed photos."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE analyzed_at IS NULL"
            ).fetchone()
            return row[0] if row else 0

    def reset_cull_results(self) -> tuple:
        """Clear non-manual star and reject statuses.

        Removes star_rating and is_rejected from photos that were set by a
        previous cull run, so a re-analysis followed by re-cull produces
        correct results.  Photos with manually_operated_at set (hand-picked
        by the photographer) are always preserved.

        Returns (stars_reset, rejects_reset) counts.
        """
        with self._get_conn() as conn:
            stars = conn.execute(
                "UPDATE photos SET star_rating = 0"
                " WHERE star_rating >= 1 AND manually_operated_at IS NULL"
            ).rowcount
            rejects = conn.execute(
                "UPDATE photos SET is_rejected = 0"
                " WHERE is_rejected >= 1 AND manually_operated_at IS NULL"
            ).rowcount
            return stars, rejects

    def get_ai_summary(self) -> dict:
        """Return a comprehensive summary of AI analysis results.

        Returns a dict with keys:
          total_analyzed, closed_eye_count, blur_count,
          burst_group_count, burst_photo_count,
          duplicate_group_count, duplicate_photo_count,
          best_count, clean_count
        """
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE analyzed_at IS NOT NULL"
            ).fetchone()[0]

            eye = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE is_closed_eye = 1"
            ).fetchone()[0]

            blur = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE is_blur = 1"
            ).fetchone()[0]

            burst_groups = conn.execute(
                "SELECT COUNT(DISTINCT burst_group) FROM photos "
                "WHERE burst_group IS NOT NULL"
            ).fetchone()[0]

            burst_photos = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE burst_group IS NOT NULL"
            ).fetchone()[0]

            dup_groups = conn.execute(
                "SELECT COUNT(DISTINCT duplicate_group) FROM photos "
                "WHERE duplicate_group IS NOT NULL"
            ).fetchone()[0]

            dup_photos = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE is_duplicate = 1"
            ).fetchone()[0]

            best = conn.execute(
                "SELECT COUNT(*) FROM photos "
                "WHERE is_best_in_burst = 1 OR is_best_in_duplicate = 1"
            ).fetchone()[0]

            # Clean = analysed photos with NO defects
            clean = conn.execute(
                "SELECT COUNT(*) FROM photos "
                "WHERE analyzed_at IS NOT NULL "
                "AND is_closed_eye = 0 "
                "AND is_blur = 0 "
                "AND burst_group IS NULL "
                "AND is_duplicate = 0"
            ).fetchone()[0]

        return {
            "total_analyzed": total,
            "closed_eye_count": eye,
            "blur_count": blur,
            "burst_group_count": burst_groups,
            "burst_photo_count": burst_photos,
            "duplicate_group_count": dup_groups,
            "duplicate_photo_count": dup_photos,
            "best_count": best,
            "clean_count": clean,
        }

    def mark_analyzed(self, image_id: str) -> bool:
        """Mark a photo as analysed by setting analyzed_at to now."""
        return self._update_fields(
            image_id,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )

    # ---- RAW+JPEG pairing methods ----

    def update_raw_jpeg_pair(self, image_id: str, pair_id: Optional[str]) -> bool:
        """Set or clear the raw_jpeg_pair_id for a photo."""
        return self._update_fields(image_id, raw_jpeg_pair_id=pair_id)

    def update_raw_jpeg_pairs_batch(self, pairs: dict[str, Optional[str]]) -> int:
        """Batch update raw_jpeg_pair_id for multiple photos in a single transaction.

        Args:
            pairs: dict mapping image_id → pair_id (or None to clear).

        Returns the number of rows updated.
        """
        if not pairs:
            return 0
        updated = 0
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            for image_id, pair_id in pairs.items():
                cursor = conn.execute(
                    "UPDATE photos SET raw_jpeg_pair_id = ?, updated_at = ? WHERE image_id = ?",
                    (pair_id, now, image_id),
                )
                updated += cursor.rowcount
        return updated

    def get_photos_by_raw_jpeg_pair(self, pair_id: str) -> list:
        """Retrieve all photos in a specific RAW+JPEG pair group."""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT {PhotoRecord.column_names()} FROM photos "
                "WHERE raw_jpeg_pair_id = ? ORDER BY file_name",
                (pair_id,),
            ).fetchall()
            return [PhotoRecord.from_row(r) for r in rows]

    def get_raw_jpeg_pair_count(self) -> int:
        """Return the count of distinct RAW+JPEG pair groups."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT raw_jpeg_pair_id) FROM photos "
                "WHERE raw_jpeg_pair_id IS NOT NULL"
            ).fetchone()
            return row[0] if row else 0

    def get_paired_photo_ids(self, image_id: str) -> list[str]:
        """Return the image_ids of all photos paired with *image_id* (excluding itself).

        Returns an empty list if the photo has no raw_jpeg_pair_id or no other members.
        """
        photo = self.get_photo_by_id(image_id)
        if not photo or not photo.raw_jpeg_pair_id:
            return []
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT image_id FROM photos WHERE raw_jpeg_pair_id = ? AND image_id != ?",
                (photo.raw_jpeg_pair_id, image_id),
            ).fetchall()
            return [r[0] for r in rows]

    # ---- Blur patch_scores cache ----

    def update_patch_scores(self, image_id: str, scores_json: Optional[str]) -> bool:
        """Store or clear the cached patch_scores for a photo.

        Args:
            image_id: The photo's unique identifier.
            scores_json: JSON string with cached scores, or None to clear.

        Returns True if the row was updated.
        """
        # _update_fields filters out None values, so handle the clear
        # case with a direct UPDATE that explicitly sets NULL.
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE photos SET patch_scores = ?, updated_at = ? WHERE image_id = ?",
                (scores_json, now, image_id),
            )
            return cursor.rowcount > 0

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
