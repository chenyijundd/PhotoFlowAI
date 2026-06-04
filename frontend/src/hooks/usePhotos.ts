/**
 * PhotoFlow AI - usePhotos Hook
 *
 * Manages photo data fetching, loading, and error states.
 * Supports "all" and "starred" filter modes.
 */

import { useState, useEffect, useCallback } from "react";
import type { PhotoInfo, PhotoFilterMode, AICategory } from "../../types";
import { fetchPhotos, fetchStarredPhotos, fetchRejectedPhotos, fetchUnprocessedPhotos, fetchBlurPhotos, fetchDuplicatePhotos, fetchBurstPhotosList, fetchBestPhotosList, fetchClosedEyePhotos, fetchTrashedPhotos } from "../api/photoApi";

export interface UsePhotosResult {
  photos: PhotoInfo[];
  total: number;
  loading: boolean;
  error: string | null;
  loadMore: () => void;
  refresh: () => void;
}

const PAGE_SIZE = 100;

export function usePhotos(filterMode: PhotoFilterMode = "all", aiCategory: AICategory = null): UsePhotosResult {
  const [photos, setPhotos] = useState<PhotoInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback(async (
    currentOffset: number,
    append: boolean,
    currentFilter: PhotoFilterMode,
    currentCategory: AICategory,
  ) => {
    try {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(null);

      let data;
      if (currentCategory) {
        switch (currentCategory) {
          case "blur":
            data = await fetchBlurPhotos(PAGE_SIZE, currentOffset);
            break;
          case "duplicate":
            data = await fetchDuplicatePhotos(PAGE_SIZE, currentOffset);
            break;
          case "burst":
            data = await fetchBurstPhotosList(PAGE_SIZE, currentOffset);
            break;
          case "best":
            data = await fetchBestPhotosList(PAGE_SIZE, currentOffset);
            break;
          case "closed_eye":
            data = await fetchClosedEyePhotos(PAGE_SIZE, currentOffset);
            break;
          default:
            data = await fetchPhotos(PAGE_SIZE, currentOffset);
        }
      } else {
        data = currentFilter === "all"
          ? await fetchPhotos(PAGE_SIZE, currentOffset)
          : currentFilter === "starred"
            ? await fetchStarredPhotos(PAGE_SIZE, currentOffset)
            : currentFilter === "rejected"
              ? await fetchRejectedPhotos(PAGE_SIZE, currentOffset)
              : currentFilter === "trash"
                ? await fetchTrashedPhotos(PAGE_SIZE, currentOffset)
                : await fetchUnprocessedPhotos(PAGE_SIZE, currentOffset);
      }

      setTotal(data.total);

      if (append) {
        setPhotos((prev) => [...prev, ...data.photos]);
      } else {
        setPhotos(data.photos);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "加载照片失败";
      setError(message);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  // Reset and fetch when filterMode or aiCategory changes
  useEffect(() => {
    setOffset(0);
    setPhotos([]);
    fetchPage(0, false, filterMode, aiCategory);
  }, [filterMode, aiCategory, fetchPage]);

  const loadMore = useCallback(() => {
    const newOffset = offset + PAGE_SIZE;
    setOffset(newOffset);
    fetchPage(newOffset, true, filterMode, aiCategory);
  }, [offset, fetchPage, filterMode, aiCategory]);

  const refresh = useCallback(() => {
    setOffset(0);
    fetchPage(0, false, filterMode, aiCategory);
  }, [fetchPage, filterMode, aiCategory]);

  return {
    photos,
    total,
    loading,
    error,
    loadMore,
    refresh,
  };
}
