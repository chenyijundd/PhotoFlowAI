"""
PhotoFlow AI - Thumbnail Cache Data Models
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ThumbnailResult:
    """Represents the result of a single thumbnail generation attempt."""

    image_id: str
    source_path: str
    thumbnail_path: Optional[str] = None
    success: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
