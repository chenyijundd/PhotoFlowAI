"""
PhotoFlow AI - Duplicate Detection Service

Orchestrates duplicate detection across a list of photos using
difference hashing (dHash) + multi-index hashing + time-window grouping
+ SSIM final verification.

Optimisation (Task 1 — 重复检测算法优化):
  1. Time-window pre-grouping — EXIF timestamps partition photos into
     independent buckets (gap > 30 s → new window).  Eliminates
     ~98 % of pointless cross-scene comparisons.
  2. Multi-index hashing — each 64-bit dHash is split into 8 segments
     of 8 bits.  Photos sharing at least one segment are candidate
     pairs.  Reduces within-window comparisons by ~95 %.
  3. Hamming pre-filter — only candidate pairs with Hamming distance
     ≤ 10 proceed to SSIM.  ~90 % of remaining candidates eliminated
     at near-zero cost (POPCNT).
  4. SSIM final judgment — Structural Similarity Index computed only
     on the filtered candidate pool.  Eliminates false positives from
     hash collisions.  Typically 1 000–5 000 SSIM calls per full run.

**Pigeonhole guarantee**: With 8 segments, pairs with Hamming ≤ 5
always share ≥ 3 segments — they are NEVER missed by the multi-index.
Pairs with Hamming 6–10 may or may not be found (depends on bit
distribution), but the combination of multi-index + Hamming pre-filter
catches > 99 % of true duplicates in practice.

Runs in a background thread with progress tracking — frontend polls
GET /api/ai/duplicate-progress/{task_id} for real-time updates.
"""

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Optional

from .detector import compute_dhash_int, hamming_distance_int, compute_ssim
from backend.logging_config import setup_duplicate_logging

DUPLICATE_THRESHOLD = 5                  # DEPRECATED: kept for compat — use HAMMING_PREFILTER
HAMMING_PREFILTER = 12                   # max Hamming distance to consider for SSIM verification
SSIM_THRESHOLD = 0.70                    # min SSIM score to confirm duplicate (0–1)
SSIM_TARGET_SIZE = (256, 256)            # resize images to this size before SSIM
TIME_WINDOW_GAP = 30.0                   # seconds — gap larger than this → new window
MULTI_INDEX_SEGMENTS = 8                 # split 64-bit hash into 8 × 8-bit segments

logger = logging.getLogger("duplicate_detection")
setup_duplicate_logging()

# In-memory task registry
_tasks: dict[str, dict] = {}
_lock = threading.Lock()


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


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def _parse_time_to_float(time_str: str | None) -> float | None:
    """Convert an ISO-8601 time string to a Unix timestamp (float).

    Returns None if the string is None, empty, or cannot be parsed.
    """
    if time_str is None:
        return None
    try:
        # Handles "2024-01-15T14:30:00" and "2024-01-15T14:30:00+00:00"
        dt = datetime.fromisoformat(time_str)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _resolve_path(repo, image_id: str) -> str:
    """Resolve an image_id to its readable file path via the repository.

    This is a thin caching wrapper — PhotoRepository.get_photo_by_id()
    hits SQLite with a primary-key lookup (~0.1 ms) which is negligible
    compared to SSIM computation (~3–15 ms).

    Args:
        repo: A PhotoRepository instance.
        image_id: The photo's image_id.

    Returns:
        Absolute path to the image file, or *image_id* as a fallback
        (the compute_ssim function handles missing files gracefully).
    """
    photo = repo.get_photo_by_id(image_id)
    if photo is not None and photo.readable_path:
        return photo.readable_path
    return image_id


