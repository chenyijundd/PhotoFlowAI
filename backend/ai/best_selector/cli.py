#!/usr/bin/env python3
"""
PhotoFlow AI - Best Selector CLI

Standalone entry point for best-in-burst photo recommendation.

Usage:
    python backend/ai/best_selector/cli.py
    python backend/ai/best_selector/cli.py --db "D:/custom.db"
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

from backend.ai.best_selector.service import select_best_for_all_bursts
from backend.ai.best_selector.selector import select_best
from database.repository import PhotoRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Best-in-Burst Selector — pick the best photo from each burst group",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database (default: auto-detect).",
    )
    args = parser.parse_args()

    repo = PhotoRepository(db_path=args.db)
    repo.init_database()

    group_ids = repo.get_burst_groups()
    if not group_ids:
        print("No burst groups found. Run burst detection first.")
        return

    print(f"Burst groups: {len(group_ids)}")
    print(f"Database: {repo.db_path or 'auto-detected'}\n")

    summary = select_best_for_all_bursts(repo)

    # ---- Detailed per-group output ----
    print("=" * 70)
    print("PER-GROUP RESULTS")
    print("=" * 70)

    for gid in group_ids:
        photos = repo.get_burst_group_photos(gid)
        selection = select_best(photos)

        print(f"\n  {gid} ({len(photos)} photos)")

        if selection.recommended_id:
            rec = next(
                (r for r in selection.rankings if r.is_recommended), None
            )
            if rec:
                print(f"    Recommended: {rec.image_id} ({rec.file_name})")
            print(f"    Reason:      {selection.selection_reason}")

            # Show ranking
            for r in selection.rankings[:5]:  # top 5
                marker = " >>>" if r.is_recommended else "    "
                print(
                    f"    {marker} #{r.rank}: {r.image_id}  "
                    f"blur={r.blur_score:.1f}  "
                    f"size={r.file_size:,}"
                )
            if len(selection.rankings) > 5:
                print(f"        ... and {len(selection.rankings) - 5} more")
        else:
            print(f"    {selection.selection_reason}")

    # ---- Summary ----
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total groups:          {summary.total_groups}")
    print(f"  Recommended:           {summary.recommended_count}")
    print(f"  No candidate:          {summary.no_candidate_count}")
    print(f"  Avg candidates/group:  {summary.avg_group_size:.1f}")
    print()


if __name__ == "__main__":
    main()
