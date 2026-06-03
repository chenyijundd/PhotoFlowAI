/**
 * PhotoFlow AI - ImageCard Component
 *
 * Displays a single photo thumbnail with filename, dimensions,
 * and actual star rating from the database.
 *
 * Supports batch multi-select via Ctrl+Click (toggle) and
 * Shift+Click (range).  Regular click sets single selection
 * and updates the detail panel.
 *
 * Performance (Task 14):
 *   - True lazy loading via IntersectionObserver (only loads near viewport)
 *   - decoding="async" for off-main-thread decode
 *   - React.memo with custom comparator for precise re-render control
 */

import React, { useCallback, useState } from "react";
import type { PhotoInfo } from "../../types";
import { usePhotoSelection } from "../context/PhotoSelectionContext";
import { useBatchSelection } from "../context/BatchSelectionContext";
import { useIntersectionObserver } from "../hooks/useIntersectionObserver";
import { imagePreloader } from "../services/ImagePreloader";

interface ImageCardProps {
  photo: PhotoInfo;
  style?: React.CSSProperties;
  /** Whether this photo is in the batch multi-selection. */
  isBatchSelected: boolean;
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
  ({ photo, style, isBatchSelected }) => {
    const { selectedId, selectPhoto } = usePhotoSelection();
    const {
      toggleSelect,
      rangeSelectTo,
      selectSingle,
      setAnchor,
      selectionCount,
    } = useBatchSelection();
    // Check preloader cache first (IndexedDB → memory), fall back to network URL
    const cachedThumb = imagePreloader.getThumbnailUrlSync(photo.image_id);
    const imgSrc = cachedThumb || thumbnailSrc(photo);
    const isDetailSelected = selectedId === photo.image_id;

    // True lazy loading via IntersectionObserver
    const { ref: lazyRef, isIntersecting } = useIntersectionObserver({
      rootMargin: "300px",
      threshold: 0,
      freezeOnceVisible: true,
    });

    const [imgLoaded, setImgLoaded] = useState(false);

    const handleClick = useCallback(
      (e: React.MouseEvent) => {
        // Trigger full-size preload BEFORE updating selection so that
        // by the time FullsizePreview re-renders the image is either
        // already being fetched (→ stall) or cached (→ instant display).
        imagePreloader.preloadFullsizeBg(photo.image_id, "high");

        if (e.ctrlKey || e.metaKey) {
          // Ctrl+Click → toggle this photo in batch selection
          e.preventDefault();
          toggleSelect(photo.image_id);
          // Also update detail panel to this photo
          selectPhoto(photo.image_id);
        } else if (e.shiftKey && selectionCount > 0) {
          // Shift+Click → select range
          e.preventDefault();
          // We need the ordered list of visible photo IDs for range calc.
          // This is passed via a data attribute on the grid container.
          rangeSelectTo(photo.image_id, getVisibleOrderedIds());
          selectPhoto(photo.image_id);
        } else {
          // Regular click → show photo detail.
          // Only clear batch selection when it is active; skipping
          // selectSingle when selectionCount === 0 prevents a
          // BatchSelectionContext update that would invalidate
          // ImageGrid.Cell useMemo and remount every visible thumbnail.
          if (selectionCount > 0) {
            selectSingle(photo.image_id);
          }
          selectPhoto(photo.image_id);
        }
      },
      [photo.image_id, toggleSelect, rangeSelectTo, selectSingle, selectPhoto, selectionCount],
    );

    const handleImgLoad = useCallback(() => {
      setImgLoaded(true);
    }, []);

    const handleImgError = useCallback(() => {
      setImgLoaded(true); // Stop showing placeholder loading state
    }, []);

    const showCheckbox = selectionCount > 0;

    return (
      <div
        ref={lazyRef}
        className={`photo-card${isDetailSelected ? " photo-card-selected" : ""}${isBatchSelected ? " photo-card-batch-selected" : ""}${showCheckbox ? " photo-card-multiselect" : ""}`}
        style={style}
        onClick={handleClick}
      >
        {/* Selection checkbox overlay — shown when any photos are selected */}
        {showCheckbox && (
          <div
            className={`photo-card-check${isBatchSelected ? " photo-card-check--on" : ""}`}
            onClick={(e) => {
              e.stopPropagation();
              toggleSelect(photo.image_id);
            }}
          >
            {isBatchSelected ? "✓" : ""}
          </div>
        )}

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
              {/* Detection badges follow cascade priority: only the highest-priority
                   problem is shown per photo (closed_eye > blur > burst > dup > best).
                   REJECT is a user action, shown independently. */}
              {/* Badge priority: defect(L1/L2) > best > group */}
              {/* 不展示 AI "最佳" 标签 — 摄影师应自主判断，AI 推荐不应干扰挑选 */}
              {photo.is_closed_eye === 1 ? (
                <div className="photo-card-eye-badge">闭眼</div>
              ) : photo.is_blur === 1 ? (
                <div className="photo-card-blur-badge">模糊</div>
              ) : photo.burst_group ? (
                <div className="photo-card-burst-badge">连拍</div>
              ) : photo.is_duplicate === 1 ? (
                <div className="photo-card-dup-badge">重复</div>
              ) : null}
              {photo.is_rejected === 1 && (
                <div className="photo-card-reject-badge">废片</div>
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
      prevPhoto.is_closed_eye === nextPhoto.is_closed_eye &&
      prevPhoto.is_duplicate === nextPhoto.is_duplicate &&
      prevPhoto.duplicate_group === nextPhoto.duplicate_group &&
      prevPhoto.burst_group === nextPhoto.burst_group &&
      prevPhoto.is_best_in_burst === nextPhoto.is_best_in_burst &&
      prevPhoto.is_best_in_duplicate === nextPhoto.is_best_in_duplicate &&
      prevProps.isBatchSelected === nextProps.isBatchSelected &&
      prevProps.style === nextProps.style
    );
  },
);

ImageCard.displayName = "ImageCard";

// ---------------------------------------------------------------------------
// Helper: get the ordered list of visible photo IDs from the DOM for
// Shift+Click range calculation.  Stored as a data attribute on the grid
// container by ImageGrid.
// ---------------------------------------------------------------------------

function getVisibleOrderedIds(): string[] {
  const el = document.querySelector("[data-photo-ids]");
  if (!el) return [];
  const raw = el.getAttribute("data-photo-ids");
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch {
    return raw.split(",");
  }
}

export default ImageCard;
