"""
PhotoFlow AI - Photo Import Module

Provides the complete photo import pipeline:
scan -> generate thumbnails -> write to database.

Logs import activity to logs/import.log.
"""

import os
import logging

LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"
)
os.makedirs(LOG_DIR, exist_ok=True)

_log_path = os.path.join(LOG_DIR, "import.log")
_handler = logging.FileHandler(_log_path, encoding="utf-8")
_handler.setLevel(logging.INFO)
_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

_logger = logging.getLogger("importer")
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)
_logger.propagate = False
