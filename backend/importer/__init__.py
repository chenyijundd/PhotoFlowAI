"""
PhotoFlow AI - Photo Import Module

Provides the complete photo import pipeline:
scan -> generate thumbnails -> write to database.

Performance (Task 14):
   Uses rotating log (10 MB × 5 files) via centralized logging_config.
"""

from backend.logging_config import setup_importer_logging

# Initialize rotating log handler for importer
setup_importer_logging()
