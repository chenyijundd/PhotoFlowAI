/**
 * PhotoFlow AI — BurstCompareGrid Component
 *
 * Full-page grid comparison layout for burst (连拍) groups.
 * Shows N photos in a responsive CSS Grid so the photographer can
 * compare facial expressions / poses side by side without switching.
 *
 * Grid adapts to photo count:
 *    2-3   photos → 2 columns
 *    4-6   photos → 3 columns
 *    7-12  photos → 4 columns
 *   13-20  photos → 5 columns
 *   21-30  photos → 6 columns
 *   31-50  photos → 7 columns
 *   51+    photos → 8 columns
 *
 * Large groups (31+ photos) automatically degrade to thumbnail images
 * to stay within ~15 MB memory instead of loading 300+ MB of full-size
 * originals.  The 400 px thumbnails are more than sufficient for
 * comparing facial expressions, poses, and blur at grid-cell scale.
 *
 * All grid images use loading="lazy" so that 100+ photo groups only
 * load the images visible in the viewport, avoiding browser connection
 * pool exhaustion (6-connections-per-origin limit).
 *
 * Keyboard shortcuts:
 *   Space  toggle star on the hovered photo
 *   D      toggle reject on the hovered photo
 *   B      return to browse mode
 *   Esc    return to browse mode
 */

import React, {
  useEffect,
  useCallback,
  useRef,
  useState,
} from "react";
import { useBurstCompare } from "../context/BurstCompareContext";
import { useKeyboardHandler, KEY_PRIORITY } from "../hooks/useKeyboardManager";
import { fullsizeUrl } from "../api/photoApi";
import { imagePreloader } from "../services/ImagePreloader";
import StatusOverlay from "./StatusOverlay";
import type { StatusType } from "./StatusOverlay";
import type { PhotoInfo } from "../../types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BACKEND_URL = "http://127.0.0.1:8765";

/** Photo-count threshold above which we switch to thumbnail images. */
const THUMBNAIL_THRESHOLD = 31;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Determine the number of grid columns based on photo count. */
function gridColumns(count: number): number {
  if (count <= 3) return 2;
  if (count <= 6) return 3;
  if (count <= 12) return 4;
  if (count <= 20) return 5;
  if (count <= 30) return 6;
  if (count <= 50) return 7;
  return 8;
}

/**
 * Build the best image source for a grid cell.
 *
 * When `useThumbnail` is true (large groups), prefer the pre-generated
 * thumbnail JPEG.  Even if `thumbnail_url` is null (e.g. cache not yet
 * built), we still construct the standard thumbnail path — the endpoint
 * may serve a just-generated file.  There is NO fallback to full-size
 * originals in thumbnail mode; loading 100+ full-size images would
 * overwhelm the browser connection pool.
 *
 * When `useThumbnail` is false, use the full-size preloader or URL.
 */
function gridImageSrc(photo: PhotoInfo, useThumbnail: boolean): string {
  if (useThumbnail) {
    // Always use the standard thumbnail path.  If the file doesn't exist
    // yet the onError handler will show a placeholder — this is far
    // better than accidentally loading 100×10 MB full-size images.
    return photo.thumbnail_url
      ? `${BACKEND_URL}${photo.thumbnail_url}`
      : `${BACKEND_URL}/api/thumbnails/${encodeURIComponent(photo.image_id)}.jpg`;
  }
  // Full-size path — use blob URL from preloader if available
  const preloaded = imagePreloader.getFullsizeUrl(photo.image_id);
  return preloaded || fullsizeUrl(photo.image_id, 1600);
}

// ---------------------------------------------------------------------------
// Single grid cell
// ---------------------------------------------------------------------------

interface GridCellProps {
  photo: PhotoInfo;
  hovered: boolean;
  /** When true, use thumbnail images instead of full-size originals. */
  useThumbnail: boolean;
  onHover: (imageId: string | null) => void;
  onToggleStar: (imageId: string) => void;
  onToggleReject: (imageId: string) => void;
}

