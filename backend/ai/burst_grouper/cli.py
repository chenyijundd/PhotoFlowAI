#!/usr/bin/env python3
"""
PhotoFlow AI - Burst Grouper CLI

Standalone command-line entry point for burst / continuous-shooting
grouping based on EXIF time proximity.

Usage:
    python backend/ai/burst_grouper/cli.py
    python backend/ai/burst_grouper/cli.py --gap 1.5
    python backend/ai/burst_grouper/cli.py --db "D:/custom.db"
"""

from __future__ import annotations

import argparse
import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.ai.burst_grouper.grouper import BURST_GAP_SECONDS
from backend.ai.burst_grouper.service import run_burst_grouping
from database.repository import PhotoRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Burst Grouper — EXIF time-clustering for continuous-shooting detection",
    )
    parser.add_argument(
        "--gap",
        type=float,
        default=BURST_GAP_SECONDS,
        help=f"Max gap between consecutive photos in a burst (seconds, default: {BURST_GAP_SECONDS})",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database (default: auto-detect).",
    )
    args = parser.parse_args()

    repo = PhotoRepository(db_path=args.db)
    repo.init_database()

    # Check there are photos
    all_photos = repo.get_all_photos()
    if not all_photos:
        print("No photos in database. Import photos first.")
        return

    print(f"Database: {repo.db_path or 'auto-detected'}")
    print(f"Total photos: {len(all_photos)}")
    print(f"Gap threshold: {args.gap}s\n")

    # Run grouping
    summary = run_burst_grouping(repo, gap_seconds=args.gap)

    # ---- Output ----
    print("=" * 60)
    print("BURST GROUPING RESULTS")
    print("=" * 60)
    print(f"  Total photos:          {summary.total_photos}")
    print(f"  Burst groups found:    {summary.burst_groups_count}")
    print(f"  Photos in bursts:      {summary.photos_in_bursts}")
    print(f"  Photos not in bursts:  {summary.photos_not_in_bursts}")
    print(f"  Skipped (no time):     {summary.skipped_no_time}")

    if summary.group_sizes:
        sizes = summary.group_sizes
        print(f"\n  Group size distribution:")
        print(f"    Max per group:       {max(sizes)}")
        print(f"    Min per group:       {min(sizes)}")
        print(f"    Average:             {sum(sizes) / len(sizes):.1f}")

        # Bucket distribution
        buckets: dict[str, int] = {}
        for s in sizes:
            if s <= 3:
                key = "2-3"
            elif s <= 5:
                key = "4-5"
            elif s <= 10:
                key = "6-10"
            elif s <= 20:
                key = "11-20"
            else:
                key = "21+"
            buckets[key] = buckets.get(key, 0) + 1

        print(f"\n  Groups by size range:")
        for key in ["2-3", "4-5", "6-10", "11-20", "21+"]:
            if key in buckets:
                print(f"    {key} photos:  {buckets[key]} groups")

    print()


if __name__ == "__main__":
    main()
