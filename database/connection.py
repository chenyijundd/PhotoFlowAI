"""
PhotoFlow AI - Database Connection Manager

Provides connection management with context manager support.
Auto-closes connections to prevent connection leaks.
"""

import os
import sqlite3
from typing import Optional

PHOTOS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS photos (
    image_id TEXT PRIMARY KEY,
    file_name TEXT,
    file_path TEXT,
    raw_preview_path TEXT DEFAULT NULL,
    thumbnail_path TEXT,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    created_time TEXT,

    blur_score REAL DEFAULT NULL,
    eye_score REAL DEFAULT NULL,
    duplicate_group TEXT DEFAULT NULL,

    is_blur INTEGER DEFAULT 0,
    is_closed_eye INTEGER DEFAULT 0,
    is_duplicate INTEGER DEFAULT 0,
    is_rejected INTEGER DEFAULT 0,

    star_rating INTEGER DEFAULT NULL,

    burst_group TEXT DEFAULT NULL,
    burst_position INTEGER DEFAULT NULL,
    is_best_in_burst INTEGER DEFAULT 0,
    is_best_in_duplicate INTEGER DEFAULT 0,
    manually_operated_at TEXT DEFAULT NULL,
    analyzed_at TEXT DEFAULT NULL,

    created_at TEXT,
    updated_at TEXT
);
"""


def get_default_db_path() -> str:
    """Compute the default database file path relative to this module."""
    db_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(db_dir, "photoflow.db")


class DatabaseConnection:
    """Context manager for SQLite database connections.

    Usage:
        with DatabaseConnection() as conn:
            conn.execute("SELECT ...")
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_default_db_path()
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._conn is None:
            return
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
            self._conn = None


def init_database(db_path: Optional[str] = None) -> str:
    """Initialize the database with the photos table.

    If the table already exists with the correct schema, this is a no-op.
    If it exists with a different schema (e.g. from an earlier version),
    the old table is dropped and recreated.

    Returns the database path.
    """
    path = db_path or get_default_db_path()
    with DatabaseConnection(path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='photos'"
        )
        if cursor.fetchone() is None:
            conn.execute(PHOTOS_TABLE_SQL)
        else:
            cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(photos)").fetchall()
            }
            if "image_id" not in cols:
                conn.execute("DROP TABLE photos")
                conn.execute(PHOTOS_TABLE_SQL)
            else:
                # Migration: add is_rejected column if missing (v0.3.0)
                if "is_rejected" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN is_rejected INTEGER DEFAULT 0"
                    )

                # Migration: add duplicate columns if missing
                if "duplicate_group" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN duplicate_group TEXT DEFAULT NULL"
                    )
                if "is_duplicate" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN is_duplicate INTEGER DEFAULT 0"
                    )

                # Migration: add burst_group column if missing
                if "burst_group" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN burst_group TEXT DEFAULT NULL"
                    )

                # Migration: add burst_position column if missing
                if "burst_position" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN burst_position INTEGER DEFAULT NULL"
                    )

                # Migration: add is_best_in_burst column if missing
                if "is_best_in_burst" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN is_best_in_burst INTEGER DEFAULT 0"
                    )

                # Migration: add is_best_in_duplicate column if missing
                if "is_best_in_duplicate" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN is_best_in_duplicate INTEGER DEFAULT 0"
                    )

                # Migration: add manually_operated_at column if missing (v1.0 — photo sorting)
                if "manually_operated_at" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN manually_operated_at TEXT DEFAULT NULL"
                    )

                # Migration: add analyzed_at column if missing (v1.1 — incremental analysis)
                if "analyzed_at" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN analyzed_at TEXT DEFAULT NULL"
                    )

                # Migration: add raw_preview_path column if missing (v1.2 — RAW support)
                if "raw_preview_path" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN raw_preview_path TEXT DEFAULT NULL"
                    )
    return path
