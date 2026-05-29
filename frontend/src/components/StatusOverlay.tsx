/**
 * PhotoFlow AI - Status Overlay
 *
 * Lightweight floating overlay that appears briefly (500ms) when
 * the photographer stars or rejects a photo. No animations, no
 * third-party libraries.
 */

import React from "react";

export type StatusType = "star" | "reject" | "ai_accept" | null;

interface StatusOverlayProps {
  type: StatusType;
}

const StatusOverlay: React.FC<StatusOverlayProps> = ({ type }) => {
  if (!type) return null;

  return (
    <div className={`status-overlay status-overlay--${type}`}>
      {type === "star" ? "★ PICKED" : type === "reject" ? "✕ REJECTED" : "AI ACCEPTED"}
    </div>
  );
};

export default StatusOverlay;
