/**
 * PhotoFlow AI - Burst Filmstrip Component
 *
 * Horizontal thumbnail strip shown below the detail panel metadata
 * when the selected photo belongs to a burst (continuous-shooting) group.
 *
 * Features:
 *   - Fetches all photos in the same burst group
 *   - Renders clickable thumbnails in a horizontal scrollable strip
 *   - Highlights the currently-viewed photo
 *   - [ and ] keys navigate within the group
 */

import React, { useEffect, useState, useCallback, useRef } from "react";
import { fetchBurstPhotos, acceptBestInBurst, acceptAllInBurst, rejectAllInBurst } from "../api/photoApi";
import { usePhotoSelection } from "../context/PhotoSelectionContext";
import { useBurstCompare } from "../context/BurstCompareContext";
import type { PhotoInfo } from "../../types";

const BACKEND_URL = "http://127.0.0.1:8765";

interface BurstFilmstripProps {
  currentImageId: string;
  burstGroupId: string;
  /** Called after any burst action completes, so the parent can refresh the grid & counts. */
  onAction?: () => void;
  /** When true, all interactive elements are disabled (e.g. during multi-select). */
  actionsDisabled?: boolean;
}

function thumbUrl(photo: PhotoInfo): string {
  if (photo.thumbnail_url) {
    return `${BACKEND_URL}${photo.thumbnail_url}`;
  }
  return "";
}

const BurstFilmstrip: React.FC<BurstFilmstripProps> = ({
  currentImageId,
  burstGroupId,
  onAction,
  actionsDisabled = false,
}) => {
  const [photos, setPhotos] = useState<PhotoInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const stripRef = useRef<HTMLDivElement>(null);
  const { selectPhoto } = usePhotoSelection();
  const { isBurstCompareMode, enterBurstCompareMode } = useBurstCompare();

  // Load burst group photos — extracted so it can be re-called after actions
  const loadPhotos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBurstPhotos(burstGroupId);
      setPhotos(data.photos);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "加载连拍组失败");
    } finally {
      setLoading(false);
    }
  }, [burstGroupId]);

  useEffect(() => {
    loadPhotos();
  }, [loadPhotos]);

  // Scroll the current photo into view (horizontal only — use the strip's
  // own scrollLeft so we never affect ancestor scroll positions like the
  // detail panel).
  useEffect(() => {
    if (!stripRef.current) return;
    const activeThumb = stripRef.current.querySelector(
      `[data-burst-id="${currentImageId}"]`
    ) as HTMLElement | null;
    if (activeThumb && stripRef.current) {
      const strip = stripRef.current;
      const thumbLeft = activeThumb.offsetLeft;
      const thumbWidth = activeThumb.offsetWidth;
      const stripWidth = strip.clientWidth;
      strip.scrollTo({
        left: Math.max(0, thumbLeft - (stripWidth - thumbWidth) / 2),
        behavior: "smooth",
      });
    }
  }, [currentImageId, photos]);

  // [ and ] keys for burst-group navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (actionsDisabled) return;
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      const currentIdx = photos.findIndex(
        (p) => p.image_id === currentImageId
      );
      if (currentIdx < 0) return;

      if (e.key === "[") {
        e.preventDefault();
        const prevIdx = currentIdx > 0 ? currentIdx - 1 : photos.length - 1;
        selectPhoto(photos[prevIdx].image_id);
      } else if (e.key === "]") {
        e.preventDefault();
        const nextIdx = currentIdx < photos.length - 1 ? currentIdx + 1 : 0;
        selectPhoto(photos[nextIdx].image_id);
      }
    },
    [currentImageId, photos, selectPhoto, actionsDisabled]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Loading / error / empty
  if (loading) {
    return (
      <div className="burst-filmstrip">
        <div className="burst-filmstrip-header">加载连拍组...</div>
      </div>
    );
  }

  if (error || photos.length === 0) {
    return null;
  }

  return (
    <div className="burst-filmstrip">
      <div className="burst-filmstrip-header">
        连拍组 {burstGroupId} · {photos.length} 张
        <button
          className="burst-filmstrip-compare-btn"
          onClick={() => enterBurstCompareMode(burstGroupId)}
          title="多图对比 (B)"
          disabled={isBurstCompareMode || actionsDisabled}
        >
          🔍
        </button>
      </div>
      <div className="burst-filmstrip-strip" ref={stripRef}>
        {photos.map((photo) => {
          const src = thumbUrl(photo);
          const isActive = photo.image_id === currentImageId;
          return (
            <div
              key={photo.image_id}
              data-burst-id={photo.image_id}
              className={`burst-filmstrip-thumb${
                isActive ? " burst-filmstrip-thumb--active" : ""
              }${actionsDisabled ? " burst-filmstrip-thumb--disabled" : ""}`}
              onClick={actionsDisabled ? undefined : () => selectPhoto(photo.image_id)}
              title={photo.file_name}
              style={actionsDisabled ? { pointerEvents: "none", opacity: 0.5 } : undefined}
            >
              {src ? (
                <img src={src} alt={photo.file_name} loading="lazy" />
              ) : (
                <div className="burst-filmstrip-thumb-placeholder">
                  {photo.file_name.slice(0, 4)}
                </div>
              )}
              {photo.star_rating === 1 && (
                <span className="burst-filmstrip-star">★</span>
              )}
              {photo.is_rejected === 1 && (
                <span className="burst-filmstrip-reject">✕</span>
              )}
            </div>
          );
        })}
      </div>
      <div className="burst-filmstrip-actions">
        <button
          className="burst-filmstrip-btn"
          onClick={async () => {
            try {
              await acceptBestInBurst(burstGroupId);
              await loadPhotos();
              onAction?.();
            } catch { /* ignore */ }
          }}
          title="保留推荐照片，拒绝其余"
          disabled={actionsDisabled}
        >
          保留推荐
        </button>
        <button
          className="burst-filmstrip-btn"
          onClick={async () => {
            try {
              await acceptAllInBurst(burstGroupId);
              await loadPhotos();
              onAction?.();
            } catch { /* ignore */ }
          }}
          title="组内全部加星"
          disabled={actionsDisabled}
        >
          全保留
        </button>
        <button
          className="burst-filmstrip-btn burst-filmstrip-btn--danger"
          onClick={async () => {
            try {
              await rejectAllInBurst(burstGroupId);
              await loadPhotos();
              onAction?.();
            } catch { /* ignore */ }
          }}
          title="组内全部拒绝"
          disabled={actionsDisabled}
        >
          全拒绝
        </button>
      </div>
    </div>
  );
};

export default BurstFilmstrip;
