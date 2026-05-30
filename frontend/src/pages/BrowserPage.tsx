import React, { useState, useCallback, useEffect, useRef, useMemo } from "react";
import ImageGrid from "../components/ImageGrid";
import DetailPanel from "../components/DetailPanel";
import ComparePage from "../components/ComparePage";
import LightboxPage from "../components/LightboxPage";
import StatusOverlay from "../components/StatusOverlay";
import type { StatusType } from "../components/StatusOverlay";
import { usePhotos } from "../hooks/usePhotos";
import { usePhotoSelection } from "../context/PhotoSelectionContext";
import { useCompareMode } from "../context/CompareModeContext";
import { useLightboxMode } from "../context/LightboxModeContext";
import { useKeyboardNavigation, findNextUnprocessed } from "../hooks/useKeyboardNavigation";
import { useKeyboardHandler, KEY_PRIORITY } from "../hooks/useKeyboardManager";
import { updateStarRating, fetchStarredCount, fetchBlurCount, runBlurDetection, blurProgress, blurCancel, updateRejectStatus, fetchRejectedCount, runDuplicateDetection, duplicateProgress, duplicateCancel, fetchDuplicateCount, generateSuggestions, fetchSuggestedCount } from "../api/photoApi";
import type { ImportResponse, PhotoFilterMode, GenerateSuggestionsResponse, DetectionProgressResponse } from "../../types";
import type { GridHandle } from "../components/ImageGrid";
import ExportDialog from "../components/ExportDialog";
import type { ExportMode } from "../../types";

