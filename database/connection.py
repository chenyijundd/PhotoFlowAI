"""
PhotoFlow AI - Database Connection Manager

Provides connection management with context manager support and connection pooling.
Connections are pooled per-thread to avoid repeated connect/close overhead.
"""

import os
import sqlite3
import threading
from typing import Optional, Dict

PHOTOS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS photos (
    image_id TEXT PRIMARY KEY,
    file_name TEXT,
    file_path TEXT,
    raw_preview_path TEXT DEFAULT NULL,
    raw_jpeg_pair_id TEXT DEFAULT NULL,
    patch_scores TEXT DEFAULT NULL,
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
    updated_at TEXT,
    deleted_at TEXT DEFAULT NULL
);
"""


# ---------------------------------------------------------------------------
# Connection Pool — thread-local reuse to eliminate repeated connect/close
# ---------------------------------------------------------------------------

# Module-level registry: one pool per database file path
_pools: Dict[str, "ConnectionPool"] = {}
_pools_lock = threading.Lock()


class ConnectionPool:
    """Thread-local SQLite connection pool.

    Each thread that touches the database gets one reusable connection.
    SQLite WAL mode allows concurrent reads/writes across threads, so
    one connection per thread is sufficient for typical workloads.

    The connection is never closed until the pool is shut down — the
    DatabaseConnection context manager only commits/rollbacks on exit
    and leaves the underlying sqlite3.Connection alive for the next
    operation on the same thread.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._thread_local = threading.local()

    def _create_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @property
    def connection(self) -> sqlite3.Connection:
        """Get (or create) the reusable connection for the current thread."""
        conn = getattr(self._thread_local, "conn", None)
        if conn is None:
            conn = self._create_connection()
            self._thread_local.conn = conn
        return conn

    def close_thread(self) -> None:
        """Close the current thread's connection (e.g. on thread exit)."""
        conn = getattr(self._thread_local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._thread_local.conn = None

    def close_all(self) -> None:
        """Close this pool's connection(s). Safe to call at shutdown."""
        self.close_thread()


def get_pool(db_path: Optional[str] = None) -> ConnectionPool:
    """Get or create a ConnectionPool for *db_path*.

    Pools are singletons keyed by the resolved absolute path, so every
    caller that references the same database file shares the same pool.
    """
    path = db_path or get_default_db_path()
    path = os.path.abspath(path)
    with _pools_lock:
        if path not in _pools:
            _pools[path] = ConnectionPool(path)
        return _pools[path]


def close_all_pools() -> None:
    """Close every pooled connection across all database paths.

    Intended for graceful-shutdown hooks.  Connections left open at
    process exit are cleaned up by the OS anyway, so this is a
    best-effort hygiene measure.
    """
    with _pools_lock:
        for pool in _pools.values():
            pool.close_all()
        _pools.clear()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_default_db_path() -> str:
    """Compute the default database file path relative to this module."""
    db_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(db_dir, "photoflow.db")


class DatabaseConnection:
    """Context manager for SQLite database connections with **connection pooling**.

    Connections are obtained from a thread-local pool and **never closed**
    by this context manager — only committed (on success) or rolled back
    (on exception).  The underlying sqlite3.Connection stays alive for
    the next operation on the same thread, eliminating the repeated
    cost of ``sqlite3.connect()`` / ``.close()``.

    Usage (identical to pre-pool version)::

        with DatabaseConnection() as conn:
            conn.execute("SELECT ...")
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        pool = get_pool(self.db_path)
        self._conn = pool.connection
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
            # IMPORTANT: do NOT close — the connection belongs to the pool.
            # Just drop our local reference so the object can be GC'd.
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

                # Migration: add raw_jpeg_pair_id column if missing (v1.3 — RAW+JPEG pairing)
                if "raw_jpeg_pair_id" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN raw_jpeg_pair_id TEXT DEFAULT NULL"
                    )

                # Migration: add patch_scores column if missing (v1.4 — blur cache)
                if "patch_scores" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN patch_scores TEXT DEFAULT NULL"
                    )

                # Migration: add deleted_at column if missing (v1.5 — photo trash)
                if "deleted_at" not in cols:
                    conn.execute(
                        "ALTER TABLE photos ADD COLUMN deleted_at TEXT DEFAULT NULL"
                    )
    return path
