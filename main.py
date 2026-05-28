#!/usr/bin/env python3
"""
PhotoFlow AI - Project Entry Point

Orchestrates the Python backend server startup.
The Electron frontend is started separately via npm.

Usage:
    python main.py                    # Start backend only
    python main.py --init-db          # Initialize database and exit
"""

import argparse
import sys
import os

# Ensure backend is in path
sys.path.insert(0, os.path.dirname(__file__))


def main():
    parser = argparse.ArgumentParser(description="PhotoFlow AI")
    parser.add_argument("--init-db", action="store_true", help="Initialize database")
    parser.add_argument("--port", type=int, default=8765, help="Backend server port")
    args = parser.parse_args()

    if args.init_db:
        from database.connection import init_database

        init_database()
        print("Database initialized. Exiting.")
        return

    print("Starting PhotoFlow AI backend...")
    from backend.api.server import start_server

    start_server(port=args.port)


if __name__ == "__main__":
    main()
