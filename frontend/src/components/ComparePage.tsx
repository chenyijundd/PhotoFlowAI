/**
 * PhotoFlow AI - ComparePage Component
 *
 * Full-page compare mode layout with left/right photo panels.
 * Handles all keyboard shortcuts for compare workflow:
 *   Left/Right  navigate within duplicate group
 *   Tab         switch active side
 *   Space       toggle star on active photo
 *   X           toggle reject on active photo
 *   ESC         exit compare mode
 */

import React, { useEffect, useCallback } from "react";
import ComparePreview from "./ComparePreview";
import { useCompareMode } from "../context/CompareModeContext";

const ComparePage: React.FC = () => {
  const {
    leftPhoto,
    rightPhoto,
    activeSide,
    groupId,
    currentIndex,
    totalInGroup,
    loading,
    error,
    navigateLeft,
    navigateRight,
    switchActiveSide,
    toggleStarActive,
    toggleRejectActive,
    exitCompareMode,
  } = useCompareMode();

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      switch (e.key) {
        case "ArrowLeft": {
          e.preventDefault();
          navigateLeft();
          break;
        }
        case "ArrowRight": {
          e.preventDefault();
          navigateRight();
          break;
        }
        case "Tab": {
          e.preventDefault();
          switchActiveSide();
          break;
        }
        case " ":
        case "Space": {
          e.preventDefault();
          toggleStarActive();
          break;
        }
        case "x":
        case "X": {
          e.preventDefault();
          toggleRejectActive();
          break;
        }
        case "Escape": {
          e.preventDefault();
          exitCompareMode();
          break;
        }
      }
    },
    [navigateLeft, navigateRight, switchActiveSide, toggleStarActive, toggleRejectActive, exitCompareMode],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

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
      {/* Header */}
      <div className="compare-header">
        <span className="compare-header-label">COMPARE MODE</span>
        <span className="compare-header-group">{groupId || ""}</span>
        <span className="compare-header-position">
          {position} / {totalInGroup}
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
