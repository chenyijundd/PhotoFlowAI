"""
PhotoFlow AI - AI API Service

Endpoints for AI-based photo analysis (blur detection, duplicate detection, etc.).

All detection tasks run in background threads. The start endpoint returns a
task_id immediately, and the frontend polls GET /api/ai/{type}-progress/{id}.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.ai.blur_detector_v2.service import start_blur_detection_v2, get_blur_progress_v2, cancel_blur_detection_v2
from backend.ai.burst_grouper.service import start_burst_grouping, get_burst_progress, cancel_burst_grouping
from backend.ai.duplicate_detector.service import start_duplicate_detection, get_duplicate_progress, cancel_duplicate_detection
from backend.ai.best_selector.service import select_best_for_all_bursts, select_best_for_all_duplicates
from backend.ai.eye_detection.service import start_eye_detection, get_eye_progress, cancel_eye_detection

import threading
import uuid
from database.repository import PhotoRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


# ---- Response models ----

class TaskStartResponse(BaseModel):
    task_id: str
    total: int


class ProgressResponse(BaseModel):
    task_id: str
    status: str  # "running" | "completed" | "cancelled" | "error"
    phase: str
    total: int
    progress: int
    current_file: str
    # Blur-specific
    blurred: int = 0
    # Duplicate-specific
    duplicate_groups: int = 0
    duplicate_count: int = 0
    failed: int = 0


# ---- Blur Detection (multi-patch, content-aware) ----

class BlurDetectRequest(BaseModel):
    photo_ids: list[str] | None = None  # None or [] = process all
    threshold: float | None = None  # None = use module default


@router.post("/blur-detect-v2", response_model=TaskStartResponse)
async def blur_detect_v2_start(body: BlurDetectRequest = BlurDetectRequest()):
    """Start **v2** blur detection (multi-patch + centre-weighted) in background."""
    # Validate threshold range
    if body.threshold is not None:
        if body.threshold < 20.0 or body.threshold > 200.0:
            raise HTTPException(
                status_code=422,
                detail="threshold must be between 20.0 and 200.0",
            )

    try:
        repo = PhotoRepository()
        photo_ids = body.photo_ids
        if not photo_ids:
            all_photos = repo.get_all_photos()
            photo_ids = [p.image_id for p in all_photos]

        if not photo_ids:
            return TaskStartResponse(task_id="", total=0)

        task_id = start_blur_detection_v2(photo_ids, threshold=body.threshold)
        return TaskStartResponse(task_id=task_id, total=len(photo_ids))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Blur detection V2 start failed: %s", exc)
        raise HTTPException(status_code=500, detail="Blur detection V2 start failed")


@router.get("/blur-progress-v2/{task_id}", response_model=ProgressResponse)
async def blur_detect_v2_progress(task_id: str):
    """Poll v2 blur detection progress."""
    state = get_blur_progress_v2(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    return ProgressResponse(
        task_id=state["task_id"],
        status=state["status"],
        phase=state.get("phase", ""),
        total=state.get("total", 0),
        progress=state.get("progress", 0),
        current_file=state.get("current_file", ""),
        blurred=state.get("blurred", 0),
        failed=state.get("failed", 0),
    )


@router.post("/blur-cancel-v2/{task_id}")
async def blur_detect_v2_cancel(task_id: str):
    """Cancel a running v2 blur detection task."""
    ok = cancel_blur_detection_v2(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
    return {"status": "cancelled"}


# ---- Eye Detection (MediaPipe + EAR) ----

@router.post("/eye-detect", response_model=TaskStartResponse)
async def eye_detect_start(body: BlurDetectRequest = BlurDetectRequest()):
    """Start eye detection (closed / half-closed eyes) in background."""
    try:
        repo = PhotoRepository()
        photo_ids = body.photo_ids
        if not photo_ids:
            all_photos = repo.get_all_photos()
            photo_ids = [p.image_id for p in all_photos]

        if not photo_ids:
            return TaskStartResponse(task_id="", total=0)

        task_id = start_eye_detection(photo_ids)
        return TaskStartResponse(task_id=task_id, total=len(photo_ids))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Eye detection start failed: %s", exc)
        raise HTTPException(status_code=500, detail="Eye detection start failed")


@router.get("/eye-progress/{task_id}", response_model=ProgressResponse)
async def eye_detect_progress(task_id: str):
    """Poll eye detection progress."""
    state = get_eye_progress(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    return ProgressResponse(
        task_id=state["task_id"],
        status=state["status"],
        phase=state.get("phase", ""),
        total=state.get("total", 0),
        progress=state.get("progress", 0),
        current_file=state.get("current_file", ""),
        blurred=state.get("closed", 0),
        failed=state.get("failed", 0),
    )


@router.post("/eye-cancel/{task_id}")
async def eye_detect_cancel(task_id: str):
    """Cancel a running eye detection task."""
    ok = cancel_eye_detection(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
    return {"status": "cancelled"}


# ---- Burst Grouping (EXIF time-clustering) ----

class AnalyzeAllRequest(BaseModel):
    photo_ids: list[str] | None = None  # None = resolve via filter_mode (default: unanalyzed)
    filter_mode: str | None = None  # "unanalyzed" (default) | "unprocessed" | "all"


class BurstGroupRequest(BaseModel):
    gap_seconds: float | None = None  # None = use default (2.0)


@router.post("/burst-group", response_model=TaskStartResponse)
async def burst_group_start(body: BurstGroupRequest = BurstGroupRequest()):
    """Start burst grouping in background. Returns task_id for polling."""
    try:
        repo = PhotoRepository()
        task_id = start_burst_grouping(repo, gap_seconds=body.gap_seconds)
        return TaskStartResponse(task_id=task_id, total=0)
    except Exception as exc:
        logger.error("Burst grouping start failed: %s", exc)
        raise HTTPException(status_code=500, detail="Burst grouping start failed")


@router.get("/burst-progress/{task_id}", response_model=ProgressResponse)
async def burst_group_progress(task_id: str):
    """Poll burst grouping progress."""
    state = get_burst_progress(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    return ProgressResponse(
        task_id=state["task_id"],
        status=state["status"],
        phase=state.get("phase", ""),
        total=state.get("total", 0),
        progress=state.get("progress", 0),
        current_file=state.get("current_file", ""),
        duplicate_groups=state.get("burst_groups", 0),
        duplicate_count=state.get("photos_in_bursts", 0),
        failed=state.get("failed", 0),
    )


@router.post("/burst-cancel/{task_id}")
async def burst_group_cancel(task_id: str):
    """Cancel a running burst grouping task."""
    ok = cancel_burst_grouping(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
    return {"status": "cancelled"}


# ---- Duplicate Detection ----

@router.post("/duplicate-detect", response_model=TaskStartResponse)
async def duplicate_detect_start(body: BlurDetectRequest):
    """Start duplicate detection in background. Returns task_id for polling."""
    try:
        repo = PhotoRepository()
        photo_ids = body.photo_ids
        if not photo_ids:
            all_photos = repo.get_all_photos()
            photo_ids = [p.image_id for p in all_photos]

        if not photo_ids:
            return TaskStartResponse(task_id="", total=0)

        task_id = start_duplicate_detection(photo_ids)
        return TaskStartResponse(task_id=task_id, total=len(photo_ids))
    except Exception as exc:
        logger.error("Duplicate detection start failed: %s", exc)
        raise HTTPException(status_code=500, detail="Duplicate detection start failed")


@router.get("/duplicate-progress/{task_id}", response_model=ProgressResponse)
async def duplicate_detect_progress(task_id: str):
    """Poll duplicate detection progress."""
    state = get_duplicate_progress(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    return ProgressResponse(
        task_id=state["task_id"],
        status=state["status"],
        phase=state.get("phase", ""),
        total=state.get("total", 0),
        progress=state.get("progress", 0),
        current_file=state.get("current_file", ""),
        duplicate_groups=state.get("duplicate_groups", 0),
        duplicate_count=state.get("duplicate_count", 0),
        failed=state.get("failed", 0),
    )


@router.post("/duplicate-cancel/{task_id}")
async def duplicate_detect_cancel(task_id: str):
    """Cancel a running duplicate detection task."""
    ok = cancel_duplicate_detection(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
    return {"status": "cancelled"}


# ---- Analyze All (combined pipeline) ----

_analyze_tasks: dict[str, dict] = {}
_analyze_lock = threading.Lock()


def _run_analyze_all(task_id: str, photo_ids: list[str] | None = None, filter_mode: str | None = None):
    """Run all 5 AI steps with cascading skip logic.

    Cascade order (severity-based triage):
      Step 1: Eye detection   — closed-eye photos skip blur / burst / duplicate
      Step 2: Blur detection  — blurry photos skip burst / duplicate
      Step 3: Burst grouping  — burst photos skip duplicate
      Step 4: Duplicate detection — only on remaining clean photos
      Step 5: Best selection  — across burst and duplicate groups

    Each photo ends up in exactly ONE AI category (the first problem detected).
    This mirrors how a human photographer triages: remove fatal flaws first,
    then quality issues, then organize the survivors.

    If photo_ids is provided, only those photos are analysed.
    If filter_mode is "unprocessed", only unprocessed photos are analysed.
    Default (no filter_mode): only unanalyzed photos (incremental analysis).
    Pass filter_mode="all" to force analysis of all photos.
    """
    state = _analyze_tasks.get(task_id)
    if not state:
        return

    repo = PhotoRepository()

    if filter_mode == "unprocessed":
        all_ids = [p.image_id for p in repo.get_unprocessed_photos()]
    elif filter_mode == "all":
        all_ids = [p.image_id for p in repo.get_all_photos()]
    elif photo_ids:
        all_ids = photo_ids
    else:
        # Default: incremental — only photos never analysed before
        all_ids = [p.image_id for p in repo.get_unanalyzed_photos()]
    total_photos = len(all_ids)

    # Steps follow the cascade: eye → blur → burst → dup → best
    # Each step collects "hit" IDs that subsequent steps skip.
    steps = [
        ("eye",   "Step 1/5: 闭眼检测", start_eye_detection,        get_eye_progress,        {}),
        ("blur",  "Step 2/5: 模糊检测", start_blur_detection_v2,    get_blur_progress_v2,    {}),
        ("burst", "Step 3/5: 连拍分组", None,                       get_burst_progress,      {}),
        ("dup",   "Step 4/5: 重复检测", start_duplicate_detection,  get_duplicate_progress,  {}),
        ("best",  "Step 5/5: 最佳推荐", None,                       None,                    {}),
    ]

    import time

    # Cumulative skip sets — each step adds its "hit" photos
    closed_eye_ids: set[str] = set()
    blurry_ids: set[str] = set()
    burst_ids: set[str] = set()

    for step_key, phase_label, start_fn, progress_fn, extra_kwargs in steps:
        if state.get("cancelled"):
            state["status"] = "cancelled"
            return

        state["phase"] = phase_label
        state["progress"] = 0
        state["total"] = total_photos

        if step_key == "best":
            # Synchronous: runs in-thread, no polling needed
            # Run both burst best and duplicate best selection
            try:
                burst_summary = select_best_for_all_bursts(repo)
                dup_count = select_best_for_all_duplicates(repo)
                state["progress"] = total_photos
                state["best_count"] = burst_summary.recommended_count + dup_count
            except Exception as exc:
                logger.error("Best selection failed: %s", exc)
            continue

        # ---- Cumulate skip_ids for this step ----
        # closed_eye → skip from blur, burst, dup
        # blurry     → skip from burst, dup
        # burst      → skip from dup
        step_skip_ids: set[str] = set()
        if step_key == "blur":
            step_skip_ids = closed_eye_ids
        elif step_key == "burst":
            step_skip_ids = closed_eye_ids | blurry_ids
        elif step_key == "dup":
            step_skip_ids = closed_eye_ids | blurry_ids | burst_ids

        # ---- Start the background task ----
        if step_key == "burst":
            # Burst grouping operates on all photos (time-based), but we
            # clear burst_group for skipped photos after completion so
            # they don't pollute burst groups.
            task_id_step = start_burst_grouping(repo)
        else:
            kwargs: dict = dict(extra_kwargs)
            if step_skip_ids:
                kwargs["skip_ids"] = step_skip_ids
            task_id_step = start_fn(all_ids, **kwargs)

        if not task_id_step:
            # Fallback: mark this step complete and move on
            state["progress"] = total_photos
            continue

        # ---- Poll until complete ----
        # Small initial sleep prevents race where the task finishes
        # before we ever poll.
        time.sleep(0.3)
        while True:
            if state.get("cancelled"):
                state["status"] = "cancelled"
                return
            p = progress_fn(task_id_step)
            if not p:
                time.sleep(0.5)
                continue
            state["progress"] = p.get("progress", 0)
            state["total"] = max(p.get("total", 0), 1)
            state["current_file"] = p.get("current_file", "")
            if p.get("status") != "running":
                # Push to 100 % so the frontend sees step completion
                state["progress"] = state["total"]
                break
            time.sleep(0.5)

        # ---- After step completes: collect "hit" IDs for cascade ----
        if step_key == "eye":
            closed_eye_ids = {p.image_id for p in repo.get_all_photos() if p.is_closed_eye == 1}
        elif step_key == "blur":
            blurry_ids = {p.image_id for p in repo.get_all_photos() if p.is_blur == 1}
        elif step_key == "burst":
            # Clear burst_group for photos that are closed-eye or blurry —
            # they should not appear in burst groups per cascade design.
            for skip_id in closed_eye_ids | blurry_ids:
                try:
                    repo.clear_burst_group(skip_id)
                except Exception:
                    pass  # photo may not have a burst_group
            # Collect burst IDs from remaining photos (not closed-eye, not blurry)
            burst_ids = {
                p.image_id for p in repo.get_all_photos()
                if p.burst_group is not None
                and p.image_id not in closed_eye_ids
                and p.image_id not in blurry_ids
            }

    # ---- Mark all analysed photos so the next run only picks up new ones ----
    if total_photos > 0 and not state.get("cancelled"):
        try:
            for image_id in all_ids:
                repo.mark_analyzed(image_id)
            logger.info("Marked %d photos as analysed", total_photos)
        except Exception as exc:
            logger.error("Failed to mark analysed_at: %s", exc)

    state["status"] = "completed"
    state["phase"] = "分析完成"
    state["progress"] = total_photos


@router.post("/analyze-all", response_model=TaskStartResponse)
async def analyze_all_start(body: AnalyzeAllRequest = AnalyzeAllRequest()):
    """Run all AI analyses in cascading sequence: eye -> blur -> burst -> duplicate -> best.

    Default: only analyses unanalyzed photos (incremental — new imports only).
    Pass filter_mode="all" to force re-analysis of every photo.
    Pass filter_mode="unprocessed" to analyse un-starred & un-rejected photos.
    """
    try:
        task_id = uuid.uuid4().hex[:8]
        state = {
            "task_id": task_id,
            "status": "running",
            "phase": "Step 1/5: 闭眼检测",
            "total": 0,
            "progress": 0,
            "current_file": "",
            "blurred": 0,
            "failed": 0,
            "cancelled": False,
        }
        with _analyze_lock:
            _analyze_tasks[task_id] = state

        t = threading.Thread(
            target=_run_analyze_all,
            args=(task_id, body.photo_ids, body.filter_mode),
            daemon=True,
        )
        t.start()
        return TaskStartResponse(task_id=task_id, total=0)
    except Exception as exc:
        logger.error("Analyze-all start failed: %s", exc)
        raise HTTPException(status_code=500, detail="Analyze-all start failed")


@router.get("/analyze-progress/{task_id}", response_model=ProgressResponse)
async def analyze_all_progress(task_id: str):
    """Poll analyze-all progress."""
    state = _analyze_tasks.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    return ProgressResponse(
        task_id=state["task_id"],
        status=state["status"],
        phase=state.get("phase", ""),
        total=state.get("total", 0),
        progress=state.get("progress", 0),
        current_file=state.get("current_file", ""),
        failed=state.get("failed", 0),
    )


# ---- AI Analysis Summary ----

class AISummaryResponse(BaseModel):
    total_analyzed: int
    closed_eye_count: int
    blur_count: int
    burst_group_count: int
    burst_photo_count: int
    duplicate_group_count: int
    duplicate_photo_count: int
    best_count: int
    clean_count: int


@router.get("/summary", response_model=AISummaryResponse)
async def get_ai_summary():
    """Return a comprehensive summary of AI analysis results.

    Provides a single snapshot that answers "What did the AI find?"
    — total analysed, defects found, groups organised, and clean photos.
    """
    try:
        repo = PhotoRepository()
        return repo.get_ai_summary()
    except Exception as exc:
        logger.error("Failed to get AI summary: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get AI summary")
