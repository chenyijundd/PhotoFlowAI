/**
 * PhotoFlow AI - Root App Component
 *
 * Manages backend connectivity and renders the photo browser.
 *
 * ErrorBoundary prevents full white-screen on crash.
 */

import React, { useState, useEffect } from "react";
import BrowserPage from "./pages/BrowserPage";
import { PhotoSelectionProvider } from "./context/PhotoSelectionContext";
import { CompareModeProvider } from "./context/CompareModeContext";
import { LightboxModeProvider } from "./context/LightboxModeContext";
import { UndoRedoProvider } from "./context/UndoRedoContext";
import { BatchSelectionProvider } from "./context/BatchSelectionContext";
import ErrorBoundary from "./components/ErrorBoundary";

type BackendStatus = "connecting" | "connected" | "error";

const App: React.FC = () => {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("connecting");

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

  return (
    <ErrorBoundary>
      <PhotoSelectionProvider>
        <UndoRedoProvider>
        <BatchSelectionProvider>
        <CompareModeProvider>
        <LightboxModeProvider>
          <BrowserPage />
        </LightboxModeProvider>
      </CompareModeProvider>
        </BatchSelectionProvider>
        </UndoRedoProvider>
      </PhotoSelectionProvider>
    </ErrorBoundary>
  );
};

export default App;
