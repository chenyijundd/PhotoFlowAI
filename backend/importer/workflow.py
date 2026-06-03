"""
PhotoFlow AI - Import Workflow

Orchestrates the complete photo import pipeline:

  Step 1 — Scan directory for images         (parallel metadata)
  Step 2 — Extract RAW previews              (parallel rawpy)
  Step 3 — Generate thumbnails                (parallel Pillow)
  Step 4 — Write metadata to SQLite           (single-thread)
  Step 5 — Sync: remove stale DB records      (filesystem check)
  Step 6 — Return import statistics

Steps 1-3 use ``ThreadPoolExecutor`` for parallel processing.
Pillow, rawpy, and OpenCV release the GIL during C-level operations
so threads achieve near-process-level parallelism without the
memory overhead of spawning child processes.

Each photo is processed individually so a single failure does not
abort the entire import.
"""

import hashlib
import logging
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from backend.image_loader.utils import (
    safe_get_image_size,
    get_file_created_time,
    generate_file_id,
)
from backend.image_loader.models import PhotoInfo
from backend.raw_preview.extractor import is_raw_file, extract_preview
from backend.thumbnail_cache.utils import (
    generate_single_thumbnail,
    ensure_cache_dir,
)
from backend.thumbnail_cache.cache_manager import DEFAULT_CACHE_DIR
from database.repository import PhotoRepository
from database.models import PhotoRecord

logger = logging.getLogger("importer")


# ---------------------------------------------------------------------------
# Worker functions (module-level for ThreadPoolExecutor)
# ---------------------------------------------------------------------------

def _resolve_photo_metadata(file_path: str, input_dir: str) -> PhotoInfo | None:
    """Resolve full metadata for a single image file.

    Called inside a ``ThreadPoolExecutor`` worker thread — Pillow and
    rawpy release the GIL so multiple threads can process images in
    parallel with near-linear speedup.

    Returns None if the file is unsupported, unreadable, or corrupted.
    """
    from backend.image_loader.utils import is_supported_format

    if not is_supported_format(file_path):
        return None
    if not os.path.isfile(file_path):
        return None

    try:
        file_size = os.path.getsize(file_path)
        created_time = get_file_created_time(file_path)
        width, height = safe_get_image_size(file_path)
    except OSError:
        return None

    if width == 0 or height == 0:
        return None

    photo_id = generate_file_id(file_path, input_dir)
    return PhotoInfo(
        id=photo_id,
        file_name=os.path.basename(file_path),
        file_path=file_path,
        file_size=file_size,
        created_time=created_time,
        width=width,
        height=height,
    )


def _list_image_files(directory: str) -> list[str]:
    """Recursively walk *directory* and return all image file paths.

    Only does filesystem listing — no Pillow/rawpy calls.
    """
    from backend.image_loader.utils import is_supported_format

    result: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for file_name in sorted(files):
            file_path = os.path.join(root, file_name)
            if not is_supported_format(file_path):
                continue
            if not os.path.isfile(file_path):
                continue
            result.append(file_path)
    return result


def _extract_raw_preview_worker(args: tuple[str, str]) -> tuple[str, str | None]:
    """Extract RAW preview for a single file.  Returns ``(image_id, preview_path)``."""
    image_id, file_path = args
    try:
        preview_path = extract_preview(file_path, image_id)
        if preview_path and os.path.isfile(preview_path):
            return (image_id, preview_path)
    except Exception as exc:
        logger.warning("RAW preview failed for %s: %s", file_path, exc)
    return (image_id, None)


def _thumbnail_worker(args: tuple[str, str, str]) -> bool:
    """Generate a thumbnail for a single photo.  Returns True on success."""
    image_id, source_path, cache_dir = args
    try:
        generate_single_thumbnail(
            source_path=source_path,
            image_id=image_id,
            cache_dir=cache_dir,
        )
        return True
    except Exception as exc:
        logger.warning("Thumbnail failed for %s: %s", image_id, exc)
        return False


# ---------------------------------------------------------------------------
# RAW+JPEG pair detection
# ---------------------------------------------------------------------------


