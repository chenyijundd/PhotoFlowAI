"""
PhotoFlow AI - Environment Configuration (Example)

Copy this file to env.py and fill in your real SECRET_KEY.
env.py is git-ignored and must NEVER be committed.

Usage (after copying):
    from backend.env import get_data_dir, is_frozen, SECRET_KEY
"""

import os
import sys

# ── Secret Keys ────────────────────────────────────────────────────────────────
# CHANGE this when you copy to env.py!
# Generate a random 32+ character string and keep it private.
# The same key must be used in license_service.py → env.py AND
# scripts/generate_license.py → env.py.
# ⚠️  Once you distribute software with a key, DO NOT change it —
#     all existing licenses would become invalid.
SECRET_KEY = "PhotoFlowAI-YOUR-SECRET-KEY-CHANGE-ME-2026"


# ── Path Utilities ────────────────────────────────────────────────────────────

def is_frozen() -> bool:
    """Return True when running as a PyInstaller-frozen executable."""
    return getattr(sys, 'frozen', False)


def get_data_dir() -> str:
    """Return the writable data directory for databases, logs, and caches.

    Resolution order:
    1. PHOTOFLOW_DATA_DIR environment variable (set by Electron in production)
    2. Project root (development mode fallback)

    The returned path is guaranteed to be an absolute, normalised path.
    """
    env_dir = os.environ.get("PHOTOFLOW_DATA_DIR")
    if env_dir:
        return os.path.normpath(os.path.abspath(env_dir))

    # Development fallback: go up from backend/env.py to project root
    # backend/env.example.py → backend/ → project_root/
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".."
    ))
