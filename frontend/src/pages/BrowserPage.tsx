import React, { useState, useCallback, useEffect, useRef, useMemo } from "react";
import ImageGrid from "../components/ImageGrid";
import DetailPanel from "../components/DetailPanel";
import ComparePage from "../components/ComparePage";
import StatusOverlay from "../components/StatusOverlay";
import type { StatusType } from "../components/StatusOverlay";
import { usePhotos } from "../hooks/usePhotos";
import { usePhotoSelection } from "../context/PhotoSelectionContext";
import { useCompareMode } from "../context/CompareModeContext";
import { useKeyboardNavigation, findNextUnprocessed } from "../hooks/useKeyboardNavigation";
import { useKeyboardHandler, KEY_PRIORITY } from "../hooks/useKeyboardManager";
import { updateStarRating, fetchStarredCount, runBlurDetection, updateRejectStatus, fetchRejectedCount, runDuplicateDetection, fetchDuplicateCount, generateSuggestions, fetchSuggestedCount } from "../api/photoApi";
import type { ImportResponse, PhotoFilterMode, BlurDetectResponse, DuplicateDetectResponse, GenerateSuggestionsResponse } from "../../types";
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

  // Blur detection state
  const [detecting, setDetecting] = useState(false);
  const [detectMsg, setDetectMsg] = useState<string | null>(null);

  // Duplicate detection state
  const [detectingDup, setDetectingDup] = useState(false);
  const [detectDupMsg, setDetectDupMsg] = useState<string | null>(null);

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

  useEffect(() => {
    loadStarredCount();
    loadRejectedCount();
    loadDuplicateCount();
    loadSuggestedCount();
  }, [loadStarredCount, loadRejectedCount, loadDuplicateCount, loadSuggestedCount]);

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
  const { zoomMode } = useKeyboardNavigation({
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

  // When exiting compare mode, refresh grid and counts
  const prevCompareRef = useRef(isCompareMode);
  useEffect(() => {
    if (prevCompareRef.current === true && isCompareMode === false) {
      refresh();
      loadStarredCount();
      loadRejectedCount();
      loadDuplicateCount();
      loadSuggestedCount();
    }
    prevCompareRef.current = isCompareMode;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCompareMode]);

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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "导入失败";
      setImportMsg(msg);
    } finally {
      setImporting(false);
    }
  }, [refresh, loadStarredCount]);

  // Duplicate detection handler
  const handleDuplicateDetect = useCallback(async () => {
    setDetectingDup(true);
    setDetectDupMsg(null);
    try {
      const result: DuplicateDetectResponse = await runDuplicateDetection([]);
      setDetectDupMsg(`重复检测完成：共 ${result.duplicate_groups} 组，${result.duplicates} 张重复照片`);
      loadDuplicateCount();
      // Suggestion safety: regenerate after duplicate detection
      generateSuggestions().then(() => loadSuggestedCount()).catch(() => {});
      // Note: no refresh() — grid stays at current scroll position
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "重复检测失败";
      setDetectDupMsg(msg);
    } finally {
      setDetectingDup(false);
    }
  }, [loadDuplicateCount, loadSuggestedCount]);

  // Blur detection handler
  const handleBlurDetect = useCallback(async () => {
    setDetecting(true);
    setDetectMsg(null);
    try {
      const result: BlurDetectResponse = await runBlurDetection([]);
      setDetectMsg(`检测完成：已处理 ${result.processed} 张，模糊 ${result.blurred} 张`);
      // Suggestion safety: regenerate after blur detection
      generateSuggestions().then(() => loadSuggestedCount()).catch(() => {});
      // Note: no refresh() — grid stays at current scroll position
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "模糊检测失败";
      setDetectMsg(msg);
    } finally {
      setDetecting(false);
    }
  }, [loadSuggestedCount]);

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
              全部照片
            </button>
            <button
              className={`filter-btn${filterMode === "starred" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("starred")}
            >
              已选照片
            </button>
            <button
              className={`filter-btn${filterMode === "blur" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("blur")}
            >
              模糊照片
            </button>
            <button
              className={`filter-btn${filterMode === "rejected" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("rejected")}
            >
              废片
            </button>
            <button
              className={`filter-btn${filterMode === "duplicate" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("duplicate")}
            >
              重复照片
            </button>
            <button
              className={`filter-btn${filterMode === "suggested" ? " filter-btn--active" : ""}`}
              onClick={() => setFilterMode("suggested")}
            >
              AI Suggestions
            </button>
            <span className="filter-starred-count">
              已选：{starredCount}
            </span>
            <span className="filter-rejected-count">
              废片：{rejectedCount}
            </span>
            <span className="filter-duplicate-count">
              重复：{duplicateCount}
            </span>
            <span className="filter-suggested-count">
              AI：{suggestedCount}
            </span>
          </div>
        </div>
        <div className="browser-header-right">
          <span className="browser-count">
            {filterMode === "starred"
              ? (total > 0 ? `已选 ${photos.length} / ${total} 张` : "已选 0 张")
              : filterMode === "blur"
                ? (total > 0 ? `模糊 ${photos.length} / ${total} 张` : "模糊 0 张")
                : filterMode === "rejected"
                  ? (total > 0 ? `废片 ${photos.length} / ${total} 张` : "废片 0 张")
                  : filterMode === "duplicate"
                    ? (total > 0 ? `重复 ${photos.length} / ${total} 张` : "重复 0 张")
                    : filterMode === "suggested"
                      ? (total > 0 ? `AI建议 ${photos.length} / ${total} 张` : "AI建议 0 张")
                      : (total > 0 ? `已加载 ${photos.length} / ${total} 张` : "")
            }
          </span>
          <button
            className="btn-detect"
            onClick={handleGenerateSuggestions}
            disabled={generating}
          >
            {generating ? "正在生成..." : "🤖 AI 建议"}
          </button>
          <button
            className="btn-detect"
            onClick={handleBlurDetect}
            disabled={detecting}
          >
            {detecting ? "正在检测..." : "🔍 检测模糊照片"}
          </button>
          <button
            className="btn-detect"
            onClick={handleDuplicateDetect}
            disabled={detectingDup}
          >
            {detectingDup ? "正在检测..." : "🔗 检测重复照片"}
          </button>
          <button
            className="btn-import"
            onClick={handleImport}
            disabled={importing}
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
          zoomMode={zoomMode}
          refreshKey={detailRefreshKey}
        />
      </div>

      {(importMsg || detectMsg || detectDupMsg) && (
        <div className="import-status">
          {detectDupMsg || detectMsg || importMsg}
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
