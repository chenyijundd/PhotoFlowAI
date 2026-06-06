/**
 * PhotoFlow AI - License API Client
 *
 * Functions for checking activation status and activating the software.
 * Supports both Electron IPC and direct HTTP (browser dev mode).
 */

import type { LicenseStatusResponse, ActivateResponse } from "../../types";

const BACKEND_URL = "http://127.0.0.1:8765";

/** Check whether the software is activated. */
export async function fetchLicenseStatus(): Promise<LicenseStatusResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getLicenseStatus();
  }
  const res = await fetch(`${BACKEND_URL}/api/license/status`);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Start a 30-day free trial.
 *
 * Only works when the device has no valid license yet. */
export async function startTrial(): Promise<ActivateResponse> {
  if (window.electronAPI) {
    return window.electronAPI.startTrial();
  }
  const res = await fetch(`${BACKEND_URL}/api/license/start-trial`, {
    method: "POST",
  });
  return res.json();
}

/** Activate the software with a license key and user name.
 *
 * Always returns the parsed response body — the `success` field tells
 * the caller whether activation succeeded.  This avoids Electron's
 * "Error invoking remote method" wrapper on expected failures. */
export async function activateLicense(
  userName: string,
  licenseKey: string,
): Promise<ActivateResponse> {
  if (window.electronAPI) {
    return window.electronAPI.activateLicense(userName, licenseKey);
  }
  const res = await fetch(`${BACKEND_URL}/api/license/activate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_name: userName, license_key: licenseKey }),
  });
  // Always read the body — activation failures (HTTP 403/422) carry
  // the error message inside the response JSON.
  return res.json();
}
