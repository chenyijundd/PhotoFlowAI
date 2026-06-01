"""
PhotoFlow AI - Blur Detector V2 Data Models

Lightweight dataclasses for internal use (not Pydantic — those
live in the API layer).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BlurDetectionResult:
    """Result for a single photo."""

    image_id: str
    """Database image_id of the photo."""

    file_path: str
    """Absolute path to the original image file."""

    blur_score: float
    """Composite sharpness score (higher = sharper)."""

    is_blur: int
    """1 if the photo is classified as blurry, else 0."""

    patch_scores: list[float] = field(default_factory=list)
    """Per‑patch Laplacian variance values (length = PATCH_GRID²)."""

    processing_time_ms: float = 0.0
    """Wall‑clock processing time in milliseconds."""


@dataclass
class BlurDetectionSummary:
    """Aggregated summary of a batch blur‑detection run."""

    total: int = 0
    """Total number of photos processed."""

    blurred: int = 0
    """Number of photos classified as blurry."""

    clear: int = 0
    """Number of photos classified as sharp."""

    errors: int = 0
    """Number of photos that could not be processed."""

    avg_time_ms: float = 0.0
    """Average processing time per photo in milliseconds."""

    scores: list[float] = field(default_factory=list)
    """All final blur scores (for distribution analysis)."""
