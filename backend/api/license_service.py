"""
PhotoFlow AI - License Activation Service

Provides offline license key generation, verification, and persistent
activation storage.  The license file lives in the user data directory
so it survives application restarts and re-installs (when the data
directory is preserved).

Flow:
  1. Developer runs scripts/generate_license.py → gets a 16-char key
  2. User purchases → receives key + enters it with their name
  3. Frontend calls POST /api/license/activate → backend verifies & stores
  4. Every startup: GET /api/license/status checks stored license

Security model:
  - SECRET_KEY is compiled into the PyInstaller executable (not in a
    plain-text config file), making extraction non-trivial.
  - License key = SHA256(user_name | expiry | SECRET_KEY)[:16].upper()
  - The stored license file is re-verified on every status check to
    prevent tampering.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.env import get_data_dir, SECRET_KEY

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────
LICENSE_FILENAME = "license.json"

router = APIRouter(prefix="/api/license", tags=["license"])


# ── Request / Response models ──────────────────────────────────────────────


class LicenseStatusResponse(BaseModel):
    activated: bool
    user_name: str | None = None
    expiry: str | None = None
    activated_at: str | None = None


class ActivateRequest(BaseModel):
    user_name: str
    license_key: str


class ActivateResponse(BaseModel):
    success: bool
    message: str
    user_name: str | None = None
    expiry: str | None = None


# ── Helpers ─────────────────────────────────────────────────────────────────


def _license_path() -> Path:
    """Absolute path to the license JSON file in the user data directory."""
    return Path(get_data_dir()) / LICENSE_FILENAME


def _generate_license(user_name: str, expiry: str = "permanent") -> str:
    """Generate a 16-character uppercase license key for the given user.

    This is the same function the developer uses offline to create keys.
    """
    payload = f"{user_name}|{expiry}|{SECRET_KEY}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16].upper()


def _verify_license(license_key: str, user_name: str, expiry: str = "permanent") -> bool:
    """Return True if the license_key matches the expected value."""
    expected = _generate_license(user_name, expiry)
    return license_key.upper().strip() == expected


def _read_license_file() -> dict | None:
    """Read and return the stored license data, or None."""
    path = _license_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Corrupted license file %s: %s", path, exc)
        return None


def _write_license_file(user_name: str, license_key: str, expiry: str) -> None:
    """Persist the activation record to disk."""
    path = _license_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "user_name": user_name,
        "license_key": license_key.upper().strip(),
        "expiry": expiry,
        "activated_at": int(time.time()),
        "activated_at_iso": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("License activated for user '%s' (expiry: %s)", user_name, expiry)


def is_license_valid() -> tuple[bool, str | None, str | None]:
    """Check whether a valid license is stored on this machine.

    Returns (valid, user_name, expiry).  Re-verifies the stored key
    against the SECRET_KEY so that tampering with the license file is
    detected.
    """
    data = _read_license_file()
    if data is None:
        return False, None, None

    user_name = data.get("user_name", "")
    license_key = data.get("license_key", "")
    expiry = data.get("expiry", "permanent")

    if not user_name or not license_key:
        logger.warning("License file present but missing fields")
        return False, None, None

    if not _verify_license(license_key, user_name, expiry):
        logger.warning("Stored license failed verification (tampered?)")
        return False, None, None

    return True, user_name, expiry


# ── API Endpoints ──────────────────────────────────────────────────────────


@router.get("/status", response_model=LicenseStatusResponse)
async def license_status():
    """Return the current activation status.

    Called by the frontend on every startup.  Re-verifies the stored
    license against the secret key so that file tampering is detected.
    """
    valid, user_name, expiry = is_license_valid()
    if not valid:
        return LicenseStatusResponse(activated=False)

    data = _read_license_file()
    activated_at = None
    if data:
        activated_at = data.get("activated_at_iso")

    return LicenseStatusResponse(
        activated=True,
        user_name=user_name,
        expiry=expiry,
        activated_at=activated_at,
    )


@router.post("/activate", response_model=ActivateResponse)
async def activate_license(body: ActivateRequest):
    """Activate the software with a license key and user name.

    On success the activation is persisted to disk.  Subsequent calls
    to /api/license/status will report activated=True.
    """
    user_name = body.user_name.strip()
    license_key = body.license_key.strip()

    if not user_name:
        raise HTTPException(status_code=422, detail="用户名不能为空")
    if not license_key:
        raise HTTPException(status_code=422, detail="激活码不能为空")
    if len(license_key) != 16:
        raise HTTPException(status_code=422, detail="激活码格式不正确（应为16位字符）")

    # Verify against the permanent expiry — the simplest model.
    # To support time-limited licenses, we would try multiple expiry values.
    if not _verify_license(license_key, user_name):
        logger.info("Activation failed for user '%s' (key mismatch)", user_name)
        raise HTTPException(
            status_code=403,
            detail="激活失败：用户名与激活码不匹配，请检查后重试",
        )

    _write_license_file(user_name, license_key, "permanent")

    return ActivateResponse(
        success=True,
        message="激活成功！感谢使用 PhotoFlow AI",
        user_name=user_name,
        expiry="permanent",
    )
