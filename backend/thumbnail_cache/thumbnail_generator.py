#!/usr/bin/env python3
"""
PhotoFlow AI - Thumbnail Generator CLI

Scans a directory for supported images and generates 200px max-side
JPEG thumbnails. Skips images whose thumbnails are already cached.

Usage:
    python thumbnail_generator.py --input "D:/Photos"
    python thumbnail_generator.py --input "D:/Photos" --cache-dir ./my_cache
"""

import argparse
import json
import os
import sys

from .cache_manager import CacheManager


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PhotoFlow AI - Thumbnail Generator",
        epilog="Scans images and generates 200px max-side JPEG thumbnails.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the directory containing photos",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Custom thumbnail cache directory (default: ./cache/thumbnails)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input)

    if not os.path.isdir(input_dir):
        print(json.dumps({"error": f"Directory not found: {input_dir}"}))
        sys.exit(1)

    manager = CacheManager(cache_dir=args.cache_dir)
    results = manager.process_directory(input_dir)
    summary = manager.summary

    output = {
        "summary": summary,
        "results": [r.to_dict() for r in results],
    }

    indent = 2 if args.pretty else None
    print(json.dumps(output, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()
