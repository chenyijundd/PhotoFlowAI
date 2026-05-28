"""
PhotoFlow AI - Blur Detection Service

Orchestrates blur detection across a list of photos.
Processes images sequentially to avoid loading all originals at once.
"""

import logging
import time
from typing import Optional

from .detector import calculate_blur

logger = logging.getLogger("blur_detection")


def run_blur_detection(
    photo_ids: list[str],
    repo,
    log_path: Optional[str] = None,
) -> tuple[int, int]:
    """Run blur detection on a list of photo IDs.

    Args:
        photo_ids: List of image IDs to process.
        repo: PhotoRepository instance for database operations.
        log_path: Optional path to write a detection log file.

    Returns:
        (processed_count, blurred_count)
    """
    if log_path:
        fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        ))
        logger.addHandler(fh)

    total = len(photo_ids)
    processed = 0
    blurred = 0
    failed = 0
    total_time = 0.0

    logger.info("=== Blur Detection Start ===")
    logger.info("Total photos: %d", total)

    for idx, image_id in enumerate(photo_ids, 1):
        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            logger.warning("[%d/%d] Skipping unknown image_id: %s", idx, total, image_id)
            failed += 1
            continue

        t0 = time.time()
        try:
            score, is_blur = calculate_blur(photo.file_path)
            elapsed = time.time() - t0
            total_time += elapsed

            repo.update_blur_status(image_id, is_blur=is_blur, blur_score=score)

            processed += 1
            if is_blur:
                blurred += 1

            logger.info(
                "[%d/%d] %s | score=%.2f is_blur=%d (%.3fs)",
                idx, total, image_id, score, is_blur, elapsed,
            )
        except Exception as exc:
            elapsed = time.time() - t0
            total_time += elapsed
            failed += 1
            logger.error(
                "[%d/%d] %s FAILED: %s (%.3fs)",
                idx, total, image_id, exc, elapsed,
            )

    avg_time = total_time / max(processed + failed, 1)
    logger.info("=== Blur Detection Complete ===")
    logger.info("Processed: %d | Blurred: %d | Failed: %d", processed, blurred, failed)
    logger.info("Avg time per image: %.3fs", avg_time)

    if log_path:
        logger.removeHandler(fh)
        fh.close()

    return processed, blurred
