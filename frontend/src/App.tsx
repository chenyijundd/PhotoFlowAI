/**
 * PhotoFlow AI - Root App Component
 *
 * Manages backend connectivity and multi-project routing:
 *   - Backend not connected → loading / retry screen
 *   - No project open         → ProjectPicker (landing page)
 *   - Project open            → BrowserPage (existing workflow)
 *
 * ErrorBoundary prevents full white-screen on crash.
 */

import React, { useState, useEffect, useCallback } from "react";
import BrowserPage from "./pages/BrowserPage";
import ProjectPicker from "./components/ProjectPicker";
import ActivationDialog from "./components/ActivationDialog";
import { PhotoSelectionProvider } from "./context/PhotoSelectionContext";
import { CompareModeProvider } from "./context/CompareModeContext";
import { BurstCompareProvider } from "./context/BurstCompareContext";
import { LightboxModeProvider } from "./context/LightboxModeContext";
import { UndoRedoProvider } from "./context/UndoRedoContext";
import { BatchSelectionProvider } from "./context/BatchSelectionContext";
import ErrorBoundary from "./components/ErrorBoundary";
import type { ProjectInfo } from "./api/projectApi";
import { fetchCurrentProject, closeProject } from "./api/projectApi";
import { fetchLicenseStatus } from "./api/licenseApi";

type BackendStatus = "connecting" | "connected" | "error";
type AppPhase = "connecting" | "activating" | "picking_project" | "browsing";

const App: React.FC = () => {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("connecting");
  const [appPhase, setAppPhase] = useState<AppPhase>("connecting");
  const [currentProject, setCurrentProject] = useState<ProjectInfo | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [licenseChecked, setLicenseChecked] = useState(false);
  const [licenseValid, setLicenseValid] = useState(false);
  const [licenseUserName, setLicenseUserName] = useState<string | null>(null);

  // ── Backend health check ──────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function checkBackend(): Promise<void> {
      try {
        const backendUrl =
          (window.electronAPI && (await window.electronAPI.getBackendUrl())) ||
          "http://127.0.0.1:8765";
        const res = await fetch(`${backendUrl}/api/health`);
        const data = await res.json();
        if (!cancelled) {
          setBackendStatus(data.status === "ok" ? "connected" : "error");
        }
      } catch {
        if (!cancelled) {
          setBackendStatus("connecting");
          setTimeout(checkBackend, 1000);
        }
      }
    }

    checkBackend();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Once backend is connected, check license status first ──
  useEffect(() => {
    if (backendStatus !== "connected" || licenseChecked) return;

    let cancelled = false;
    (async () => {
      try {
        const status = await fetchLicenseStatus();
        if (!cancelled) {
          setLicenseChecked(true);
          if (status.activated) {
            setLicenseValid(true);
            setLicenseUserName(status.user_name);
          } else {
            setAppPhase("activating");
          }
        }
      } catch {
        // If the license check fails, treat as not activated
        if (!cancelled) {
          setLicenseChecked(true);
          setAppPhase("activating");
        }
      }
    })();

    return () => { cancelled = true; };
  }, [backendStatus, licenseChecked]);

  // ── Once license is confirmed valid, check if a project is already open ──
  useEffect(() => {
    if (backendStatus !== "connected" || !licenseValid) return;

    let cancelled = false;
    (async () => {
      try {
        const project = await fetchCurrentProject();
        if (!cancelled) {
          if (project) {
            setCurrentProject(project);
            setAppPhase("browsing");
          } else {
            setAppPhase("picking_project");
          }
        }
      } catch {
        // API not available or error — fall back to browsing (legacy single-db mode)
        if (!cancelled) {
          setAppPhase("browsing");
        }
      }
    })();

    return () => { cancelled = true; };
  }, [backendStatus, licenseValid]);

  // ── Callbacks ─────────────────────────────────────────────────────

  const handleProjectOpened = useCallback((project: ProjectInfo) => {
    setCurrentProject(project);
    setAppPhase("browsing");
  }, []);

  const handleActivated = useCallback((userName: string) => {
    setLicenseValid(true);
    setLicenseUserName(userName);
    // The next useEffect will pick up licenseValid=true
    // and transition to picking_project or browsing
  }, []);

  const handleProjectClosed = useCallback(async () => {
    // Sync backend — clear the current project so a subsequent open
    // starts from a clean state.  Swallow errors so the UI always
    // returns to the picker even if the backend is unreachable.
    try {
      await closeProject();
    } catch {
      // ignore — UI navigation proceeds regardless
    }
    setCurrentProject(null);
    setAppPhase("picking_project");
  }, []);

  // ── Render ────────────────────────────────────────────────────────

  // Backend not connected yet
  if (backendStatus !== "connected") {
    return (
      <div className="state-screen loading-state">
        <div className="spinner" />
        <h2>PhotoFlow AI</h2>
        <p>
          {backendStatus === "connecting"
            ? "正在连接后端服务..."
            : "后端连接失败"}
        </p>
      </div>
    );
  }

  // License activation required
  if (appPhase === "activating") {
    return (
      <ErrorBoundary>
        <ActivationDialog onActivated={handleActivated} />
      </ErrorBoundary>
    );
  }

  // Project picker (no project open)
  if (appPhase === "picking_project") {
    return (
      <ErrorBoundary>
        <ProjectPicker
          onProjectOpened={handleProjectOpened}
          showArchived={showArchived}
          onShowArchivedChange={setShowArchived}
        />
      </ErrorBoundary>
    );
  }

  // Normal browsing mode (project is open, or legacy single-db fallback)
  return (
    <ErrorBoundary>
      <PhotoSelectionProvider>
        <UndoRedoProvider>
        <BatchSelectionProvider>
        <CompareModeProvider>
        <BurstCompareProvider>
        <LightboxModeProvider>
          <BrowserPage
            projectName={currentProject?.name ?? null}
            onProjectClosed={currentProject ? handleProjectClosed : undefined}
          />
        </LightboxModeProvider>
        </BurstCompareProvider>
      </CompareModeProvider>
        </BatchSelectionProvider>
        </UndoRedoProvider>
      </PhotoSelectionProvider>
    </ErrorBoundary>
  );
};

export default App;
