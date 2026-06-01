"""
PhotoFlow AI — Export Models

Data models for the professional export workflow.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ExportMode(str, Enum):
    """Valid export modes."""
    PICKED = "picked"           # star_rating == 1 AND is_rejected == false
    REJECTED = "rejected"       # is_rejected == true
    CURRENT_FILTER = "current_filter"  # photos specified by ID list
    COMPARE = "compare"         # current duplicate group


class ExportFormat(str, Enum):
    """Output file format for export."""
    ORIGINAL = "original"  # Keep source format (default)
    JPEG = "jpeg"
    PNG = "png"


class ExportStartRequest(BaseModel):
    """Request to start an export."""
    target_folder: str
    mode: ExportMode
    photo_ids: Optional[list[str]] = None  # Required for compare mode
    filter_mode: Optional[str] = None  # "all" | "starred" | "unprocessed" | "rejected" — resolves full list server-side

    # Naming template fields
    name_template: Optional[str] = None  # "original" (default) | "custom_index" | "custom_date_index"
    name_prefix: Optional[str] = None    # Custom text for {custom} placeholder
    start_index: Optional[int] = None    # Starting sequence number (default 1)

    # Output format
    export_format: Optional[ExportFormat] = ExportFormat.ORIGINAL  # "original" | "jpeg" | "png"


class ExportProgressResponse(BaseModel):
    """Current export progress."""
    export_id: str
    status: str  # "running" | "completed" | "cancelled" | "error"
    total: int
    succeeded: int
    failed: int
    skipped: int
    current_file: str
    duration_seconds: float


class ExportSummaryResponse(BaseModel):
    """Final export summary."""
    export_id: str
    status: str
    total: int
    succeeded: int
    failed: int
    skipped: int
    duration_seconds: float
    errors: list[str]
