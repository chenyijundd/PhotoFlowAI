"""
PhotoFlow AI - AI API Service

Endpoints for AI-based photo analysis (blur detection, duplicate detection, etc.).

All detection tasks run in background threads. The start endpoint returns a
task_id immediately, and the frontend polls GET /api/ai/{type}-progress/{id}.
"""

import asyncio
import json
import logging
import queue
import threading
import time
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.ai.blur_detector_v2.service import start_blur_detection_v2, get_blur_progress_v2, cancel_blur_detection_v2
from backend.ai.burst_grouper.service import start_burst_grouping, get_burst_progress, cancel_burst_grouping
from backend.ai.duplicate_detector.service import start_duplicate_detection, get_duplicate_progress, cancel_duplicate_detection
from backend.ai.best_selector.service import select_best_for_all_bursts, select_best_for_all_duplicates
from backend.ai.eye_detection.service import start_eye_detection, get_eye_progress, cancel_eye_detection
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
_analyze_event_queues: dict[str, queue.Queue] = {}


def _push_analyze_event(task_id: str, event_type: str, data: dict):
    """Push an SSE event into the task's event queue (thread-safe)."""
    q = _analyze_event_queues.get(task_id)
    if q is not None:
        try:
            q.put({"event": event_type, "data": data})
        except Exception:
            pass  # Queue might be full or closed — silently ignore


