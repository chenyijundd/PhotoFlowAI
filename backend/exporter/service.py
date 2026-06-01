"""
PhotoFlow AI — Export Service

Streaming file-copy export with cooperative cancel support.
Processes one file at a time to avoid loading all files into memory.
"""

import logging
import os
import threading
import time
import uuid
from typing import Optional

from database.repository import PhotoRepository
from .models import ExportMode
from .utils import copy_file_safe

logger = logging.getLogger("export")

# In-memory export state registry (cooperative cancel via flag)
_export_states: dict[str, dict] = {}
_lock = threading.Lock()


def _resolve_by_filter(repo: PhotoRepository, filter_mode: str) -> list[str]:
    """Resolve photo IDs from the database based on a filter mode string."""
    if filter_mode == "starred":
        photos = repo.get_starred_photos()
    elif filter_mode == "rejected":
        photos = repo.get_rejected_photos()
    elif filter_mode == "unprocessed":
        photos = repo.get_unprocessed_photos()
    else:  # "all"
        photos = repo.get_all_photos()
    return [p.image_id for p in photos]


def _get_photo_ids(repo: PhotoRepository, mode: ExportMode, photo_ids: Optional[list[str]], filter_mode: Optional[str] = None) -> list[str]:
    """Resolve the list of photo IDs to export based on mode."""
    if mode == ExportMode.PICKED:
        photos = repo.get_starred_photos()
        return [p.image_id for p in photos if (p.is_rejected or 0) == 0]
    elif mode == ExportMode.REJECTED:
        photos = repo.get_rejected_photos()
        return [p.image_id for p in photos]
    elif mode == ExportMode.CURRENT_FILTER:
        # If filter_mode is provided, resolve the full list server-side
        if filter_mode:
            return _resolve_by_filter(repo, filter_mode)
        # Fallback: use provided photo_ids (legacy path)
        if not photo_ids:
            return []
        result = []
        for pid in photo_ids:
            photo = repo.get_photo_by_id(pid)
            if photo:
                result.append(pid)
        return result
    elif mode == ExportMode.COMPARE:
        if not photo_ids:
            return []
        result = []
        for pid in photo_ids:
            photo = repo.get_photo_by_id(pid)
            if photo:
                result.append(pid)
        return result
    return []


def _build_filename(
    template: str | None,
    original_name: str,
    prefix: str | None,
    index: int,
    created_time: str | None,
    export_format: str = "original",
) -> str:
    """Generate target filename from the naming template and export format.

    Supported templates:
      - None / "original": keep the original filename
      - "custom_index": {prefix}_{index:03d}.ext
      - "custom_date_index": {prefix}_{date}_{index:03d}.ext

    When export_format is not "original", the extension is replaced accordingly.
    """
    _, ext = os.path.splitext(original_name)

    # Determine target extension
    target_ext = ext
    if export_format == "jpeg":
        target_ext = ".jpg"
    elif export_format == "png":
        target_ext = ".png"

    if template == "custom_index":
        pre = (prefix or "Export").strip()
        result = f"{pre}_{index:03d}{target_ext}"
        logger.debug("_build_filename: template=%s original=%s → %s", template, original_name, result)
        return result

    if template == "custom_date_index":
        pre = (prefix or "Export").strip()
        date_str = "00000000"
        if created_time:
            # Normalise ISO-ish date to YYYYMMDD
            raw = created_time.strip()[:10]
            date_str = raw.replace("-", "").replace("/", "").replace(" ", "")
            if len(date_str) != 8:
                date_str = "00000000"
        result = f"{pre}_{date_str}_{index:03d}{target_ext}"
        logger.debug("_build_filename: template=%s original=%s → %s", template, original_name, result)
        return result

    # Default: "original" template — replace extension if format conversion requested
    if export_format != "original":
        base, _ = os.path.splitext(original_name)
        result = base + target_ext
        logger.debug("_build_filename: original name with format change: %s → %s", original_name, result)
        return result

    logger.debug("_build_filename: no template, keeping original name: %s", original_name)
    return original_name