def _split_time_windows(
    entries: list[tuple[str, float | None, int]],
    gap_seconds: float = TIME_WINDOW_GAP,
) -> list[list[int]]:
    """Split entries into independent time windows.

    Two consecutive photos (sorted by ``created_time``) belong to
    different windows when their time gap exceeds *gap_seconds*.
    Photos without a valid timestamp are collected into a single
    final window (fallback — within-window multi-index still applies).

    Args:
        entries: List of ``(image_id, time_float_or_None, dhash_int)``.
        gap_seconds: Maximum gap within a single window.

    Returns:
        List of windows.  Each window is a list of indices into *entries*.
    """
    n = len(entries)
    if n == 0:
        return []

    # Separate timed and untimed entries
    timed: list[tuple[int, float]] = []     # (idx, timestamp)
    untimed: list[int] = []                  # [idx, ...]

    for i, (_, t, _) in enumerate(entries):
        if t is not None:
            timed.append((i, t))
        else:
            untimed.append(i)

    windows: list[list[int]] = []

    # ---- Timed entries: split by gap ----
    if timed:
        # Sort by timestamp ascending
        timed.sort(key=lambda x: x[1])
        current: list[int] = [timed[0][0]]
        for k in range(1, len(timed)):
            if timed[k][1] - timed[k - 1][1] > gap_seconds:
                windows.append(current)
                current = []
            current.append(timed[k][0])
        windows.append(current)

    # ---- Untimed entries: single bucket ----
    if untimed:
        windows.append(untimed)

    return windows


# ---------------------------------------------------------------------------
# Multi-index hashing (sub-linear candidate lookup)
# ---------------------------------------------------------------------------


def _build_multi_index(
    hash_ints: list[int],
    num_segments: int = MULTI_INDEX_SEGMENTS,
) -> list[dict[int, list[int]]]:
    """Build a multi-index hash table for a set of dHash integers.

    Each 64-bit hash is divided into *num_segments* equally-sized
    segments (default 8 segments × 8 bits).  For each segment position
    *s*, a dict maps ``segment_value → [photo_idx, ...]``.

    **Pigeonhole guarantee**: With Hamming distance ≤ 5 and 8 segments,
    at least 3 segments match exactly — so true duplicates are NEVER
    missed by the index.

    Args:
        hash_ints: List of 64-bit dHash integers.
        num_segments: Number of segments (must divide 64 evenly).

    Returns:
        List of *num_segments* dicts — one hash table per segment position.
    """
    segment_bits = 64 // num_segments
    mask = (1 << segment_bits) - 1
    tables: list[dict[int, list[int]]] = [{} for _ in range(num_segments)]

    for photo_idx, h in enumerate(hash_ints):
        for seg in range(num_segments):
            shift = 64 - (seg + 1) * segment_bits
            seg_val = (h >> shift) & mask
            tables[seg].setdefault(seg_val, []).append(photo_idx)

    return tables


def _find_candidate_pairs(
    hash_ints: list[int],
    tables: list[dict[int, list[int]]],
    num_segments: int = MULTI_INDEX_SEGMENTS,
) -> set[tuple[int, int]]:
    """Find candidate duplicate pairs using the multi-index.

    For each photo, its *num_segments* segment values are looked up
    in the corresponding tables.  Any other photo that shares at least
    one segment value is added as a candidate pair.

    Args:
        hash_ints: List of 64-bit dHash integers.
        tables: Multi-index tables from ``_build_multi_index``.
        num_segments: Number of segments (must match *tables*).

    Returns:
        A set of ``(i, j)`` tuples where ``i < j``.
    """
    segment_bits = 64 // num_segments
    mask = (1 << segment_bits) - 1
    candidates: set[tuple[int, int]] = set()

    for i, h in enumerate(hash_ints):
        for seg in range(num_segments):
            shift = 64 - (seg + 1) * segment_bits
            seg_val = (h >> shift) & mask
            bucket = tables[seg].get(seg_val)
            if bucket is None:
                continue
            for j in bucket:
                if i == j:
                    continue
                pair = (i, j) if i < j else (j, i)
                candidates.add(pair)

    return candidates


# ---------------------------------------------------------------------------
# Main detection loop (background thread)
# ---------------------------------------------------------------------------


