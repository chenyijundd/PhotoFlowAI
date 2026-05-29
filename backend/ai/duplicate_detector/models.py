"""PhotoFlow AI - Duplicate Detection Pydantic Models."""

from pydantic import BaseModel


from typing import Optional


class DuplicateDetectRequest(BaseModel):
    photo_ids: Optional[list[str]] = None  # None = process all photos


class DuplicateDetectResponse(BaseModel):
    processed: int
    duplicate_groups: int
    duplicates: int
