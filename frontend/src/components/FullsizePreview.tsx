/**
 * PhotoFlow AI - Fullsize Preview Component
 *
 * Loads and displays the original full-size image on demand.
 * Supports two zoom modes:
 *   fit    — image fits within the container (current behavior)
 *   zoom100 — image rendered at its natural pixel size
 */

import React, { useState, useCallback } from "react";
import { fullsizeUrl } from "../api/photoApi";
import type { ZoomMode } from "../hooks/useKeyboardNavigation";

interface FullsizePreviewProps {
  imageId: string;
  fileName: string;
  zoomMode: ZoomMode;
}

const FullsizePreview: React.FC<FullsizePreviewProps> = ({
  imageId,
  fileName,
  zoomMode,
}) => {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  const src = fullsizeUrl(imageId);

  const handleLoad = useCallback(() => setLoaded(true), []);
  const handleError = useCallback(() => {
    setLoaded(true);
    setError(true);
  }, []);

  const containerClass =
    zoomMode === "zoom100"
      ? "fullsize-preview fullsize-preview--zoom100"
      : "fullsize-preview fullsize-preview--fit";

  return (
    <div className={containerClass}>
      {!loaded && !error && (
        <div className="fullsize-loading">
          <div className="spinner" />
          <span>加载原图中...</span>
        </div>
      )}
      {error && (
        <div className="fullsize-error">
          <span>原图加载失败</span>
        </div>
      )}
      <img
        src={src}
        alt={fileName}
        onLoad={handleLoad}
        onError={handleError}
        style={{ display: loaded && !error ? "block" : "none" }}
        draggable={false}
      />
    </div>
  );
};

export default FullsizePreview;
