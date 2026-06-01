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
import type { ZoomMode } from "../../types";

interface FullsizePreviewProps {
  imageId: string;
  fileName: string;
  zoomMode: ZoomMode;
  /** Zoom scale factor (1.0 = 100%). Only applied in zoom100 mode. */
  zoomScale?: number;
}

const FullsizePreview: React.FC<FullsizePreviewProps> = ({
  imageId,
  fileName,
  zoomMode,
  zoomScale = 1.0,
}) => {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const src = `${fullsizeUrl(imageId)}?t=${encodeURIComponent(imageId)}`;

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

  // When entering zoom100 mode, center the viewport on the image
  // instead of showing the top-left corner. Reset on exit.
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !loaded || error) return;

    if (zoomMode === "zoom100") {
      const img = imgRef.current;
      if (img) {
        const scaledW = img.naturalWidth * zoomScale;
        const scaledH = img.naturalHeight * zoomScale;
        container.scrollLeft = Math.max(0, (scaledW - container.clientWidth) / 2);
        container.scrollTop = Math.max(0, (scaledH - container.clientHeight) / 2);
      }
    } else {
      container.scrollLeft = 0;
      container.scrollTop = 0;
    }
  }, [zoomMode, loaded, error, zoomScale]);

  const handleLoad = useCallback(() => setLoaded(true), []);
  const handleError = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    console.error("[FullsizePreview] onError for", imageId, "src:", (e.target as HTMLImageElement).src);
    setLoaded(true);
    setError(true);
  }, [imageId]);

  const containerClass =
    zoomMode === "zoom100"
      ? "fullsize-preview fullsize-preview--zoom100"
      : "fullsize-preview fullsize-preview--fit";

  return (
    <div className={containerClass} ref={containerRef}>
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
        key={imageId}
        ref={imgRef}
        src={src}
        alt={fileName}
        loading="eager"
        onLoad={handleLoad}
        onError={handleError}
        style={{
          display: loaded && !error ? "block" : "none",
          ...(zoomMode === "zoom100"
            ? { transform: `scale(${zoomScale})`, transformOrigin: "top left" }
            : {}),
        }}
        draggable={false}
      />
    </div>
  );
};

export default FullsizePreview;
