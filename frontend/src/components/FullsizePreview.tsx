/**
 * PhotoFlow AI - Fullsize Preview Component
 *
 * Loads and displays the original full-size image on demand.
 * Supports two zoom modes:
 *   fit    — image fits within the container (current behavior)
 *   zoom100 — image rendered at its natural pixel size
 *
 * Performance (Task 14):
 *   - Memory safety: releases old image object on photo switch
 *   - decoding="async" for off-main-thread decode
 *   - loading="eager" to prioritize full-size preview
 */

import React, { useState, useCallback, useEffect, useRef } from "react";
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
  const imgRef = useRef<HTMLImageElement>(null);

  const src = fullsizeUrl(imageId);

  // Reset state when imageId changes.
  // Then check img.complete — for cached images, onLoad fires
  // synchronously before this effect runs, so we must manually
  // sync the loaded state.
  useEffect(() => {
    setLoaded(false);
    setError(false);
    // Handle cached / already-loaded images
    const img = imgRef.current;
    if (img?.complete && img.naturalWidth > 0) {
      setLoaded(true);
    }
  }, [imageId]);

  const handleLoad = useCallback(() => setLoaded(true), []);
  const handleError = useCallback(() => {
    setLoaded(true);
    setError(true);
    // Release failed resource
    if (imgRef.current) {
      imgRef.current.src = "";
    }
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
        ref={imgRef}
        src={src}
        alt={fileName}
        loading="eager"
        decoding="async"
        onLoad={handleLoad}
        onError={handleError}
        style={{ display: loaded && !error ? "block" : "none" }}
        draggable={false}
      />
    </div>
  );
};

export default FullsizePreview;
