"""
PhotoFlow AI - Duplicate Detection Module

Detects near-duplicate images (burst shots, highly similar compositions).
CLI-able skeleton module for V1.

CLI usage:
    python duplicate_detector.py --input ./photos

Example input:
    ./photos/burst_001.jpg
    ./photos/burst_002.jpg  (very similar to burst_001)
    ./photos/different.jpg  (completely different)

Example output:
    {
        "groups": [
            {"best": "burst_001.jpg", "duplicates": ["burst_002.jpg"], "similarity": 0.95}
        ]
    }
"""

import argparse
import os


def find_duplicates(image_paths: list) -> dict:
    """Group near-duplicate images and recommend the best one."""
    return {
        "groups": [],
        "total_duplicates": 0,
        "total_unique": len(image_paths),
    }


def main():
    parser = argparse.ArgumentParser(
        description="PhotoFlow AI - Duplicate Detection"
    )
    parser.add_argument("--input", required=True, help="Input directory path")
    args = parser.parse_args()

    path = args.input
    if not os.path.exists(path):
        print(f"Error: {path} does not exist")
        return

    print(f"Duplicate detection module ready. Input: {path}")
    print("(AI implementation pending)")


if __name__ == "__main__":
    main()