const GridCell: React.FC<GridCellProps> = ({
  photo,
  hovered,
  useThumbnail,
  onHover,
  onToggleStar,
  onToggleReject,
}) => {
  const [imageReady, setImageReady] = useState(false);
  const [imgError, setImgError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const src = gridImageSrc(photo, useThumbnail);

  const isStarred = (photo.star_rating ?? 0) >= 1;
  const isRejected = (photo.is_rejected ?? 0) >= 1;

  // Preload — skip for thumbnails (they're tiny and already cached locally)
  useEffect(() => {
    if (!useThumbnail) {
      imagePreloader.preloadFullsizeBg(photo.image_id, "high");
    }
  }, [photo.image_id, useThumbnail]);

  const handleLoad = useCallback(() => {
    setImageReady(true);
    setImgError(false);
  }, []);

  const handleError = useCallback(() => {
    setImageReady(true);
    setImgError(true);
  }, []);

  return (
    <div
      className={`burst-grid-cell${hovered ? " burst-grid-cell--hovered" : ""}${isStarred ? " burst-grid-cell--starred" : ""}${isRejected ? " burst-grid-cell--rejected" : ""}`}
      onMouseEnter={() => onHover(photo.image_id)}
      onMouseLeave={() => onHover(null)}
    >
      {/* Image area */}
      <div className="burst-grid-image-area">
        {!imageReady && !imgError && (
          <div className="burst-grid-loading">
            <div className="spinner" />
          </div>
        )}
        {imgError && (
          <div className="burst-grid-error">
            <span>加载失败</span>
          </div>
        )}
        <img
          ref={imgRef}
          src={src}
          alt={photo.file_name}
          loading="lazy"
          onLoad={handleLoad}
          onError={handleError}
          draggable={false}
        />
      </div>

      {/* Info bar */}
      <div className="burst-grid-info">
        <span className="burst-grid-filename" title={photo.file_name}>
          {photo.file_name}
        </span>
        <span className="burst-grid-actions">
          <button
            className={`burst-grid-star${isStarred ? " burst-grid-star--active" : ""}`}
            onClick={(e) => { e.stopPropagation(); onToggleStar(photo.image_id); }}
            title="加星 (Space)"
          >
            {isStarred ? "★" : "☆"}
          </button>
          <button
            className={`burst-grid-reject${isRejected ? " burst-grid-reject--active" : ""}`}
            onClick={(e) => { e.stopPropagation(); onToggleReject(photo.image_id); }}
            title="废片 (D)"
          >
            {isRejected ? "✕" : "🗑"}
          </button>
        </span>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const BurstCompareGrid: React.FC = () => {
  const {
    burstPhotos,
    burstGroupId,
    totalInBurst,
    loading,
    error,
    exitBurstCompareMode,
    toggleStar,
    toggleReject,
  } = useBurstCompare();

  // Currently hovered photo (for Space / D targeting)
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const hoveredIdRef = useRef<string | null>(null);
  const setHovered = useCallback((id: string | null) => {
    setHoveredId(id);
    hoveredIdRef.current = id;
  }, []);

  // Status overlay for visual feedback
  const [statusType, setStatusType] = useState<StatusType>(null);

  // Action guard
  const actionInFlightRef = useRef(false);

  // Derived values
  const columns = gridColumns(totalInBurst);
  const useThumbnail = totalInBurst >= THUMBNAIL_THRESHOLD;

  // Preload full-size images only for manageable groups (≤30 photos).
  // Large groups use thumbnails directly — no preloading needed.
  useEffect(() => {
    if (useThumbnail) return;
    burstPhotos.forEach((p) => {
      imagePreloader.preloadFullsizeBg(p.image_id, "high");
    });
  }, [burstPhotos, useThumbnail]);

  // ---- Keyboard handler ----
  const handleBurstCompareKey = useCallback(
    (e: KeyboardEvent): boolean => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;

      const targetId = hoveredIdRef.current;
      if (!targetId && [" ", "Space", "d", "D"].includes(e.key)) {
        if (e.key === " " || e.key === "Space" || e.key === "d" || e.key === "D") {
          e.preventDefault();
          return true;
        }
        return false;
      }

      // Guard rapid actions
      if ([" ", "Space", "d", "D"].includes(e.key) && actionInFlightRef.current) {
        e.preventDefault();
        return true;
      }

      switch (e.key) {
        case " ":
        case "Space": {
          e.preventDefault();
          if (!targetId) return true;
          actionInFlightRef.current = true;
          toggleStar(targetId).then((newRating) => {
            actionInFlightRef.current = false;
            if (newRating >= 1) {
              setStatusType("star");
              setTimeout(() => setStatusType(null), 400);
            }
          });
          return true;
        }
        case "d":
        case "D": {
          e.preventDefault();
          if (!targetId) return true;
          actionInFlightRef.current = true;
          toggleReject(targetId).then((newReject) => {
            actionInFlightRef.current = false;
            if (newReject >= 1) {
              setStatusType("reject");
              setTimeout(() => setStatusType(null), 400);
            }
          });
          return true;
        }
        case "b":
        case "B":
        case "Escape": {
          e.preventDefault();
          exitBurstCompareMode();
          return true;
        }
      }
      return false;
    },
    [toggleStar, toggleReject, exitBurstCompareMode],
  );

  useKeyboardHandler(
    "burst-compare-mode",
    handleBurstCompareKey,
    KEY_PRIORITY.COMPARE,
    true,
  );

  // ---- Loading state ----
  if (loading) {
    return (
      <div className="burst-compare-page">
        <div className="state-screen">
          <div className="spinner" />
          <p>加载连拍组...</p>
        </div>
      </div>
    );
  }

  // ---- Error state ----
  if (error) {
    return (
      <div className="burst-compare-page">
        <div className="state-screen">
          <div className="state-icon">⚠️</div>
          <h2>连拍对比</h2>
          <p>{error}</p>
          <button className="btn-primary" onClick={exitBurstCompareMode}>
            退出
          </button>
        </div>
      </div>
    );
  }

  // ---- Grid view ----
  return (
    <div className="burst-compare-page">
      <StatusOverlay type={statusType} />

      {/* Header */}
      <div className="burst-compare-header">
        <span className="burst-compare-header-label">BURST COMPARE</span>
        <span className="burst-compare-header-group">{burstGroupId || ""}</span>
        <span className="burst-compare-header-count">
          {totalInBurst} 张 · {columns} 列
        </span>
        {useThumbnail && (
          <span className="burst-compare-header-mode" title="照片数超过30张，自动使用缩略图以节省内存">
            ⚡ 缩略图模式
          </span>
        )}
        <span className="burst-compare-header-hint">
          鼠标悬停照片 · Space 加星 · D 废片 · B / Esc 退出
        </span>
        <button className="burst-compare-header-exit" onClick={exitBurstCompareMode}>
          退出对比 B / Esc
        </button>
      </div>

      {/* Grid body */}
      <div
        className="burst-compare-body"
        style={{ "--burst-columns": columns } as React.CSSProperties}
      >
        {burstPhotos.map((photo) => (
          <GridCell
            key={photo.image_id}
            photo={photo}
            useThumbnail={useThumbnail}
            hovered={hoveredId === photo.image_id}
            onHover={setHovered}
            onToggleStar={async (id) => {
              const r = await toggleStar(id);
              if (r >= 1) {
                setStatusType("star");
                setTimeout(() => setStatusType(null), 400);
              }
            }}
            onToggleReject={async (id) => {
              const r = await toggleReject(id);
              if (r >= 1) {
                setStatusType("reject");
                setTimeout(() => setStatusType(null), 400);
              }
            }}
          />
        ))}
      </div>
    </div>
  );
};

export default BurstCompareGrid;
