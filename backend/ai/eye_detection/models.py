"""
PhotoFlow AI - Eye Detection Data Models

Lightweight dataclasses for internal use (not Pydantic — those
live in the API layer).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PerFaceResult:
    """Eye state for a single detected face."""

    face_index: int
    """0-based index of this face in the image."""

    left_ear: float
    """Eye Aspect Ratio for the left eye (lower = more closed)."""

    right_ear: float
    """Eye Aspect Ratio for the right eye (lower = more closed)."""

    min_ear: float
    """Minimum EAR across both eyes."""

    is_closed: bool
    """True if either eye is below the half-closed threshold."""


@dataclass
class EyeDetectionResult:
    """Result for a single photo."""

    image_id: str
    """Database image_id of the photo."""

    file_path: str
    """Absolute path to the original image file."""

    eyes_open: bool
    """True if all detected eyes are open (no face = True)."""

    score: float
    """Lowest EAR across all faces (1.0 if no face detected).  Lower = more closed."""

    face_detected: bool
    """Whether at least one face was found in the image."""

    num_faces: int
    """Total number of faces detected."""

    closed_count: int
    """Number of faces with closed or half-closed eyes."""

    per_face: list[PerFaceResult] = field(default_factory=list)
    """Per-face EAR details."""

    processing_time_ms: float = 0.0
    """Wall-clock processing time in milliseconds."""


@dataclass
class EyeDetectionSummary:
    """Aggregated summary of a batch eye-detection run."""

    total: int = 0
    """Total number of photos processed."""

    closed: int = 0
    """Number of photos with at least one closed/half-closed eye."""

    open: int = 0
    """Number of photos where all eyes are open."""

    no_face: int = 0
    """Number of photos where no face was detected."""

    errors: int = 0
    """Number of photos that could not be processed."""

    avg_time_ms: float = 0.0
    """Average processing time per photo in milliseconds."""

    scores: list[float] = field(default_factory=list)
    """All final eye scores (for distribution analysis)."""
