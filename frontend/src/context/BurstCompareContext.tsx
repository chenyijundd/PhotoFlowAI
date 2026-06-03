/**
 * PhotoFlow AI — Burst Compare Context
 *
 * Manages the multi-photo grid comparison mode for burst (连拍) groups.
 * Follows the same pattern as CompareModeContext (duplicate A/B compare).
 *
 * Entry points:
 *   - Keyboard shortcut B (when current photo belongs to a burst group)
 *   - 🔍 icon in BurstFilmstrip header bar
 *
 * Keyboard shortcuts while in burst compare mode:
 *   Space  toggle star on hovered photo
 *   D      toggle reject on hovered photo
 *   B      exit burst compare mode (return to browse)
 *   Esc    exit burst compare mode
 */

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
} from "react";
import type { PhotoInfo } from "../../types";
import {
  fetchBurstPhotos,
  updateStarRating,
  updateRejectStatus,
} from "../api/photoApi";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BurstCompareContextType {
  /** Whether the burst compare grid is currently shown. */
  isBurstCompareMode: boolean;

  /** All photos in the burst group. */
  burstPhotos: PhotoInfo[];

  /** The burst group ID. */
  burstGroupId: string | null;

  /** Total number of photos in the burst group. */
  totalInBurst: number;

  /** Loading state when fetching burst photos. */
  loading: boolean;

  /** Error message, if any. */
  error: string | null;

  /** Enter burst compare mode for the given burst group. */
  enterBurstCompareMode: (groupId: string) => Promise<void>;

  /** Exit burst compare mode. */
  exitBurstCompareMode: () => void;

  /** Toggle star on a specific photo (by image_id). Returns the updated rating. */
  toggleStar: (imageId: string) => Promise<number>;

  /** Toggle reject on a specific photo (by image_id). Returns the updated status. */
  toggleReject: (imageId: string) => Promise<number>;
}

const BurstCompareContext = createContext<BurstCompareContextType | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export const BurstCompareProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [isBurstCompareMode, setIsBurstCompareMode] = useState(false);
  const [burstPhotos, setBurstPhotos] = useState<PhotoInfo[]>([]);
  const [burstGroupId, setBurstGroupId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Guard against rapid successive actions
  const actionInFlightRef = useRef(false);

  const exitBurstCompareMode = useCallback(() => {
    actionInFlightRef.current = false;
    setIsBurstCompareMode(false);
    setBurstPhotos([]);
    setBurstGroupId(null);
    setError(null);
  }, []);

  const enterBurstCompareMode = useCallback(
    async (groupId: string) => {
      setIsBurstCompareMode(true);
      setLoading(true);
      setError(null);
      try {
        const response = await fetchBurstPhotos(groupId);
        const photos = response.photos;
        if (photos.length === 0) {
          setError("该连拍组没有照片");
          setIsBurstCompareMode(false);
          return;
        }
        setBurstPhotos(photos);
        setBurstGroupId(groupId);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "加载连拍组失败";
        setError(msg);
        setIsBurstCompareMode(false);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  /** Update a photo in the local state after star/reject change. */
  const updatePhotoInState = useCallback(
    (imageId: string, updates: Partial<PhotoInfo>) => {
      setBurstPhotos((prev) =>
        prev.map((p) => (p.image_id === imageId ? { ...p, ...updates } : p)),
      );
    },
    [],
  );

  const toggleStar = useCallback(
    async (imageId: string): Promise<number> => {
      if (actionInFlightRef.current) return -1;
      actionInFlightRef.current = true;

      try {
        const photo = burstPhotos.find((p) => p.image_id === imageId);
        if (!photo) return -1;
        const newRating = (photo.star_rating ?? 0) >= 1 ? 0 : 1;
        await updateStarRating(imageId, newRating);
        updatePhotoInState(imageId, { star_rating: newRating });
        return newRating;
      } catch {
        return -1;
      } finally {
        actionInFlightRef.current = false;
      }
    },
    [burstPhotos, updatePhotoInState],
  );

  const toggleReject = useCallback(
    async (imageId: string): Promise<number> => {
      if (actionInFlightRef.current) return -1;
      actionInFlightRef.current = true;

      try {
        const photo = burstPhotos.find((p) => p.image_id === imageId);
        if (!photo) return -1;
        const newReject = (photo.is_rejected ?? 0) >= 1 ? 0 : 1;
        await updateRejectStatus(imageId, newReject);
        updatePhotoInState(imageId, { is_rejected: newReject });
        return newReject;
      } catch {
        return -1;
      } finally {
        actionInFlightRef.current = false;
      }
    },
    [burstPhotos, updatePhotoInState],
  );

  const totalInBurst = burstPhotos.length;

  return (
    <BurstCompareContext.Provider
      value={{
        isBurstCompareMode,
        burstPhotos,
        burstGroupId,
        totalInBurst,
        loading,
        error,
        enterBurstCompareMode,
        exitBurstCompareMode,
        toggleStar,
        toggleReject,
      }}
    >
      {children}
    </BurstCompareContext.Provider>
  );
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useBurstCompare(): BurstCompareContextType {
  const ctx = useContext(BurstCompareContext);
  if (!ctx) {
    throw new Error(
      "useBurstCompare must be used within BurstCompareProvider",
    );
  }
  return ctx;
}
