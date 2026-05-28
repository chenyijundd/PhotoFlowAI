"""
PhotoFlow AI - Export Module

Exports selected photos to a target directory while preserving folder structure.
CLI-able skeleton module for V1.

CLI usage:
    python exporter.py --input ./photos --selected ./selected_list.txt --output ./exports

Example input:
    ./photos/wedding_001.jpg
    ./photos/wedding_002.jpg

Example output:
    ./exports/wedding_001.jpg
    ./exports/wedding_002.jpg
"""

import argparse
import os


def export_selected(image_paths: list, output_dir: str) -> dict:
    """Copy selected images to output directory, preserving structure."""
    os.makedirs(output_dir, exist_ok=True)
    return {
        "exported": 0,
        "output_dir": output_dir,
    }


def main():
    parser = argparse.ArgumentParser(description="PhotoFlow AI - Export")
    parser.add_argument("--input", required=True, help="Source directory")
    parser.add_argument("--selected", required=True, help="File with list of selected paths")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    for d in [args.input, args.selected]:
        if not os.path.exists(d):
            print(f"Error: {d} does not exist")
            return

    print(f"Export module ready. Input: {args.input}, Output: {args.output}")
    print("(AI implementation pending)")


if __name__ == "__main__":
    main()
