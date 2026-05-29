/**
 * PhotoFlow AI - ComparePage Component
 *
 * Full-page compare mode layout with left/right photo panels.
 * Handles all keyboard shortcuts for compare workflow:
 *   Left/Right  navigate within duplicate group
 *   Tab         switch active side
 *   Space       toggle star on active photo (auto-advance)
 *   X           toggle reject on active photo (auto-advance)
 *   ESC         exit compare mode
 *
 * Cull Workflow features:
 *   - ACTIVE: LEFT / RIGHT indicator
 *   - Smart progression after star/reject
 *   - Auto cleanup when group becomes invalid
 *   - Keyboard priority over browse mode
 *
 * Performance (Task 14):
 *   - Uses centralized keyboard manager (no duplicate listeners)
 *   - Lightweight preload of next compare pair
 *   - Guards against rapid key presses / stale photo states
 */

import React, { useEffect, useCallback, useRef } from "react";
import ComparePreview from "./ComparePreview";
import StatusOverlay from "./StatusOverlay";
import type { StatusType } from "../context/CompareModeContext";
import { useCompareMode } from "../context/CompareModeContext";
import { useKeyboardHandler, KEY_PRIORITY } from "../hooks/useKeyboardManager";
import { setComparePreloadCount } from "./PerformanceOverlay";
import { fullsizeUrl } from "../api/photoApi";

/** Lightweight preload helper: creates an off-screen Image to warm the browser cache. */
function preloadImage(src: string) {
  const img = new Image();
  img.src = src;
  return img;
}

const ComparePage: React.FC = () => {
  const {
    leftPhoto,
    rightPhoto,
    activeSide,
    groupId,
    currentIndex,
    totalInGroup,
    groupPhotos,
    loading,
    error,
    navigateLeft,
    navigateRight,
    switchActiveSide,
    toggleStarActive,
    toggleRejectActive,
    exitCompareMode,
    setOnStatus,
  } = useCompareMode();

  // State for status overlay in compare mode
  const [statusType, setStatusType] = React.useState<StatusType>(null);

  // Guard against rapid key presses — track if an action is in flight
  const actionInFlightRef = useRef(false);

  // Preload refs to hold references so GC doesn't collect them
  const preloadRefs = useRef<HTMLImageElement[]>([]);

  // Register the status callback with CompareModeContext
  useEffect(() => {
    setOnStatus((type: StatusType) => {
      setStatusType(type);
      setTimeout(() => setStatusType(null), 500);
    });
  }, [setOnStatus]);

  // ---- Lightweight Preload of next compare pair ----
  useEffect(() => {
    // Clean up old preload refs
    preloadRefs.current.forEach((img) => { img.src = ""; });
    preloadRefs.current = [];

    if (!groupPhotos || groupPhotos.length < 3) {
      setComparePreloadCount(0);
      return;
    }

    // Preload the next pair (currentIndex + 1, currentIndex + 2)
    const nextIdx = Math.min(groupPhotos.length - 2, currentIndex + 1);
    if (nextIdx === currentIndex) {
      setComparePreloadCount(0);
      return;
    }

    const imgs: HTMLImageElement[] = [];
    const p1 = groupPhotos[nextIdx];
    const p2 = nextIdx + 1 < groupPhotos.length ? groupPhotos[nextIdx + 1] : null;

    if (p1) imgs.push(preloadImage(fullsizeUrl(p1.image_id)));
    if (p2) imgs.push(preloadImage(fullsizeUrl(p2.image_id)));

    preloadRefs.current = imgs;
    if (process.env.NODE_ENV === "development") {
      setComparePreloadCount(imgs.length);
    }
  }, [groupPhotos, currentIndex]);

  // ---- Compare mode keyboard handler (centralized) ----
  const handleCompareKey = useCallback(
    (e: KeyboardEvent): boolean => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;

      // Guard against rapid key presses
      if ([" ", "Space", "x", "X"].includes(e.key) && actionInFlightRef.current) {
        e.preventDefault();
        return true; // Consume but skip if action in flight
      }

      switch (e.key) {
        case "ArrowLeft": {
          e.preventDefault();
          navigateLeft();
          return true;
        }
        case "ArrowRight": {
          e.preventDefault();
          navigateRight();
          return true;
        }
        case "Tab": {
          e.preventDefault();
          switchActiveSide();
          return true;
        }
        case " ":
        case "Space": {
          e.preventDefault();
          actionInFlightRef.current = true;
          toggleStarActive().finally(() => {
            actionInFlightRef.current = false;
          });
          return true;
        }
        case "x":
        case "X": {
          e.preventDefault();
          actionInFlightRef.current = true;
          toggleRejectActive().finally(() => {
            actionInFlightRef.current = false;
          });
          return true;
        }
        case "Escape": {
          e.preventDefault();
          exitCompareMode();
          return true;
        }
      }
      return false;
    },
    [navigateLeft, navigateRight, switchActiveSide, toggleStarActive, toggleRejectActive, exitCompareMode],
  );

  // Use centralized keyboard manager with highest priority
  useKeyboardHandler("compare-mode", handleCompareKey, KEY_PRIORITY.COMPARE, true);

  // Loading state
  if (loading) {
    return (
      <div className="compare-page">
        <div className="state-screen">
          <div className="spinner" />
          <p>加载对比照片...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="compare-page">
        <div className="state-screen">
          <div className="state-icon">⚠️</div>
          <h2>对比模式</h2>
          <p>{error}</p>
          <button className="btn-primary" onClick={exitCompareMode}>
            退出
          </button>
        </div>
      </div>
    );
  }

  const position = totalInGroup > 0 ? currentIndex + 1 : 0;

  return (
    <div className="compare-page">
      <StatusOverlay type={statusType} />

      {/* Header */}
      <div className="compare-header">
        <span className="compare-header-label">COMPARE MODE</span>
        <span className="compare-header-group">{groupId || ""}</span>
        <span className="compare-header-position">
          {position} / {totalInGroup}
        </span>
        <span className="compare-header-active">
          ACTIVE: {activeSide === "left" ? "LEFT" : "RIGHT"}
        </span>
        <span className="compare-header-hint">
          ← → 切换 · Tab切换 · Space标星 · X废片 · ESC退出
        </span>
        <button className="compare-header-exit" onClick={exitCompareMode}>
          退出对比 ESC
        </button>
      </div>

      {/* Body */}
      <div className="compare-body">
        {leftPhoto && (
          <ComparePreview photo={leftPhoto} isActive={activeSide === "left"} />
        )}
        {rightPhoto && (
          <ComparePreview photo={rightPhoto} isActive={activeSide === "right"} />
        )}
        {!rightPhoto && leftPhoto && (
          <div className="compare-panel">
            <div className="compare-image-area">
              <span className="compare-empty-hint">仅一张照片</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ComparePage;
