"""
PhotoFlow AI — Suggestion Models

Data models for the AI suggestion system.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class SuggestionType(str, Enum):
    """Valid suggestion types. A photo can have at most one suggestion."""
    POSSIBLE_BLUR = "POSSIBLE_BLUR"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    POSSIBLE_BEST = "POSSIBLE_BEST"


class GenerateSuggestionsRequest(BaseModel):
    """Request body for POST /api/ai/generate-suggestions."""
    photo_ids: Optional[list[str]] = None


class GenerateSuggestionsResponse(BaseModel):
    """Response from suggestion generation."""
    processed: int
    suggestions_generated: int
    suggestion_counts: dict  # { "POSSIBLE_BLUR": N, "POSSIBLE_DUPLICATE": M, ... }


class SuggestionResult:
    """Internal result for a single photo's suggestion evaluation."""
    def __init__(self, image_id: str, suggestion: Optional[str]):
        self.image_id = image_id
        self.suggestion = suggestion
