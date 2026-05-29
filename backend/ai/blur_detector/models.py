"""PhotoFlow AI - Blur Detection Pydantic Models."""

from pydantic import BaseModel


from typing import Optional


class BlurDetectRequest(BaseModel):
    photo_ids: Optional[list[str]] = None  # None = process all photos


class BlurDetectResponse(BaseModel):
    processed: int
    blurred: int
