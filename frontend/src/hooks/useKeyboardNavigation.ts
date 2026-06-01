/**
 * PhotoFlow AI - Keyboard Navigation Hook
 *
 * Drives the photographer's keyboard-only selection workflow:
 *   ← →  navigate photos (skip rejected unless in reject mode)
 *   Space toggle star (0 ↔ 1) → auto-advance
 *   D     toggle reject (0 ↔ 1) → auto-advance
 *   Enter toggle fit / 100 % zoom
 *   Home first photo
 *   End   last photo
 *
 * Only active when no input / textarea is focused.
 *
 * Performance (Task 14):
 *   - Uses centralized keyboard manager (single global listener)
 *   - Stable callback via ref to avoid stale closures
 */

import { useEffect, useCallback, useMemo, useRef } from "react";
import type { PhotoInfo, PhotoFilterMode } from "../../types";
import { useKeyboardHandler, KEY_PRIORITY } from "./useKeyboardManager";

// ZoomMode type is now in types/index.ts — kept export for backward compat
export type { ZoomMode } from "../../types";

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
  // Current index of selected photo in the photos array
  const selectedIndex = useMemo(() => {
    if (!selectedId) return -1;
    return photos.findIndex((p) => p.image_id === selectedId);
  }, [photos, selectedId]);

  // Use refs to avoid stale closures in the keyboard handler
  const photosRef = useRef(photos);
  photosRef.current = photos;
  const selectedIndexRef = useRef(selectedIndex);
  selectedIndexRef.current = selectedIndex;
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;
  const selectPhotoRef = useRef(selectPhoto);
  selectPhotoRef.current = selectPhoto;
  const onToggleStarRef = useRef(onToggleStar);
  onToggleStarRef.current = onToggleStar;
  const onToggleRejectRef = useRef(onToggleReject);
  onToggleRejectRef.current = onToggleReject;

  // In rejected filter mode, we should NOT skip rejected photos
  const skipRejected = filterMode !== "rejected";
  const skipRejectedRef = useRef(skipRejected);
  skipRejectedRef.current = skipRejected;

  // Grid keyboard handler via centralized manager
  const handleGridKey = useCallback(
    (e: KeyboardEvent): boolean => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;

      const p = photosRef.current;
      const idx = selectedIndexRef.current;
      const sid = selectedIdRef.current;

      switch (e.key) {
        case "ArrowLeft": {
          e.preventDefault();
          const nextIdx = findNextNonRejectedIndex(p, idx, -1, skipRejectedRef.current);
          if (nextIdx >= 0) {
            selectPhotoRef.current(p[nextIdx].image_id);
          }
          return true;
        }
        case "ArrowRight": {
          e.preventDefault();
          const nextIdx = findNextNonRejectedIndex(p, idx, 1, skipRejectedRef.current);
          if (nextIdx >= 0) {
            selectPhotoRef.current(p[nextIdx].image_id);
          }
          return true;
        }
        case " ":
        case "Space": {
          e.preventDefault();
          if (sid && idx >= 0) {
            const currentStar = p[idx].star_rating ?? 0;
            onToggleStarRef.current(sid, currentStar);
          }
          return true;
        }
        case "d":
        case "D": {
          e.preventDefault();
          if (sid && idx >= 0) {
            const currentReject = p[idx].is_rejected ?? 0;
            onToggleRejectRef.current(sid, currentReject);
          }
          return true;
        }
        case "Home": {
          e.preventDefault();
          const firstIdx = findNextNonRejectedIndex(p, -1, 1, skipRejectedRef.current);
          if (firstIdx >= 0) {
            selectPhotoRef.current(p[firstIdx].image_id);
          } else if (p.length > 0) {
            selectPhotoRef.current(p[0].image_id);
          }
          return true;
        }
        case "End": {
          e.preventDefault();
          const lastIdx = findNextNonRejectedIndex(p, p.length, -1, skipRejectedRef.current);
          if (lastIdx >= 0) {
            selectPhotoRef.current(p[lastIdx].image_id);
          } else if (p.length > 0) {
            selectPhotoRef.current(p[p.length - 1].image_id);
          }
          return true;
        }
      }
      return false;
    },
    [], // Stable reference — all data via refs
  );

  // Register via centralized keyboard manager
  useKeyboardHandler("grid-navigation", handleGridKey, KEY_PRIORITY.GRID, active);

  // Auto-scroll grid when selection changes
  useEffect(() => {
    if (selectedIndex >= 0) {
      scrollToIndex(selectedIndex);
    }
  }, [selectedIndex, scrollToIndex]);

  return { selectedIndex };
}

/**
 * Helper exported for BrowserPage to implement smart next selection
 * after Space/X auto-advance.
 */
export { findNextUnprocessed };