const BrowserPage: React.FC = () => {
  const [filterMode, setFilterMode] = useState<PhotoFilterMode>("all");
  const [starredCount, setStarredCount] = useState(0);

  // Export dialog state
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportMode, setExportMode] = useState<ExportMode>("picked");
  const [exportPhotoIds, setExportPhotoIds] = useState<string[] | undefined>(undefined);
  const [rejectedCount, setRejectedCount] = useState(0);
  const [duplicateCount, setDuplicateCount] = useState(0);
  const [suggestedCount, setSuggestedCount] = useState(0);
  const [blurCount, setBlurCount] = useState(0);
  const [allCount, setAllCount] = useState(0);

  const {
    photos,
    total,
    loading,
    error,
    loadMore,
    refresh,
  } = usePhotos(filterMode);

  const { selectedId, selectPhoto } = usePhotoSelection();

  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState<string | null>(null);

  // Detection progress state (shared for both blur and duplicate)
  const [detectType, setDetectType] = useState<"blur" | "duplicate" | null>(null);
  const [detectPhase, setDetectPhase] = useState("");
  const [detectProgress, setDetectProgress] = useState(0);
  const [detectTotal, setDetectTotal] = useState(0);
  const [detectMsg, setDetectMsg] = useState<string | null>(null);
  const detectPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Detail panel refresh trigger for star rating changes
  const [detailRefreshKey, setDetailRefreshKey] = useState(0);

  // Grid ref for auto-scroll
  const gridRef = useRef<GridHandle>(null);

  // Status overlay state
  const [statusOverlay, setStatusOverlay] = useState<StatusType>(null);

  // Compare mode
  const {
    isCompareMode,
    enterCompareMode,
    exitCompareMode,
    setOnStatus,
  } = useCompareMode();

  // Lightbox mode
  const {
    isLightboxMode,
    enterLightbox,
  } = useLightboxMode();

  // Register status overlay callback with compare mode context
  useEffect(() => {
    setOnStatus((type: StatusType) => {
      setStatusOverlay(type);
      setTimeout(() => setStatusOverlay(null), 500);
    });
  }, [setOnStatus]);

  // Current selected photo object
  const selectedPhoto = useMemo(() => {
    if (!selectedId) return null;
    return photos.find((p) => p.image_id === selectedId) || null;
  }, [photos, selectedId]);

  // Fetch starred count on mount and after star toggles
  const loadStarredCount = useCallback(async () => {
    try {
      const res = await fetchStarredCount();
      setStarredCount(res.count);
    } catch {
      // silently ignore
    }
  }, []);

  // Fetch rejected count on mount and after reject toggles
  const loadRejectedCount = useCallback(async () => {
    try {
      const res = await fetchRejectedCount();
      setRejectedCount(res.count);
    } catch {
      // silently ignore
    }
  }, []);

  // Fetch duplicate count on mount and after detection
  const loadDuplicateCount = useCallback(async () => {
    try {
      const res = await fetchDuplicateCount();
      setDuplicateCount(res.count);
    } catch {
      // silently ignore
    }
  }, []);

  // Fetch suggested count
  const loadSuggestedCount = useCallback(async () => {
    try {
      const res = await fetchSuggestedCount();
      setSuggestedCount(res.count);
    } catch {
      // silently ignore
    }
  }, []);

  // Fetch blur count
  const loadBlurCount = useCallback(async () => {
    try {
      const res = await fetchBlurCount();
      setBlurCount(res.count);
    } catch {
      // silently ignore
    }
  }, []);

  useEffect(() => {
    loadStarredCount();
    loadRejectedCount();
    loadDuplicateCount();
    loadSuggestedCount();
    loadBlurCount();
  }, [loadStarredCount, loadRejectedCount, loadDuplicateCount, loadSuggestedCount, loadBlurCount]);

  /**
   * Compute the next photo to select after a star/reject action.
   * Prioritizes unprocessed photos (star_rating==0 && is_rejected==0).
   */
  const getNextIdAfterAction = useCallback(
    (imageId: string, newValue: number, isReject: boolean) => {
      const currentIdx = photos.findIndex((p) => p.image_id === imageId);
      if (currentIdx < 0) return null;

      // In starred mode, if we're un-starring, the photo will disappear — handle it
      if (filterMode === "starred" && !isReject && newValue === 0) {
        if (currentIdx < photos.length - 1) return photos[currentIdx + 1].image_id;
        if (currentIdx > 0) return photos[currentIdx - 1].image_id;
        return null;
      }

      // In reject mode, if we're un-rejecting, the photo will disappear — handle it
      if (filterMode === "rejected" && isReject && newValue === 0) {
        if (currentIdx < photos.length - 1) return photos[currentIdx + 1].image_id;
        if (currentIdx > 0) return photos[currentIdx - 1].image_id;
        return null;
      }

      // Auto-advance: find next unprocessed photo
      const nextIdx = findNextUnprocessed(photos, currentIdx);
      if (nextIdx >= 0) {
        return photos[nextIdx].image_id;
      }

      // If no unprocessed next, stay on current
      return null;
    },
    [photos, filterMode],
  );

  // Star toggle handler
  const handleToggleStar = useCallback(async (imageId: string, currentRating: number) => {
    const newRating = currentRating >= 1 ? 0 : 1;
    try {
      await updateStarRating(imageId, newRating);
      setDetailRefreshKey((k) => k + 1);
      loadStarredCount();

      // Show status overlay
      setStatusOverlay("star");
      setTimeout(() => setStatusOverlay(null), 500);

      // Pre-compute next photo before refresh
      const nextId = getNextIdAfterAction(imageId, newRating, false);

      await refresh();

      // Auto-advance to next photo
      if (nextId) {
        selectPhoto(nextId);
      }
    } catch (err) {
      console.error("Failed to update star rating:", err);
    }
  }, [refresh, getNextIdAfterAction, selectPhoto, loadStarredCount]);

  // Reject toggle handler
  const handleToggleReject = useCallback(async (imageId: string, currentReject: number) => {
    const newReject = currentReject >= 1 ? 0 : 1;
    try {
      await updateRejectStatus(imageId, newReject);
      setDetailRefreshKey((k) => k + 1);
      loadRejectedCount();

      // Show status overlay
      setStatusOverlay("reject");
      setTimeout(() => setStatusOverlay(null), 500);

      // Pre-compute next photo before refresh
      const nextId = getNextIdAfterAction(imageId, newReject, true);

      await refresh();

      // Auto-advance to next photo
      if (nextId) {
        selectPhoto(nextId);
      }
    } catch (err) {
      console.error("Failed to update reject status:", err);
    }
  }, [refresh, getNextIdAfterAction, selectPhoto, loadRejectedCount]);

  // Sync allCount when viewing all photos
  useEffect(() => {
    if (filterMode === "all" && total > 0) {
      setAllCount(total);
    }
  }, [filterMode, total]);

  // When filter switches, select first photo once data for the new mode arrives.
  const pendingFilterRef = useRef<PhotoFilterMode | null>(null);
  const prevFilterRef = useRef<PhotoFilterMode>(filterMode);
  useEffect(() => {
    if (prevFilterRef.current !== filterMode) {
      pendingFilterRef.current = filterMode;
      prevFilterRef.current = filterMode;
    }
    if (pendingFilterRef.current === filterMode && photos.length > 0) {
      pendingFilterRef.current = null;
      selectPhoto(photos[0].image_id);
    }
  }, [photos, filterMode, selectPhoto]);

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
    active: !isCompareMode,
    filterMode,
  });

  // 'C' key — enter compare mode (via centralized keyboard manager)
  // Using refs to avoid stale closures
  const selectedPhotoRef = useRef(selectedPhoto);
  selectedPhotoRef.current = selectedPhoto;
  const enterCompareModeRef = useRef(enterCompareMode);
  enterCompareModeRef.current = enterCompareMode;
  const isCompareModeRef = useRef(isCompareMode);
  isCompareModeRef.current = isCompareMode;

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
      }
      return false;
    },
    [],
  );

  useKeyboardHandler("app-compare-trigger", handleCKey, KEY_PRIORITY.APP, !isCompareMode);

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
        if (idx >= 0 && !isCompareModeRef.current && !isLightboxModeRef.current) {
          e.preventDefault();
          enterLightboxRef.current(p, idx);
          return true;
        }
      }
      return false;
    },
    [],
  );

  useKeyboardHandler("enter-lightbox", handleEnterKey, KEY_PRIORITY.GRID, !isCompareMode && !isLightboxMode);

  // When exiting compare mode, refresh grid and counts
  const prevCompareRef = useRef(isCompareMode);
  useEffect(() => {
    if (prevCompareRef.current === true && isCompareMode === false) {
      refresh();
      loadStarredCount();
      loadRejectedCount();
      loadDuplicateCount();
      loadSuggestedCount();
      loadBlurCount();
    }
    prevCompareRef.current = isCompareMode;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCompareMode]);

  // When exiting lightbox mode, refresh grid and counts
  const prevLightboxRef = useRef(isLightboxMode);
  useEffect(() => {
    if (prevLightboxRef.current === true && isLightboxMode === false) {
      refresh();
      loadStarredCount();
      loadRejectedCount();
      loadDuplicateCount();
      loadSuggestedCount();
      loadBlurCount();
    }
    prevLightboxRef.current = isLightboxMode;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLightboxMode]);

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
      if (result.total === 0) {
        setImportMsg("未找到图片文件（支持 JPG/PNG）");
      } else {
        setImportMsg(`已导入 ${result.imported} 张${result.skipped > 0 ? `（跳过 ${result.skipped} 张重复）` : ""}`);
      }
      refresh();
      loadStarredCount();
      loadBlurCount();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "导入失败";
      setImportMsg(msg);
    } finally {
      setImporting(false);
    }
  }, [refresh, loadStarredCount, loadBlurCount]);

  // Duplicate detection handler (async with progress polling)
  const handleDuplicateDetect = useCallback(async () => {
    setDetectType("duplicate");
    setDetectMsg(null);
    setDetectPhase("正在检测重复照片");
    setDetectProgress(0);
    setDetectTotal(0);
    try {
      const started = await runDuplicateDetection([]);
      if (!started.task_id) { setDetectType(null); return; }
      setDetectTotal(started.total);

      detectPollRef.current = setInterval(async () => {
        try {
          const p: DetectionProgressResponse = await duplicateProgress(started.task_id);
          setDetectPhase(p.phase);
          setDetectProgress(p.progress);
          if (p.status !== "running") {
            if (detectPollRef.current) clearInterval(detectPollRef.current);
            detectPollRef.current = null;
            setDetectType(null);
            if (p.status === "completed") {
              setDetectMsg(`重复检测完成：共 ${p.duplicate_groups} 组，${p.duplicate_count} 张重复照片`);
              loadDuplicateCount();
              generateSuggestions().then(() => loadSuggestedCount()).catch(() => {});
            } else if (p.status === "cancelled") {
              setDetectMsg("检测已取消");
            }
          }
        } catch { /* poll retry */ }
      }, 400);
    } catch (err: unknown) {
      setDetectType(null);
      setDetectMsg(err instanceof Error ? err.message : "重复检测失败");
    }
  }, [loadDuplicateCount, loadSuggestedCount]);

  // Blur detection handler (async with progress polling)
  const handleBlurDetect = useCallback(async () => {
    setDetectType("blur");
    setDetectMsg(null);
    setDetectPhase("正在检测模糊照片");
    setDetectProgress(0);
    setDetectTotal(0);
    try {
      const started = await runBlurDetection([]);
      if (!started.task_id) { setDetectType(null); return; }
      setDetectTotal(started.total);

      detectPollRef.current = setInterval(async () => {
        try {
          const p: DetectionProgressResponse = await blurProgress(started.task_id);
          setDetectPhase(p.phase);
          setDetectProgress(p.progress);
          if (p.status !== "running") {
            if (detectPollRef.current) clearInterval(detectPollRef.current);
            detectPollRef.current = null;
            setDetectType(null);
            if (p.status === "completed") {
              setDetectMsg(`检测完成：已处理 ${p.progress} 张，模糊 ${p.blurred} 张`);
              loadBlurCount();
              generateSuggestions().then(() => loadSuggestedCount()).catch(() => {});
            } else if (p.status === "cancelled") {
              setDetectMsg("检测已取消");
            }
          }
        } catch { /* poll retry */ }
      }, 400);
    } catch (err: unknown) {
      setDetectType(null);
      setDetectMsg(err instanceof Error ? err.message : "模糊检测失败");
    }
  }, [loadSuggestedCount, loadBlurCount]);

  // AI Suggestions generation handler
  const [generating, setGenerating] = useState(false);
  const handleGenerateSuggestions = useCallback(async () => {
    setGenerating(true);
    setDetectMsg(null);
    try {
      const result: GenerateSuggestionsResponse = await generateSuggestions();
      setDetectMsg(`AI 建议生成完成：${result.suggestions_generated} 条建议`);
      loadSuggestedCount();
      // Note: no refresh() — grid stays at current scroll position
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "AI 建议生成失败";
      setDetectMsg(msg);
    } finally {
      setGenerating(false);
    }
  }, [loadSuggestedCount]);

  // 'A' key — accept AI suggestion for current photo
  const acceptSuggestion = useCallback(async () => {
    const photo = selectedPhotoRef.current;
    if (!photo?.ai_suggestion) return;

    const suggestion = photo.ai_suggestion;
    try {
      if (suggestion === "POSSIBLE_BEST") {
        // Accept best → star it
        const currentStar = photo.star_rating ?? 0;
        if (currentStar < 1) {
          await updateStarRating(photo.image_id, 1);
          setDetailRefreshKey((k) => k + 1);
          loadStarredCount();
        }
      } else if (suggestion === "POSSIBLE_BLUR") {
        // Accept blur → reject it
        const currentReject = photo.is_rejected ?? 0;
        if (currentReject < 1) {
          await updateRejectStatus(photo.image_id, 1);
          setDetailRefreshKey((k) => k + 1);
          loadRejectedCount();
        }
      }
      // POSSIBLE_DUPLICATE: no action (informational only)

      // Show AI ACCEPTED overlay
      setStatusOverlay("ai_accept");
      setTimeout(() => setStatusOverlay(null), 500);

      // Regenerate suggestions (safety: invalidates stale suggestions)
      generateSuggestions().then(() => loadSuggestedCount()).catch(() => {});
      // Note: no refresh() — grid stays at current scroll position
    } catch (err) {
      console.error("Failed to accept AI suggestion:", err);
    }
  }, [loadStarredCount, loadRejectedCount, loadSuggestedCount]);

  // 'A' key handler via centralized keyboard manager
  const handleAKey = useCallback(
    (e: KeyboardEvent): boolean => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;
      if (e.key === "a" || e.key === "A") {
        const photo = selectedPhotoRef.current;
        if (photo?.ai_suggestion && !isCompareModeRef.current) {
          e.preventDefault();
          acceptSuggestion();
          return true;
        }
      }
      return false;
    },
    [acceptSuggestion],
  );

  useKeyboardHandler("app-accept-suggestion", handleAKey, KEY_PRIORITY.APP, !isCompareMode);

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
        setExportPhotoIds(mode === "current_filter" ? photos.map(p => p.image_id) : undefined);
        setShowExportDialog(true);
        return true;
      }
      return false;
    },
    [filterMode, photos],
  );

  useKeyboardHandler("app-export", handleEKey, KEY_PRIORITY.APP, !showExportDialog);

  // Export estimated count
  const exportEstimatedCount =
    exportMode === "picked" ? starredCount :
    exportMode === "rejected" ? rejectedCount :
    photos.length;

  // Listen for menu "导入照片" command
  useEffect(() => {
    const unsubscribe = window.electronAPI?.onMenuImport(() => {
      handleImport();
    });
    return () => {
      unsubscribe?.();
    };
  }, [handleImport]);

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
      <StatusOverlay type={statusOverlay} />

      <header className="browser-header">
        <h1 className="browser-title">PhotoFlow AI</h1>
        <div className="browser-header-center">
          <div className="filter-bar">
            <button
              className={`filter-btn${filterMode === "all" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("all")}
            >
              全部({allCount})
            </button>
            <button
              className={`filter-btn${filterMode === "starred" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("starred")}
            >
              已选({starredCount})
            </button>
            <button
              className={`filter-btn${filterMode === "blur" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("blur")}
            >
              模糊({blurCount})
            </button>
            <button
              className={`filter-btn${filterMode === "rejected" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("rejected")}
            >
              废片({rejectedCount})
            </button>
            <button
              className={`filter-btn${filterMode === "duplicate" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("duplicate")}
            >
              重复({duplicateCount})
            </button>
            <button
              className={`filter-btn${filterMode === "suggested" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("suggested")}
            >
              AI建议({suggestedCount})
            </button>
          </div>
        </div>
        <div className="browser-header-right">
          {/* Detection progress bar */}
          {detectType && detectTotal > 0 && (
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
            </div>
          )}

          <button
            className="btn-detect"
            onClick={handleGenerateSuggestions}
            disabled={generating || detectType !== null}
          >
            {generating ? "正在生成..." : "🤖 AI 建议"}
          </button>
          <button
            className="btn-detect"
            onClick={handleBlurDetect}
            disabled={detectType !== null}
          >
            {detectType === "blur" ? "检测中..." : "🔍 检测模糊照片"}
          </button>
          <button
            className="btn-detect"
            onClick={handleDuplicateDetect}
            disabled={detectType !== null}
          >
            {detectType === "duplicate" ? "检测中..." : "🔗 检测重复照片"}
          </button>
          <button
            className="btn-import"
            onClick={handleImport}
            disabled={importing || detectType !== null}
          >
            {importing ? "正在导入..." : "📁 导入照片目录"}
          </button>
        </div>
      </header>

      <div className="browser-body">
        <div className="browser-grid-area">
          {filterMode === "starred" && photos.length === 0 && !loading ? (
            <div className="grid-empty">
              <div className="empty-icon">⭐</div>
              <h3>暂无已选照片</h3>
              <p>按 Space 可标记照片</p>
            </div>
          ) : filterMode === "blur" && photos.length === 0 && !loading ? (
            <div className="grid-empty">
              <div className="empty-icon">🔍</div>
              <h3>暂无模糊照片</h3>
              <p>点击「检测模糊照片」开始分析</p>
            </div>
          ) : filterMode === "rejected" && photos.length === 0 && !loading ? (
            <div className="grid-empty">
              <div className="empty-icon">🗑️</div>
              <h3>暂无废片</h3>
              <p>按 X 可标记废片</p>
            </div>
          ) : filterMode === "duplicate" && photos.length === 0 && !loading ? (
            <div className="grid-empty">
              <div className="empty-icon">🔗</div>
              <h3>暂无重复照片</h3>
              <p>点击「检测重复照片」开始分析</p>
            </div>
          ) : filterMode === "suggested" && photos.length === 0 && !loading ? (
            <div className="grid-empty">
              <div className="empty-icon">🤖</div>
              <h3>暂无 AI 建议</h3>
              <p>点击「AI 建议」按钮生成建议</p>
            </div>
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
        />
      </div>

      {(importMsg || detectMsg) && (
        <div className="import-status">
          {detectMsg || importMsg}
        </div>
      )}

      {/* Export Dialog */}
      {showExportDialog && (
        <ExportDialog
          defaultMode={exportMode}
          photoIds={exportPhotoIds}
          estimatedCount={exportEstimatedCount}
          onClose={() => setShowExportDialog(false)}
        />
      )}
    </div>
  );
};

export default BrowserPage;
