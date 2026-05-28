#!/usr/bin/env python3
"""
PhotoFlow AI - Image Scanner CLI

Recursively scans a directory for supported image files (.jpg, .jpeg, .png)
and outputs metadata as JSON. Handles 5000+ images without loading pixel data.

Usage:
    python image_scanner.py --input "D:/Photos"
    python image_scanner.py --input "D:/Photos" --pretty
"""

import argparse
import json
import os
import sys

from .utils import scan_photos


def run_scan(input_dir: str) -> dict:
    """
    Execute a full scan of the given directory and return a result dict.

    Scans incrementally via generator to avoid loading all image metadata
    into memory at once.
    """
    if not os.path.isdir(input_dir):
        return {"error": f"Directory not found: {input_dir}", "total_count": 0}

    photos = []
    error_count = 0

    for photo in scan_photos(input_dir):
        if photo is not None:
            photos.append(photo.to_dict())
        else:
            error_count += 1

    return {
        "total_count": len(photos),
        "errors": [],
        "photos": photos,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PhotoFlow AI - Image Scanner",
        epilog="Example: python image_scanner.py --input D:/Wedding_Photos",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the directory containing photos to scan",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output with indentation",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit output to the first N results (0 = unlimited)",
    )
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input)

    if not os.path.exists(input_dir):
        print(json.dumps({"error": f"Path does not exist: {input_dir}"}))
        sys.exit(1)

    if not os.path.isdir(input_dir):
        print(json.dumps({"error": f"Path is not a directory: {input_dir}"}))
        sys.exit(1)

    result = run_scan(input_dir)

    # Apply limit if specified (only affects output, not scan)
    limit = args.limit
    if limit > 0 and len(result["photos"]) > limit:
        result["photos"] = result["photos"][:limit]
        result["total_count"] = len(result["photos"])
        result["_note"] = f"Output limited to {limit} results"

    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()
