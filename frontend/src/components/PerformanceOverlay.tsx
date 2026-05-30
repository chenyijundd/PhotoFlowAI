/**
 * PhotoFlow AI — Performance Debug Overlay (Development Mode Only)
 *
 * Displays key performance metrics:
 *   - Rendered ImageCard count (estimated)
 *   - Currently loaded thumbnail count
 *   - Compare mode preload count
 *   - Keyboard listener count
 *
 * Only rendered when NODE_ENV === 'development'.
 * Current phase: simple overlay — no complex profiler.
 */

import React, { useEffect, useState } from "react";
import { getKeyboardListenerCount } from "../hooks/useKeyboardManager";

interface PerfStats {
  renderedCards: number;
  loadedThumbnails: number;
  comparePreload: number;
  keyboardListeners: number;
}

// Global mutable stats (updated by components)
export const perfStats: PerfStats = {
  renderedCards: 0,
  loadedThumbnails: 0,
  comparePreload: 0,
  keyboardListeners: 0,
};

export function incrementRenderedCards(n: number = 1) { perfStats.renderedCards += n; }
export function decrementRenderedCards(n: number = 1) { perfStats.renderedCards = Math.max(0, perfStats.renderedCards - n); }
export function incrementLoadedThumbnails() { perfStats.loadedThumbnails++; }
export function decrementLoadedThumbnails() { perfStats.loadedThumbnails = Math.max(0, perfStats.loadedThumbnails - 1); }
export function setComparePreloadCount(n: number) { perfStats.comparePreload = n; }

const PerformanceOverlay: React.FC = () => {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    // Poll every second for keyboard listener count
    const interval = setInterval(() => {
      perfStats.keyboardListeners = getKeyboardListenerCount();
      setTick((t) => t + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Only show in development (Vite dev server)
  if (!import.meta.env.DEV) {
    return null;
  }

  return (
    <div
      style={{
        position: "fixed",
        bottom: 8,
        right: 8,
        background: "rgba(0,0,0,0.85)",
        color: "#0f0",
        fontFamily: "monospace",
        fontSize: 11,
        padding: "6px 10px",
        borderRadius: 4,
        zIndex: 99999,
        pointerEvents: "none",
        lineHeight: 1.6,
        userSelect: "none",
      }}
    >
      <div>Cards: {perfStats.renderedCards}</div>
      <div>Thumbs: {perfStats.loadedThumbnails}</div>
      <div>Preload: {perfStats.comparePreload}</div>
      <div>KeyListeners: {perfStats.keyboardListeners}</div>
    </div>
  );
};

export default PerformanceOverlay;
