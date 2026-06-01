"""
PhotoFlow AI — Centralized Logging Configuration

Sets up rotating file handlers for all backend log files.
Rotation policy: max 10 MB per file, keep 5 backups.

Usage:
    from backend.logging_config import setup_logging
    setup_logging()  # Call once at application startup
"""

import os
import logging
from logging.handlers import RotatingFileHandler

# Log directory (relative to this file: backend/ → project root/)
LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
)

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

_LOG_FORMAT = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _create_rotating_handler(filename: str) -> RotatingFileHandler:
    """Create a RotatingFileHandler for the given log filename."""
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, filename)
    handler = RotatingFileHandler(
        path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(_LOG_FORMAT)
    return handler


def setup_importer_logging() -> logging.Logger:
    """Set up rotating log for the importer module."""
    logger = logging.getLogger("importer")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()

    handler = _create_rotating_handler("import.log")
    logger.addHandler(handler)
    return logger


def setup_blur_logging() -> logging.Logger:
    """Set up rotating log for blur detection."""
    logger = logging.getLogger("blur_detection")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = _create_rotating_handler("blur_detection.log")
    logger.addHandler(handler)
    return logger


def setup_duplicate_logging() -> logging.Logger:
    """Set up rotating log for duplicate detection."""
    logger = logging.getLogger("duplicate_detection")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = _create_rotating_handler("duplicate_detection.log")
    logger.addHandler(handler)
    return logger


def setup_app_logging() -> logging.Logger:
    """Set up rotating log for general application events."""
    logger = logging.getLogger("photoflow")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = _create_rotating_handler("app.log")
    logger.addHandler(handler)
    return logger


def setup_export_logging() -> logging.Logger:
    """Set up rotating log for export operations."""
    logger = logging.getLogger("export")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = _create_rotating_handler("export.log")
    logger.addHandler(handler)
    return logger


def setup_batch_operations_logging() -> logging.Logger:
    """Set up rotating log for batch operations."""
    logger = logging.getLogger("batch_operations")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = _create_rotating_handler("batch_operations.log")
    logger.addHandler(handler)
    return logger


def setup_best_selector_logging() -> logging.Logger:
    """Set up rotating log for best-in-burst selection."""
    logger = logging.getLogger("best_selector")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = _create_rotating_handler("best_selector.log")
    logger.addHandler(handler)
    return logger


def setup_burst_grouping_logging() -> logging.Logger:
    """Set up rotating log for burst grouping."""
    logger = logging.getLogger("burst_grouping")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = _create_rotating_handler("burst_grouping.log")
    logger.addHandler(handler)
    return logger


def setup_blur_v2_logging() -> logging.Logger:
    """Set up rotating log for blur detection v2."""
    logger = logging.getLogger("blur_detection_v2")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = _create_rotating_handler("blur_detection_v2.log")
    logger.addHandler(handler)
    return logger


def setup_eye_detection_logging() -> logging.Logger:
    """Set up rotating log for eye detection."""
    logger = logging.getLogger("eye_detection")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = _create_rotating_handler("eye_detection.log")
    logger.addHandler(handler)
    return logger


def setup_all_logging():
    """Initialize all rotating log handlers at once. Call at startup."""
    setup_importer_logging()
    setup_blur_logging()
    setup_duplicate_logging()
    setup_app_logging()
    setup_export_logging()
    setup_eye_detection_logging()
