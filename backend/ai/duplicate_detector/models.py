"""PhotoFlow AI - Duplicate Detection Pydantic Models."""

from pydantic import BaseModel


class DuplicateDetectRequest(BaseModel):
    photo_ids: list[str]


class DuplicateDetectResponse(BaseModel):
    processed: int
    duplicate_groups: int
    duplicates: int
