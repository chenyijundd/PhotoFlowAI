/**
 * PhotoFlow AI - Compare Mode Context
 *
 * Manages the dual-photo compare workflow for duplicate groups.
 *
 * Cull Workflow features:
 *   - Smart progression: after starring or rejecting the active photo,
 *     auto-advance to the next pair in the duplicate group.
 *   - Auto exit: when the group has only 1 non-rejected photo left,
 *     automatically exit compare mode.
 *   - Compare keyboard takes priority over browse keyboard.
 *
 * Stability (Task 14):
 *   - Guards against rapid successive key presses
 *   - Handles active photo disappearing mid-operation
 *   - Handles duplicate group updates during compare
 *   - Safe handling of preload image failures (via ComparePage)
 */

import React, { createContext, useContext, useState, useCallback, useRef } from "react";
import type { PhotoInfo } from "../../types";
import { fetchPhotosByGroup, updateStarRating, updateRejectStatus } from "../api/photoApi";

export type StatusType = "star" | "reject" | null;

interface CompareModeContextType {
  isCompareMode: boolean;
  leftPhoto: PhotoInfo | null;
  rightPhoto: PhotoInfo | null;
  activeSide: "left" | "right";
  groupPhotos: PhotoInfo[];
  currentIndex: number;
  groupId: string | null;
  totalInGroup: number;
  loading: boolean;
  error: string | null;

  enterCompareMode: (photoId: string, groupId: string) => Promise<void>;
  exitCompareMode: () => void;
  navigateLeft: () => void;
  navigateRight: () => void;
  switchActiveSide: () => void;
  toggleStarActive: () => Promise<void>;
  toggleRejectActive: () => Promise<void>;
  onStatus: (type: StatusType) => void;
  setOnStatus: (fn: (type: StatusType) => void) => void;
}

const CompareModeContext = createContext<CompareModeContextType | null>(null);

