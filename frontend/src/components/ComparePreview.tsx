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

  // Check preloader cache first for zero-latency display
  const preloadedUrl = imagePreloader.getFullsizeUrl(photo.image_id);
  const src = preloadedUrl || fullsizeUrl(photo.image_id);

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

    // Check if browser already has this image decoded
    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth > 0) {
      setImageReady(true);
      return;
    }

    // New image loading — keep old image visible, delay spinner
    setImageReady(false);
    spinnerTimerRef.current = setTimeout(() => {
      setShowSpinner(true);
    }, 200);
  }, [photo.image_id]);

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
          src={src}
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
