#!/usr/bin/env python3
"""
PhotoFlow AI — v1 vs v2 Blur Detector Comparison CLI

Scans a directory of images, runs *both* the legacy v1 detector (global
Laplacian) and the v2 detector (multi-patch + centre-weighted) on every
image, and writes a CSV comparison report.

Usage:
    python tests/compare_blur_v1_v2.py --input "D:/Photos/test"
    python tests/compare_blur_v1_v2.py --input "D:/Photos" --threshold 55 --output my_report.csv

Output columns:
    file_name, v1_score, v1_is_blur, v2_score, v2_is_blur,
    v2_w_avg, v2_top_med, agreement, notes

Agreement values:
    both_clear   — neither detector flagged the photo as blurry
    both_blur    — both detectors agree the photo is blurry
    v1_only_blur — v1 says blurry, v2 says clear  (likely a v2 fix)
    v2_only_blur — v2 says blurry, v1 says clear  (possible v2 over-correction)
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from typing import Any

# Ensure the project root is on sys.path.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.ai.blur_detector.detector import calculate_blur, BLUR_THRESHOLD as V1_DEFAULT_THRESHOLD
from backend.ai.blur_detector_v2.detector import calculate_blur_v2, BLUR_THRESHOLD as V2_DEFAULT_THRESHOLD

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def scan_directory(directory: str) -> list[str]:
    """Recursively scan *directory* for supported image files."""
    result: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS:
                result.append(os.path.join(root, f))
    return sorted(result)


def agreement_label(v1_blur: int, v2_blur: int) -> str:
    """Return a human-readable agreement label."""
    if v1_blur == 1 and v2_blur == 1:
        return "both_blur"
    if v1_blur == 0 and v2_blur == 0:
        return "both_clear"
    if v1_blur == 1 and v2_blur == 0:
        return "v1_only_blur"
    return "v2_only_blur"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare v1 (global Laplacian) vs v2 (multi-patch) blur detectors.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Directory containing images to compare.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=V2_DEFAULT_THRESHOLD,
        help=(
            f"Threshold for v2 classification (default: {V2_DEFAULT_THRESHOLD}). "
            f"v1 always uses its own default ({V1_DEFAULT_THRESHOLD}). "
            "Use --v1-threshold to override v1 separately."
        ),
    )
    parser.add_argument(
        "--v1-threshold",
        type=float,
        default=V1_DEFAULT_THRESHOLD,
        help=f"Threshold for v1 classification (default: {V1_DEFAULT_THRESHOLD}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: tests/results/blur_compare.csv).",
    )
    args = parser.parse_args()

    output_path = args.output or os.path.join(
        _PROJECT_ROOT, "tests", "results", "blur_compare.csv"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # ---- Scan ----
    print(f"Scanning: {args.input}")
    files = scan_directory(args.input)
    if not files:
        print("No supported images found.")
        return
    print(f"Found {len(files)} image(s)\n")

    # ---- Process ----
    rows: list[dict[str, Any]] = []
    stats = {
        "both_clear": 0,
        "both_blur": 0,
        "v1_only_blur": 0,
        "v2_only_blur": 0,
        "errors": 0,
    }
    v1_times: list[float] = []
    v2_times: list[float] = []

    print(f"{'#':>4}  {'File':<40} {'v1_score':>9} {'v1':>5} {'v2_score':>9} {'v2':>5}  {'Agreement':<14}")
    print("-" * 96)

    for i, filepath in enumerate(files, 1):
        fname = os.path.basename(filepath)
        row: dict[str, Any] = {"file_name": fname}

        # --- v1 ---
        try:
            t0 = time.perf_counter()
            v1_score, v1_blur = calculate_blur(filepath)
            v1_times.append((time.perf_counter() - t0) * 1000.0)
            row["v1_score"] = round(v1_score, 2)
            row["v1_is_blur"] = v1_blur
        except Exception as exc:
            v1_times.append(0)
            row["v1_score"] = None
            row["v1_is_blur"] = None
            row["v1_error"] = str(exc)

        # --- v2 ---
        try:
            t0 = time.perf_counter()
            v2_score, v2_blur, _, _, w_avg, top_med = calculate_blur_v2(
                filepath,
                threshold=args.threshold,
            )
            v2_times.append((time.perf_counter() - t0) * 1000.0)
            row["v2_score"] = round(v2_score, 2)
            row["v2_is_blur"] = v2_blur
            row["v2_w_avg"] = round(w_avg, 2)
            row["v2_top_med"] = round(top_med, 2)
        except Exception as exc:
            v2_times.append(0)
            row["v2_score"] = None
            row["v2_is_blur"] = None
            row["v2_w_avg"] = None
            row["v2_top_med"] = None
            row["v2_error"] = str(exc)

        # --- Agreement ---
        if row.get("v1_is_blur") is not None and row.get("v2_is_blur") is not None:
            v1b = int(row["v1_is_blur"])
            v2b = int(row["v2_is_blur"])
            ag = agreement_label(v1b, v2b)
            row["agreement"] = ag
            stats[ag] += 1

            # Notes for disagreement analysis
            if ag == "v1_only_blur":
                row["notes"] = (
                    f"v1 says blur ({row['v1_score']:.1f}) but v2 says clear "
                    f"(final={row['v2_score']:.1f}, w_avg={row['v2_w_avg']:.1f}, "
                    f"top_med={row['v2_top_med']:.1f}) — likely bokeh / plain bg rescue"
                )
            elif ag == "v2_only_blur":
                row["notes"] = (
                    f"v2 says blur (final={row['v2_score']:.1f}) but v1 says clear "
                    f"({row['v1_score']:.1f}) — possible v2 over-correction, "
                    f"check w_avg={row['v2_w_avg']:.1f} top_med={row['v2_top_med']:.1f}"
                )
            else:
                row["notes"] = ""
        else:
            row["agreement"] = "error"
            row["notes"] = "One or both detectors failed"
            stats["errors"] += 1

        # Console output
        v1_str = f"{row.get('v1_score', 'ERR'):>9}" if isinstance(row.get("v1_score"), (int, float)) else f"{'ERR':>9}"
        v2_str = f"{row.get('v2_score', 'ERR'):>9}" if isinstance(row.get("v2_score"), (int, float)) else f"{'ERR':>9}"
        v1b_str = "BLUR" if row.get("v1_is_blur") == 1 else ("CLEAR" if row.get("v1_is_blur") == 0 else "ERR")
        v2b_str = "BLUR" if row.get("v2_is_blur") == 1 else ("CLEAR" if row.get("v2_is_blur") == 0 else "ERR")
        print(
            f"{i:>4}  {fname:<40} {v1_str} {v1b_str:>5} {v2_str} {v2b_str:>5}  "
            f"{row.get('agreement', 'error'):<14}"
        )

        rows.append(row)

    # ---- Write CSV ----
    fieldnames = [
        "file_name", "v1_score", "v1_is_blur",
        "v2_score", "v2_is_blur", "v2_w_avg", "v2_top_med",
        "agreement", "notes",
    ]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # ---- Summary ----
    total = len(files)
    agreed = stats["both_clear"] + stats["both_blur"]
    disagreed = stats["v1_only_blur"] + stats["v2_only_blur"]
    agreement_pct = (agreed / total * 100) if total > 0 else 0

    print("\n" + "=" * 96)
    print("SUMMARY")
    print("=" * 96)
    print(f"  Total images:        {total}")
    print(f"  Both clear:          {stats['both_clear']}")
    print(f"  Both blur:           {stats['both_blur']}")
    print(f"  Agreement:           {agreed} / {total} ({agreement_pct:.1f}%)")
    print(f"  v1 only blur:        {stats['v1_only_blur']}  (v2 rescued these)")
    print(f"  v2 only blur:        {stats['v2_only_blur']}  (v2 over-corrections?)")
    print(f"  Errors:              {stats['errors']}")
    if v1_times:
        print(f"  v1 avg time:         {sum(v1_times)/len(v1_times):.1f} ms")
    if v2_times:
        print(f"  v2 avg time:         {sum(v2_times)/len(v2_times):.1f} ms")
    print(f"\n  Report saved to:     {output_path}")

    # Highlight key insight
    if stats["v1_only_blur"] > 0:
        rescued_pct = stats["v1_only_blur"] / total * 100
        print(f"\n  >>> v2 rescued {stats['v1_only_blur']} photos ({rescued_pct:.1f}%) "
              f"that v1 would have falsely flagged as blurry.")
        print(f"  >>> Check the CSV 'notes' column for per-photo analysis.")

    print()


if __name__ == "__main__":
    main()
