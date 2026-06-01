#!/usr/bin/env python3
"""
PhotoFlow AI - Eye Detection CLI

Standalone command-line entry point for testing and benchmarking
the MediaPipe + EAR eye detector.

Usage:
    python -m backend.ai.eye_detection.cli --input "D:/Photos/test"
    python -m backend.ai.eye_detection.cli --input "D:/Photos/test" --output results.json
    python -m backend.ai.eye_detection.cli --input "D:/Photos/portrait.jpg"

The CLI scans the given directory for images (or processes a single file),
runs eye detection on each one, and prints a summary to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Ensure the project root is on sys.path so we can import sibling packages.
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.ai.eye_detection.eye_detector import (
    detect_eyes,
    detect_eyes_batch,
    EAR_CLOSED_THRESHOLD,
    EAR_HALF_CLOSED_THRESHOLD,
)
from backend.ai.eye_detection.models import EyeDetectionResult, EyeDetectionSummary

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
        description="Eye Detection - MediaPipe Face Mesh + EAR",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Image file or directory containing images to analyse.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSON file to write detailed results to.",
    )
    args = parser.parse_args()

    # ---- Find images ----
    if os.path.isfile(args.input):
        files = [args.input]
    elif os.path.isdir(args.input):
        print(f"Scanning: {args.input}")
        files = scan_directory(args.input)
        if not files:
            print("No supported images found.")
            return
        print(f"Found {len(files)} image(s)\n")
    else:
        print(f"Error: {args.input} does not exist")
        return

    # ---- Process ----
    results: list[dict] = []
    errors = 0
    times: list[float] = []
    total_closed = 0
    total_no_face = 0

    print(
        f"{'#':>4}  {'File':<40} {'Eyes':>8} {'Score':>8}  "
        f"{'Faces':>6} {'Closed':>7}  {'Time':>8}"
    )
    print("-" * 90)

    for i, filepath in enumerate(files, 1):
        fname = os.path.basename(filepath)

        try:
            r = detect_eyes(filepath)
            eyes_label = "OPEN" if r["eyes_open"] else "CLOSED"
            faces_str = str(r["num_faces"]) if r["face_detected"] else "--"
            closed_str = str(r["closed_count"]) if r["face_detected"] else "--"

            print(
                f"{i:>4}  {fname:<40} {eyes_label:>8} {r['score']:>8.4f}  "
                f"{faces_str:>6} {closed_str:>7}  {r['processing_time_ms']:>7.1f}ms"
            )

            if not r["eyes_open"]:
                total_closed += 1
            if not r["face_detected"]:
                total_no_face += 1

            results.append(r)
            times.append(r["processing_time_ms"])

        except Exception as exc:
            errors += 1
            print(f"{i:>4}  {fname:<40} {'ERROR':>8} {'--':>8}  --")
            results.append({"file": filepath, "error": str(exc)})

    # ---- Summary ----
    total_open = len(files) - total_closed - errors
    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)
    print(f"  Total:              {len(files)}")
    print(f"  Eyes open:          {total_open}")
    print(f"  Eyes closed:        {total_closed}")
    print(f"  No face detected:   {total_no_face}")
    print(f"  Errors:             {errors}")
    if times:
        avg_ms = sum(times) / len(times)
        print(f"  Avg time:           {avg_ms:.1f} ms")
        print(f"  Total time:         {sum(times) / 1000:.2f} s")

    # ---- Score distribution ----
    valid_scores = [r["score"] for r in results if "score" in r and r.get("face_detected")]
    if valid_scores:
        scores_sorted = sorted(valid_scores)
        n = len(scores_sorted)
        print(f"\n  EAR distribution (closed < {EAR_HALF_CLOSED_THRESHOLD}, fully-closed < {EAR_CLOSED_THRESHOLD}):")
        print(f"    Max:               {scores_sorted[-1]:.4f}")
        print(f"    Min:               {scores_sorted[0]:.4f}")
        print(f"    Median:            {scores_sorted[n // 2]:.4f}")
        if n >= 4:
            print(f"    Q1:                {scores_sorted[n // 4]:.4f}")
            print(f"    Q3:                {scores_sorted[3 * n // 4]:.4f}")

    # ---- Per-face detail ----
    for r in results:
        if "per_face" in r and r["per_face"]:
            fname = os.path.basename(r.get("file", ""))
            print(f"\n  {fname} - {r['num_faces']} face(s), {r['closed_count']} closed:")
            for face in r["per_face"]:
                status = "CLOSED" if face["is_closed"] else "open"
                print(
                    f"    Face #{face['face_index']}: "
                    f"L={face['left_ear']:.4f} R={face['right_ear']:.4f} "
                    f"min={face['min_ear']:.4f} → {status}"
                )

    # ---- JSON output ----
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n  Detailed results written to: {args.output}")

    print()


if __name__ == "__main__":
    main()
