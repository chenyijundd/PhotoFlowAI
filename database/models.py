"""
PhotoFlow AI - Database Data Models

Defines data structures for database operations.
All models use dataclasses with full type annotations.
"""

from dataclasses import dataclass, asdict
from typing import Optional

import sqlite3


PHOTO_COLUMNS = (
    "image_id",
    "file_name",
    "file_path",
    "thumbnail_path",
    "file_size",
    "width",
    "height",
    "created_time",
    "blur_score",
    "eye_score",
    "duplicate_group",
    "is_blur",
    "is_closed_eye",
    "is_duplicate",
    "is_rejected",
    "star_rating",
    "created_at",
    "updated_at",
)


@dataclass
class PhotoRecord:
    """Represents a photo record in the database."""

    image_id: str
    file_name: str
    file_path: str
    thumbnail_path: Optional[str] = None
    file_size: int = 0
    width: int = 0
    height: int = 0
    created_time: Optional[str] = None
    blur_score: Optional[float] = None
    eye_score: Optional[float] = None
    duplicate_group: Optional[str] = None
    is_blur: int = 0
    is_closed_eye: int = 0
    is_duplicate: int = 0
    is_rejected: int = 0
    star_rating: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to a serializable dictionary, omitting None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_row_values(self) -> tuple:
        """Return column values in PHOTO_COLUMNS order for SQL insertion."""
        return tuple(getattr(self, col) for col in PHOTO_COLUMNS)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "PhotoRecord":
        """Create a PhotoRecord from a sqlite3.Row object."""
        return cls(**dict(row))

    @classmethod
    def column_names(cls) -> str:
        """Return comma-separated column names for SQL statements."""
        return ", ".join(PHOTO_COLUMNS)

    @classmethod
    def placeholders(cls) -> str:
        """Return SQL placeholders for all columns."""
        return ", ".join("?" for _ in PHOTO_COLUMNS)

    @classmethod
    def update_set_clause(cls, *fields: str) -> str:
        """Return SET clause for UPDATE, e.g. \"blur_score = ?, is_blur = ?\"."""
        return ", ".join(f"{f} = ?" for f in fields)
