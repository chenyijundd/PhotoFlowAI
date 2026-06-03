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


@router.get("/current")
async def get_current_project():
    """Return the currently-open project, or null if no project is open."""
    manager = get_project_manager()
    current = manager.current_project
    if current is None:
        return {"project": None}
    return {"project": ProjectResponse.from_info(current).dict()}
