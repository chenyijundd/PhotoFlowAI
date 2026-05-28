"""
PhotoFlow AI - Image Loader Module

CLI usage:
    python loader.py --input ./photos
"""

import argparse
import os
from pathlib import Path

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png"}


def scan_images(input_dir: str) -> list:
    """Scan directory for supported image files."""
    images = []
    for root, _, files in os.walk(input_dir):
        for f in sorted(files):
            ext = Path(f).suffix.lower()
            if ext in SUPPORTED_FORMATS:
                images.append(os.path.join(root, f))
    return images


def main():
    parser = argparse.ArgumentParser(description="PhotoFlow AI - Image Loader")
    parser.add_argument("--input", required=True, help="Input directory path")
    args = parser.parse_args()

    if not os.path.isdir(args.input):
        print(f"Error: {args.input} is not a valid directory")
        return

    images = scan_images(args.input)
    print(f"Found {len(images)} images in {args.input}")
    for img in images[:10]:
        print(f"  {img}")
    if len(images) > 10:
        print(f"  ... and {len(images) - 10} more")


if __name__ == "__main__":
    main()
