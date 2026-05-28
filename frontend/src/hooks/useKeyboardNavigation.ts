/**
 * PhotoFlow AI - Keyboard Navigation Hook
 *
 * Drives the photographer's keyboard-only selection workflow:
 *   ← →  navigate photos (skip rejected unless in reject mode)
 *   Space toggle star (0 ↔ 1) → auto-advance
 *   X     toggle reject (0 ↔ 1) → auto-advance
 *   Enter toggle fit / 100 % zoom
 *   Home first photo
 *   End   last photo
 *
 * Only active when no input / textarea is focused.
 */

import { useEffect, useCallback, useMemo, useState } from "react";
import type { PhotoInfo, PhotoFilterMode } from "../../types";

export type ZoomMode = "fit" | "zoom100";

interface UseKeyboardNavigationProps {
  photos: PhotoInfo[];
  selectedId: string | null;
  selectPhoto: (id: string) => void;
  onToggleStar: (imageId: string, currentRating: number) => void;
  onToggleReject: (imageId: string, currentReject: number) => void;
  scrollToIndex: (index: number) => void;
  active: boolean;
  filterMode: PhotoFilterMode;
}

interface UseKeyboardNavigationResult {
  zoomMode: ZoomMode;
  setZoomMode: (mode: ZoomMode) => void;
  selectedIndex: number;
}

/**
 * Find the next photo in a given direction that is not rejected.
 * When filterMode is "rejected", rejected photos are NOT skipped.
 */
function findNextNonRejectedIndex(
  photos: PhotoInfo[],
  currentIdx: number,
  direction: 1 | -1,
  skipRejected: boolean,
): number {
  let idx = currentIdx + direction;
  while (idx >= 0 && idx < photos.length) {
    if (!skipRejected || (photos[idx].is_rejected ?? 0) === 0) {
      return idx;
    }
    idx += direction;
  }
  return -1; // no valid photo in that direction
}

/**
 * Find the next "unprocessed" photo (not starred AND not rejected).
 * If none found, just return the next photo index.
 */
function findNextUnprocessed(
  photos: PhotoInfo[],
  currentIdx: number,
): number {
  // First, try to find next unprocessed photo
  for (let i = currentIdx + 1; i < photos.length; i++) {
    const p = photos[i];
    if ((p.star_rating ?? 0) === 0 && (p.is_rejected ?? 0) === 0) {
      return i;
    }
  }
  // Fallback: next photo (if any)
  if (currentIdx + 1 < photos.length) {
    return currentIdx + 1;
  }
  return -1;
}

export function useKeyboardNavigation({
  photos,
  selectedId,
  selectPhoto,
  onToggleStar,
  onToggleReject,
  scrollToIndex,
  active,
  filterMode,
}: UseKeyboardNavigationProps): UseKeyboardNavigationResult {
  const [zoomMode, setZoomMode] = useState<ZoomMode>("fit");

  // Current index of selected photo in the photos array
  const selectedIndex = useMemo(() => {
    if (!selectedId) return -1;
    return photos.findIndex((p) => p.image_id === selectedId);
  }, [photos, selectedId]);

  // In rejected filter mode, we should NOT skip rejected photos
  const skipRejected = filterMode !== "rejected";

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      switch (e.key) {
        case "ArrowLeft": {
          e.preventDefault();
          const nextIdx = findNextNonRejectedIndex(photos, selectedIndex, -1, skipRejected);
          if (nextIdx >= 0) {
            selectPhoto(photos[nextIdx].image_id);
          }
          break;
        }
        case "ArrowRight": {
          e.preventDefault();
          const nextIdx = findNextNonRejectedIndex(photos, selectedIndex, 1, skipRejected);
          if (nextIdx >= 0) {
            selectPhoto(photos[nextIdx].image_id);
          }
          break;
        }
        case " ":
        case "Space": {
          // Space — toggle star
          e.preventDefault();
          if (selectedId && selectedIndex >= 0) {
            const currentStar = photos[selectedIndex].star_rating ?? 0;
            onToggleStar(selectedId, currentStar);
          }
          break;
        }
        case "x":
        case "X": {
          // X — toggle reject
          e.preventDefault();
          if (selectedId && selectedIndex >= 0) {
            const currentReject = photos[selectedIndex].is_rejected ?? 0;
            onToggleReject(selectedId, currentReject);
          }
          break;
        }
        case "Enter": {
          e.preventDefault();
          setZoomMode((prev) => (prev === "fit" ? "zoom100" : "fit"));
          break;
        }
        case "Home": {
          e.preventDefault();
          const firstIdx = findNextNonRejectedIndex(photos, -1, 1, skipRejected);
          if (firstIdx >= 0) {
            selectPhoto(photos[firstIdx].image_id);
          } else if (photos.length > 0) {
            selectPhoto(photos[0].image_id);
          }
          break;
        }
        case "End": {
          e.preventDefault();
          const lastIdx = findNextNonRejectedIndex(photos, photos.length, -1, skipRejected);
          if (lastIdx >= 0) {
            selectPhoto(photos[lastIdx].image_id);
          } else if (photos.length > 0) {
            selectPhoto(photos[photos.length - 1].image_id);
          }
          break;
        }
      }
    },
    [selectedIndex, photos, selectedId, selectPhoto, onToggleStar, onToggleReject, skipRejected],
  );

  // Attach / detach global listener
  useEffect(() => {
    if (!active) return;
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [active, handleKeyDown]);

  // Auto-scroll grid when selection changes
  useEffect(() => {
    if (selectedIndex >= 0) {
      scrollToIndex(selectedIndex);
    }
  }, [selectedIndex, scrollToIndex]);

  return { zoomMode, setZoomMode, selectedIndex };
}

/**
 * Helper exported for BrowserPage to implement smart next selection
 * after Space/X auto-advance.
 */
export { findNextUnprocessed };
