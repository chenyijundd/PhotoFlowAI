#!/usr/bin/env python3
"""
PhotoFlow AI - Project Entry Point

Orchestrates the Python backend server startup.
Used both in development (``python main.py``) and production
(PyInstaller-frozen executable).

Usage:
    python main.py                          # Start backend (dev mode)
    python main.py --init-db                # Initialize database and exit
    python main.py --port 8765
    python main.py --port 8765 --data-dir "C:\\Users\\...\\PhotoFlowAI"

The --data-dir flag tells the backend where to store persistent data
(databases, logs, caches).  In production the Electron shell passes
``app.getPath('userData')`` here so user data lives in the standard
OS application-data folder.
"""

import argparse
import os
import sys

# Ensure project root is on sys.path so that ``import backend`` works
# regardless of the working directory (no-op in PyInstaller frozen mode).
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def main():
    parser = argparse.ArgumentParser(description="PhotoFlow AI Backend")
    parser.add_argument(
        "--init-db", action="store_true",
        help="Initialise the database schema and exit.",
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="Backend server port (default: 8765).",
    )
    parser.add_argument(
        "--data-dir", type=str, default=None,
        help=(
            "Writable data directory for databases, logs, and caches.  "
            "When omitted the project root is used (development fallback)."
        ),
    )
    args = parser.parse_args()

    # ── Set data directory BEFORE any backend imports ──────────────────
    # Module-level constants (LOG_DIR, DEFAULT_CACHE_DIR, …) are evaluated
    # when their modules are first imported.  By setting the env var here
    # we guarantee that every module sees the correct writable location.
    if args.data_dir:
        os.environ["PHOTOFLOW_DATA_DIR"] = os.path.abspath(args.data_dir)

    if args.init_db:
        from database.connection import init_database
        init_database()
        print("Database initialised. Exiting.")
        return

    print(f"Starting PhotoFlow AI backend on port {args.port}...")
    from backend.api.server import start_server
    start_server(port=args.port)


if __name__ == "__main__":
    main()
