"""
PhotoFlow AI - Project Manager

Manages multiple projects, each backed by an independent SQLite database file.

Design:
  - A lightweight meta-database (projects.db) stored in the user's app-data
    directory tracks all projects and their database file paths.
  - A module-level singleton ProjectManager provides thread-safe access to
    the currently-open project.
  - When no project is explicitly opened, ``get_current_db_path()`` falls
    back to the legacy default database, preserving backward compatibility.

Usage::

    from backend.project_manager import (
        get_project_manager,
        get_current_db_path,
    )

    # List all projects
    projects = get_project_manager().list_projects()

    # Open a project — subsequent PhotoRepository() calls use its database
    get_project_manager().open_project(project_id)

    # All existing code continues to work:
    repo = PhotoRepository()  # → uses current project's db_path
"""

import os
import sqlite3
import threading
import uuid
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

from database.connection import get_default_db_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Meta-database location — stored alongside the default database
# ---------------------------------------------------------------------------

def _get_meta_db_path() -> str:
    """Path to the meta-database that tracks all projects."""
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(os.path.dirname(db_dir), "database")
    return os.path.join(db_dir, "projects.db")


_META_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    db_path TEXT NOT NULL,
    photo_dir TEXT,
    created_at TEXT NOT NULL,
    last_opened_at TEXT,
    archived INTEGER DEFAULT 0,
    photo_count INTEGER DEFAULT 0,
    picked_count INTEGER DEFAULT 0
);
"""

# ---------------------------------------------------------------------------
# Project data class
# ---------------------------------------------------------------------------


@dataclass
class ProjectInfo:
    """Lightweight representation of a project (row from meta-database)."""

    id: str
    name: str
    db_path: str
    photo_dir: Optional[str] = None
    created_at: str = ""
    last_opened_at: Optional[str] = None
    archived: bool = False
    photo_count: int = 0
    picked_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "db_path": self.db_path,
            "photo_dir": self.photo_dir,
            "created_at": self.created_at,
            "last_opened_at": self.last_opened_at,
            "archived": self.archived,
            "photo_count": self.photo_count,
            "picked_count": self.picked_count,
        }


# ---------------------------------------------------------------------------
# ProjectManager singleton
# ---------------------------------------------------------------------------

_manager: Optional["ProjectManager"] = None
_manager_lock = threading.Lock()


def get_project_manager() -> "ProjectManager":
    """Return the module-level ProjectManager singleton."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = ProjectManager()
        return _manager


def get_current_db_path() -> str:
    """Return the database path of the currently-open project.

    Falls back to the legacy default database when no project is open,
    preserving backward compatibility for single-project usage.
    """
    manager = get_project_manager()
    if manager._current_project is not None:
        return manager._current_project.db_path
    return get_default_db_path()