def _detect_raw_jpeg_pairs(repo: PhotoRepository) -> int:
    """Detect RAW+JPEG pairs across ALL photos in the database.

    Two (or more) files are paired when they share the same base stem
    (filename without extension) in the same directory, and at least
    one is a RAW file while at least one other is a non-RAW image.

    Each pair group is assigned a stable *raw_jpeg_pair_id* (an MD5
    hash of ``directory/stem``, truncated to 12 hex chars).

    Returns the number of distinct pair groups detected.
    """
    all_photos = repo.get_all_photos()
    if not all_photos:
        return 0

    # Group photos by (directory, stem)
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for p in all_photos:
        directory = os.path.dirname(p.file_path)
        stem = os.path.splitext(p.file_name)[0]
        groups[(directory, stem)].append(p)

    # Find groups with RAW + non-RAW coexistence
    pairs: dict[str, str | None] = {}
    pair_groups = 0
    for (directory, stem), photos in groups.items():
        if len(photos) < 2:
            continue
        raw_photos = [p for p in photos if is_raw_file(p.file_path)]
        non_raw = [p for p in photos if not is_raw_file(p.file_path)]
        if not raw_photos or not non_raw:
            continue

        # Generate a stable pair ID from directory + stem
        pair_id = hashlib.md5(
            f"{directory}/{stem}".encode("utf-8")
        ).hexdigest()[:12]

        for p in photos:
            pairs[p.image_id] = pair_id
        pair_groups += 1
        logger.debug(
            "RAW+JPEG pair: %s ← %d RAW + %d non-RAW (%s)",
            pair_id, len(raw_photos), len(non_raw), stem,
        )

    # Clear pair_id for photos that were previously paired but no longer are
    # (e.g., one of the pair files was deleted from disk and then re-imported).
    currently_paired = set(pairs.keys())
    for p in all_photos:
        if p.raw_jpeg_pair_id and p.image_id not in currently_paired:
            pairs[p.image_id] = None

    if pairs:
        repo.update_raw_jpeg_pairs_batch(pairs)

    return pair_groups


# ---------------------------------------------------------------------------
# Main import workflow
# ---------------------------------------------------------------------------


def _worker_count() -> int:
    """Return a sensible ThreadPoolExecutor worker count for I/O + CPU work."""
    cpu = os.cpu_count() or 4
    return max(4, min(cpu * 2, 16))  # I/O-heavy: 2× cores, capped at 16


