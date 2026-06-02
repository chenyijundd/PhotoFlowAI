/**
 * PhotoFlow AI - Fullsize Preview Component
 *
 * Loads and displays the original full-size image on demand.
 * Supports two zoom modes:
 *   fit    — image fits within the container (current behavior)
 *   zoom100 — image rendered at its natural pixel size
 *
 * Zero-latency image switching:
 *   - No `key={imageId}` — the <img> element stays mounted across photo
 *     changes, so the browser keeps displaying the old image while the
 *     new one decodes in the background.
 *   - Spinner only appears after a 200 ms delay, so preloaded images
 *     (which decode in < 50 ms) never show a loading state.
 *   - Preloader blob URLs are checked before falling back to the network.
 */

import React, { useState, useCallback, useEffect, useRef } from "react";
import { fullsizeUrl } from "../api/photoApi";
import { imagePreloader } from "../services/ImagePreloader";
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
  // `imageReady` tracks whether the CURRENT image has finished loading.
  // It is ONLY used for zoom-centering — NOT for hiding the <img> tag,
  // which stays visible at all times so the browser can display the old
  // image during the transition.
  const [imageReady, setImageReady] = useState(false);
  const [error, setError] = useState(false);
  // Delayed spinner — only shown when decoding takes > 200 ms
  const [showSpinner, setShowSpinner] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const spinnerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevImageIdRef = useRef(imageId);

  // Check preloader cache first for zero-latency display.
  // Falls back to direct backend URL if not yet preloaded.
  const preloadedUrl = imagePreloader.getFullsizeUrl(imageId);
  const src = preloadedUrl || `${fullsizeUrl(imageId)}?t=${encodeURIComponent(imageId)}`;

  // ---- Image change handling (no key={imageId} — smooth transition) ----

  useEffect(() => {
    // Clear any pending spinner timer from the previous image
    if (spinnerTimerRef.current) {
      clearTimeout(spinnerTimerRef.current);
      spinnerTimerRef.current = null;
    }

    const isNewImage = prevImageIdRef.current !== imageId;
    prevImageIdRef.current = imageId;

    if (!isNewImage) return;

    setError(false);
    setShowSpinner(false);

    // Check if the browser already has this image decoded (HTTP cache hit).
    // When src has already been updated by React, the browser may have the
    // new image cached.  img.complete is true if the browser didn't need to
    // start a new load.
    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth > 0) {
      // Already decoded — no spinner needed, image is ready immediately
      setImageReady(true);
      return;
    }

    // New image is loading — keep the old image visible (browser handles
    // this natively when <img> stays mounted).  Only show a spinner if
    // loading takes longer than 200 ms.
    setImageReady(false);
    spinnerTimerRef.current = setTimeout(() => {
      setShowSpinner(true);
    }, 200);
  }, [imageId]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (spinnerTimerRef.current) clearTimeout(spinnerTimerRef.current);
    };
  }, []);

  // ---- Event handlers ----

  const handleLoad = useCallback(() => {
    if (spinnerTimerRef.current) {
      clearTimeout(spinnerTimerRef.current);
      spinnerTimerRef.current = null;
    }
    setShowSpinner(false);
    setImageReady(true);
    setError(false);
  }, []);

  const handleError = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    console.error("[FullsizePreview] onError for", imageId, "src:", (e.target as HTMLImageElement).src);
    if (spinnerTimerRef.current) {
      clearTimeout(spinnerTimerRef.current);
      spinnerTimerRef.current = null;
    }
    setShowSpinner(false);
    setImageReady(true);
    setError(true);
  }, [imageId]);

  // ---- Zoom centering ----

  useEffect(() => {
    const container = containerRef.current;
    if (!container || error) return;

    if (zoomMode === "zoom100") {
      const img = imgRef.current;
      if (img && imageReady) {
        const scaledW = img.naturalWidth * zoomScale;
        const scaledH = img.naturalHeight * zoomScale;
        container.scrollLeft = Math.max(0, (scaledW - container.clientWidth) / 2);
        container.scrollTop = Math.max(0, (scaledH - container.clientHeight) / 2);
      }
    } else {
      container.scrollLeft = 0;
      container.scrollTop = 0;
    }
  }, [zoomMode, imageReady, error, zoomScale]);

  // ---- Render ----

  const containerClass =
    zoomMode === "zoom100"
      ? "fullsize-preview fullsize-preview--zoom100"
      : "fullsize-preview fullsize-preview--fit";

  return (
    <div className={containerClass} ref={containerRef}>
      {/* Spinner overlay — only appears after 200 ms delay.
          Preloaded images decode fast enough to never trigger this. */}
      {showSpinner && !imageReady && !error && (
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
      {/* No key={imageId}: the <img> stays mounted across photo changes.
          The browser keeps displaying the old decoded image while the new
          one loads, providing a flicker-free transition. */}
      <img
        ref={imgRef}
        src={src}
        alt={fileName}
        loading="eager"
        onLoad={handleLoad}
        onError={handleError}
        style={{
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
