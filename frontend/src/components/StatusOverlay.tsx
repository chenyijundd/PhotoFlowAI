/**
 * PhotoFlow AI - Status Overlay
 *
 * Lightweight floating overlay that appears briefly (500ms) when
 * the photographer stars or rejects a photo. No animations, no
 * third-party libraries.
 */

import React from "react";

export type StatusType = "star" | "reject" | "ai_accept" | "hint" | "undo" | "redo" | "trash" | null;

interface StatusOverlayProps {
  type: StatusType;
  message?: string;
}

const StatusOverlay: React.FC<StatusOverlayProps> = ({ type, message }) => {
  if (!type) return null;

  const label =
    type === "star" ? "★ PICKED" :
    type === "reject" ? "✕ REJECTED" :
    type === "ai_accept" ? "AI ACCEPTED" :
    type === "undo" ? (message || "↩ 已撤销") :
    type === "redo" ? (message || "↪ 已重做") :
    type === "trash" ? (message || "🗑️ 已移至回收站") :
    message || "";

  return (
    <div className={`status-overlay status-overlay--${type}`}>
      {label}
    </div>
  );
};

export default StatusOverlay;
