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

import React, { useState, useEffect } from "react";
import BrowserPage from "./pages/BrowserPage";
import ProjectPicker from "./components/ProjectPicker";
import { PhotoSelectionProvider } from "./context/PhotoSelectionContext";
import { CompareModeProvider } from "./context/CompareModeContext";
import { BurstCompareProvider } from "./context/BurstCompareContext";
import { LightboxModeProvider } from "./context/LightboxModeContext";
import { UndoRedoProvider } from "./context/UndoRedoContext";
import { BatchSelectionProvider } from "./context/BatchSelectionContext";
import ErrorBoundary from "./components/ErrorBoundary";
import type { ProjectInfo } from "./api/projectApi";
import { fetchCurrentProject, closeProject } from "./api/projectApi";

type BackendStatus = "connecting" | "connected" | "error";
type AppPhase = "connecting" | "picking_project" | "browsing";

const App: React.FC = () => {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("connecting");
  const [appPhase, setAppPhase] = useState<AppPhase>("connecting");
  const [currentProject, setCurrentProject] = useState<ProjectInfo | null>(null);

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

  // ── Once backend is connected, check if a project is already open ──
  useEffect(() => {
    if (backendStatus !== "connected") return;

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
  }, [backendStatus]);

  // ── Callbacks ─────────────────────────────────────────────────────

  const handleProjectOpened = (project: ProjectInfo) => {
    setCurrentProject(project);
    setAppPhase("browsing");
  };

  const handleProjectClosed = async () => {
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
  };

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

  // Project picker (no project open)
  if (appPhase === "picking_project") {
    return (
      <ErrorBoundary>
        <ProjectPicker onProjectOpened={handleProjectOpened} />
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
