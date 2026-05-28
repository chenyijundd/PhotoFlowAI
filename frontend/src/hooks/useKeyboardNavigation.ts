/**
 * PhotoFlow AI - Keyboard Navigation Hook
 *
 * Drives the photographer's keyboard-only selection workflow:
 *   ← →  navigate photos
 *   Space toggle star (0 ↔ 1)
 *   X     toggle reject (0 ↔ 1)
 *   Enter toggle fit / 100 % zoom
 *   Home first photo
 *   End   last photo
 *
 * Only active when no input / textarea is focused.
 */

import { useEffect, useCallback, useMemo, useState } from "react";
import type { PhotoInfo } from "../../types";

export type ZoomMode = "fit" | "zoom100";

interface UseKeyboardNavigationProps {
  photos: PhotoInfo[];
  selectedId: string | null;
  selectPhoto: (id: string) => void;
  onToggleStar: (imageId: string, currentRating: number) => void;
  onToggleReject: (imageId: string, currentReject: number) => void;
  scrollToIndex: (index: number) => void;
  active: boolean;
}

interface UseKeyboardNavigationResult {
  zoomMode: ZoomMode;
  setZoomMode: (mode: ZoomMode) => void;
  selectedIndex: number;
}

export function useKeyboardNavigation({
  photos,
  selectedId,
  selectPhoto,
  onToggleStar,
  onToggleReject,
  scrollToIndex,
  active,
}: UseKeyboardNavigationProps): UseKeyboardNavigationResult {
  const [zoomMode, setZoomMode] = useState<ZoomMode>("fit");

  // Current index of selected photo in the photos array
  const selectedIndex = useMemo(() => {
    if (!selectedId) return -1;
    return photos.findIndex((p) => p.image_id === selectedId);
  }, [photos, selectedId]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      switch (e.key) {
        case "ArrowLeft": {
          e.preventDefault();
          if (selectedIndex > 0) {
            selectPhoto(photos[selectedIndex - 1].image_id);
          }
          break;
        }
        case "ArrowRight": {
          e.preventDefault();
          if (selectedIndex < photos.length - 1) {
            selectPhoto(photos[selectedIndex + 1].image_id);
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
          if (photos.length > 0) {
            selectPhoto(photos[0].image_id);
          }
          break;
        }
        case "End": {
          e.preventDefault();
          if (photos.length > 0) {
            selectPhoto(photos[photos.length - 1].image_id);
          }
          break;
        }
      }
    },
    [selectedIndex, photos, selectedId, selectPhoto, onToggleStar, onToggleReject],
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
