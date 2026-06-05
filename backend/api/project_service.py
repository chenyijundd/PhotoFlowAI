"""
PhotoFlow AI - Project API Service

REST endpoints for multi-project management:
  - List / create / open / close / archive / delete projects.
  - Query the currently-open project.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.project_manager import get_project_manager, ProjectInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    name: str
    photo_dir: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    db_path: str
    photo_dir: Optional[str] = None
    created_at: str
    last_opened_at: Optional[str] = None
    archived: bool = False
    photo_count: int = 0
    picked_count: int = 0

    @classmethod
    def from_info(cls, p: ProjectInfo) -> "ProjectResponse":
        return cls(**p.to_dict())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_projects(include_archived: bool = False):
    """List all projects, most recently opened first."""
    manager = get_project_manager()
    projects = manager.list_projects(include_archived=include_archived)
    return {
        "projects": [ProjectResponse.from_info(p).dict() for p in projects],
    }


@router.post("")
async def create_project(body: CreateProjectRequest):
    """Create a new project with an independent database file.

    The project database is initialised with the standard schema immediately.
    """
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")

    manager = get_project_manager()
    project = manager.create_project(
        name=body.name.strip(),
        photo_dir=body.photo_dir,
    )
    return ProjectResponse.from_info(project).dict()


@router.post("/{project_id}/open")
async def open_project(project_id: str):
    """Open a project — subsequent photo/data API calls use this project's database."""
    manager = get_project_manager()
    try:
        project = manager.open_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Refresh stats after open
    manager.refresh_current_stats()
    current = manager.current_project
    return ProjectResponse.from_info(current).dict() if current else {}


@router.post("/close")
async def close_project():
    """Close the current project — reverts to the legacy default database."""
    manager = get_project_manager()
    manager.close_project()
    return {"status": "ok"}


@router.post("/{project_id}/archive")
async def archive_project(project_id: str, archive: bool = True):
    """Archive (or un-archive) a project."""
    manager = get_project_manager()
    ok = manager.archive_project(project_id, archived=archive)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return {"status": "ok", "archived": archive}


@router.delete("/{project_id}")
async def delete_project(project_id: str, delete_db: bool = False):
    """Delete a project from the meta-database.

    Set *delete_db=true* to also remove the project's .photoflow file from disk.
    """
    manager = get_project_manager()
    try:
        ok = manager.delete_project(project_id, delete_db=delete_db)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return {"status": "ok"}


@router.post("/current/clear")
async def clear_current_project_photos():
    """Clear all photos from the currently-open project. Does NOT delete local files."""
    manager = get_project_manager()
    if manager.current_project is None:
        raise HTTPException(status_code=400, detail="No project is currently open.")
    return _do_clear(manager, manager.current_project.id, manager.current_project)


@router.post("/{project_id}/clear")
async def clear_project_photos(project_id: str):
    """Clear all photos from a project. Does NOT delete local image files.

    Only removes the database records and cached thumbnails.  The original
    photos on disk are never touched.
    """
    import os as _os

    manager = get_project_manager()
    project = _do_clear(manager, project_id, manager.get_project(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return project


def _do_clear(manager, project_id: str, project):
    """Internal: clear all photos from a project database. Returns response dict."""
    import os as _os

    if project is None:
        return None

    from database.repository import PhotoRepository
    repo = PhotoRepository(db_path=project.db_path)
    all_photos = repo.get_all_photos()
    image_ids = [p.image_id for p in all_photos]

    deleted = repo.clear_all()
    logger.info("Cleared %d photos from project '%s'", deleted, project.name)

    removed_thumbs = 0
    _cache_dir = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))),
        "cache", "thumbnails",
    )
    for image_id in image_ids:
        thumb_path = _os.path.join(_cache_dir, f"{image_id}.jpg")
        if _os.path.isfile(thumb_path):
            try:
                _os.remove(thumb_path)
                removed_thumbs += 1
            except OSError:
                pass

    manager._refresh_project_stats(project.db_path)

    return {
        "status": "ok",
        "deleted": deleted,
        "thumbnails_removed": removed_thumbs,
    }


@router.get("/current")
async def get_current_project():
    """Return the currently-open project, or null if no project is open."""
    manager = get_project_manager()
    current = manager.current_project
    if current is None:
        return {"project": None}
    return {"project": ProjectResponse.from_info(current).dict()}
