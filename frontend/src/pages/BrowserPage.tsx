import React, { useState, useCallback, useEffect, useRef, useMemo } from "react";
import ImageGrid from "../components/ImageGrid";
import DetailPanel from "../components/DetailPanel";
import ComparePage from "../components/ComparePage";
import BurstCompareGrid from "../components/BurstCompareGrid";
import LightboxPage from "../components/LightboxPage";
import StatusOverlay from "../components/StatusOverlay";
import type { StatusType } from "../components/StatusOverlay";
import { usePhotos } from "../hooks/usePhotos";
import { usePhotoSelection } from "../context/PhotoSelectionContext";
import { useCompareMode } from "../context/CompareModeContext";
import { useBurstCompare } from "../context/BurstCompareContext";
import { useLightboxMode } from "../context/LightboxModeContext";
import { useKeyboardNavigation } from "../hooks/useKeyboardNavigation";
import { useKeyboardHandler, KEY_PRIORITY } from "../hooks/useKeyboardManager";
import { useImagePreloader } from "../hooks/useImagePreloader";
import { imagePreloader } from "../services/ImagePreloader";
import { updateStarRating, updateRejectStatus, fetchCounts, analyzeAll, analyzeProgress, cullAll, cullProgress, fetchAISummary, batchUpdate, connectAnalyzeStream, connectCullStream, cancelAnalyze, cancelCull } from "../api/photoApi";
import type { ImportResponse, PhotoFilterMode, AICategory, DetectionProgressResponse, CullProgressResponse, AISummaryResponse } from "../../types";
import type { GridHandle } from "../components/ImageGrid";
import ExportDialog from "../components/ExportDialog";
import AnalysisSummaryModal from "../components/AnalysisSummaryModal";
import { useUndoRedo } from "../context/UndoRedoContext";
import type { HistoryEntry } from "../context/UndoRedoContext";
import { useBatchSelection } from "../context/BatchSelectionContext";
import type { ExportMode } from "../../types";

/** Strip Electron IPC wrapper prefix from error messages.
 *  Electron serialises a thrown Error as:
 *    "Error invoking remote method '<channel>': Error: <actual message>"
 *  Both the IPC wrapper and the "Error: " prefix are noise to the user. */
function cleanIpcError(raw: string): string {
  return raw
    .replace(/^Error invoking remote method '[^']*':\s*/, "")
    .replace(/^Error:\s*/, "");
}

