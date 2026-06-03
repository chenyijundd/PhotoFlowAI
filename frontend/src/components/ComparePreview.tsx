/**
 * PhotoFlow AI - ComparePreview Component
 *
 * Displays a single photo's full-size preview with filename, star,
 * and reject status in the compare mode side panel.
 *
 * Zero-latency image switching:
 *   - No `key={imageId}` — the <img> stays mounted across changes
 *   - Spinner only appears after a 200 ms delay so preloaded images
 *     never show a loading state.
 *   - When the preloader is still fetching, the src is frozen
 *     synchronously during render to prevent flicker.
 */

import React, { useState, useCallback, useEffect, useRef } from "react";
import { fullsizeUrl } from "../api/photoApi";
import { imagePreloader } from "../services/ImagePreloader";
import type { PhotoInfo } from "../../types";

interface ComparePreviewProps {
  photo: PhotoInfo;
  isActive: boolean;
}

const ComparePreview: React.FC<ComparePreviewProps> = ({ photo, isActive }) => {
  const [imageReady, setImageReady] = useState(false);
  const [error, setError] = useState(false);
  const [showSpinner, setShowSpinner] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const spinnerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevImageIdRef = useRef<string | null>(null);

  // ---- Stall mechanism ----
  const [version, setVersion] = useState(0);
  const displaySrcRef = useRef<string>("");
  const stallTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  // Check preloader cache first for zero-latency display
  const preloadedUrl = imagePreloader.getFullsizeUrl(photo.image_id);
  const isFetching = imagePreloader.isFetchingFullsize(photo.image_id);
  const networkUrl = fullsizeUrl(photo.image_id, 1600);

  // ---- Render-time src resolution (synchronous — no flash frame) ----
  // Falls back to network URL on initial mount (!displaySrcRef.current)
  // to avoid <img src=""> resolving to the page base URL and triggering onError.
  if (preloadedUrl) {
    displaySrcRef.current = preloadedUrl;
  } else if (!isFetching || !displaySrcRef.current) {
    displaySrcRef.current = networkUrl;
  }
  // else: isFetching → stall (keep displaySrcRef.current unchanged)

  const displaySrc = displaySrcRef.current;

  // ---- Image change handling (no key — smooth transition) ----

  useEffect(() => {
    // Clear pending spinner timer
    if (spinnerTimerRef.current) {
      clearTimeout(spinnerTimerRef.current);
      spinnerTimerRef.current = null;
    }

    const isNewImage = prevImageIdRef.current !== photo.image_id;
    prevImageIdRef.current = photo.image_id;

    if (!isNewImage) return;

    setError(false);
    setShowSpinner(false);

    // Clean up previous stall
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }
    if (stallTimerRef.current) {
      clearTimeout(stallTimerRef.current);
      stallTimerRef.current = null;
    }

    // Case 1: Already cached → use blob URL immediately
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

    // Case 2: Being fetched → stall, keep old image (already done in render)
    if (isFetching) {
      setImageReady(false);

      unsubscribeRef.current = imagePreloader.onFullsizeLoaded(photo.image_id, () => {
        setVersion((v) => v + 1);
      });

      stallTimerRef.current = setTimeout(() => {
        if (unsubscribeRef.current) {
          unsubscribeRef.current();
          unsubscribeRef.current = null;
        }
        displaySrcRef.current = networkUrl;
        setVersion((v) => v + 1);
      }, 4000);
      return;
    }

    // Case 3: Not cached, not fetching → use network, trigger preload
    imagePreloader.preloadFullsizeBg(photo.image_id, "high");

    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth > 0) {
      setImageReady(true);
      return;
    }
    setImageReady(false);
    spinnerTimerRef.current = setTimeout(() => setShowSpinner(true), 200);
  }, [photo.image_id, preloadedUrl, isFetching, networkUrl]);

  // Cleanup timers on unmount
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
    console.error("[ComparePreview] onError for", photo.image_id, "src:", (e.target as HTMLImageElement).src);
    if (spinnerTimerRef.current) {
      clearTimeout(spinnerTimerRef.current);
      spinnerTimerRef.current = null;
    }
    setShowSpinner(false);
    setImageReady(true);
    setError(true);
  }, [photo.image_id]);

  return (
    <div className={`compare-panel${isActive ? " compare-panel--active" : ""}`}>
      <div className="compare-image-area">
        {/* Spinner overlay — only shown after 200 ms delay */}
        {showSpinner && !imageReady && !error && (
          <div className="fullsize-loading">
            <div className="spinner" />
          </div>
        )}
        {error && (
          <div className="fullsize-error">
            <span>原图加载失败</span>
          </div>
        )}
        {/* No key={imageId}: smooth transition — browser keeps displaying
            the old image while the new one decodes in the background. */}
        <img
          ref={imgRef}
          src={displaySrc}
          alt={photo.file_name}
          loading="eager"
          onLoad={handleLoad}
          onError={handleError}
          draggable={false}
        />
      </div>
      <div className="compare-meta">
        <span className="compare-meta-name" title={photo.file_name}>
          {photo.file_name}
        </span>
        <span className="compare-meta-star">
          {(photo.star_rating ?? 0) >= 1 ? "★" : ""}
        </span>
        {(photo.is_rejected ?? 0) >= 1 && (
          <span className="compare-meta-reject">废片</span>
        )}
        {isActive && <span className="compare-meta-badge">当前</span>}
      </div>
    </div>
  );
};

export default ComparePreview;
