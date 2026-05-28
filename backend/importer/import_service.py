"""
PhotoFlow AI - Import API Service

FastAPI endpoint for triggering the photo import workflow.
"""

import os
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .workflow import import_directory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["import"])


class ImportRequest(BaseModel):
    directory: str


@router.post("/import")
async def import_photos(req: ImportRequest):
    """Scan a directory and import all photos into the application.

    Returns import statistics (total, imported, skipped, errors).
    """
    directory = req.directory

    if not os.path.isdir(directory):
        raise HTTPException(
            status_code=400, detail=f"Directory not found: {directory}"
        )

    try:
        result = import_directory(directory)
        result["success"] = True
        return result
    except Exception as exc:
        logger.error("Import failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
