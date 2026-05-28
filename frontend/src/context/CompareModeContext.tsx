/**
 * PhotoFlow AI - Compare Mode Context
 *
 * Manages the dual-photo compare workflow for duplicate groups.
 * Photographers can compare photos side-by-side, star, and reject.
 */

import React, { createContext, useContext, useState, useCallback } from "react";
import type { PhotoInfo } from "../../types";
import { fetchPhotosByGroup, updateStarRating, updateRejectStatus } from "../api/photoApi";

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
        // Ensure there's always a right photo if possible
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

  const exitCompareMode = useCallback(() => {
    setIsCompareMode(false);
    setLeftPhoto(null);
    setRightPhoto(null);
    setGroupPhotos([]);
    setCurrentIndex(0);
    setGroupId(null);
    setActiveSide("left");
    setError(null);
  }, []);

  const navigateLeft = useCallback(() => {
    const newIdx = Math.max(0, currentIndex - 1);
    if (newIdx !== currentIndex) {
      setPair(groupPhotos, newIdx);
    }
  }, [currentIndex, groupPhotos, setPair]);

  const navigateRight = useCallback(() => {
    const newIdx = Math.min(groupPhotos.length - 2, currentIndex + 1);
    if (newIdx !== currentIndex && newIdx >= 0) {
      setPair(groupPhotos, newIdx);
    }
  }, [currentIndex, groupPhotos, setPair]);

  const switchActiveSide = useCallback(() => {
    setActiveSide((prev) => (prev === "left" ? "right" : "left"));
  }, []);

  const toggleStarActive = useCallback(async () => {
    const target = activeSide === "left" ? leftPhoto : rightPhoto;
    if (!target) return;
    const newRating = (target.star_rating ?? 0) >= 1 ? 0 : 1;
    try {
      await updateStarRating(target.image_id, newRating);
      updatePhotoInState(target.image_id, { star_rating: newRating });
    } catch {
      // silently fail — don't crash compare mode
    }
  }, [activeSide, leftPhoto, rightPhoto, updatePhotoInState]);

  const toggleRejectActive = useCallback(async () => {
    const target = activeSide === "left" ? leftPhoto : rightPhoto;
    if (!target) return;
    const newReject = (target.is_rejected ?? 0) >= 1 ? 0 : 1;
    try {
      await updateRejectStatus(target.image_id, newReject);
      updatePhotoInState(target.image_id, { is_rejected: newReject });
    } catch {
      // silently fail
    }
  }, [activeSide, leftPhoto, rightPhoto, updatePhotoInState]);

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