const BrowserPage: React.FC = () => {
  const [filterMode, setFilterMode] = useState<PhotoFilterMode>("all");
  const [starredCount, setStarredCount] = useState(0);

  // Export dialog state
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportMode, setExportMode] = useState<ExportMode>("picked");
  const [exportPhotoIds, setExportPhotoIds] = useState<string[] | undefined>(undefined);
  const [exportFilterMode, setExportFilterMode] = useState<string | undefined>(undefined);
  const [rejectedCount, setRejectedCount] = useState(0);
  const [unprocessedCount, setUnprocessedCount] = useState(0);
  const [allCount, setAllCount] = useState(0);

  // AI category filter (applied on top of filterMode)
  const [aiCategory, setAiCategory] = useState<AICategory>(null);
  const [blurCount, setBlurCount] = useState(0);
  const [dupCount, setDupCount] = useState(0);
  const [burstCount, setBurstCount] = useState(0);
  const [bestCount, setBestCount] = useState(0);
  const [eyeClosedCount, setEyeClosedCount] = useState(0);

  const {
    photos,
    total,
    loading,
    error,
    loadMore,
    refresh,
  } = usePhotos(filterMode, aiCategory);

  const { selectedId, selectPhoto, deselectPhoto } = usePhotoSelection();

  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState<string | null>(null);

  // Smart button state machine: 🔍智能分析 → ⟳分析中... → ⚡一键选片 → ⟳处理中... → ✔已完成
  type SmartButtonState = "idle" | "analyzing" | "cull_ready" | "culling" | "done";
  const [smartState, setSmartState] = useState<SmartButtonState>("idle");

  // Persists once AI analysis completes — keeps the AI category bar visible
  // even after smartState returns to "idle" (post-cull done timer).
  const [aiAnalysisDone, setAiAnalysisDone] = useState(false);

  // Detection progress state (shared for both blur and duplicate)
  const [detectPhase, setDetectPhase] = useState("");
  const [detectProgress, setDetectProgress] = useState(0);
  const [detectTotal, setDetectTotal] = useState(0);
  const [detectMsg, setDetectMsg] = useState<string | null>(null);
  const detectStreamRef = useRef<(() => void) | null>(null);  // SSE cleanup
  const analyzeTaskIdRef = useRef<string | null>(null);  // for cancel
  const doneTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Detail panel refresh trigger for star rating changes
  const [detailRefreshKey, setDetailRefreshKey] = useState(0);

  // Grid ref for auto-scroll
  const gridRef = useRef<GridHandle>(null);

  // Tracks whether modifications (star/reject) happened during Lightbox/Compare
  const dirtyRef = useRef(false);

  // AI summary modal state — shown after analysis completes
  const [showSummary, setShowSummary] = useState(false);
  const [aiSummary, setAiSummary] = useState<AISummaryResponse | null>(null);

  // Status overlay state
  const [statusOverlay, setStatusOverlay] = useState<StatusType>(null);
  const [statusMessage, setStatusMessage] = useState<string | undefined>(undefined);

  // Compare mode
  const {
    isCompareMode,
    enterCompareMode,
    exitCompareMode,
    setOnStatus,
    setDirtyRef: setCompareDirtyRef,
  } = useCompareMode();

  // Burst compare mode
  const {
    isBurstCompareMode,
    enterBurstCompareMode,
  } = useBurstCompare();

  // Lightbox mode
  const {
    isLightboxMode,
    enterLightbox,
    setDirtyRef: setLightboxDirtyRef,
  } = useLightboxMode();

  // Wire dirtyRef so contexts can mark when modifications happen
  useEffect(() => {
    setCompareDirtyRef(dirtyRef);
  }, [setCompareDirtyRef]);

  useEffect(() => {
    setLightboxDirtyRef(dirtyRef);
  }, [setLightboxDirtyRef]);

  // Register status overlay callback with compare mode context
  useEffect(() => {
    setOnStatus((type: StatusType) => {
      setStatusOverlay(type);
      setTimeout(() => setStatusOverlay(null), 500);
    });
  }, [setOnStatus]);

  // Cleanup SSE stream + done timer on unmount
  useEffect(() => {
    return () => {
      if (detectStreamRef.current) detectStreamRef.current();
      if (doneTimerRef.current) clearTimeout(doneTimerRef.current);
    };
  }, []);

  // Current selected photo object
  const selectedPhoto = useMemo(() => {
    if (!selectedId) return null;
    return photos.find((p) => p.image_id === selectedId) || null;
  }, [photos, selectedId]);

  // Current index of selected photo (for preloader range calculation)
  const selectedIndex = useMemo(() => {
    if (!selectedId) return -1;
    return photos.findIndex((p) => p.image_id === selectedId);
  }, [photos, selectedId]);

  // Approximate grid column count for preloader range calculation.
  // Uses the same formula as ImageGrid: colWidth=212, sidebar≈460px.
  const [gridColumnCount, setGridColumnCount] = useState(6);
  useEffect(() => {
    const update = () => {
      const gridWidth = window.innerWidth - 460;
      setGridColumnCount(Math.max(1, Math.floor(gridWidth / 212)));
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  // Smart image preloader: zero-latency photo review
  const { onNavigate } = useImagePreloader({
    photos,
    selectedIndex,
    columnCount: gridColumnCount,
    enabled: !isCompareMode && !isLightboxMode && !isBurstCompareMode,
  });

  // Fetch all filter counts (basic + AI category) in a single request.
  // Replaces 6 HTTP calls (1 basic + 5 AI category) with 1.
  const loadCounts = useCallback(async () => {
    try {
      const counts = await fetchCounts();
      setAllCount(counts.all);
      setStarredCount(counts.starred);
      setRejectedCount(counts.rejected);
      setUnprocessedCount(counts.unprocessed);
      setBlurCount(counts.blur_count);
      setEyeClosedCount(counts.closed_eye_count);
      setDupCount(counts.duplicate_count);
      setBurstCount(counts.burst_group_count);
      setBestCount(counts.best_count);
    } catch {
      // silently ignore
    }
  }, []);

  useEffect(() => {
    loadCounts();
  }, [loadCounts]);

  // ---- Undo / Redo ----
  const { recordAction, recordBatch, undo, redo, canUndo, canRedo, setOnChanged } = useUndoRedo();

  // ---- Batch Selection ----
  const { selectedIds, selectionCount, clearSelection, selectAll } = useBatchSelection();

  // After undo/redo, refresh grid and counts so the UI reflects the
  // restored state immediately.
  useEffect(() => {
    setOnChanged(() => {
      refresh();
      loadCounts();
    });
    return () => setOnChanged(null);
  }, [setOnChanged, refresh, loadCounts]);

  // On mount, detect if AI analysis was previously completed (across sessions).
  // Uses the merged /api/photos/counts to get all counts in one request.
  useEffect(() => {
    (async () => {
      try {
        const counts = await fetchCounts();
        const hasAIResults =
          counts.blur_count > 0 ||
          counts.closed_eye_count > 0 ||
          counts.duplicate_count > 0 ||
          counts.burst_group_count > 0 ||
          counts.best_count > 0;
        if (hasAIResults) {
          setAiAnalysisDone(true);
        }
        setBlurCount(counts.blur_count);
        setDupCount(counts.duplicate_count);
        setBurstCount(counts.burst_group_count);
        setBestCount(counts.best_count);
        setEyeClosedCount(counts.closed_eye_count);
      } catch {
        // Backend not ready or no AI results — bar stays hidden, which is correct
      }
    })();
  }, []);


  /** Fetch AI category counts after analysis or cull step completes. */
  const fetchAICounts = useCallback(async () => {
    try {
      const counts = await fetchCounts();
      setBlurCount(counts.blur_count);
      setDupCount(counts.duplicate_count);
      setBurstCount(counts.burst_group_count);
      setBestCount(counts.best_count);
      setEyeClosedCount(counts.closed_eye_count);
    } catch {
      // silently ignore
    }
  }, []);

  /** Pick the next photo after a star/reject action. Always advances forward. */
  const getNextIdAfterAction = useCallback(
    (imageId: string) => {
      const idx = photos.findIndex((p) => p.image_id === imageId);
      if (idx < 0) return null;
      // Try next photo, fall back to previous if at the end
      if (idx < photos.length - 1) return photos[idx + 1].image_id;
      if (idx > 0) return photos[idx - 1].image_id;
      return null;
    },
    [photos],
  );

  // Star toggle handler
  const handleToggleStar = useCallback(async (imageId: string, currentRating: number) => {
    const newRating = currentRating >= 1 ? 0 : 1;
    // Capture state BEFORE mutation for undo history
    const photoBefore = photos.find((p) => p.image_id === imageId);
    const starBefore = currentRating;
    const rejectBefore = photoBefore?.is_rejected ?? 0;
    // Starring to 1 auto-clears reject
    const starAfter = newRating;
    const rejectAfter = newRating === 1 ? 0 : rejectBefore;
    const fileName = photoBefore?.file_name || imageId;

    try {
      await updateStarRating(imageId, newRating);
      setDetailRefreshKey((k) => k + 1);
      // Starring auto-clears reject, so all three counts may change
      loadCounts();

      // Record for undo
      recordAction({
        image_id: imageId,
        star_before: starBefore,
        star_after: starAfter,
        reject_before: rejectBefore,
        reject_after: rejectAfter,
        description: newRating === 1
          ? `加星 ${fileName}`
          : `取消加星 ${fileName}`,
      });

      // Show status overlay
      setStatusOverlay("star");
      setTimeout(() => setStatusOverlay(null), 500);

      // Pre-compute next photo before refresh
      const nextId = getNextIdAfterAction(imageId);

      await refresh();

      // Auto-advance to next photo
      if (nextId) {
        selectPhoto(nextId);
      }
    } catch (err) {
      console.error("Failed to update star rating:", err);
    }
  }, [refresh, getNextIdAfterAction, selectPhoto, loadCounts, recordAction, photos]);

  // Reject toggle handler
  const handleToggleReject = useCallback(async (imageId: string, currentReject: number) => {
    const newReject = currentReject >= 1 ? 0 : 1;
    // Capture state BEFORE mutation for undo history
    const photoBefore = photos.find((p) => p.image_id === imageId);
    const starBefore = photoBefore?.star_rating ?? 0;
    const rejectBefore = currentReject;
    // Rejecting to 1 auto-clears star
    const rejectAfter = newReject;
    const starAfter = newReject === 1 ? 0 : starBefore;
    const fileName = photoBefore?.file_name || imageId;

    try {
      await updateRejectStatus(imageId, newReject);
      setDetailRefreshKey((k) => k + 1);
      // Rejecting auto-clears star, so all three counts may change
      loadCounts();

      // Record for undo
      recordAction({
        image_id: imageId,
        star_before: starBefore,
        star_after: starAfter,
        reject_before: rejectBefore,
        reject_after: rejectAfter,
        description: newReject === 1
          ? `废片 ${fileName}`
          : `取消废片 ${fileName}`,
      });

      // Show status overlay
      setStatusOverlay("reject");
      setTimeout(() => setStatusOverlay(null), 500);

      // Pre-compute next photo before refresh
      const nextId = getNextIdAfterAction(imageId);

      await refresh();

      // Auto-advance to next photo
      if (nextId) {
        selectPhoto(nextId);
      }
    } catch (err) {
      console.error("Failed to update reject status:", err);
    }
  }, [refresh, getNextIdAfterAction, selectPhoto, loadCounts, recordAction, photos]);

  // ---- Batch star / reject handlers ----

  const handleBatchStar = useCallback(async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    // Collect history entries for undo BEFORE mutation
    const entries: HistoryEntry[] = [];
    for (const id of ids) {
      const p = photos.find((ph) => ph.image_id === id);
      if (!p) continue;
      const starBefore = p.star_rating ?? 0;
      const rejectBefore = p.is_rejected ?? 0;
      const starAfter = 1;
      const rejectAfter = 0; // starring clears reject
      entries.push({
        image_id: id,
        star_before: starBefore,
        star_after: starAfter,
        reject_before: rejectBefore,
        reject_after: rejectAfter,
        description: `加星 ${p.file_name}`,
      });
    }

    try {
      await batchUpdate({ photo_ids: ids, star_rating: 1 });
      recordBatch(entries, `批量加星 ${ids.length} 张`);
      clearSelection();
      refresh();
      loadCounts();
      setStatusOverlay("star");
      setTimeout(() => setStatusOverlay(null), 500);
    } catch (err) {
      console.error("Batch star failed:", err);
    }
  }, [selectedIds, photos, recordBatch, clearSelection, refresh, loadCounts]);

  const handleBatchReject = useCallback(async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    const entries: HistoryEntry[] = [];
    for (const id of ids) {
      const p = photos.find((ph) => ph.image_id === id);
      if (!p) continue;
      const starBefore = p.star_rating ?? 0;
      const rejectBefore = p.is_rejected ?? 0;
      const rejectAfter = 1;
      const starAfter = 0; // rejecting clears star
      entries.push({
        image_id: id,
        star_before: starBefore,
        star_after: starAfter,
        reject_before: rejectBefore,
        reject_after: rejectAfter,
        description: `废片 ${p.file_name}`,
      });
    }

    try {
      await batchUpdate({ photo_ids: ids, is_rejected: 1 });
      recordBatch(entries, `批量废片 ${ids.length} 张`);
      clearSelection();
      refresh();
      loadCounts();
      setStatusOverlay("reject");
      setTimeout(() => setStatusOverlay(null), 500);
    } catch (err) {
      console.error("Batch reject failed:", err);
    }
  }, [selectedIds, photos, recordBatch, clearSelection, refresh, loadCounts]);

  // Ctrl+A — select all visible photos
  const handleCtrlA = useCallback(
    (e: KeyboardEvent): boolean => {
      if (!(e.ctrlKey || e.metaKey)) return false;
      if (e.key !== "a" && e.key !== "A") return false;
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;
      e.preventDefault();
      selectAll(photos.map((p) => p.image_id));
      return true;
    },
    [photos, selectAll],
  );

  useKeyboardHandler("ctrl-a", handleCtrlA, KEY_PRIORITY.APP, true);

  // Per-tab selection memory: each (filterMode × aiCategory) combination
  // remembers its last-selected photo.  Key format: "filterMode:aiCategory"
  // (aiCategory defaults to "default" when null).
  const lastSelPerTab = useRef<Record<string, string | null>>({});

  const getTabKey = useCallback(
    (fm: PhotoFilterMode, ac: AICategory) => `${fm}:${ac ?? "default"}`,
    [],
  );

  // Persist selectedId to the current (filterMode, aiCategory) combo.
  // Only depends on selectedId — tab-switch effects should not trigger a persist,
  // otherwise the old-selectedId gets saved under the new tab's key, overwriting
  // the memory we are about to restore.
  useEffect(() => {
    if (selectedId) {
      lastSelPerTab.current[getTabKey(filterMode, aiCategory)] = selectedId;
    }
  }, [selectedId, getTabKey]);

  // When a tab finishes loading and is truly empty, clear the detail panel.
  // This is a simple standalone effect — independent of the tab-switch
  // restoration logic below, to avoid subtle interaction bugs.
  useEffect(() => {
    if (!loading && photos.length === 0 && selectedId !== null) {
      deselectPhoto();
    }
  }, [photos, loading, selectedId, deselectPhoto]);

  // When filterMode or aiCategory switches, restore the saved selection
  // for the new tab.  We guard against usePhotos' reset cycle with
  // sawEmptyRef — only act after observing the empty-array reset.
  const prevTabKeyRef = useRef<string>("");
  const pendingTabKeyRef = useRef<string | null>(null);
  const sawEmptyRef = useRef(false);
  useEffect(() => {
    const currentKey = getTabKey(filterMode, aiCategory);
    if (prevTabKeyRef.current !== currentKey) {
      pendingTabKeyRef.current = currentKey;
      prevTabKeyRef.current = currentKey;
      sawEmptyRef.current = false;
    }
    // Confirm usePhotos has finished its reset (photos went from old → [])
    if (photos.length === 0 && pendingTabKeyRef.current === currentKey) {
      sawEmptyRef.current = true;
    }
    // Only act after the empty-array reset has been observed AND photos loaded
    if (pendingTabKeyRef.current === currentKey && photos.length > 0 && sawEmptyRef.current) {
      pendingTabKeyRef.current = null;
      const saved = lastSelPerTab.current[currentKey];
      if (saved && photos.some(p => p.image_id === saved)) {
        selectPhoto(saved);
      } else {
        selectPhoto(photos[0].image_id);
      }
    }
  }, [photos, filterMode, aiCategory, selectPhoto, getTabKey]);

  // Scroll-to-index for keyboard nav

  // Scroll-to-index for keyboard nav
  const scrollToIndex = useCallback((index: number) => {
    gridRef.current?.scrollToIndex(index);
  }, []);

  // Keyboard navigation hook (uses centralized keyboard manager internally)
  useKeyboardNavigation({
    photos,
    selectedId,
    selectPhoto,
    onToggleStar: handleToggleStar,
    onToggleReject: handleToggleReject,
    scrollToIndex,
    active: !isCompareMode && !isBurstCompareMode,
    filterMode,
    aiCategory,
    onNavigate,
  });

  // 'C' key — enter compare mode (via centralized keyboard manager)
  // Using refs to avoid stale closures
  const selectedPhotoRef = useRef(selectedPhoto);
  selectedPhotoRef.current = selectedPhoto;
  const enterCompareModeRef = useRef(enterCompareMode);
  enterCompareModeRef.current = enterCompareMode;
  const isCompareModeRef = useRef(isCompareMode);
  isCompareModeRef.current = isCompareMode;
  const enterBurstCompareModeRef = useRef(enterBurstCompareMode);
  enterBurstCompareModeRef.current = enterBurstCompareMode;
  const isBurstCompareModeRef = useRef(isBurstCompareMode);
  isBurstCompareModeRef.current = isBurstCompareMode;
  const setStatusOverlayRef = useRef(setStatusOverlay);
  setStatusOverlayRef.current = setStatusOverlay;

  const handleCKey = useCallback(
    (e: KeyboardEvent): boolean => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;

      if (e.key === "c" || e.key === "C") {
        const photo = selectedPhotoRef.current;
        if (photo?.duplicate_group && !isCompareModeRef.current) {
          e.preventDefault();
          enterCompareModeRef.current(photo.image_id, photo.duplicate_group);
          return true;
        }
        // Photo has no duplicate_group — show hint
        if (photo && !photo.duplicate_group && !isCompareModeRef.current) {
          e.preventDefault();
          setStatusOverlayRef.current("hint");
          setTimeout(() => setStatusOverlayRef.current(null), 800);
          return true;
        }
      }
      return false;
    },
    [],
  );

  useKeyboardHandler("app-compare-trigger", handleCKey, KEY_PRIORITY.APP, !isCompareMode && !isBurstCompareMode);

  // 'B' key — enter burst compare mode (same pattern as C key for duplicate compare)
  const handleBKey = useCallback(
    (e: KeyboardEvent): boolean => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;

      if (e.key === "b" || e.key === "B") {
        const photo = selectedPhotoRef.current;
        if (photo?.burst_group && !isBurstCompareModeRef.current && !isCompareModeRef.current) {
          e.preventDefault();
          enterBurstCompareModeRef.current(photo.burst_group);
          return true;
        }
        // Photo has no burst_group — show hint
        if (photo && !photo.burst_group && !isBurstCompareModeRef.current && !isCompareModeRef.current) {
          e.preventDefault();
          setStatusOverlayRef.current("hint");
          setTimeout(() => setStatusOverlayRef.current(null), 800);
          return true;
        }
      }
      return false;
    },
    [],
  );

  useKeyboardHandler("app-burst-compare-trigger", handleBKey, KEY_PRIORITY.APP, !isBurstCompareMode && !isCompareMode);

  // 'Enter' key — enter Lightbox mode
  const enterLightboxRef = useRef(enterLightbox);
  enterLightboxRef.current = enterLightbox;
  const isLightboxModeRef = useRef(isLightboxMode);
  isLightboxModeRef.current = isLightboxMode;
  const photosRef = useRef(photos);
  photosRef.current = photos;

  const handleEnterKey = useCallback(
    (e: KeyboardEvent): boolean => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;

      if (e.key === "Enter") {
        const p = photosRef.current;
        const idx = p.findIndex((ph) => ph.image_id === selectedPhotoRef.current?.image_id);
        if (idx >= 0 && !isCompareModeRef.current && !isLightboxModeRef.current && !isBurstCompareModeRef.current) {
          e.preventDefault();
          enterLightboxRef.current(p, idx);
          return true;
        }
      }
      return false;
    },
    [],
  );

  useKeyboardHandler("enter-lightbox", handleEnterKey, KEY_PRIORITY.GRID, !isCompareMode && !isLightboxMode && !isBurstCompareMode);

  // Ctrl+Z / Ctrl+Y — undo / redo for star and reject operations
  const handleUndoRedoKey = useCallback(
    (e: KeyboardEvent): boolean => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;

      if (e.ctrlKey || e.metaKey) {
        if (e.key === "z" || e.key === "Z") {
          if (e.shiftKey) {
            // Ctrl+Shift+Z → Redo
            e.preventDefault();
            setStatusOverlay("redo");
            setStatusMessage("↪ 处理中...");
            redo().then((msg) => {
              if (msg) {
                setStatusOverlay("redo");
                setStatusMessage(undefined);
                setTimeout(() => setStatusOverlay(null), 800);
              } else {
                setStatusOverlay(null);
              }
            });
            return true;
          } else {
            // Ctrl+Z → Undo
            e.preventDefault();
            setStatusOverlay("undo");
            setStatusMessage("↩ 处理中...");
            undo().then((msg) => {
              if (msg) {
                setStatusOverlay("undo");
                setStatusMessage(undefined);
                setTimeout(() => setStatusOverlay(null), 800);
              } else {
                setStatusOverlay(null);
              }
            });
            return true;
          }
        }
        if (e.key === "y" || e.key === "Y") {
          // Ctrl+Y → Redo
          e.preventDefault();
          setStatusOverlay("redo");
          setStatusMessage("↪ 处理中...");
          redo().then((msg) => {
            if (msg) {
              setStatusOverlay("redo");
              setStatusMessage(undefined);
              setTimeout(() => setStatusOverlay(null), 800);
            } else {
              setStatusOverlay(null);
            }
          });
          return true;
        }
      }
      return false;
    },
    [undo, redo],
  );

  useKeyboardHandler("undo-redo", handleUndoRedoKey, KEY_PRIORITY.APP, true);

  // When exiting compare mode, only refresh if modifications happened
  const prevCompareRef = useRef(isCompareMode);
  useEffect(() => {
    if (prevCompareRef.current === true && isCompareMode === false) {
      if (dirtyRef.current) {
        refresh();
        loadCounts();
        dirtyRef.current = false;
      }
    }
    prevCompareRef.current = isCompareMode;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCompareMode]);

  // When exiting lightbox mode, only refresh if modifications happened
  const prevLightboxRef = useRef(isLightboxMode);
  useEffect(() => {
    if (prevLightboxRef.current === true && isLightboxMode === false) {
      if (dirtyRef.current) {
        refresh();
        loadCounts();
        dirtyRef.current = false;
      }
    }
    prevLightboxRef.current = isLightboxMode;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLightboxMode]);

  // When exiting burst compare mode, only refresh if modifications happened
  const prevBurstCompareRef = useRef(isBurstCompareMode);
  useEffect(() => {
    if (prevBurstCompareRef.current === true && isBurstCompareMode === false) {
      if (dirtyRef.current) {
        refresh();
        loadCounts();
        dirtyRef.current = false;
      }
    }
    prevBurstCompareRef.current = isBurstCompareMode;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isBurstCompareMode]);

  const handleImport = useCallback(async () => {
    if (!window.electronAPI) {
      setImportMsg("导入功能仅限桌面版使用");
      return;
    }

    const dir = await window.electronAPI.selectDirectory();
    if (!dir) return;

    setImporting(true);
    setImportMsg(null);
    try {
      const result: ImportResponse = await window.electronAPI.importPhotos(dir);
      if (result.total === 0 && !(result.removed ?? 0)) {
        setImportMsg("未找到图片文件（支持 JPG/PNG）");
      } else {
        const parts: string[] = [];
        if (result.imported > 0 || result.total > 0) {
          parts.push(`已扫描 ${result.total} 个文件`);
          if (result.imported > 0) parts.push(`新导入 ${result.imported} 张`);
          if (result.skipped > 0) parts.push(`跳过 ${result.skipped} 张已存在`);
        }
        if (result.removed && result.removed > 0) {
          parts.push(`移除 ${result.removed} 张已删文件`);
        }
        setImportMsg(parts.join("，"));
      }
      refresh();
      loadCounts();
      // Clear preloader cache — old cached images may be from a different project
      imagePreloader.clear();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "导入失败";
      setImportMsg(msg);
    } finally {
      setImporting(false);
    }
  }, [refresh, loadCounts]);

  // Apply cull results (no confirm — caller handles confirmation)
  const runCull = useCallback(async () => {
    // Close any existing SSE stream
    if (detectStreamRef.current) { detectStreamRef.current(); detectStreamRef.current = null; }

    setSmartState("culling");
    setDetectMsg(null);
    setDetectPhase("准备中...");
    setDetectProgress(0);
    setDetectTotal(0);
    try {
      const started = await cullAll();
      if (!started.task_id) { setSmartState("cull_ready"); return; }

      analyzeTaskIdRef.current = started.task_id;

      detectStreamRef.current = connectCullStream(started.task_id, {
        onStepStart: (data) => {
          setDetectPhase(data.phase);
          setDetectTotal(data.total);
          setDetectProgress(0);
        },
        onProgress: (data) => {
          setDetectPhase(data.phase);
          setDetectProgress(data.progress);
          setDetectTotal(data.total);
        },
        onStepComplete: (_data) => {
          // Refresh counts and grid incrementally
          fetchAICounts();
          refresh();
          loadCounts();
        },
        onTaskComplete: (data) => {
          detectStreamRef.current = null;
          analyzeTaskIdRef.current = null;
          const parts: string[] = [];
          if (data.total_accepted > 0) parts.push(`${data.total_accepted} 张加星`);
          if (data.total_rejected > 0) parts.push(`${data.total_rejected} 张废片`);
          if (data.blur_flagged > 0) parts.push(`${data.blur_flagged} 张模糊(仅标记)`);
          setDetectMsg(
            `一键选片完成：${parts.join("，")}` +
            (data.untouched > 0 ? `，${data.untouched} 张未处理（需手动判断）` : "")
          );
          setSmartState("done");
          refresh();
          loadCounts();
          fetchAICounts();
          doneTimerRef.current = setTimeout(() => {
            setSmartState("idle");
            setDetectMsg(null);
            setAiCategory(null);
          }, 2000);
        },
        onTaskCancelled: () => {
          detectStreamRef.current = null;
          analyzeTaskIdRef.current = null;
          setDetectMsg("选片已取消");
          setSmartState("cull_ready");
        },
        onTaskError: (error) => {
          detectStreamRef.current = null;
          analyzeTaskIdRef.current = null;
          setDetectMsg(cleanIpcError(error));
          setSmartState("cull_ready");
        },
      });
    } catch (err: unknown) {
      setSmartState("cull_ready");
      const raw = err instanceof Error ? err.message : "选片失败";
      setDetectMsg(cleanIpcError(raw));
    }
  }, [refresh, loadCounts, fetchAICounts]);


  // Combined AI analysis handler (incremental: unanalyzed only, unless overridden)
  const handleAnalyzeAll = useCallback(async () => {
    // Analysis scope is INDEPENDENT of the browsing filter tab.
    // Default: incremental — only unanalyzed (newly imported) photos.
    // "unprocessed": photos neither starred nor rejected.
    let scopeLabel: string;
    let analysisFilterMode: string | undefined;
    if (filterMode === "unprocessed") {
      scopeLabel = "待处理";
      analysisFilterMode = "unprocessed";
    } else {
      scopeLabel = "未分析（新导入）";
      analysisFilterMode = undefined;  // backend default: unanalyzed
    }

    if (!window.confirm(
      `AI 分析将依次执行以下 5 个步骤：\n\n· 闭眼检测（致命缺陷，自动判废）\n· 模糊检测（仅标记，不自动筛选）\n· 连拍分组（按时间聚类）\n· 重复检测（仅查剩余照片）\n· 最佳推荐\n\n每张照片只归入最先命中的分类。\n分析范围：${scopeLabel}照片\n分析过程中可继续浏览照片，单击取消按钮可中止。\n是否继续？`
    )) return;

    // Close any existing SSE stream
    if (detectStreamRef.current) { detectStreamRef.current(); detectStreamRef.current = null; }

    setSmartState("analyzing");
    setDetectMsg(null);
    setDetectPhase("Step 1/5: 闭眼检测");
    setDetectProgress(0);
    setDetectTotal(0);
    try {
      const started = await analyzeAll(undefined, analysisFilterMode);
      if (!started.task_id) { setSmartState("idle"); setAiCategory(null); return; }

      analyzeTaskIdRef.current = started.task_id;

      detectStreamRef.current = connectAnalyzeStream(started.task_id, {
        onStepStart: (data) => {
          setDetectPhase(data.phase);
          setDetectTotal(data.total);
          setDetectProgress(0);
        },
        onProgress: (data) => {
          setDetectPhase(data.phase);
          setDetectProgress(data.progress);
          setDetectTotal(data.total);
        },
        onStepComplete: (_data) => {
          // Show AI category bar as soon as first step completes
          setAiAnalysisDone(true);
          fetchAICounts();
          refresh();
          loadCounts();
        },
        onTaskComplete: (data) => {
          detectStreamRef.current = null;
          analyzeTaskIdRef.current = null;
          refresh();
          loadCounts();
          fetchAICounts();
          if (data.total_analyzed > 0) {
            setSmartState("cull_ready");
            setAiAnalysisDone(true);
            setDetectMsg("AI 分析完成，点击 ⚡ 一键选片 应用推荐");
            // Fetch summary & show analysis result modal
            (async () => {
              try {
                const s = await fetchAISummary();
                if (s.total_analyzed > 0) {
                  setAiSummary(s);
                  setShowSummary(true);
                }
              } catch {
                // Summary fetch failed — modal won't show, analysis bar is still visible
              }
            })();
          } else {
            // No photos were actually analysed (e.g. all already analysed,
            // or no eligible photos). Stay idle — don't offer cull.
            setSmartState("idle");
            setAiCategory(null);
            setDetectMsg("没有需要分析的新照片");
          }
        },
        onTaskCancelled: () => {
          detectStreamRef.current = null;
          analyzeTaskIdRef.current = null;
          setDetectMsg("AI 分析已取消");
          setSmartState("idle");
          setAiCategory(null);
        },
        onTaskError: (error) => {
          detectStreamRef.current = null;
          analyzeTaskIdRef.current = null;
          setSmartState("idle");
          setDetectMsg(cleanIpcError(error));
          setAiCategory(null);
        },
      });
    } catch (err: unknown) {
      setSmartState("idle");
      const raw = err instanceof Error ? err.message : "AI 分析失败";
      setDetectMsg(cleanIpcError(raw));
      setAiCategory(null);
    }
  }, [refresh, loadCounts, filterMode, fetchAICounts]);


  // Open export dialog
  const handleExport = useCallback(() => {
    const mode: ExportMode =
      filterMode === "starred" ? "picked" :
      filterMode === "rejected" ? "rejected" :
      "current_filter";
    setExportMode(mode);
    setExportPhotoIds(undefined);
    // Always pass the current browser filter so "当前筛选" works
    // even when the user switches modes inside the dialog.
    setExportFilterMode(filterMode);
    setShowExportDialog(true);
  }, [filterMode]);

  // Burst group action callback — refresh grid & counts after burst button clicks
  const handleBurstAction = useCallback(async () => {
    refresh();
    loadCounts();
  }, [refresh, loadCounts]);

  // 'E' key — open export dialog
  const handleEKey = useCallback(
    (e: KeyboardEvent): boolean => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;
      if (e.key === "e" || e.key === "E") {
        if (isCompareModeRef.current) return false; // Compare mode handles its own E
        e.preventDefault();
        // Determine export mode based on current filter
        const mode: ExportMode =
          filterMode === "starred" ? "picked" :
          filterMode === "rejected" ? "rejected" :
          "current_filter";
        setExportMode(mode);
        setExportPhotoIds(undefined);
        // Always pass current browser filter for "当前筛选" support
        setExportFilterMode(filterMode);
        setShowExportDialog(true);
        return true;
      }
      return false;
    },
    [filterMode, photos],
  );

  useKeyboardHandler("app-export", handleEKey, KEY_PRIORITY.APP, !showExportDialog);

  // Listen for menu "导入照片" command
  useEffect(() => {
    const unsubscribe = window.electronAPI?.onMenuImport(() => {
      handleImport();
    });
    return () => {
      unsubscribe?.();
    };
  }, [handleImport]);

  // ---- Burst Compare Mode takes over the entire page ----
  if (isBurstCompareMode) {
    return <BurstCompareGrid />;
  }

  // ---- Compare Mode takes over the entire page ----
  if (isCompareMode) {
    return <ComparePage />;
  }

  // ---- Lightbox Mode takes over the entire page ----
  if (isLightboxMode) {
    return <LightboxPage />;
  }

  if (error && photos.length === 0) {
    return (
      <div className="state-screen error-state">
        <div className="state-icon">⚠️</div>
        <h2>加载照片失败</h2>
        <p>{error}</p>
        <button className="btn-primary" onClick={refresh}>
          重试
        </button>
      </div>
    );
  }

  if (loading && photos.length === 0) {
    return (
      <div className="state-screen loading-state">
        <div className="spinner" />
        <p>正在加载照片...</p>
      </div>
    );
  }

  const hasMore = photos.length < total;

  return (
    <div className="browser-page">
      <StatusOverlay type={statusOverlay} message={statusMessage ?? (statusOverlay === "hint" ? "无重复组，无法对比" : undefined)} />

      <header className="browser-header">
        <h1 className="browser-title">PhotoFlow AI</h1>
        <div className="browser-header-center">
          <div className="filter-bar">
            <button
              className={`filter-btn${filterMode === "all" ? " filter-btn--active" : ""}`}
              onClick={() => { setFilterMode("all"); setAiCategory(null); }}
            >
              全部({allCount})
            </button>
            <button
              className={`filter-btn${filterMode === "starred" ? " filter-btn--active" : ""}`}
              onClick={() => { setFilterMode("starred"); setAiCategory(null); }}
            >
              已选({starredCount})
            </button>
            <button
              className={`filter-btn${filterMode === "unprocessed" ? " filter-btn--active" : ""}`}
              onClick={() => { setFilterMode("unprocessed"); setAiCategory(null); }}
            >
              待处理({unprocessedCount})
            </button>
            <button
              className={`filter-btn${filterMode === "rejected" ? " filter-btn--active" : ""}`}
              onClick={() => { setFilterMode("rejected"); setAiCategory(null); }}
            >
              废片({rejectedCount})
            </button>
          </div>
        </div>
        <div className="browser-header-right">
          <button
            className="btn-import"
            onClick={handleImport}
            disabled={importing}
          >
            {importing ? "正在导入..." : "📁 导入照片目录"}
          </button>
          <button
            className="btn-export"
            onClick={handleExport}
          >
            📤 导出
          </button>
          <button
            className={
              smartState === "cull_ready" || smartState === "culling" ? "btn-cull" :
              smartState === "done" ? "btn-done" :
              "btn-detect"
            }
            onClick={() => {
              if (smartState === "idle") handleAnalyzeAll();
              else if (smartState === "cull_ready") runCull();
              // analyzing / culling / done — no action
            }}
            disabled={
              smartState === "analyzing" ||
              smartState === "culling" ||
              (smartState === "idle" && (filterMode === "starred" || filterMode === "rejected"))
            }
            title={
              smartState === "idle" && (filterMode === "starred" || filterMode === "rejected")
                ? "AI 分析仅在「全部」或「待处理」下可用"
                : smartState === "cull_ready"
                  ? "根据 AI 分析结果自动加星 / 废片"
                  : ""
            }
          >
            {smartState === "analyzing" ? "⟳ 分析中..." :
             smartState === "cull_ready" ? "⚡ 一键选片" :
             smartState === "culling" ? "⟳ 处理中..." :
             smartState === "done" ? "✔ 已完成" :
             "🔍 智能分析"}
          </button>
        </div>
      </header>

      {/* Detection progress bar (below header) — cull_ready shows green completion bar */}
      {smartState === "cull_ready" ? (
        <div className="detect-progress detect-progress-ready">
          <span className="detect-progress-label">🤖 AI 分析完成，点击 ⚡ 一键选片 应用推荐</span>
          <div className="detect-progress-bar">
            <div className="detect-progress-fill detect-progress-fill--complete" style={{ width: "100%" }} />
          </div>
        </div>
      ) : smartState !== "idle" && smartState !== "done" && detectTotal > 0 && (
        <div className="detect-progress">
          <span className="detect-progress-label">{detectPhase}</span>
          <span className="detect-progress-nums">{detectProgress} / {detectTotal}</span>
          <div className="detect-progress-bar">
            <div
              className="detect-progress-fill"
              style={{ width: `${detectTotal > 0 ? Math.round(detectProgress / detectTotal * 100) : 0}%` }}
            />
          </div>
          <span className="detect-progress-pct">
            {detectTotal > 0 ? Math.round(detectProgress / detectTotal * 100) : 0}%
          </span>
          {analyzeTaskIdRef.current && (smartState === "analyzing" || smartState === "culling") && (
            <button
              className="btn-cancel-task"
              onClick={() => {
                const tid = analyzeTaskIdRef.current;
                if (tid) {
                  if (smartState === "analyzing") cancelAnalyze(tid).catch(() => {});
                  else cancelCull(tid).catch(() => {});
                }
              }}
              title="取消当前任务"
            >
              ✕ 取消
            </button>
          )}
        </div>
      )}

      {/* AI category filter bar — always visible, counts update as analysis runs */}
      <div className="ai-category-bar">
        <span className="ai-cat-label">🤖 基于全部照片</span>
        <span
          className={`ai-cat-chip${aiCategory === null ? " ai-cat-active" : ""}`}
          onClick={() => { setAiCategory(null); setFilterMode("all"); }}
        >
          全部
        </span>
        <span
          className={`ai-cat-chip${aiCategory === "closed_eye" ? " ai-cat-active" : ""} ai-cat-eye`}
          onClick={() => { setAiCategory("closed_eye"); setFilterMode("all"); }}
        >
          闭眼{eyeClosedCount > 0 ? ` (${eyeClosedCount})` : ""}
        </span>
        <span
          className={`ai-cat-chip${aiCategory === "blur" ? " ai-cat-active" : ""} ai-cat-blur`}
          onClick={() => { setAiCategory("blur"); setFilterMode("all"); }}
        >
          模糊{blurCount > 0 ? ` (${blurCount})` : ""}
        </span>
        <span
          className={`ai-cat-chip${aiCategory === "burst" ? " ai-cat-active" : ""} ai-cat-burst`}
          onClick={() => { setAiCategory("burst"); setFilterMode("all"); }}
        >
          连拍{burstCount > 0 ? ` (${burstCount})` : ""}
        </span>
        <span
          className={`ai-cat-chip${aiCategory === "duplicate" ? " ai-cat-active" : ""} ai-cat-dup`}
          onClick={() => { setAiCategory("duplicate"); setFilterMode("all"); }}
        >
          重复{dupCount > 0 ? ` (${dupCount})` : ""}
        </span>
        <span
          className={`ai-cat-chip${aiCategory === "best" ? " ai-cat-active" : ""} ai-cat-best`}
          onClick={() => { setAiCategory("best"); setFilterMode("all"); }}
        >
          最佳推荐{bestCount > 0 ? ` (${bestCount})` : ""}
        </span>
        <button
          className="ai-summary-reopen-btn"
          title="查看 AI 分析摘要"
          onClick={async () => {
            try {
              const s = await fetchAISummary();
              setAiSummary(s);
              setShowSummary(true);
            } catch { /* ignore */ }
          }}
        >
          📊
        </button>
      </div>

      <div className="browser-body">
        <div className="browser-grid-area">
          {(importMsg || detectMsg) && (
            <div className="import-status">
              {detectMsg || importMsg}
            </div>
          )}

          {/* Batch operation bar — shown when 2+ photos are selected */}
          {selectionCount >= 2 && (
            <div className="batch-bar">
              <span className="batch-bar-count">
                已选 <strong>{selectionCount}</strong> 张
              </span>
              <button className="batch-bar-btn batch-bar-btn--star" onClick={handleBatchStar}>
                ⭐ 全部加星
              </button>
              <button className="batch-bar-btn batch-bar-btn--reject" onClick={handleBatchReject}>
                🗑️ 全部废片
              </button>
              <button className="batch-bar-btn batch-bar-btn--cancel" onClick={clearSelection}>
                ✕ 取消选择
              </button>
            </div>
          )}

          {filterMode === "starred" && photos.length === 0 && !loading ? (
            <div className="grid-empty">
              <div className="empty-icon">⭐</div>
              <h3>暂无已选照片</h3>
              <p>按 Space 可标记照片</p>
            </div>
          ) : filterMode === "rejected" && photos.length === 0 && !loading ? (
            <div className="grid-empty">
              <div className="empty-icon">🗑️</div>
              <h3>暂无废片</h3>
              <p>按 D 可标记废片</p>
            </div>
          ) : filterMode === "unprocessed" && photos.length === 0 && !loading ? (
            allCount === 0 ? (
              <div className="grid-empty">
                <div className="empty-icon">📷</div>
                <h3>暂无照片</h3>
                <p>请先导入照片开始筛选</p>
              </div>
            ) : (
              <div className="grid-empty">
                <div className="empty-icon">📋</div>
                <h3>全部处理完成</h3>
                <p>所有照片已选或已废</p>
              </div>
            )
          ) : (
            <ImageGrid
              ref={gridRef}
              photos={photos}
              total={total}
              loading={loading}
              hasMore={hasMore}
              onLoadMore={loadMore}
            />
          )}
        </div>
        <DetailPanel
          imageId={selectedId}
          refreshKey={detailRefreshKey}
          onBurstAction={handleBurstAction}
        />
      </div>

      {/* AI Analysis Summary Modal — shown after analysis completes */}
      {showSummary && aiSummary && (
        <AnalysisSummaryModal
          summary={aiSummary}
          onCull={() => {
            setShowSummary(false);
            runCull();
          }}
          onClose={() => setShowSummary(false)}
        />
      )}

      {/* Export Dialog */}
      {showExportDialog && (
        <ExportDialog
          defaultMode={exportMode}
          photoIds={exportPhotoIds}
          filterMode={exportFilterMode}
          pickedCount={starredCount}
          rejectedCount={rejectedCount}
          allCount={allCount}
          onClose={() => setShowExportDialog(false)}
        />
      )}
    </div>
  );
};

export default BrowserPage;
