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
 *   - When the preloader is still fetching the target image, the src is
 *     frozen synchronously during render — no "first frame with network URL"
 *     flash before the useEffect stall kicks in.
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
  // which stays visible at all times.
  const [imageReady, setImageReady] = useState(false);
  const [error, setError] = useState(false);
  // Delayed spinner — only shown when decoding takes > 200 ms
  const [showSpinner, setShowSpinner] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const spinnerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevImageIdRef = useRef(imageId);

  // ---- Stall mechanism ----
  // displaySrcRef is updated SYNCHRONOUSLY during render so the <img>
  // never receives a network URL while the preloader is working.
  // A version counter forces re-render when a stalled preload completes.
  const [version, setVersion] = useState(0);
  const displaySrcRef = useRef<string>("");
  const stallTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  // Resolve URLs for the current imageId
  const preloadedUrl = imagePreloader.getFullsizeUrl(imageId);
  const isFetching = imagePreloader.isFetchingFullsize(imageId);
  const networkUrl = fullsizeUrl(imageId, 1600);

  // ---- Render-time src resolution (SYNCHRONOUS — no frame with wrong URL) ----
  //
  // Cases:
  //   1. Cached           → displaySrcRef = blob URL       (instant display)
  //   2. Fetching in bg   → displaySrcRef UNCHANGED        (stall — old img stays)
  //   3. Not cached/not fetching → displaySrcRef = network (fresh load, trigger preload in effect)
  //
  // Caveat: on the very first render displaySrcRef is "". Stalling with an
  // empty string would cause <img src=""> which the browser resolves to the
  // page base URL — producing a spurious onError.  Fall back to network when
  // there is no old image to keep.

  if (preloadedUrl) {
    // Case 1: blob URL ready — use it immediately
    displaySrcRef.current = preloadedUrl;
  } else if (!isFetching || !displaySrcRef.current) {
    // Case 3: no preload in progress, OR initial mount (no old image to stall)
    displaySrcRef.current = networkUrl;
  }
  // else: isFetching && !preloadedUrl && displaySrcRef.current is set → stall

  const displaySrc = displaySrcRef.current;

  // ---- Image change handling ----

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

    // Clean up any previous stall subscription / timer
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }
    if (stallTimerRef.current) {
      clearTimeout(stallTimerRef.current);
      stallTimerRef.current = null;
    }

    // Case 1: Already cached — the render already set displaySrcRef.
    // Just manage spinner / imageReady.
    if (preloadedUrl) {
      const img = imgRef.current;
      if (img && img.complete && img.naturalWidth > 0) {
        setImageReady(true);
        return;
      }
      setImageReady(false);
      spinnerTimerRef.current = setTimeout(() => setShowSpinner(true), 200);
      return;
    }

    // Case 2: Preloader is fetching — the render already stalled displaySrcRef.
    // Subscribe so we can re-render (and un-stall) when the blob arrives.
    if (isFetching) {
      setImageReady(false);

      unsubscribeRef.current = imagePreloader.onFullsizeLoaded(imageId, () => {
        // Preload finished — force re-render to pick up the blob URL
        setVersion((v) => v + 1);
      });

      // Safety timeout: if preload takes > 4 s, force fallback to network
      stallTimerRef.current = setTimeout(() => {
        if (unsubscribeRef.current) {
          unsubscribeRef.current();
          unsubscribeRef.current = null;
        }
        // Force displaySrcRef to network URL and re-render
        displaySrcRef.current = networkUrl;
        setVersion((v) => v + 1);
      }, 4000);

      return;
    }

    // Case 3: Not cached and not fetching — render already used networkUrl.
    // Trigger a preload so NEXT time is instant.
    imagePreloader.preloadFullsizeBg(imageId, "high");

    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth > 0) {
      setImageReady(true);
      return;
    }
    setImageReady(false);
    spinnerTimerRef.current = setTimeout(() => setShowSpinner(true), 200);
  }, [imageId, preloadedUrl, isFetching, networkUrl]);

  // Cleanup timers and subscriptions on unmount
  useEffect(() => {
    return () => {
      if (spinnerTimerRef.current) clearTimeout(spinnerTimerRef.current);
      if (stallTimerRef.current) clearTimeout(stallTimerRef.current);
      if (unsubscribeRef.current) unsubscribeRef.current();
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

  // Only update displaySrc when it actually changed, to avoid
  // React re-applying the same src to the DOM.
  // displaySrc is stable during stall (same as previous render).

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
          one loads, providing a flicker-free transition.

          displaySrc is frozen to the OLD URL during stall — React passes
          the same src string, the DOM sees no change, and the old image
          stays visible until the preload completes. */}
      <img
        ref={imgRef}
        src={displaySrc}
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
