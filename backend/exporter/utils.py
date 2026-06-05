"""
PhotoFlow AI — Export Utilities

File copy with duplicate filename safety and optional format conversion.
Streaming-safe — processes one file at a time.
"""

import os
import shutil
import logging

from PIL import Image

logger = logging.getLogger("export")

def _convert_image(source_path: str, target_path: str, target_format: str) -> None:
    """Open source image with Pillow and save in the target format.

    Handles:
      - RGBA / P → RGB for JPEG (no alpha channel support)
      - JPEG quality fixed at 95
    """
    img = Image.open(source_path)
    save_kwargs = {}

    if target_format == "jpeg":
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        save_kwargs["quality"] = 95

    elif target_format == "png":
        # PNG handles RGBA natively — no conversion needed
        pass

    img.save(target_path, format=target_format.upper(), **save_kwargs)
    logger.info("Converted: %s → %s (%s)", os.path.basename(source_path),
                os.path.basename(target_path), target_format)


def copy_file_safe(
    source_path: str,
    target_dir: str,
    target_filename: str = "",
    max_path_length: int = 260,
    export_format: str = "original",
) -> tuple[bool, str]:
    """
    Copy a single file to a target directory with duplicate name safety.

    If a file with the same name already exists, appends _1, _2, etc.

    Args:
        source_path: Absolute path to the source file.
        target_dir: Absolute path to the destination directory.
        target_filename: Optional custom filename (e.g., "Wedding_001.jpg").
                         If empty, uses the original source filename.
        max_path_length: Maximum allowed path length (Windows default 260).
        export_format: "original" (keep source), "jpeg", or "png".

    Returns:
        (success, error_message) — error_message is empty on success.
    """
    # Validate source
    if not os.path.isfile(source_path):
        return False, f"Source file not found: {source_path}"

    # Create target directory
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as exc:
        return False, f"Failed to create target directory: {exc}"

    if target_filename:
        base_name = target_filename
    else:
        base_name = os.path.basename(source_path)
    name, ext = os.path.splitext(base_name)

    # Find a unique filename
    target_path = os.path.join(target_dir, base_name)
    counter = 1
    while os.path.exists(target_path):
        ext_actual = os.path.splitext(base_name)[1]
        target_path = os.path.join(target_dir, f"{name}_{counter}{ext_actual}")
        counter += 1
        if counter > 999:
            return False, f"Too many duplicates for: {base_name}"

    # Check path length
    if len(target_path) >= max_path_length:
        return False, f"Target path too long ({len(target_path)} chars): {target_path}"

    # Copy or convert the file
    try:
        if export_format == "original":
            shutil.copy2(source_path, target_path)
            logger.info("Copied: %s → %s", os.path.basename(source_path), os.path.basename(target_path))
        else:
            _convert_image(source_path, target_path, export_format)
        return True, ""
    except PermissionError:
        return False, f"Permission denied: {source_path}"
    except OSError as exc:
        return False, f"Copy failed: {exc}"