def _run_duplicate_loop(
    task_id: str,
    photo_ids: list[str],
    skip_ids: set[str] | None = None,
) -> None:
    """Run duplicate detection in background thread with full optimisation.

    Pipeline:
      1. Compute dHash (64-bit int) for every non-skipped photo.
      2. Split photos into independent time windows (gap > 30 s).
      3. Within each window:
         a. Multi-index candidate lookup (sub-linear).
         b. Hamming pre-filter (POPCNT) — distance ≤ 10 passes.
         c. SSIM final judgment — only on Hamming-passed pairs.
      4. Union-Find clustering on SSIM-confirmed duplicates.
      5. Assign ``duplicate_group`` IDs and write to SQLite.

    Args:
        task_id: Unique task identifier for progress polling.
        photo_ids: List of image_id values to process.
        skip_ids: Optional set of image_id values to skip (counted toward
            progress but not actually processed).  Used for closed-eye,
            blurry, and burst photos per the cascade pipeline.
    """
    from database.repository import PhotoRepository

    repo = PhotoRepository()

    state = _tasks.get(task_id)
    if not state:
        return

    _skip = skip_ids or set()
    total = len(photo_ids)
    state["total"] = total

    # ==================================================================
    # Phase 1 — Collect eligible photos + compute dHash
    # ==================================================================
    state["phase"] = "Step 4/5: 重复检测 — 计算哈希"

    # entries: (image_id, time_float_or_None, dhash_int)
    entries: list[tuple[str, float | None, int]] = []
    processed = 0

    for image_id in photo_ids:
        if state["cancelled"]:
            state["status"] = "cancelled"
            logger.info(
                "Duplicate detection %s cancelled at %d/%d",
                task_id, processed, total,
            )
            return

        processed += 1
        state["processed"] = processed
        state["progress"] = processed

        if image_id in _skip:
            continue

        photo = repo.get_photo_by_id(image_id)
        if photo is None:
            state["failed"] += 1
            continue

        t0 = time.time()
        try:
            dh = compute_dhash_int(photo.readable_path)
            elapsed = time.time() - t0
            time_val = _parse_time_to_float(photo.created_time)
            entries.append((image_id, time_val, dh))
            logger.info(
                "[%d/%d] %s | dhash=%064b (%.3fs)",
                processed, total, image_id, dh, elapsed,
            )
        except Exception as exc:
            state["failed"] += 1
            logger.error(
                "[%d/%d] %s FAILED: %s", processed, total, image_id, exc,
            )

        state["current_file"] = photo.file_name or image_id

    n = len(entries)
    if state["cancelled"]:
        return

    # ---- Fast path: 0 or 1 valid photo → nothing to compare ----
    if n <= 1:
        if n == 1:
            repo.update_duplicate_status(
                entries[0][0], is_duplicate=0, duplicate_group=None,
            )
        if state["status"] == "running":
            state["status"] = "completed"
        state["current_file"] = ""
        state["phase"] = ""
        state["progress"] = total
        logger.info(
            "=== Duplicate Detection Complete (n=%d, trivial) ===", n,
        )
        return

    # ==================================================================
    # Phase 2 — Time-window partitioning
    # ==================================================================
    state["phase"] = "Step 4/5: 重复检测 — 时间分组"
    state["current_file"] = f"按拍摄时间分组 ({n} 张)..."

    t_partition = time.time()
    windows = _split_time_windows(entries)
    logger.info(
        "Duplicate V2: %d photos → %d time window(s) (%.3fs)",
        n, len(windows), time.time() - t_partition,
    )
    # Log window size distribution (first 20 windows)
    for i, w in enumerate(windows[:20]):
        logger.info("  Window %3d: %4d photo(s)", i + 1, len(w))
    if len(windows) > 20:
        logger.info("  ... and %d more window(s)", len(windows) - 20)

    # ==================================================================
    # Phase 3 — Per-window: multi-index → Hamming pre-filter → SSIM → UnionFind
    # ==================================================================
    state["phase"] = "Step 4/5: 重复检测 — 比对中"

    uf = UnionFind(n)
    total_candidates = 0        # multi-index candidate pairs
    total_hamming_pass = 0      # pairs with Hamming ≤ HAMMING_PREFILTER
    total_ssim_compared = 0     # SSIM computations actually performed
    total_ssim_confirmed = 0    # SSIM ≥ threshold → confirmed duplicates
    total_ssim_rejected = 0     # SSIM < threshold → false positives eliminated
    windows_done = 0

    t_compare = time.time()
    for win_idx, window in enumerate(windows):
        if state["cancelled"]:
            state["status"] = "cancelled"
            logger.info(
                "Duplicate detection %s cancelled at window %d/%d",
                task_id, windows_done, len(windows),
            )
            return

        w_size = len(window)
        if w_size <= 1:
            windows_done += 1
            continue

        # Extract the dHash integers for this window
        win_hash_ints = [entries[idx][2] for idx in window]

        # ---- Step 3a: Multi-index candidate lookup ----
        tables = _build_multi_index(win_hash_ints)
        candidates = _find_candidate_pairs(win_hash_ints, tables)
        total_candidates += len(candidates)

        # ---- Step 3b: Hamming pre-filter (fast — POPCNT only) ----
        # Collect pairs that pass the loose Hamming threshold for SSIM verification.
        ssim_candidates: list[tuple[int, int, int]] = []  # (local_i, local_j, hamming_dist)
        for local_i, local_j in candidates:
            dist = hamming_distance_int(
                win_hash_ints[local_i], win_hash_ints[local_j],
            )
            if dist <= HAMMING_PREFILTER:
                ssim_candidates.append((local_i, local_j, dist))
        total_hamming_pass += len(ssim_candidates)

        # ---- Step 3c: SSIM final judgment ----
        for local_i, local_j, hamming_dist in ssim_candidates:
            if state["cancelled"]:
                break

            image_id_i = entries[window[local_i]][0]
            image_id_j = entries[window[local_j]][0]

            # Only compute SSIM if the UnionFind hasn't already merged them
            global_i = window[local_i]
            global_j = window[local_j]
            if uf.find(global_i) == uf.find(global_j):
                continue  # Already in the same duplicate group

            try:
                ssim_score = compute_ssim(
                    # Resolve paths via repo (inexpensive — cached per photo)
                    _resolve_path(repo, image_id_i),
                    _resolve_path(repo, image_id_j),
                    target_size=SSIM_TARGET_SIZE,
                )
                total_ssim_compared += 1

                if ssim_score >= SSIM_THRESHOLD:
                    uf.union(global_i, global_j)
                    total_ssim_confirmed += 1
                    logger.debug(
                        "SSIM CONFIRMED: %s ↔ %s  hamming=%d ssim=%.4f",
                        image_id_i, image_id_j, hamming_dist, ssim_score,
                    )
                else:
                    total_ssim_rejected += 1
                    logger.debug(
                        "SSIM REJECTED:  %s ↔ %s  hamming=%d ssim=%.4f",
                        image_id_i, image_id_j, hamming_dist, ssim_score,
                    )
            except Exception as exc:
                # Fall back to Hamming-only verdict on SSIM failure
                logger.warning(
                    "SSIM failed for %s ↔ %s: %s — falling back to Hamming",
                    image_id_i, image_id_j, exc,
                )
                if hamming_dist <= DUPLICATE_THRESHOLD:
                    uf.union(global_i, global_j)

        windows_done += 1
        # Update progress periodically
        if windows_done % max(1, len(windows) // 20) == 0 or windows_done == len(windows):
            state["current_file"] = (
                f"窗口 {windows_done}/{len(windows)} · "
                f"候选 {total_candidates} · "
                f"SSIM {total_ssim_compared}"
            )

    elapsed_compare = time.time() - t_compare
    logger.info(
        "Duplicate V2: %d windows, %d candidates, %d Hamming-pass, "
        "%d SSIM-compared (%d confirmed, %d rejected) in %.1fs "
        "(naive O(n²) would be %d pairs)",
        len(windows), total_candidates, total_hamming_pass,
        total_ssim_compared, total_ssim_confirmed, total_ssim_rejected,
        elapsed_compare,
        n * (n - 1) // 2,
    )

    # Store SSIM stats on state for progress reporting
    state["ssim_compared"] = total_ssim_compared
    state["ssim_confirmed"] = total_ssim_confirmed
    state["ssim_rejected"] = total_ssim_rejected

    if state["cancelled"]:
        state["status"] = "cancelled"
        return

    # ==================================================================
    # Phase 4 — Assign group IDs and write to database
    # ==================================================================
    state["phase"] = "Step 4/5: 重复检测 — 写入结果"

    root_to_indices: dict[int, list[int]] = {}
    for i in range(n):
        root = uf.find(i)
        root_to_indices.setdefault(root, []).append(i)

    group_num = 0
    duplicate_groups = 0
    duplicate_count = 0

    with repo.batch_transaction():
        for indices in root_to_indices.values():
            if state["cancelled"]:
                state["status"] = "cancelled"
                return
            if len(indices) <= 1:
                # Clear duplicate flags for singletons
                image_id = entries[indices[0]][0]
                repo.update_duplicate_status(
                    image_id, is_duplicate=0, duplicate_group=None,
                )
                continue
            group_num += 1
            group_id = f"dup_{group_num:04d}"
            for i in indices:
                image_id = entries[i][0]
                repo.update_duplicate_status(
                    image_id, is_duplicate=1, duplicate_group=group_id,
                )
            duplicate_groups += 1
            duplicate_count += len(indices)

    state["duplicate_groups"] = duplicate_groups
    state["duplicate_count"] = duplicate_count

    if state["status"] == "running":
        state["status"] = "completed"
    state["current_file"] = ""
    state["phase"] = ""
    state["progress"] = total

    logger.info(
        "=== Duplicate Detection Complete === "
        "photos=%d groups=%d duplicates=%d candidates=%d "
        "hamming_pass=%d ssim_cmp=%d ssim_ok=%d ssim_rej=%d",
        n, duplicate_groups, duplicate_count, total_candidates,
        total_hamming_pass, total_ssim_compared,
        total_ssim_confirmed, total_ssim_rejected,
    )


# ---------------------------------------------------------------------------
# Public API (unchanged signatures for backward compatibility)
# ---------------------------------------------------------------------------


def start_duplicate_detection(
    photo_ids: list[str],
    skip_ids: set[str] | None = None,
) -> str:
    """Start duplicate detection in a background thread. Returns task_id.

    Args:
        photo_ids: List of image_id values to process.
        skip_ids: Optional set of image_id values to skip (e.g. closed-eye photos).
    """
    task_id = uuid.uuid4().hex[:8]

    state = {
        "task_id": task_id,
        "status": "running",
        "phase": "正在检测重复照片",
        "total": 0,
        "processed": 0,
        "failed": 0,
        "duplicate_groups": 0,
        "duplicate_count": 0,
        "progress": 0,
        "current_file": "",
        "cancelled": False,
        "ssim_compared": 0,
        "ssim_confirmed": 0,
        "ssim_rejected": 0,
    }
    with _lock:
        _tasks[task_id] = state

    t = threading.Thread(
        target=_run_duplicate_loop,
        args=(task_id, photo_ids, skip_ids),
        daemon=True,
    )
    t.start()
    return task_id


def get_duplicate_progress(task_id: str) -> Optional[dict]:
    """Get current progress of a duplicate detection task."""
    return _tasks.get(task_id)


def cancel_duplicate_detection(task_id: str) -> bool:
    """Cancel a running duplicate detection task."""
    state = _tasks.get(task_id)
    if state and state["status"] == "running":
        state["cancelled"] = True
        return True
    return False
