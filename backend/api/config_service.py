"""
PhotoFlow AI - Config API Service

Endpoints for reading and writing project-level configuration,
including detection sensitivity presets.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config.presets import (
    Preset,
    PresetThresholds,
    get_active_preset,
    get_preset,
    list_presets,
    set_active_preset,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


# ---- Response / Request models ----


class PresetThresholdsResponse(BaseModel):
    blink_score_threshold: float
    ear_closed_threshold: float
    ear_half_closed_threshold: float
    blur_threshold: float
    preview_sharp_threshold: float
    preview_blur_threshold: float
    hamming_prefilter: int
    ssim_threshold: float
    time_window_gap: float
    burst_gap_seconds: float
    min_burst_size: int
    blur_tie_pct: float
    size_tie_pct: float


class PresetResponse(BaseModel):
    id: str
    name: str
    description: str
    thresholds: PresetThresholdsResponse


class PresetListResponse(BaseModel):
    presets: list[PresetResponse]
    active_preset_id: str


class SetPresetRequest(BaseModel):
    preset_id: str


class SetPresetResponse(BaseModel):
    status: str
    active_preset_id: str
    preset_name: str


def _thresholds_to_response(t: PresetThresholds) -> PresetThresholdsResponse:
    return PresetThresholdsResponse(
        blink_score_threshold=t.blink_score_threshold,
        ear_closed_threshold=t.ear_closed_threshold,
        ear_half_closed_threshold=t.ear_half_closed_threshold,
        blur_threshold=t.blur_threshold,
        preview_sharp_threshold=t.preview_sharp_threshold,
        preview_blur_threshold=t.preview_blur_threshold,
        hamming_prefilter=t.hamming_prefilter,
        ssim_threshold=t.ssim_threshold,
        time_window_gap=t.time_window_gap,
        burst_gap_seconds=t.burst_gap_seconds,
        min_burst_size=t.min_burst_size,
        blur_tie_pct=t.blur_tie_pct,
        size_tie_pct=t.size_tie_pct,
    )


def _preset_to_response(p: Preset) -> PresetResponse:
    return PresetResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        thresholds=_thresholds_to_response(p.thresholds),
    )


# ---- Endpoints ----


@router.get("/presets", response_model=PresetListResponse)
async def list_all_presets():
    """Return all available sensitivity presets and the currently active one."""
    presets = list_presets()
    active_id = get_active_preset().id
    return PresetListResponse(
        presets=[_preset_to_response(p) for p in presets],
        active_preset_id=active_id,
    )


@router.get("/presets/active", response_model=PresetResponse)
async def get_active():
    """Return the currently active sensitivity preset."""
    return _preset_to_response(get_active_preset())


@router.put("/presets/active", response_model=SetPresetResponse)
async def set_active(body: SetPresetRequest):
    """Set the active sensitivity preset for the current project."""
    preset_id = body.preset_id
    if preset_id not in ("strict", "standard", "lenient"):
        raise HTTPException(
            status_code=422,
            detail=f"Unknown preset: '{preset_id}'. Valid values: strict, standard, lenient",
        )
    try:
        preset = set_active_preset(preset_id)
    except Exception as exc:
        logger.error("Failed to persist active preset: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save active preset")
    return SetPresetResponse(
        status="ok",
        active_preset_id=preset.id,
        preset_name=preset.name,
    )
