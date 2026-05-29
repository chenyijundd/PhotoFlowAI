"""
PhotoFlow AI — Export API Service

Endpoints for starting, polling, and cancelling exports.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.exporter.models import ExportStartRequest, ExportProgressResponse, ExportSummaryResponse
from backend.exporter.service import start_export, get_progress, cancel_export

logger = logging.getLogger("export")

router = APIRouter(prefix="/api/export", tags=["export"])


class ExportStartResult(BaseModel):
    export_id: str


@router.post("/start", response_model=ExportStartResult)
async def export_start(body: ExportStartRequest):
    """Start an export. Returns an export_id to poll for progress."""
    try:
        export_id = start_export(
            target_folder=body.target_folder,
            mode=body.mode,
            photo_ids=body.photo_ids,
        )
        return ExportStartResult(export_id=export_id)
    except Exception as exc:
        logger.error("Export start failed: %s", exc)
        raise HTTPException(status_code=500, detail="Export start failed")


@router.get("/progress/{export_id}", response_model=ExportProgressResponse)
async def export_progress(export_id: str):
    """Get the current progress of an export."""
    state = get_progress(export_id)
    if not state:
        raise HTTPException(status_code=404, detail="Export not found")

    return ExportProgressResponse(
        export_id=state["export_id"],
        status=state["status"],
        total=state["total"],
        succeeded=state["succeeded"],
        failed=state["failed"],
        skipped=state["skipped"],
        current_file=state["current_file"],
        duration_seconds=state.get("duration_seconds", 0.0),
    )


@router.post("/cancel/{export_id}")
async def export_cancel(export_id: str):
    """Cancel a running export."""
    ok = cancel_export(export_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Export not found or already completed")
    return {"status": "cancelled"}


@router.get("/summary/{export_id}", response_model=ExportSummaryResponse)
async def export_summary(export_id: str):
    """Get the final summary of an export."""
    state = get_progress(export_id)
    if not state:
        raise HTTPException(status_code=404, detail="Export not found")
    if state["status"] == "running":
        raise HTTPException(status_code=400, detail="Export still running")

    return ExportSummaryResponse(
        export_id=state["export_id"],
        status=state["status"],
        total=state["total"],
        succeeded=state["succeeded"],
        failed=state["failed"],
        skipped=state["skipped"],
        duration_seconds=state.get("duration_seconds", 0.0),
        errors=state.get("errors", []),
    )