class ProjectManager:
    """Singleton manager for multi-project workflow.

    The meta-database (projects.db) lives alongside the default photoflow.db.
    Each project gets its own SQLite database file, conventionally with a
    ``.photoflow`` extension.
    """

    def __init__(self):
        self._meta_path = _get_meta_db_path()
        self._lock = threading.Lock()
        self._current_project: Optional[ProjectInfo] = None
        self._init_meta_db()
        logger.info("ProjectManager initialised — meta-db at %s", self._meta_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_meta_db(self) -> None:
        """Create the meta-database and projects table if they don't exist."""
        os.makedirs(os.path.dirname(self._meta_path), exist_ok=True)
        conn = sqlite3.connect(self._meta_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_META_TABLE_SQL)
            conn.commit()
        finally:
            conn.close()

    def _get_meta_conn(self) -> sqlite3.Connection:
        """Return a connection to the meta-database."""
        conn = sqlite3.connect(self._meta_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> ProjectInfo:
        return ProjectInfo(
            id=row["id"],
            name=row["name"],
            db_path=row["db_path"],
            photo_dir=row["photo_dir"],
            created_at=row["created_at"],
            last_opened_at=row["last_opened_at"],
            archived=bool(row["archived"]),
            photo_count=row["photo_count"] or 0,
            picked_count=row["picked_count"] or 0,
        )

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        photo_dir: Optional[str] = None,
    ) -> ProjectInfo:
        """Create a new project with its own database file.

        The database is created in the same directory as the default db,
        named ``<uuid>.photoflow``.
        """
        project_id = uuid.uuid4().hex[:12]
        db_dir = os.path.dirname(get_default_db_path())
        db_path = os.path.join(db_dir, f"{project_id}.photoflow")
        now = datetime.now(timezone.utc).isoformat()

        # Initialise the project database with the standard schema
        from database.connection import init_database as init_project_db
        init_project_db(db_path)

        conn = self._get_meta_conn()
        try:
            conn.execute(
                "INSERT INTO projects (id, name, db_path, photo_dir, created_at, last_opened_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, name, db_path, photo_dir, now, now),
            )
            conn.commit()
        finally:
            conn.close()

        project = ProjectInfo(
            id=project_id,
            name=name,
            db_path=db_path,
            photo_dir=photo_dir,
            created_at=now,
            last_opened_at=now,
        )
        logger.info("Created project '%s' (id=%s) at %s", name, project_id, db_path)
        return project

    def list_projects(self, include_archived: bool = False) -> list[ProjectInfo]:
        """Return all projects, most recently opened first."""
        conn = self._get_meta_conn()
        try:
            if include_archived:
                rows = conn.execute(
                    "SELECT * FROM projects ORDER BY last_opened_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM projects WHERE archived = 0 ORDER BY last_opened_at DESC"
                ).fetchall()
            return [self._row_to_project(r) for r in rows]
        finally:
            conn.close()

    def get_project(self, project_id: str) -> Optional[ProjectInfo]:
        """Return a single project by ID, or None."""
        conn = self._get_meta_conn()
        try:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            return self._row_to_project(row) if row else None
        finally:
            conn.close()

    def open_project(self, project_id: str) -> ProjectInfo:
        """Open a project — subsequent repo calls use its database.

        Raises ValueError if the project does not exist.
        """
        project = self.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        # Verify the project database file still exists
        if not os.path.isfile(project.db_path):
            raise FileNotFoundError(
                f"Project database not found: {project.db_path}. "
                "The file may have been moved or deleted."
            )

        # Run schema migrations (e.g. add missing columns from newer versions)
        from database.connection import init_database as init_project_db
        init_project_db(project.db_path)

        with self._lock:
            self._current_project = project

        # Update last_opened_at
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_meta_conn()
        try:
            conn.execute(
                "UPDATE projects SET last_opened_at = ? WHERE id = ?",
                (now, project_id),
            )
            conn.commit()
        finally:
            conn.close()

        # Refresh stats from the project database
        self._refresh_project_stats(project.db_path)

        logger.info("Opened project '%s' (id=%s)", project.name, project_id)
        return project

    def close_project(self) -> None:
        """Close the current project, reverting to default database.

        Refreshes photo/picked counts in the meta-database before closing
        so the project list always shows up-to-date stats.
        """
        with self._lock:
            if self._current_project:
                # Save current stats to meta-db before closing
                self._refresh_project_stats(self._current_project.db_path)
                logger.info(
                    "Closed project '%s' (id=%s)",
                    self._current_project.name,
                    self._current_project.id,
                )
            self._current_project = None

    def archive_project(self, project_id: str, archived: bool = True) -> bool:
        """Set or clear the archived flag on a project."""
        conn = self._get_meta_conn()
        try:
            cursor = conn.execute(
                "UPDATE projects SET archived = ? WHERE id = ?",
                (1 if archived else 0, project_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_project(self, project_id: str, delete_db: bool = False) -> bool:
        """Delete a project from the meta-database.

        If *delete_db* is True, also removes the project's database file.
        The currently-open project cannot be deleted.
        """
        with self._lock:
            if self._current_project and self._current_project.id == project_id:
                raise RuntimeError("Cannot delete the currently-open project. Close it first.")

        project = self.get_project(project_id)
        if project is None:
            return False

        conn = self._get_meta_conn()
        try:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
        finally:
            conn.close()

        if delete_db and os.path.isfile(project.db_path):
            # Close any pooled connections to the project database before
            # attempting deletion (Windows locks open files).
            from database.connection import _pools, _pools_lock
            abs_path = os.path.abspath(project.db_path)
            with _pools_lock:
                pool = _pools.pop(abs_path, None)
            if pool:
                pool.close_all()

            try:
                os.remove(project.db_path)
                # Also remove WAL/SHM files if present
                for suffix in ("-wal", "-shm"):
                    wal = project.db_path + suffix
                    if os.path.isfile(wal):
                        os.remove(wal)
            except OSError as exc:
                logger.warning("Failed to delete project db %s: %s", project.db_path, exc)

        logger.info("Deleted project '%s' (id=%s)", project.name, project_id)
        return True

    @property
    def current_project(self) -> Optional[ProjectInfo]:
        """The currently-open project, or None."""
        return self._current_project

    @property
    def is_project_open(self) -> bool:
        """True if a project is currently open."""
        return self._current_project is not None

    # ------------------------------------------------------------------
    # Stats refresh
    # ------------------------------------------------------------------

    def _refresh_project_stats(self, db_path: str) -> None:
        """Pull photo_count and picked_count from a project database."""
        try:
            from database.repository import PhotoRepository
            repo = PhotoRepository(db_path=db_path)
            all_photos = repo.get_all_photos()
            photo_count = len(all_photos)
            picked_count = sum(
                1 for p in all_photos
                if p.star_rating is not None and p.star_rating >= 1
            )
            conn = self._get_meta_conn()
            try:
                conn.execute(
                    "UPDATE projects SET photo_count = ?, picked_count = ? WHERE db_path = ?",
                    (photo_count, picked_count, db_path),
                )
                conn.commit()
            finally:
                conn.close()

            # Update in-memory project if it's the current one
            if self._current_project and self._current_project.db_path == db_path:
                self._current_project.photo_count = photo_count
                self._current_project.picked_count = picked_count
        except Exception:
            logger.warning("Failed to refresh stats for %s", db_path, exc_info=True)

    def refresh_current_stats(self) -> None:
        """Refresh photo_count / picked_count for the currently-open project."""
        if self._current_project:
            self._refresh_project_stats(self._current_project.db_path)
