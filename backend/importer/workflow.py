"""
PhotoFlow AI - Import Workflow

Orchestrates the complete photo import pipeline:

  Step 1 — Scan directory for images         (image_loader)
  Step 2 — Generate thumbnails                (thumbnail_cache)
  Step 3 — Write metadata to SQLite           (database repository)
  Step 4 — Return import statistics

Each photo is processed individually so a single failure does not
abort the entire import.
"""

import logging
from typing import List

from backend.image_loader.utils import collect_scan
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
    """
    # ------------------------------------------------------------------
    # Step 1 — Scan directory
    # ------------------------------------------------------------------
    logger.info("Step 1/4: Scanning %s", directory)
    scanned_photos = collect_scan(directory)
    total = len(scanned_photos)
    logger.info("Found %d image(s)", total)

    if total == 0:
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 0}

    # ------------------------------------------------------------------
    # Step 2 — Generate thumbnails (per-file error tolerance)
    # ------------------------------------------------------------------
    logger.info("Step 2/4: Generating thumbnails")
    cache_dir = ensure_cache_dir(DEFAULT_CACHE_DIR)
    thumb_errors = 0

    for p in scanned_photos:
        try:
            generate_single_thumbnail(
                source_path=p.file_path,
                image_id=p.id,
                cache_dir=cache_dir,
            )
            # generate_single_thumbnail skips already-cached images
        except Exception as exc:
            thumb_errors += 1
            logger.warning("Thumbnail failed for %s: %s", p.file_name, exc)

    # ------------------------------------------------------------------
    # Step 3 — Write to database  (INSERT OR IGNORE → duplicate-safe)
    # ------------------------------------------------------------------
    logger.info("Step 3/4: Writing to database")
    records: List[PhotoRecord] = []
    for p in scanned_photos:
        records.append(
            PhotoRecord(
                image_id=p.id,
                file_name=p.file_name,
                file_path=p.file_path,
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
    # Step 4 — Return statistics
    # ------------------------------------------------------------------
    result = {
        "total": total,
        "imported": imported,
        "skipped": skipped,
        "errors": thumb_errors,
    }
    logger.info("Step 4/4: Import complete — %s", result)
    return result