def _run_export_loop(
    export_id: str,
    ids: list[str],
    target_dir: str,
    subfolder: str,
    name_template: str | None = None,
    name_prefix: str | None = None,
    start_index: int = 1,
    export_format: str = "original",
):
    """Run the actual export in a background thread, updating shared state."""
    state = _export_states.get(export_id)
    if not state:
        return

    # Each thread needs its own repo instance (SQLite connections are per-thread)
    repo = PhotoRepository()
    idx = start_index

    logger.info("=== Export Start ===")
    logger.info("ID: %s | Mode: %s | Total: %d | Target: %s",
                export_id, subfolder, len(ids), target_dir)
    logger.info("Naming: template=%s prefix=%s start_index=%d format=%s",
                name_template or "original", name_prefix or "(none)", start_index, export_format)

    for pid in ids:
        # Cooperative cancel check
        if state["cancelled"]:
            state["status"] = "cancelled"
            logger.info("Export %s cancelled at %d/%d", export_id, state["succeeded"], state["total"])
            break

        photo = repo.get_photo_by_id(pid)
        if not photo:
            state["failed"] += 1
            state["errors"].append(f"Photo not found in DB: {pid}")
            logger.warning("Export skip: photo not found %s", pid)
            continue

        source_path = photo.file_path
        state["current_file"] = photo.file_name or pid

        if not source_path or not os.path.isfile(source_path):
            state["failed"] += 1
            state["errors"].append(f"Source file missing: {source_path or pid}")
            logger.warning("Export skip: source missing %s", source_path)
            continue

        target_filename = _build_filename(
            name_template, photo.file_name, name_prefix, idx, photo.created_time,
            export_format,
        )
        success, error_msg = copy_file_safe(source_path, target_dir, target_filename,
                                            export_format=export_format)
        if success:
            state["succeeded"] += 1
            idx += 1
        else:
            state["failed"] += 1
            state["errors"].append(error_msg)
            logger.warning("Export error: %s", error_msg)

    if state["status"] == "running":
        state["status"] = "completed"

    state["duration_seconds"] = round(time.time() - state["start_time"], 1)
    state["current_file"] = ""

    logger.info("=== Export %s ===", state["status"].upper())
    logger.info(
        "Succeeded: %d | Failed: %d | Skipped: %d | Duration: %.1fs",
        state["succeeded"], state["failed"], state["skipped"], state["duration_seconds"],
    )


def start_export(
    target_folder: str,
    mode: ExportMode,
    photo_ids: Optional[list[str]] = None,
    filter_mode: Optional[str] = None,
    name_template: Optional[str] = None,
    name_prefix: Optional[str] = None,
    start_index: Optional[int] = None,
    export_format: Optional[str] = None,
    repo: Optional[PhotoRepository] = None,
) -> str:
    """
    Start an export in a background thread. Returns an export_id immediately.

    The frontend polls GET /api/export/progress/{export_id} for real-time
    progress updates while the export runs in the background.
    """
    if repo is None:
        repo = PhotoRepository()

    export_id = uuid.uuid4().hex[:12]
    ids = _get_photo_ids(repo, mode, photo_ids, filter_mode)

    subfolder_map = {
        ExportMode.PICKED: "Picked",
        ExportMode.REJECTED: "Rejected",
        ExportMode.CURRENT_FILTER: "CurrentFilter",
        ExportMode.COMPARE: "CompareExport",
    }
    subfolder = subfolder_map.get(mode, "Export")
    target_dir = f"{target_folder}/{subfolder}"

    fmt = export_format or "original"

    state = {
        "export_id": export_id,
        "status": "running",
        "total": len(ids),
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "current_file": "",
        "errors": [],
        "cancelled": False,
        "start_time": time.time(),
        "duration_seconds": 0.0,
    }

    with _lock:
        _export_states[export_id] = state

    idx = start_index or 1

    # Start background thread — API returns immediately
    t = threading.Thread(
        target=_run_export_loop,
        args=(export_id, ids, target_dir, subfolder, name_template, name_prefix, idx, fmt),
        daemon=True,
    )
    t.start()

    return export_id


def get_progress(export_id: str) -> Optional[dict]:
    """Get the current progress of an export."""
    return _export_states.get(export_id)


def cancel_export(export_id: str) -> bool:
    """Request cancellation of a running export."""
    state = _export_states.get(export_id)
    if state and state["status"] == "running":
        state["cancelled"] = True
        logger.info("Export %s cancellation requested", export_id)
        return True
    return False


def cleanup_export(export_id: str):
    """Remove export state from memory."""
    _export_states.pop(export_id, None)
