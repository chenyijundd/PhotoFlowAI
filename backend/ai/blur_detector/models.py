"""PhotoFlow AI - Blur Detection Pydantic Models."""

from pydantic import BaseModel


class BlurDetectRequest(BaseModel):
    photo_ids: list[str]


class BlurDetectResponse(BaseModel):
    processed: int
    blurred: int
