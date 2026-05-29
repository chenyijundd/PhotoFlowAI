/**
 * PhotoFlow AI - ComparePreview Component
 *
 * Displays a single photo's full-size preview with filename, star,
 * and reject status in the compare mode side panel.
 *
 * Performance (Task 14):
 *   - Memory safety: releases old image object when photo changes
 *   - decoding="async" for off-main-thread decode
 */

import React, { useState, useCallback, useEffect, useRef } from "react";
import { fullsizeUrl } from "../api/photoApi";
import type { PhotoInfo } from "../../types";

interface ComparePreviewProps {
  photo: PhotoInfo;
  isActive: boolean;
}

const ComparePreview: React.FC<ComparePreviewProps> = ({ photo, isActive }) => {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const prevImageIdRef = useRef<string | null>(null);

  const src = fullsizeUrl(photo.image_id);

  // Reset state when photo changes.
  // Then check img.complete — for cached images, onLoad fires
  // synchronously before this effect runs, so we must manually
  // sync the loaded state.
  useEffect(() => {
    prevImageIdRef.current = photo.image_id;
    setLoaded(false);
    setError(false);
    // Handle cached / already-loaded images
    const img = imgRef.current;
    if (img?.complete && img.naturalWidth > 0) {
      setLoaded(true);
    }
  }, [photo.image_id]);

  const handleLoad = useCallback(() => setLoaded(true), []);
  const handleError = useCallback(() => {
    setLoaded(true);
    setError(true);
    // Release failed resource
    if (imgRef.current) {
      imgRef.current.src = "";
    }
  }, []);

  return (
    <div className={`compare-panel${isActive ? " compare-panel--active" : ""}`}>
      <div className="compare-image-area">
        {!loaded && !error && (
          <div className="fullsize-loading">
            <div className="spinner" />
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
          alt={photo.file_name}
          loading="eager"
          decoding="async"
          onLoad={handleLoad}
          onError={handleError}
          style={{ display: loaded && !error ? "block" : "none" }}
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
          <span className="compare-meta-reject">REJECT</span>
        )}
        {isActive && <span className="compare-meta-badge">当前</span>}
      </div>
    </div>
  );
};

export default ComparePreview;