def _run_analyze_all(
    task_id: str,
    photo_ids: list[str] | None = None,
    filter_mode: str | None = None,
    event_queue: queue.Queue | None = None,
):
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

    If *event_queue* is provided, SSE events are pushed at step boundaries
    and progress checkpoints for real-time streaming to the frontend.
    """
    _push = lambda evt, data: _push_analyze_event(task_id, evt, data) if event_queue else None

    state = _analyze_tasks.get(task_id)
    if not state:
        return

    # ---- Read active sensitivity preset ----
    from backend.config.presets import get_active_preset
    preset = get_active_preset()
    t = preset.thresholds
    logger.info(
        "Analyze-all using preset: %s (%s)", preset.name, preset.id,
    )

    repo = PhotoRepository()

    # ---- Detect preset change → reset old analysis results ----
    last_preset = repo.get_config("analysis_preset_id")
    if last_preset and last_preset != preset.id:
        logger.info(
            "Preset changed: %s → %s — resetting non-manual analysis results",
            last_preset, preset.id,
        )
        analysis_reset = repo.reset_analysis_results()
        stars_r, rejects_r = repo.reset_cull_results()
        logger.info(
            "Reset: analysis=%s cull_stars=%d cull_rejects=%d",
            analysis_reset, stars_r, rejects_r,
        )
        if event_queue:
            # Let the frontend know results were cleared
            _push("preset_changed", {
                "from": last_preset,
                "to": preset.id,
                "reset_fields": sum(analysis_reset.values()) if analysis_reset else 0,
            })

    # Persist this preset as the one used for the analysis about to start
    repo.set_config("analysis_preset_id", preset.id)

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

    # Cumulative skip sets — each step adds its "hit" photos
    closed_eye_ids: set[str] = set()
    blurry_ids: set[str] = set()
    burst_ids: set[str] = set()

    # ---- Pre-query already-analysed photos (incremental skip) ----
    # Photos that already have per‑step results from a previous run
    # are skipped so re‑analysis only processes NEW / CHANGED photos.
    all_db = repo.get_all_photos()
    already_eye_analysed: set[str] = {
        p.image_id for p in all_db if p.eye_score is not None
    }
    already_blur_analysed: set[str] = {
        p.image_id for p in all_db if p.blur_score is not None
    }
    logger.info(
        "Incremental skip: eye=%d already analysed, blur=%d already analysed",
        len(already_eye_analysed), len(already_blur_analysed),
    )

    for step_key, phase_label, start_fn, progress_fn, extra_kwargs in steps:
        if state.get("cancelled"):
            state["status"] = "cancelled"
            _push("task_cancelled", {})
            return

        state["phase"] = phase_label
        state["progress"] = 0
        state["total"] = total_photos

        _push("step_start", {"step": step_key, "phase": phase_label, "total": total_photos})

        if step_key == "best":
            # Synchronous: runs in-thread, no polling needed
            # Run both burst best and duplicate best selection
            _push("step_start", {"step": "best", "phase": phase_label, "total": total_photos})
            try:
                burst_summary = select_best_for_all_bursts(
                    repo,
                    blur_tie_pct=t.blur_tie_pct,
                    size_tie_pct=t.size_tie_pct,
                )
                dup_count = select_best_for_all_duplicates(repo)
                state["progress"] = total_photos
                state["best_count"] = burst_summary.recommended_count + dup_count
                _push("progress", {
                    "step": "best",
                    "phase": phase_label,
                    "progress": total_photos,
                    "total": total_photos,
                    "current_file": "",
                })
                _push("step_complete", {
                    "step": "best",
                    "best_count": state["best_count"],
                })
            except Exception as exc:
                logger.error("Best selection failed: %s", exc)
            continue

        # ---- Cumulate skip_ids for this step ----
        # Cascade skips (severity-based):
        #   closed_eye → skip from blur, burst, dup
        #   blurry     → skip from burst, dup
        #   burst      → skip from dup
        #
        # Incremental skips (already analysed):
        #   eye_score IS NOT NULL  → skip from eye
        #   blur_score IS NOT NULL → skip from blur
        step_skip_ids: set[str] = set()
        if step_key == "eye":
            step_skip_ids = already_eye_analysed
        elif step_key == "blur":
            step_skip_ids = closed_eye_ids | already_blur_analysed
        elif step_key == "burst":
            step_skip_ids = closed_eye_ids | blurry_ids
        elif step_key == "dup":
            step_skip_ids = closed_eye_ids | blurry_ids | burst_ids

        # ---- Start the background task ----
        if step_key == "burst":
            # Burst grouping operates on all photos (time-based), but we
            # clear burst_group for skipped photos after completion so
            # they don't pollute burst groups.
            task_id_step = start_burst_grouping(
                repo,
                gap_seconds=t.burst_gap_seconds,
                min_burst_size=t.min_burst_size,
            )
        elif step_key == "best":
            # Skip here — handled below
            continue
        else:
            kwargs: dict = dict(extra_kwargs)
            if step_skip_ids:
                kwargs["skip_ids"] = step_skip_ids

            # Inject preset thresholds
            if step_key == "eye":
                kwargs["thresholds"] = {
                    "blink_score_threshold": t.blink_score_threshold,
                    "ear_closed_threshold": t.ear_closed_threshold,
                    "ear_half_closed_threshold": t.ear_half_closed_threshold,
                }
            elif step_key == "blur":
                kwargs["threshold"] = t.blur_threshold
                kwargs["preview_sharp_threshold"] = t.preview_sharp_threshold
                kwargs["preview_blur_threshold"] = t.preview_blur_threshold
            elif step_key == "dup":
                kwargs["hamming_prefilter"] = t.hamming_prefilter
                kwargs["ssim_threshold"] = t.ssim_threshold
                kwargs["time_window_gap"] = t.time_window_gap

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
                _push("task_cancelled", {})
                return
            p = progress_fn(task_id_step)
            if not p:
                time.sleep(0.5)
                continue
            state["progress"] = p.get("progress", 0)
            state["total"] = max(p.get("total", 0), 1)
            state["current_file"] = p.get("current_file", "")
            # Push progress event (~every 0.5s while running)
            _push("progress", {
                "step": step_key,
                "phase": phase_label,
                "progress": state["progress"],
                "total": state["total"],
                "current_file": state["current_file"],
            })
            if p.get("status") != "running":
                # Push to 100 % so the frontend sees step completion
                state["progress"] = state["total"]
                _push("progress", {
                    "step": step_key,
                    "phase": phase_label,
                    "progress": state["total"],
                    "total": state["total"],
                    "current_file": "",
                })
                break
            time.sleep(0.5)

        # ---- After step completes: collect "hit" IDs for cascade ----
        if step_key == "eye":
            closed_eye_ids = {p.image_id for p in repo.get_all_photos() if p.is_closed_eye == 1}
            _push("step_complete", {
                "step": "eye",
                "closed_eye_count": len(closed_eye_ids),
            })
        elif step_key == "blur":
            blurry_ids = {p.image_id for p in repo.get_all_photos() if p.is_blur == 1}
            _push("step_complete", {
                "step": "blur",
                "blur_count": len(blurry_ids),
            })
        elif step_key == "burst":
            # Clear burst_group for photos that are closed-eye or blurry —
            # they should not appear in burst groups per cascade design.
            # Use batch transaction: N updates in 1 commit instead of N commits.
            skip_burst = closed_eye_ids | blurry_ids
            if skip_burst:
                with repo.batch_transaction():
                    for skip_id in skip_burst:
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
            # Count burst groups
            burst_groups = repo.get_burst_groups()
            _push("step_complete", {
                "step": "burst",
                "burst_group_count": len(burst_groups),
                "burst_photo_count": len(burst_ids),
            })
        elif step_key == "dup":
            # Count duplicate results from DB
            dup_groups = repo.get_duplicate_groups()
            dup_photos = {
                p.image_id for p in repo.get_all_photos() if p.is_duplicate == 1
            }
            _push("step_complete", {
                "step": "dup",
                "duplicate_group_count": len(dup_groups),
                "duplicate_photo_count": len(dup_photos),
            })

    # ---- Mark all analysed photos so the next run only picks up new ones ----
    if total_photos > 0 and not state.get("cancelled"):
        try:
            with repo.batch_transaction():
                for image_id in all_ids:
                    repo.mark_analyzed(image_id)
            logger.info("Marked %d photos as analysed", total_photos)
        except Exception as exc:
            logger.error("Failed to mark analysed_at: %s", exc)

    state["status"] = "completed"
    state["phase"] = "分析完成"
    state["progress"] = total_photos

    # Push final task_complete event with summary
    try:
        summary = repo.get_ai_summary()
        _push("task_complete", {
            "total_analyzed": summary.total_analyzed,
            "closed_eye_count": summary.closed_eye_count,
            "blur_count": summary.blur_count,
            "burst_group_count": summary.burst_group_count,
            "burst_photo_count": summary.burst_photo_count,
            "duplicate_group_count": summary.duplicate_group_count,
            "duplicate_photo_count": summary.duplicate_photo_count,
            "best_count": summary.best_count,
            "clean_count": summary.clean_count,
        })
    except Exception:
        _push("task_complete", {"total_analyzed": total_photos})


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
            _analyze_event_queues[task_id] = queue.Queue()

        t = threading.Thread(
            target=_run_analyze_all,
            args=(task_id, body.photo_ids, body.filter_mode, _analyze_event_queues[task_id]),
            daemon=True,
        )
        t.start()
        return TaskStartResponse(task_id=task_id, total=0)
    except Exception as exc:
        logger.error("Analyze-all start failed: %s", exc)
        raise HTTPException(status_code=500, detail="Analyze-all start failed")


@router.get("/analyze-progress/{task_id}", response_model=ProgressResponse)
async def analyze_all_progress(task_id: str):
    """Poll analyze-all progress (legacy — prefer SSE /analyze-stream for new clients)."""
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


@router.get("/analyze-stream/{task_id}")
async def analyze_stream(task_id: str):
    """SSE endpoint — stream analyze-all progress events in real time.

    Events emitted:
      - step_start    {step, phase, total}
      - progress      {step, phase, progress, total, current_file}
      - step_complete {step, ...counts}
      - task_complete {summary}
      - task_cancelled {}
    """
    event_queue = _analyze_event_queues.get(task_id)

    # If no queue yet but task exists, create one (race: task thread hasn't started yet)
    if event_queue is None:
        with _analyze_lock:
            if _analyze_tasks.get(task_id) and task_id not in _analyze_event_queues:
                _analyze_event_queues[task_id] = queue.Queue()
        event_queue = _analyze_event_queues.get(task_id)

    if event_queue is None:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        loop = asyncio.get_running_loop()
        try:
            while True:
                try:
                    event = await loop.run_in_executor(None, lambda: event_queue.get(timeout=1.0))
                    yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                    if event["event"] in ("task_complete", "task_cancelled", "task_error"):
                        break
                except queue.Empty:
                    # Heartbeat to keep the connection alive
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass  # Client disconnected — clean exit
        finally:
            _analyze_event_queues.pop(task_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze-cancel/{task_id}")
async def analyze_cancel(task_id: str):
    """Cancel a running analyze-all task."""
    state = _analyze_tasks.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    if state.get("status") != "running":
        raise HTTPException(status_code=400, detail="Task is not running")
    state["cancelled"] = True
    # Push cancellation event through SSE if connected
    _push_analyze_event(task_id, "task_cancelled", {})
    return {"status": "cancelling"}


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
