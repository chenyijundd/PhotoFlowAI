/**
 * PhotoFlow AI - ImageCard Component
 *
 * Displays a single photo thumbnail with filename, dimensions,
 * and actual star rating from the database.
 *
 * Performance (Task 14):
 *   - True lazy loading via IntersectionObserver (only loads near viewport)
 *   - decoding="async" for off-main-thread decode
 *   - React.memo with custom comparator for precise re-render control
 *   - Tracks loaded state for PerformanceOverlay
 */

import React, { useCallback, useState, useEffect } from "react";
import type { PhotoInfo } from "../../types";
import { usePhotoSelection } from "../context/PhotoSelectionContext";
import { useIntersectionObserver } from "../hooks/useIntersectionObserver";
import {
  incrementLoadedThumbnails,
  decrementLoadedThumbnails,
} from "./PerformanceOverlay";

interface ImageCardProps {
  photo: PhotoInfo;
  style?: React.CSSProperties;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function thumbnailSrc(photo: PhotoInfo): string {
  if (photo.thumbnail_url) {
    return `http://127.0.0.1:8765${photo.thumbnail_url}`;
  }
  return "";
}

const ImageCard: React.FC<ImageCardProps> = React.memo(
  ({ photo, style }) => {
    const { selectedId, selectPhoto } = usePhotoSelection();
    const imgSrc = thumbnailSrc(photo);
    const isSelected = selectedId === photo.image_id;

    // True lazy loading via IntersectionObserver
    const { ref: lazyRef, isIntersecting } = useIntersectionObserver({
      rootMargin: "300px",
      threshold: 0,
      freezeOnceVisible: true,
    });

    const [imgLoaded, setImgLoaded] = useState(false);

    const handleClick = useCallback(() => {
      selectPhoto(photo.image_id);
    }, [photo.image_id, selectPhoto]);

    const handleImgLoad = useCallback(() => {
      setImgLoaded(true);
      if (process.env.NODE_ENV === "development") {
        incrementLoadedThumbnails();
      }
    }, []);

    const handleImgError = useCallback(() => {
      setImgLoaded(true); // Stop showing placeholder loading state
    }, []);

    // Cleanup on unmount for dev overlay tracking
    useEffect(() => {
      return () => {
        if (imgLoaded && process.env.NODE_ENV === "development") {
          decrementLoadedThumbnails();
        }
      };
    }, [imgLoaded]);

    return (
      <div
        ref={lazyRef}
        className={`photo-card${isSelected ? " photo-card-selected" : ""}`}
        style={style}
        onClick={handleClick}
      >
        <div className="photo-card-thumb">
          {imgSrc && isIntersecting ? (
            <>
              <img
                src={imgSrc}
                alt={photo.file_name}
                loading="lazy"
                decoding="async"
                draggable={false}
                onLoad={handleImgLoad}
                onError={handleImgError}
              />
              {photo.is_blur === 1 && (
                <div className="photo-card-blur-badge">BLUR</div>
              )}
              {photo.is_rejected === 1 && (
                <div className="photo-card-reject-badge">REJECT</div>
              )}
              {photo.is_duplicate === 1 && (
                <div className="photo-card-dup-badge">DUP</div>
              )}
              {photo.ai_suggestion && (
                <div className="photo-card-ai-badge">
                  AI: {photo.ai_suggestion === "POSSIBLE_BEST" ? "BEST" : photo.ai_suggestion === "POSSIBLE_BLUR" ? "BLUR" : "DUP"}
                </div>
              )}
            </>
          ) : (
            <div className="photo-card-placeholder">
              <span>{imgSrc ? "" : "无缩略图"}</span>
            </div>
          )}
        </div>
        <div className="photo-card-info">
          <span className="photo-card-name" title={photo.file_name}>
            {photo.file_name}
          </span>
          <span className="photo-card-dims">
            {photo.width} × {photo.height}
            {photo.file_size > 0 && ` · ${formatFileSize(photo.file_size)}`}
          </span>
          <span className="photo-card-rating">
            {photo.star_rating === 1 ? "★" : ""}
          </span>
        </div>
      </div>
    );
  },
  // Custom comparator: only re-render if photo data or selection state changed
  (prevProps, nextProps) => {
    const prevPhoto = prevProps.photo;
    const nextPhoto = nextProps.photo;
    return (
      prevPhoto.image_id === nextPhoto.image_id &&
      prevPhoto.star_rating === nextPhoto.star_rating &&
      prevPhoto.is_rejected === nextPhoto.is_rejected &&
      prevPhoto.is_blur === nextPhoto.is_blur &&
      prevPhoto.is_duplicate === nextPhoto.is_duplicate &&
      prevPhoto.duplicate_group === nextPhoto.duplicate_group &&
      prevPhoto.ai_suggestion === nextPhoto.ai_suggestion &&
      prevProps.style === nextProps.style
    );
  },
);

ImageCard.displayName = "ImageCard";

export default ImageCard;
