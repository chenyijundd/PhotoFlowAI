"""
PhotoFlow AI - Duplicate Detection Service

Orchestrates duplicate detection across a list of photos using
perceptual hashing (phash) and Hamming Distance comparison.

Algorithm:
  1. Compute phash for each photo sequentially (one image at a time).
  2. Pairwise compare all hashes via Hamming Distance.
  3. Group duplicates (distance <= 5) using union-find.
  4. Assign group IDs (dup_0001, dup_0002, ...) and write to database.
"""

import logging
import time
from typing import Optional

from .detector import compute_phash, hamming_distance
from backend.logging_config import setup_duplicate_logging

DUPLICATE_THRESHOLD = 5

logger = logging.getLogger("duplicate_detection")

# Ensure rotating log handler is set up at import time
setup_duplicate_logging()


class UnionFind:
    """Union-Find / Disjoint Set Union data structure."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.size[rx] < self.size[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        self.size[rx] += self.size[ry]


def run_duplicate_detection(
    photo_ids: list[str],
    repo,
    log_path: Optional[str] = None,
) -> tuple[int, int, int]:
    """Run duplicate detection on a list of photo IDs.

    Args:
        photo_ids: List of image IDs to process.
        repo: PhotoRepository instance for database operations.
        log_path: Deprecated — rotating log is configured at import time.

    Returns:
        (processed_count, duplicate_group_count, duplicate_count)
    """

    total = len(photo_ids)
    processed = 0
    failed = 0
    total_time = 0.0

    logger.info("=== Duplicate Detection Start ===")
    logger.info("Total photos: %d", total)

    # Step 1: Compute phashes
    phashes: list[tuple[str, int, imagehash.ImageHash]] = []  # (image_id, index, hash)

    for idx, image_id in enumerate(photo_ids, 1):
        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            logger.warning("[%d/%d] Skipping unknown image_id: %s", idx, total, image_id)
            failed += 1
            continue

        t0 = time.time()
        try:
            phash = compute_phash(photo.file_path)
            elapsed = time.time() - t0
            total_time += elapsed
            phashes.append((image_id, len(phashes), phash))
            processed += 1
            logger.info(
                "[%d/%d] %s | phash=%s (%.3fs)",
                idx, total, image_id, str(phash), elapsed,
            )
        except Exception as exc:
            elapsed = time.time() - t0
            total_time += elapsed
            failed += 1
            logger.error(
                "[%d/%d] %s FAILED: %s (%.3fs)",
                idx, total, image_id, exc, elapsed,
            )

    # Step 2: Pairwise comparison and grouping
    n = len(phashes)
    duplicate_groups = 0
    duplicate_count = 0

    if n > 1:
        uf = UnionFind(n)
        comparison_time = 0.0
        compared = 0

        logger.info("Starting pairwise comparison (%d items)...", n)
        t0 = time.time()

        for i in range(n):
            for j in range(i + 1, n):
                dist = hamming_distance(phashes[i][2], phashes[j][2])
                compared += 1
                if dist <= DUPLICATE_THRESHOLD:
                    uf.union(i, j)

        comparison_time = time.time() - t0
        logger.info(
            "Comparison complete: %d pairs in %.3fs",
            compared, comparison_time,
        )
        total_time += comparison_time

        # Step 3: Collect groups by root
        root_to_indices: dict[int, list[int]] = {}
        for i in range(n):
            root = uf.find(i)
            root_to_indices.setdefault(root, []).append(i)

        # Step 4: Assign group IDs to groups with 2+ members
        group_num = 0
        for indices in root_to_indices.values():
            if len(indices) <= 1:
                # Singleton — not a duplicate
                continue
            group_num += 1
            group_id = f"dup_{group_num:04d}"
            for i in indices:
                image_id = phashes[i][0]
                repo.update_duplicate_status(
                    image_id, is_duplicate=1, duplicate_group=group_id,
                )
            duplicate_groups += 1
            duplicate_count += len(indices)
            logger.info(
                "Group %s: %d photos — %s",
                group_id, len(indices),
                ", ".join(phashes[i][0] for i in indices),
            )

        # Clear duplicate flags for singletons (they were not duplicates)
        for indices in root_to_indices.values():
            if len(indices) <= 1:
                i = indices[0]
                image_id = phashes[i][0]
                repo.update_duplicate_status(
                    image_id, is_duplicate=0, duplicate_group=None,
                )

    avg_time = total_time / max(processed, 1)
    logger.info("=== Duplicate Detection Complete ===")
    logger.info(
        "Processed: %d | Groups: %d | Duplicates: %d | Failed: %d",
        processed, duplicate_groups, duplicate_count, failed,
    )
    logger.info("Avg time per image: %.3fs", avg_time)

    return processed, duplicate_groups, duplicate_count
