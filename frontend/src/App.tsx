/**
 * PhotoFlow AI - Root App Component
 *
 * Manages backend connectivity and renders the photo browser.
 */

import React, { useState, useEffect } from "react";
import BrowserPage from "./pages/BrowserPage";
import { PhotoSelectionProvider } from "./context/PhotoSelectionContext";
import { CompareModeProvider } from "./context/CompareModeContext";

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
    <PhotoSelectionProvider>
      <CompareModeProvider>
        <BrowserPage />
      </CompareModeProvider>
    </PhotoSelectionProvider>
  );
};

export default App;
