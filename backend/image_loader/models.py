"""
PhotoFlow AI - Image Scanner Data Models

Defines data structures for scanned image information.
All models use dataclasses for type safety and clarity.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class PhotoInfo:
    """Represents metadata for a single scanned image."""

    id: str
    file_name: str
    file_path: str
    file_size: int
    created_time: str
    width: int
    height: int

    def to_dict(self) -> dict:
        """Convert to a serializable dictionary."""
        return asdict(self)


@dataclass
class ScanResult:
    """Represents the complete result of a directory scan."""

    total_count: int
    photos: list[PhotoInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to a serializable dictionary."""
        return {
            "total_count": self.total_count,
            "photos": [p.to_dict() for p in self.photos],
            "errors": self.errors,
        }
