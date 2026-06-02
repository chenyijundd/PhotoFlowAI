/**
 * PhotoFlow AI — useImagePreloader Hook
 *
 * Integrates the ImagePreloader service with React. Computes the visible
 * range (±2 rows) around the currently selected photo and triggers
 * preloading at appropriate priority levels.
 *
 * Priority levels:
 *   HIGH   — current photo, immediate neighbors (±1 index)
 *   MEDIUM — visible range ±2 rows
 *   LOW    — further ahead in the scroll direction
 *
 * Also triggers thumbnail preloading for all photos in the current view.
 */

import { useEffect, useRef, useCallback } from "react";
import { imagePreloader } from "../services/ImagePreloader";
import type { Priority } from "../services/ImagePreloader";
import type { PhotoInfo } from "../../types";

interface UseImagePreloaderOptions {
  /** Flat list of all currently displayed photos. */
  photos: PhotoInfo[];
  /** Index of the currently selected photo in `photos` (or -1). */
  selectedIndex: number;
  /** Number of columns in the grid (to compute rows). */
  columnCount: number;
  /** Whether preloading is active (e.g. pause during import). */
  enabled?: boolean;
}

interface UseImagePreloaderResult {
  /** Manually preload a specific photo at high priority. */
  preloadPhoto: (index: number) => void;
  /** Call on keyboard navigation to prefetch ahead in that direction. */
  onNavigate: (direction: 1 | -1) => void;
}

/**
 * Compute the range of indices that should be preloaded.
 * Range = selectedIndex ± (2 rows of photos + 2 extra on each side).
 */
function computePreloadRange(
  selectedIndex: number,
  totalCount: number,
  columnCount: number,
): { start: number; end: number } {
  if (selectedIndex < 0 || totalCount === 0 || columnCount <= 0) {
    return { start: 0, end: 0 };
  }

  const rowExtent = Math.max(2, columnCount) * 2; // ±2 rows in terms of photo count
  const margin = 4; // extra margin per side
  const range = rowExtent + margin;

  const start = Math.max(0, selectedIndex - range);
  const end = Math.min(totalCount - 1, selectedIndex + range);

  return { start, end };
}

function thumbnailNetworkUrl(photo: PhotoInfo): string {
  if (photo.thumbnail_url) {
    return photo.thumbnail_url; // relative path, Vite proxies to backend
  }
  return "";
}

export function useImagePreloader({
  photos,
  selectedIndex,
  columnCount,
  enabled = true,
}: UseImagePreloaderOptions): UseImagePreloaderResult {
  // Track the last known range so we can detect direction changes
  const lastRangeRef = useRef<{ start: number; end: number }>({ start: 0, end: 0 });
  const lastIndexRef = useRef(selectedIndex);

  /**
   * Main preload effect: runs whenever selectedIndex or photos change.
   * Computes the priority for each photo in range and enqueues preloads.
   */
  useEffect(() => {
    if (!enabled || photos.length === 0 || columnCount <= 0) return;

    const range = computePreloadRange(selectedIndex, photos.length, columnCount);
    lastRangeRef.current = range;

    if (range.start >= range.end) return;

    // 1. Full-size preloading with priority levels
    for (let i = range.start; i <= range.end; i++) {
      const photo = photos[i];
      if (!photo) continue;

      const dist = Math.abs(i - selectedIndex);
      let priority: Priority;

      if (dist <= 1) {
        priority = "high";
      } else if (dist <= columnCount * 2) {
        priority = "medium";
      } else {
        priority = "low";
      }

      imagePreloader.preloadFullsizeBg(photo.image_id, priority);
    }

    // 2. Thumbnail preloading for visible range
    const thumbList: Array<{ imageId: string; thumbnailUrl: string }> = [];
    for (let i = range.start; i <= range.end; i++) {
      const photo = photos[i];
      if (!photo || !photo.thumbnail_url) continue;
      thumbList.push({
        imageId: photo.image_id,
        thumbnailUrl: thumbnailNetworkUrl(photo),
      });
    }
    if (thumbList.length > 0) {
      imagePreloader.preloadThumbnailsBg(thumbList);
    }
  }, [photos, selectedIndex, columnCount, enabled]);

  /**
   * When the user navigates, prefetch further ahead in that direction.
   */
  const onNavigate = useCallback(
    (direction: 1 | -1) => {
      if (!enabled || photos.length === 0) return;

      const lookAhead = columnCount * 3; // 3 rows ahead
      const startIdx =
        direction === 1
          ? selectedIndex + 1
          : selectedIndex - lookAhead;
      const endIdx =
        direction === 1
          ? selectedIndex + lookAhead
          : selectedIndex - 1;

      for (let i = Math.max(0, startIdx); i <= Math.min(photos.length - 1, endIdx); i++) {
        const photo = photos[i];
        if (!photo) continue;
        const dist = Math.abs(i - selectedIndex);
        imagePreloader.preloadFullsizeBg(
          photo.image_id,
          dist <= columnCount ? "medium" : "low",
        );
      }
    },
    [photos, selectedIndex, columnCount, enabled],
  );

  /**
   * Manually preload a specific photo (e.g. on hover or focus).
   */
  const preloadPhoto = useCallback(
    (index: number) => {
      if (!enabled || index < 0 || index >= photos.length) return;
      imagePreloader.preloadFullsizeBg(photos[index].image_id, "high");
    },
    [photos, enabled],
  );

  // Update last index on each render
  lastIndexRef.current = selectedIndex;

  return { preloadPhoto, onNavigate };
}
