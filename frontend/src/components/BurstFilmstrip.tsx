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
import type { PhotoInfo } from "../../types";

const BACKEND_URL = "http://127.0.0.1:8765";

interface BurstFilmstripProps {
  currentImageId: string;
  burstGroupId: string;
  /** Called after any burst action completes, so the parent can refresh the grid & counts. */
  onAction?: () => void;
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
}) => {
  const [photos, setPhotos] = useState<PhotoInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const stripRef = useRef<HTMLDivElement>(null);
  const { selectPhoto } = usePhotoSelection();

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

  // Scroll the current photo into view when it changes
  useEffect(() => {
    if (!stripRef.current) return;
    const activeThumb = stripRef.current.querySelector(
      `[data-burst-id="${currentImageId}"]`
    ) as HTMLElement | null;
    if (activeThumb) {
      activeThumb.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "center",
      });
    }
  }, [currentImageId, photos]);

  // [ and ] keys for burst-group navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
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
    [currentImageId, photos, selectPhoto]
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
              }`}
              onClick={() => selectPhoto(photo.image_id)}
              title={photo.file_name}
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
        >
          全拒绝
        </button>
      </div>
    </div>
  );
};

export default BurstFilmstrip;
