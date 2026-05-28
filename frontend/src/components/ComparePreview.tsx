/**
 * PhotoFlow AI - ComparePreview Component
 *
 * Displays a single photo's full-size preview with filename, star,
 * and reject status in the compare mode side panel.
 */

import React, { useState, useCallback } from "react";
import { fullsizeUrl } from "../api/photoApi";
import type { PhotoInfo } from "../../types";

interface ComparePreviewProps {
  photo: PhotoInfo;
  isActive: boolean;
}

const ComparePreview: React.FC<ComparePreviewProps> = ({ photo, isActive }) => {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  const src = fullsizeUrl(photo.image_id);

  const handleLoad = useCallback(() => setLoaded(true), []);
  const handleError = useCallback(() => {
    setLoaded(true);
    setError(true);
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
          src={src}
          alt={photo.file_name}
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