def import_directory(directory: str) -> dict:
    """Execute the full import workflow for *directory*.

    Steps 1-3 run with ``ThreadPoolExecutor`` for parallel processing
    (Pillow / rawpy release the GIL during C-level operations).

    Returns a dict with keys:
        total      — number of images found on disk
        imported   — number of new rows inserted into the database
        skipped    — total - imported (already existed)
        errors     — number of thumbnail-generation failures
        raw_count  — number of RAW files with previews extracted
        removed    — number of stale DB records cleaned up
    """
    t0_total = time.time()
    workers = _worker_count()
    logger.info("Import start: %s (workers=%d)", directory, workers)

    # ==================================================================
    # Step 1 — Parallel: discover files + resolve metadata
    # ==================================================================
    logger.info("Step 1/6: Scanning %s (parallel)", directory)
    t0 = time.time()

    file_paths = _list_image_files(directory)
    if not file_paths:
        logger.info("No supported images found in %s", directory)
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 0,
                "raw_count": 0, "removed": 0, "pair_count": 0}

    scanned_photos: list[PhotoInfo] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_resolve_photo_metadata, fp, directory): fp
            for fp in file_paths
        }
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                scanned_photos.append(result)

    # Sort by file name to maintain consistent ordering
    scanned_photos.sort(key=lambda p: p.file_name)
    total = len(scanned_photos)
    elapsed = time.time() - t0
    logger.info(
        "Step 1/6: Found %d image(s) in %.1fs (%.0f photos/s)",
        total, elapsed, total / elapsed if elapsed > 0 else 0,
    )

    if total == 0:
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 0,
                "raw_count": 0, "removed": 0, "pair_count": 0}

    # ==================================================================
    # Step 2 — Parallel: extract RAW previews
    # ==================================================================
    logger.info("Step 2/6: Extracting RAW previews (parallel)")
    t0 = time.time()
    preview_map: dict[str, str] = {}
    raw_count = 0

    raw_tasks = [
        (p.id, p.file_path) for p in scanned_photos
        if is_raw_file(p.file_path)
    ]
    if raw_tasks:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_extract_raw_preview_worker, task): task[0]
                for task in raw_tasks
            }
            for future in as_completed(futures):
                image_id, preview_path = future.result()
                if preview_path:
                    preview_map[image_id] = preview_path
                    raw_count += 1

    elapsed = time.time() - t0
    if raw_count > 0:
        logger.info(
            "Step 2/6: Extracted %d RAW preview(s) in %.1fs (%.0f previews/s)",
            raw_count, elapsed, raw_count / elapsed if elapsed > 0 else 0,
        )

    # ==================================================================
    # Step 3 — Parallel: generate thumbnails
    # ==================================================================
    logger.info("Step 3/6: Generating thumbnails (parallel)")
    t0 = time.time()
    cache_dir = ensure_cache_dir(DEFAULT_CACHE_DIR)
    thumb_errors = 0

    thumb_tasks = [
        (p.id, preview_map.get(p.id, p.file_path), cache_dir)
        for p in scanned_photos
    ]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_thumbnail_worker, task): task[0]
            for task in thumb_tasks
        }
        for future in as_completed(futures):
            if not future.result():
                thumb_errors += 1

    elapsed = time.time() - t0
    logger.info(
        "Step 3/6: %d thumbnails in %.1fs (%.0f thumbs/s), %d errors",
        total - thumb_errors, elapsed,
        (total - thumb_errors) / elapsed if elapsed > 0 else 0,
        thumb_errors,
    )

    # ==================================================================
    # Step 4 — Write to database  (INSERT OR IGNORE → duplicate-safe)
    # ==================================================================
    logger.info("Step 4/6: Writing to database")
    t0 = time.time()

    records: List[PhotoRecord] = []
    for p in scanned_photos:
        records.append(
            PhotoRecord(
                image_id=p.id,
                file_name=p.file_name,
                file_path=p.file_path,
                raw_preview_path=preview_map.get(p.id),
                file_size=p.file_size,
                width=p.width,
                height=p.height,
                created_time=p.created_time,
            )
        )

    repo = PhotoRepository()
    repo.init_database()
    imported = repo.insert_photos(records)
    skipped = total - imported
    logger.info("Step 4/6: DB write in %.1fs — %d imported, %d skipped",
                time.time() - t0, imported, skipped)

    # ==================================================================
    # Step 4.5 — RAW+JPEG pair detection
    # ==================================================================
    logger.info("Step 4.5: RAW+JPEG 配对检测")
    t0 = time.time()
    pair_count = _detect_raw_jpeg_pairs(repo)
    elapsed = time.time() - t0
    if pair_count > 0:
        logger.info(
            "Step 4.5: 发现 %d 个 RAW+JPEG 配对组 (%.2fs)",
            pair_count, elapsed,
        )

    # ==================================================================
    # Step 5 — Sync: remove photos from DB whose files no longer exist
    # ==================================================================
    logger.info("Step 5/6: Syncing deleted files")
    t0 = time.time()
    all_photos = repo.get_all_photos()
    removed = 0
    for p in all_photos:
        if not os.path.isfile(p.file_path):
            repo.delete_photo(p.image_id)
            removed += 1
            logger.info("Removed stale record: %s", p.file_path)
    if removed > 0:
        logger.info("Synced: %d stale record(s) removed in %.1fs", removed, time.time() - t0)

    # ==================================================================
    # Step 6 — Return statistics
    # ==================================================================
    elapsed_total = time.time() - t0_total
    result = {
        "total": total,
        "imported": imported,
        "skipped": skipped,
        "errors": thumb_errors,
        "raw_count": raw_count,
        "removed": removed,
        "pair_count": pair_count,
    }
    logger.info(
        "Step 6/6: Import complete — total=%d imported=%d skipped=%d "
        "raw=%d removed=%d pairs=%d errors=%d | %.1fs total",
        total, imported, skipped, raw_count, removed, pair_count, thumb_errors,
        elapsed_total,
    )
    return result
