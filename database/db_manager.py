#!/usr/bin/env python3
"""
PhotoFlow AI - Database Manager CLI

Manages the SQLite image index database.

Usage:
    python db_manager.py --init
    python db_manager.py --import "D:/Photos"
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from .repository import PhotoRepository
from .models import PhotoRecord
from backend.image_loader.utils import collect_scan

logger = logging.getLogger(__name__)


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize the database schema."""
    repo = PhotoRepository(db_path=args.db_path)
    path = repo.init_database()
    output = {"status": "ok", "db_path": path}
    print(json.dumps(output, ensure_ascii=False))


def cmd_import(args: argparse.Namespace) -> None:
    """Scan a directory and import photos into the database."""
    repo = PhotoRepository(db_path=args.db_path)
    repo.init_database()

    photos = collect_scan(args.import_dir)
    total_scanned = len(photos)

    records = [
        PhotoRecord(
            image_id=p.id,
            file_name=p.file_name,
            file_path=p.file_path,
            file_size=p.file_size,
            width=p.width,
            height=p.height,
            created_time=p.created_time,
        )
        for p in photos
    ]

    imported = repo.insert_photos(records)

    output = {
        "status": "ok",
        "imported": imported,
        "total_scanned": total_scanned,
    }
    print(json.dumps(output, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PhotoFlow AI - Database Manager",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to the SQLite database file (default: ./database/photoflow.db)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize the database schema",
    )
    parser.add_argument(
        "--import",
        dest="import_dir",
        default=None,
        metavar="DIR",
        help="Scan a directory and import image metadata into the database",
    )
    args = parser.parse_args()

    if args.init:
        cmd_init(args)
    elif args.import_dir:
        cmd_import(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