export const CompareModeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isCompareMode, setIsCompareMode] = useState(false);
  const [leftPhoto, setLeftPhoto] = useState<PhotoInfo | null>(null);
  const [rightPhoto, setRightPhoto] = useState<PhotoInfo | null>(null);
  const [activeSide, setActiveSide] = useState<"left" | "right">("left");
  const [groupPhotos, setGroupPhotos] = useState<PhotoInfo[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [groupId, setGroupId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statusFn, setStatusFn] = useState<((type: StatusType) => void) | null>(null);

  // Guard against rapid successive actions
  const actionInFlightRef = useRef(false);

  const setOnStatus = useCallback((fn: (type: StatusType) => void) => {
    setStatusFn(() => fn);
  }, []);

  const onStatus = useCallback((type: StatusType) => {
    statusFn?.(type);
  }, [statusFn]);

  const updatePhotoInState = useCallback(
    (imageId: string, updates: Partial<PhotoInfo>) => {
      setGroupPhotos((prev) =>
        prev.map((p) => (p.image_id === imageId ? { ...p, ...updates } : p)),
      );
      setLeftPhoto((prev) =>
        prev?.image_id === imageId ? { ...prev, ...updates } : prev,
      );
      setRightPhoto((prev) =>
        prev?.image_id === imageId ? { ...prev, ...updates } : prev,
      );
    },
    [],
  );

  const setPair = useCallback((photos: PhotoInfo[], idx: number) => {
    setCurrentIndex(idx);
    setLeftPhoto(photos[idx] || null);
    setRightPhoto(photos.length > idx + 1 ? photos[idx + 1] : null);
  }, []);

  const exitCompareMode = useCallback(() => {
    actionInFlightRef.current = false;
    setIsCompareMode(false);
    setLeftPhoto(null);
    setRightPhoto(null);
    setGroupPhotos([]);
    setCurrentIndex(0);
    setGroupId(null);
    setActiveSide("left");
    setError(null);
  }, []);

  /**
   * After a star or reject action, check if we should advance the pair
   * or auto-exit. Receives the fully-updated photos array (already
   * reflecting the star/reject change).
   */
  const advanceAfterAction = useCallback(
    (photos: PhotoInfo[], currentIdx: number) => {
      // Validate current state — active photo may have been removed
      const validPhotos = photos.filter((p) => p && p.image_id);
      if (validPhotos.length === 0) {
        exitCompareMode();
        return;
      }

      // Count non-rejected photos
      const nonRejected = validPhotos.filter((p) => (p.is_rejected ?? 0) === 0);
      if (nonRejected.length < 2) {
        exitCompareMode();
        return;
      }

      // Try advancing to next pair
      const newIdx = Math.min(validPhotos.length - 2, currentIdx + 1);

      // Check if the new pair has both photos non-rejected
      if (newIdx !== currentIdx && newIdx >= 0) {
        const l = validPhotos[newIdx];
        const r = newIdx + 1 < validPhotos.length ? validPhotos[newIdx + 1] : null;
        if (l && (l.is_rejected ?? 0) === 0 && r && (r.is_rejected ?? 0) === 0) {
          setPair(validPhotos, newIdx);
          setActiveSide("left");
          return;
        }
      }

      // Fallback: find any valid pair with both non-rejected
      for (let i = 0; i <= validPhotos.length - 2; i++) {
        const l = validPhotos[i];
        const r = validPhotos[i + 1];
        if (l && (l.is_rejected ?? 0) === 0 && r && (r.is_rejected ?? 0) === 0) {
          setPair(validPhotos, i);
          setActiveSide("left");
          return;
        }
      }

      // No valid pair found — auto exit
      exitCompareMode();
    },
    [setPair, exitCompareMode],
  );

  const enterCompareMode = useCallback(
    async (photoId: string, gId: string) => {
      setIsCompareMode(true);
      setLoading(true);
      setError(null);
      setActiveSide("left");
      try {
        const response = await fetchPhotosByGroup(gId);
        const photos = response.photos;
        if (photos.length === 0) {
          setError("未找到该组的照片");
          setIsCompareMode(false);
          return;
        }
        let idx = photos.findIndex((p) => p.image_id === photoId);
        if (idx < 0) idx = 0;
        if (idx >= photos.length - 1 && photos.length >= 2) {
          idx = photos.length - 2;
        }
        if (photos.length === 1) {
          idx = 0;
        }
        setGroupPhotos(photos);
        setGroupId(gId);
        setPair(photos, idx);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "加载失败";
        setError(msg);
        setIsCompareMode(false);
      } finally {
        setLoading(false);
      }
    },
    [setPair],
  );

  const navigateLeft = useCallback(() => {
    if (actionInFlightRef.current) return;
    const newIdx = Math.max(0, currentIndex - 1);
    if (newIdx !== currentIndex) {
      setPair(groupPhotos, newIdx);
    }
  }, [currentIndex, groupPhotos, setPair]);

  const navigateRight = useCallback(() => {
    if (actionInFlightRef.current) return;
    const newIdx = Math.min(groupPhotos.length - 2, currentIndex + 1);
    if (newIdx !== currentIndex && newIdx >= 0) {
      setPair(groupPhotos, newIdx);
    }
  }, [currentIndex, groupPhotos, setPair]);

  const switchActiveSide = useCallback(() => {
    // Only switch if the other side has a photo
    setActiveSide((prev) => {
      const target = prev === "left" ? "right" : "left";
      if (target === "right" && !rightPhoto) return prev;
      if (target === "left" && !leftPhoto) return prev;
      return target;
    });
  }, [leftPhoto, rightPhoto]);

  const toggleStarActive = useCallback(async () => {
    if (actionInFlightRef.current) return;
    actionInFlightRef.current = true;

    try {
      const target = activeSide === "left" ? leftPhoto : rightPhoto;
      if (!target) {
        actionInFlightRef.current = false;
        return;
      }
      const newRating = (target.star_rating ?? 0) >= 1 ? 0 : 1;
      try {
        await updateStarRating(target.image_id, newRating);

        // Compute the updated photos array for advance logic
        const updatedPhotos = groupPhotos.map((p) =>
          p.image_id === target.image_id ? { ...p, star_rating: newRating } : p,
        );

        updatePhotoInState(target.image_id, { star_rating: newRating });
        onStatus("star");

        // Auto-advance when starring (not un-starring)
        if (newRating >= 1) {
          advanceAfterAction(updatedPhotos, currentIndex);
        }
      } catch {
        // silently fail — but still release the guard
      }
    } finally {
      actionInFlightRef.current = false;
    }
  }, [activeSide, leftPhoto, rightPhoto, groupPhotos, currentIndex, updatePhotoInState, advanceAfterAction, onStatus]);

  const toggleRejectActive = useCallback(async () => {
    if (actionInFlightRef.current) return;
    actionInFlightRef.current = true;

    try {
      const target = activeSide === "left" ? leftPhoto : rightPhoto;
      if (!target) {
        actionInFlightRef.current = false;
        return;
      }
      const newReject = (target.is_rejected ?? 0) >= 1 ? 0 : 1;
      try {
        await updateRejectStatus(target.image_id, newReject);

        // Compute the updated photos array for advance logic
        const updatedPhotos = groupPhotos.map((p) =>
          p.image_id === target.image_id ? { ...p, is_rejected: newReject } : p,
        );

        updatePhotoInState(target.image_id, { is_rejected: newReject });
        onStatus("reject");

        // Auto-advance when rejecting (not un-rejecting)
        if (newReject >= 1) {
          advanceAfterAction(updatedPhotos, currentIndex);
        }
      } catch {
        // silently fail — but still release the guard
      }
    } finally {
      actionInFlightRef.current = false;
    }
  }, [activeSide, leftPhoto, rightPhoto, groupPhotos, currentIndex, updatePhotoInState, advanceAfterAction, onStatus]);

  const totalInGroup = groupPhotos.length;

  return (
    <CompareModeContext.Provider
      value={{
        isCompareMode,
        leftPhoto,
        rightPhoto,
        activeSide,
        groupPhotos,
        currentIndex,
        groupId,
        totalInGroup,
        loading,
        error,
        enterCompareMode,
        exitCompareMode,
        navigateLeft,
        navigateRight,
        switchActiveSide,
        toggleStarActive,
        toggleRejectActive,
        onStatus,
        setOnStatus,
      }}
    >
      {children}
    </CompareModeContext.Provider>
  );
};

export function useCompareMode(): CompareModeContextType {
  const ctx = useContext(CompareModeContext);
  if (!ctx) {
    throw new Error("useCompareMode must be used within CompareModeProvider");
  }
  return ctx;
}
