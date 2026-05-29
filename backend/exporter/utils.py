"""
PhotoFlow AI — Export Utilities

File copy with duplicate filename safety.
Streaming-safe — processes one file at a time.
"""

import os
import shutil
import logging

logger = logging.getLogger("export")


def copy_file_safe(
    source_path: str,
    target_dir: str,
    max_path_length: int = 260,
) -> tuple[bool, str]:
    """
    Copy a single file to a target directory with duplicate name safety.

    If a file with the same name already exists, appends _1, _2, etc.

    Args:
        source_path: Absolute path to the source file.
        target_dir: Absolute path to the destination directory.
        max_path_length: Maximum allowed path length (Windows default 260).

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

    base_name = os.path.basename(source_path)
    name, ext = os.path.splitext(base_name)

    # Find a unique filename
    target_path = os.path.join(target_dir, base_name)
    counter = 1
    while os.path.exists(target_path):
        target_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
        counter += 1
        if counter > 999:
            return False, f"Too many duplicates for: {base_name}"

    # Check path length
    if len(target_path) >= max_path_length:
        return False, f"Target path too long ({len(target_path)} chars): {target_path}"

    # Copy the file
    try:
        shutil.copy2(source_path, target_path)
        logger.debug("Copied: %s → %s", source_path, target_path)
        return True, ""
    except PermissionError:
        return False, f"Permission denied: {source_path}"
    except OSError as exc:
        return False, f"Copy failed: {exc}"


def estimate_export_count(
    photo_ids: list[str],
    repo,
) -> int:
    """
    Count how many source files actually exist for the given photo IDs.

    Args:
        photo_ids: List of image IDs to export.
        repo: PhotoRepository instance.

    Returns:
        Number of exportable files.
    """
    count = 0
    for pid in photo_ids:
        photo = repo.get_photo_by_id(pid)
        if photo and os.path.isfile(photo.file_path):
            count += 1
    return count
