"""
PhotoFlow AI - Detection Sensitivity Presets

Provides three pre-configured sensitivity profiles (严格/标准/宽松) that adjust
all 13 detection thresholds across the 5 AI modules simultaneously.

Usage:
    from backend.config.presets import get_preset, get_active_preset, PRESETS

    preset = get_active_preset()
    thresholds = preset.thresholds
    # Pass thresholds to detectors...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Threshold data class
# ---------------------------------------------------------------------------


@dataclass
class PresetThresholds:
    """All tunable thresholds for a single sensitivity preset."""

    # ---- Eye detection ----
    blink_score_threshold: float = 0.55
    ear_closed_threshold: float = 0.18
    ear_half_closed_threshold: float = 0.20

    # ---- Blur detection ----
    blur_threshold: float = 25.0
    preview_sharp_threshold: float = 80.0
    preview_blur_threshold: float = 25.0

    # ---- Duplicate detection ----
    hamming_prefilter: int = 15
    ssim_threshold: float = 0.60
    time_window_gap: float = 300.0

    # ---- Burst grouping ----
    burst_gap_seconds: float = 2.0
    min_burst_size: int = 2

    # ---- Best selector ----
    blur_tie_pct: float = 0.10
    size_tie_pct: float = 0.20


@dataclass
class Preset:
    """A named sensitivity preset with human-readable description."""

    id: str
    name: str
    description: str
    thresholds: PresetThresholds = field(default_factory=PresetThresholds)


# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

PRESETS: dict[str, Preset] = {
    "strict": Preset(
        id="strict",
        name="严格",
        description="重要场合（仪式、合影）— 宁可多标、不可漏过。检出量最多，适合不想错过任何好照片的场景。",
        thresholds=PresetThresholds(
            # Eye: easier to flag → more closed-eye detected
            blink_score_threshold=0.45,
            ear_closed_threshold=0.22,
            ear_half_closed_threshold=0.24,
            # Blur: easier to flag → more blurry
            blur_threshold=35.0,
            preview_sharp_threshold=60.0,
            preview_blur_threshold=35.0,
            # Duplicate: wider net → more duplicates
            hamming_prefilter=20,
            ssim_threshold=0.50,
            time_window_gap=600.0,
            # Burst: wider window → more groups
            burst_gap_seconds=3.0,
            min_burst_size=2,
            # Best: wider ties → more photos get recommended
            blur_tie_pct=0.20,
            size_tie_pct=0.30,
        ),
    ),
    "standard": Preset(
        id="standard",
        name="标准",
        description="日常选片 — 均衡配置，适合大多数婚礼场景。推荐默认使用。",
        thresholds=PresetThresholds(
            # Eye: current defaults
            blink_score_threshold=0.55,
            ear_closed_threshold=0.18,
            ear_half_closed_threshold=0.20,
            # Blur: current defaults
            blur_threshold=25.0,
            preview_sharp_threshold=80.0,
            preview_blur_threshold=25.0,
            # Duplicate: current defaults
            hamming_prefilter=15,
            ssim_threshold=0.60,
            time_window_gap=300.0,
            # Burst: current defaults
            burst_gap_seconds=2.0,
            min_burst_size=2,
            # Best: current defaults
            blur_tie_pct=0.10,
            size_tie_pct=0.20,
        ),
    ),
    "lenient": Preset(
        id="lenient",
        name="宽松",
        description="快速过片（准备花絮、宾客抓拍）— 疑罪从无，只标明确缺陷。检出量最少，减少假阳性干扰。",
        thresholds=PresetThresholds(
            # Eye: harder to flag → fewer closed-eye
            blink_score_threshold=0.70,
            ear_closed_threshold=0.15,
            ear_half_closed_threshold=0.17,
            # Blur: harder to flag → fewer blurry
            blur_threshold=18.0,
            preview_sharp_threshold=100.0,
            preview_blur_threshold=18.0,
            # Duplicate: stricter → fewer duplicates
            hamming_prefilter=10,
            ssim_threshold=0.70,
            time_window_gap=120.0,
            # Burst: narrower window → fewer groups
            burst_gap_seconds=1.5,
            min_burst_size=2,
            # Best: narrower ties → more decisive
            blur_tie_pct=0.05,
            size_tie_pct=0.10,
        ),
    ),
}

DEFAULT_PRESET_ID = "standard"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_preset(preset_id: str) -> Preset:
    """Get a preset by ID. Falls back to 'standard' if the ID is unknown."""
    return PRESETS.get(preset_id, PRESETS[DEFAULT_PRESET_ID])


def list_presets() -> list[Preset]:
    """Return all available presets ordered by id."""
    return [PRESETS[k] for k in ("strict", "standard", "lenient")]


def get_active_preset_id() -> str:
    """Read the active preset ID from the current project's config table.

    Returns ``"standard"`` if no preset has been saved yet or if the
    database is not available (e.g. before a project is opened).
    """
    try:
        from database.repository import PhotoRepository

        repo = PhotoRepository()
        return repo.get_config("active_preset") or DEFAULT_PRESET_ID
    except Exception:
        return DEFAULT_PRESET_ID


def get_active_preset() -> Preset:
    """Return the full Preset object for the active preset."""
    return get_preset(get_active_preset_id())


def set_active_preset(preset_id: str) -> Preset:
    """Persist the active preset ID and return the corresponding Preset.

    Silently falls back to ``"standard"`` when *preset_id* is unknown.
    """
    preset = get_preset(preset_id)
    try:
        from database.repository import PhotoRepository

        repo = PhotoRepository()
        repo.set_config("active_preset", preset.id)
    except Exception:
        pass  # best-effort — preset still returned even if DB write fails
    return preset
