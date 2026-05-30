/**
 * PhotoFlow AI - Lightbox Mode Context
 *
 * Full-screen photo viewer that replaces the grid layout.
 * Follows the same "page takeover" pattern as CompareModeContext.
 *
 * Features:
 *   - Zoom: Fit-to-screen (default) / 100% toggle via Z key
 *   - Mouse wheel zoom scaling in 100% mode
 *   - Arrow key navigation within photo set
 *   - Star/Reject actions with status overlay
 *   - Status bar showing "FIT" or zoom percentage
 */

import React, { createContext, useContext, useState, useCallback, useRef } from "react";
import type { PhotoInfo, ZoomMode } from "../../types";
import { updateStarRating, updateRejectStatus } from "../api/photoApi";
import type { StatusType } from "../components/StatusOverlay";

// Re-export ZoomMode for convenience
export type { ZoomMode } from "../../types";

/** Minimum / maximum zoom scale (10% to 500%). */
const MIN_ZOOM = 0.1;
const MAX_ZOOM = 5.0;
const ZOOM_STEP = 0.1;

interface LightboxModeContextType {
  isLightboxMode: boolean;
  photos: PhotoInfo[];
  currentIndex: number;
  zoomMode: ZoomMode;
  zoomScale: number;
  statusType: StatusType;

  enterLightbox: (photos: PhotoInfo[], startIndex: number) => void;
  exitLightbox: () => void;
  navigateLeft: () => void;
  navigateRight: () => void;
  toggleStar: () => Promise<void>;
  toggleReject: () => Promise<void>;
  setZoomMode: (mode: ZoomMode) => void;
  setZoomScale: (scale: number) => void;
}

const LightboxModeContext = createContext<LightboxModeContextType | null>(null);

export const LightboxModeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isLightboxMode, setIsLightboxMode] = useState(false);
  const [photos, setPhotos] = useState<PhotoInfo[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [zoomMode, setZoomModeState] = useState<ZoomMode>("fit");
  const [zoomScale, setZoomScaleState] = useState(1.0);
  const [statusType, setStatusType] = useState<StatusType>(null);

  const actionInFlightRef = useRef(false);

  /** Update a single photo in the snapshot (in-place mutation via setState). */
  const updatePhoto = useCallback((imageId: string, updates: Partial<PhotoInfo>) => {
    setPhotos((prev) =>
      prev.map((p) => (p.image_id === imageId ? { ...p, ...updates } : p)),
    );
  }, []);

  /** Enter lightbox with a snapshot of the current grid photos. */
  const enterLightbox = useCallback(
    (photoList: PhotoInfo[], startIndex: number) => {
      if (photoList.length === 0) return;
      const idx = Math.max(0, Math.min(startIndex, photoList.length - 1));
      setPhotos([...photoList]);
      setCurrentIndex(idx);
      setZoomModeState("fit");
      setZoomScaleState(1.0);
      setIsLightboxMode(true);
    },
    [],
  );

  /** Exit lightbox and clear all state. */
  const exitLightbox = useCallback(() => {
    actionInFlightRef.current = false;
    setIsLightboxMode(false);
    setPhotos([]);
    setCurrentIndex(0);
    setZoomModeState("fit");
    setZoomScaleState(1.0);
  }, []);

  /** Navigate to the previous photo. */
  const navigateLeft = useCallback(() => {
    setCurrentIndex((prev) => {
      if (prev <= 0) return prev;
      setZoomScaleState(1.0);
      return prev - 1;
    });
  }, []);

  /** Navigate to the next photo. */
  const navigateRight = useCallback(() => {
    setCurrentIndex((prev) => {
      if (prev >= photos.length - 1) return prev;
      setZoomScaleState(1.0);
      return prev + 1;
    });
  }, [photos.length]);

  /** Set zoom mode (fit / zoom100). Reset scale when toggling. */
  const setZoomMode = useCallback((mode: ZoomMode) => {
    setZoomModeState(mode);
    if (mode === "zoom100") {
      setZoomScaleState(1.0);
    }
  }, []);

  /** Set zoom scale, clamped to [MIN_ZOOM, MAX_ZOOM]. */
  const setZoomScale = useCallback((scale: number) => {
    setZoomScaleState((prev) => {
      const next = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, scale));
      // Round to 1 decimal to avoid floating-point noise
      return Math.round(next * 10) / 10;
    });
  }, []);

  /** Toggle star on the current photo. */
  const toggleStar = useCallback(async () => {
    if (actionInFlightRef.current) return;
    const photo = photos[currentIndex];
    if (!photo) return;
    actionInFlightRef.current = true;

    try {
      const newRating = (photo.star_rating ?? 0) >= 1 ? 0 : 1;
      await updateStarRating(photo.image_id, newRating);
      updatePhoto(photo.image_id, { star_rating: newRating });
      setStatusType("star");
      setTimeout(() => setStatusType(null), 500);
    } catch {
      // silently fail
    } finally {
      actionInFlightRef.current = false;
    }
  }, [photos, currentIndex, updatePhoto]);

  /** Toggle reject on the current photo. */
  const toggleReject = useCallback(async () => {
    if (actionInFlightRef.current) return;
    const photo = photos[currentIndex];
    if (!photo) return;
    actionInFlightRef.current = true;

    try {
      const newReject = (photo.is_rejected ?? 0) >= 1 ? 0 : 1;
      await updateRejectStatus(photo.image_id, newReject);
      updatePhoto(photo.image_id, { is_rejected: newReject });
      setStatusType("reject");
      setTimeout(() => setStatusType(null), 500);
    } catch {
      // silently fail
    } finally {
      actionInFlightRef.current = false;
    }
  }, [photos, currentIndex, updatePhoto]);

  return (
    <LightboxModeContext.Provider
      value={{
        isLightboxMode,
        photos,
        currentIndex,
        zoomMode,
        zoomScale,
        statusType,
        enterLightbox,
        exitLightbox,
        navigateLeft,
        navigateRight,
        toggleStar,
        toggleReject,
        setZoomMode,
        setZoomScale,
      }}
    >
      {children}
    </LightboxModeContext.Provider>
  );
};

/** Hook to consume lightbox state. Must be used inside LightboxModeProvider. */
export function useLightboxMode(): LightboxModeContextType {
  const ctx = useContext(LightboxModeContext);
  if (!ctx) {
    throw new Error("useLightboxMode must be used within LightboxModeProvider");
  }
  return ctx;
}
