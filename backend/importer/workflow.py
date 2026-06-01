"""
PhotoFlow AI - Import Workflow

Orchestrates the complete photo import pipeline:

  Step 1 — Scan directory for images         (image_loader)
  Step 2 — Extract RAW previews              (raw_preview)
  Step 3 — Generate thumbnails                (thumbnail_cache)
  Step 4 — Write metadata to SQLite           (database repository)
  Step 5 — Sync: remove stale DB records      (filesystem check)
  Step 6 — Return import statistics

Each photo is processed individually so a single failure does not
abort the entire import.
"""

import logging
import os
from typing import List

from backend.image_loader.utils import collect_scan
from backend.raw_preview.extractor import is_raw_file, extract_preview
from backend.thumbnail_cache.utils import (
    generate_single_thumbnail,
    ensure_cache_dir,
)
from backend.thumbnail_cache.cache_manager import DEFAULT_CACHE_DIR
from database.repository import PhotoRepository
from database.models import PhotoRecord

logger = logging.getLogger("importer")


def import_directory(directory: str) -> dict:
    """Execute the full import workflow for *directory*.

    Returns a dict with keys:
        total      — number of images found on disk
        imported   — number of new rows inserted into the database
        skipped    — total - imported (already existed)
        errors     — number of thumbnail-generation failures
        raw_count  — number of RAW files with previews extracted
    """
    # ------------------------------------------------------------------
    # Step 1 — Scan directory
    # ------------------------------------------------------------------
    logger.info("Step 1/6: Scanning %s", directory)
    scanned_photos = collect_scan(directory)
    total = len(scanned_photos)
    logger.info("Found %d image(s)", total)

    if total == 0:
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 0, "raw_count": 0}

    # ------------------------------------------------------------------
    # Step 2 — Extract RAW previews
    # ------------------------------------------------------------------
    logger.info("Step 2/6: Extracting RAW previews")
    raw_count = 0
    # Build a mapping: image_id → raw_preview_path
    preview_map: dict[str, str] = {}

    for p in scanned_photos:
        if not is_raw_file(p.file_path):
            continue
        try:
            preview_path = extract_preview(p.file_path, p.id)
            if preview_path and os.path.isfile(preview_path):
                preview_map[p.id] = preview_path
                raw_count += 1
                logger.info(
                    "RAW preview extracted: %s → %s",
                    p.file_name, preview_path,
                )
            else:
                logger.warning("RAW preview extraction returned no file for %s", p.file_name)
        except Exception as exc:
            logger.warning("RAW preview failed for %s: %s", p.file_name, exc)

    if raw_count > 0:
        logger.info("Extracted %d RAW preview(s)", raw_count)

    # ------------------------------------------------------------------
    # Step 3 — Generate thumbnails (per-file error tolerance)
    # ------------------------------------------------------------------
    logger.info("Step 3/6: Generating thumbnails")
    cache_dir = ensure_cache_dir(DEFAULT_CACHE_DIR)
    thumb_errors = 0

    for p in scanned_photos:
        try:
            # For RAW files, use the extracted preview as the source
            # so Pillow can read it for thumbnail generation
            source = preview_map.get(p.id, p.file_path)
            generate_single_thumbnail(
                source_path=source,
                image_id=p.id,
                cache_dir=cache_dir,
            )
            # generate_single_thumbnail skips already-cached images
        except Exception as exc:
            thumb_errors += 1
            logger.warning("Thumbnail failed for %s: %s", p.file_name, exc)

    # ------------------------------------------------------------------
    # Step 4 — Write to database  (INSERT OR IGNORE → duplicate-safe)
    # ------------------------------------------------------------------
    logger.info("Step 4/6: Writing to database")
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

    # ------------------------------------------------------------------
    # Step 5 — Sync: remove photos from DB whose files no longer exist
    # ------------------------------------------------------------------
    logger.info("Step 5/6: Syncing deleted files")
    all_photos = repo.get_all_photos()
    removed = 0
    for p in all_photos:
        if not os.path.isfile(p.file_path):
            repo.delete_photo(p.image_id)
            removed += 1
            logger.info("Removed stale record: %s", p.file_path)
    if removed > 0:
        logger.info("Synced: %d stale record(s) removed", removed)

    # ------------------------------------------------------------------
    # Step 6 — Return statistics
    # ------------------------------------------------------------------
    result = {
        "total": total,
        "imported": imported,
        "skipped": skipped,
        "errors": thumb_errors,
        "raw_count": raw_count,
        "removed": removed,
    }
    logger.info(
        "Step 6/6: Import complete — total=%d imported=%d skipped=%d raw=%d removed=%d errors=%d",
        total, imported, skipped, raw_count, removed, thumb_errors,
    )
    return result
