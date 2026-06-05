#!/usr/bin/env python3
"""
PhotoFlow AI - Blur Detector V2 CLI

Standalone command-line entry point for testing and benchmarking
the multi‑patch blur detector.

Usage:
    python backend/ai/blur_detector_v2/cli.py --input "D:/Photos/test"
    python backend/ai/blur_detector_v2/cli.py --input "D:/Photos" --threshold 60
    python backend/ai/blur_detector_v2/cli.py --input "D:/Photos" --grid 3

The CLI scans the given directory for images, runs v2 detection on
each one, and prints a summary to stdout.
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure the project root is on sys.path so we can import sibling packages.
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.ai.blur_detector_v2.detector import (
    BLUR_THRESHOLD,
    PATCH_GRID,
    calculate_blur_v2,
)
from backend.ai.blur_detector_v2.models import BlurDetectionResult

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png"}


def scan_directory(directory: str) -> list[str]:
    """Recursively scan *directory* for supported image files."""
    result: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS:
                result.append(os.path.join(root, f))
    return sorted(result)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Blur Detector V2 — Multi-patch Laplacian Variance",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Directory containing images to analyse.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=BLUR_THRESHOLD,
        help=f"Blur classification threshold (default: {BLUR_THRESHOLD}).",
    )
    parser.add_argument(
        "--grid",
        type=int,
        default=PATCH_GRID,
        help=f"Patch grid size, e.g. 4 → 4×4=16 patches (default: {PATCH_GRID}).",
    )
    args = parser.parse_args()

    # ---- Find images ----
    print(f"Scanning: {args.input}")
    files = scan_directory(args.input)
    if not files:
        print("No supported images found.")
        return

    print(f"Found {len(files)} image(s)\n")

    # ---- Process ----
    results: list[BlurDetectionResult] = []
    errors = 0
    times: list[float] = []

    print(f"{'#':>4}  {'File':<40} {'Score':>8} {'Verdict':>8}  {'Time':>8}")
    print("-" * 76)

    for i, filepath in enumerate(files, 1):
        fname = os.path.basename(filepath)

        try:
            score, is_blur, patch_scores, proc_ms, w_avg, top_med = calculate_blur_v2(
                filepath,
                threshold=args.threshold,
                patch_grid=args.grid,
            )
            verdict = "BLUR" if is_blur else "CLEAR"
            print(
                f"{i:>4}  {fname:<40} {score:>8.1f} {verdict:>8}  {proc_ms:>7.1f}ms"
            )

            results.append(
                BlurDetectionResult(
                    image_id=fname,
                    file_path=filepath,
                    blur_score=score,
                    is_blur=is_blur,
                    patch_scores=patch_scores,
                    processing_time_ms=proc_ms,
                )
            )
            times.append(proc_ms)

        except Exception as exc:
            errors += 1
            print(f"{i:>4}  {fname:<40} {'ERROR':>8} {'ERROR':>8}  — {exc}")

    # ---- Summary ----
    blurred = sum(1 for r in results if r.is_blur)
    clear = len(results) - blurred
    print("\n" + "=" * 76)
    print("SUMMARY")
    print("=" * 76)
    print(f"  Total:          {len(files)}")
    print(f"  Blurred:        {blurred}")
    print(f"  Clear:          {clear}")
    print(f"  Errors:         {errors}")
    if times:
        avg_ms = sum(times) / len(times)
        print(f"  Avg time:       {avg_ms:.1f} ms")
        print(f"  Total time:     {sum(times) / 1000:.2f} s")

    # ---- Score distribution ----
    if results:
        scores = [r.blur_score for r in results]
        scores_sorted = sorted(scores)
        n = len(scores_sorted)
        print(f"\n  Score distribution (threshold={args.threshold:.1f}):")
        print(f"    Max:           {scores_sorted[-1]:.1f}")
        print(f"    Min:           {scores_sorted[0]:.1f}")
        print(f"    Median:        {scores_sorted[n // 2]:.1f}")
        if n >= 4:
            q1 = scores_sorted[n // 4]
            q3 = scores_sorted[3 * n // 4]
            print(f"    Q1:            {q1:.1f}")
            print(f"    Q3:            {q3:.1f}")

    # ---- Per-photo patch detail ----
    if results:
        print(f"\n  Per-photo patch scores ({args.grid}x{args.grid} grid):")
        for r in results:
            print(
                f"    {r.image_id:<40} "
                f"score={r.blur_score:>7.1f}  "
                f"patches={[round(s, 1) for s in r.patch_scores]}"
            )

    print()


if __name__ == "__main__":
    main()
