"""
PhotoFlow AI - Scoring Module

Computes a composite 1-5 star rating based on blur, eye, duplicate, and exposure analysis.
CLI-able skeleton module for V1.

CLI usage:
    python scorer.py --input ./photos

Example output:
    {
        "photo_001.jpg": {"overall": 4, "clarity": 5, "face": 4, "exposure": 4, "composition": 3},
        "photo_002.jpg": {"overall": 2, "clarity": 1, "face": 3, "exposure": 3, "composition": 2}
    }
"""

import argparse
import os


def score_image(image_path: str) -> dict:
    """Compute composite score (1-5) for a single image."""
    return {
        "file": os.path.basename(image_path),
        "overall": 3,
        "clarity": 3,
        "face": 3,
        "exposure": 3,
        "composition": 3,
    }


def main():
    parser = argparse.ArgumentParser(description="PhotoFlow AI - Scoring")
    parser.add_argument("--input", required=True, help="Input image or directory path")
    args = parser.parse_args()

    path = args.input
    if not os.path.exists(path):
        print(f"Error: {path} does not exist")
        return

    print(f"Scoring module ready. Input: {path}")
    print("(AI implementation pending)")


if __name__ == "__main__":
    main()
