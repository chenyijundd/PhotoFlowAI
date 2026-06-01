/**
 * PhotoFlow AI — Export Dialog Component
 *
 * Professional export dialog with mode selection, naming template,
 * progress tracking, and cancel support. Displays export summary
 * on completion.
 */

import React, { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { exportStart, exportProgress, exportCancel, exportSummary } from "../api/photoApi";
import type { ExportMode, ExportProgressResponse, ExportSummaryResponse } from "../../types";

interface ExportDialogProps {
  /** Pre-set export mode. */
  defaultMode: ExportMode;
  /** For compare mode: list of photo IDs. */
  photoIds?: string[];
  /** For current_filter mode: server-side filter string. */
  filterMode?: string;
  /** Counts for each mode (dynamic, updates when dropdown changes). */
  pickedCount?: number;
  rejectedCount?: number;
  allCount?: number;
  /** Called when dialog is closed. */
  onClose: () => void;
}

type DialogPhase = "config" | "exporting" | "summary";

const MODE_LABELS: Record<ExportMode, string> = {
  picked: "已选照片 (Picked)",
  rejected: "废片 (Rejected)",
  current_filter: "当前筛选 (Current Filter)",
  compare: "对比组 (Compare Group)",
};

type NameTemplate = "original" | "custom_index" | "custom_date_index";

const TEMPLATE_LABELS: Record<NameTemplate, string> = {
  original: "保持原名",
  custom_index: "自定义前缀 + 序号",
  custom_date_index: "自定义前缀 + 日期 + 序号",
};

type ExportFormat = "original" | "jpeg" | "png";

const FORMAT_LABELS: Record<ExportFormat, string> = {
  original: "保持原格式",
  jpeg: "JPEG",
  png: "PNG",
};

const FORMAT_HINTS: Record<ExportFormat, string> = {
  original: "不转换，保留原始文件格式（JPG / HEIC / RAW 等）",
  jpeg: "通用 JPEG 格式，兼容性最好，适合客户交付",
  png: "无损 PNG 格式，文件较大，适合精修或印刷",
};

/** Generate a preview filename for the given template. */
function previewName(
  template: NameTemplate,
  prefix: string,
  index: number,
): string {
  const pre = prefix.trim() || "Export";
  const idx = String(index).padStart(3, "0");
  const today = new Date();
  const dateStr =
    String(today.getFullYear()) +
    String(today.getMonth() + 1).padStart(2, "0") +
    String(today.getDate()).padStart(2, "0");

  switch (template) {
    case "custom_index":
      return `${pre}_${idx}.{ext}`;
    case "custom_date_index":
      return `${pre}_${dateStr}_${idx}.{ext}`;
    default:
      return "IMG_0001.{ext}";
  }
}

const ExportDialog: React.FC<ExportDialogProps> = ({
  defaultMode,
  photoIds,
  filterMode,
  pickedCount,
  rejectedCount,
  allCount,
  onClose,
}) => {
  const [phase, setPhase] = useState<DialogPhase>("config");
  const [mode, setMode] = useState<ExportMode>(defaultMode);
  const [targetFolder, setTargetFolder] = useState("");

  // Naming template state
  const [nameTemplate, setNameTemplate] = useState<NameTemplate>("original");
  const [namePrefix, setNamePrefix] = useState("");
  const [startIndex, setStartIndex] = useState(1);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("original");

  /** Derive export count from current mode (updates on dropdown change). */
  const exportCount = useMemo(() => {
    if (mode === "compare") return photoIds?.length ?? 0;
    if (mode === "picked") return pickedCount ?? 0;
    if (mode === "rejected") return rejectedCount ?? 0;
    // current_filter: count depends on which browser filter tab is active
    if (filterMode === "starred") return pickedCount ?? 0;
    if (filterMode === "rejected") return rejectedCount ?? 0;
    return allCount ?? 0; // "all" or "unprocessed"
  }, [mode, photoIds, pickedCount, rejectedCount, allCount, filterMode]);

  const [exportId, setExportId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ExportProgressResponse | null>(null);
  const [summ, setSumm] = useState<ExportSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleBrowse = useCallback(async () => {
    if (window.electronAPI?.selectDirectory) {
      const dir = await window.electronAPI.selectDirectory();
      if (dir) setTargetFolder(dir);
    }
  }, []);

  const startPolling = useCallback((id: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const p = await exportProgress(id);
        setProgress(p);
        if (p.status !== "running") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          // Fetch final summary
          const s = await exportSummary(id);
          setSumm(s);
          setPhase("summary");
        }
      } catch {
        // Poll failed silently — will retry
      }
    }, 300);
  }, []);

  const handleStart = useCallback(async () => {
    if (!targetFolder) return;
    setError(null);
    try {
      const tpl = nameTemplate !== "original" ? nameTemplate : undefined;
      const pre = nameTemplate !== "original" && namePrefix.trim()
        ? namePrefix.trim()
        : undefined;
      const idx = nameTemplate !== "original" ? startIndex : undefined;
      console.log("[ExportDialog] Starting export:",
        { template: tpl, prefix: pre, startIndex: idx, mode, filterMode, exportFormat });
      const result = await exportStart(
        targetFolder, mode, photoIds, filterMode,
        tpl, pre, idx,
        exportFormat !== "original" ? exportFormat : undefined,
      );
      setExportId(result.export_id);
      setPhase("exporting");
      startPolling(result.export_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "导出启动失败");
    }
  }, [targetFolder, mode, photoIds, filterMode, nameTemplate, namePrefix, startIndex, exportFormat, startPolling]);

  const handleCancel = useCallback(async () => {
    if (exportId) {
      try {
        await exportCancel(exportId);
      } catch {
        // Silently ignore
      }
    }
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setPhase("config");
    setProgress(null);
    setExportId(null);
  }, [exportId]);

  const formatDuration = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  // ---- Summary Phase ----
  if (phase === "summary" && summ) {
    return (
      <div className="export-overlay">
        <div className="export-dialog">
          <h3 className="export-dialog-title">导出完成</h3>
          <div className="export-summary">
            <div className="export-summary-row">
              <span>成功</span>
              <span className="export-summary-ok">{summ.succeeded}</span>
            </div>
            <div className="export-summary-row">
              <span>失败</span>
              <span className={summ.failed > 0 ? "export-summary-err" : ""}>{summ.failed}</span>
            </div>
            <div className="export-summary-row">
              <span>跳过</span>
              <span>{summ.skipped}</span>
            </div>
            <div className="export-summary-row">
              <span>耗时</span>
              <span>{formatDuration(summ.duration_seconds)}</span>
            </div>
          </div>
          {summ.errors.length > 0 && (
            <div className="export-errors">
              <span>错误详情：</span>
              {summ.errors.slice(0, 5).map((e, i) => (
                <div key={i} className="export-error-item">{e}</div>
              ))}
              {summ.errors.length > 5 && (
                <div className="export-error-item">... 共 {summ.errors.length} 条错误</div>
              )}
            </div>
          )}
          <div className="export-dialog-actions">
            <button className="btn-primary" onClick={onClose}>关闭</button>
          </div>
        </div>
      </div>
    );
  }

  // ---- Exporting Phase ----
  if (phase === "exporting" && progress) {
    const pct = progress.total > 0 ? Math.round((progress.succeeded + progress.failed) / progress.total * 100) : 0;
    return (
      <div className="export-overlay">
        <div className="export-dialog">
          <h3 className="export-dialog-title">正在导出...</h3>
          <div className="export-progress-bar">
            <div className="export-progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="export-progress-text">
            {progress.succeeded + progress.failed} / {progress.total}
          </div>
          {progress.current_file && (
            <div className="export-current-file" title={progress.current_file}>
              {progress.current_file}
            </div>
          )}
          <div className="export-dialog-actions">
            <button className="btn-cancel" onClick={handleCancel}>取消导出</button>
          </div>
        </div>
      </div>
    );
  }

  const preview = previewName(nameTemplate, namePrefix, startIndex);

  // ---- Config Phase ----
  return (
    <div className="export-overlay">
      <div className="export-dialog">
        <h3 className="export-dialog-title">导出照片</h3>

        <div className="export-field">
          <label className="export-label">导出对象</label>
          <select
            className="export-select"
            value={mode}
            onChange={(e) => setMode(e.target.value as ExportMode)}
          >
            <option value="picked">{MODE_LABELS.picked}</option>
            <option value="rejected">{MODE_LABELS.rejected}</option>
            <option value="current_filter">{MODE_LABELS.current_filter}</option>
          </select>
        </div>

        <div className="export-field">
          <label className="export-label">文件命名</label>
          <select
            className="export-select"
            value={nameTemplate}
            onChange={(e) => setNameTemplate(e.target.value as NameTemplate)}
          >
            <option value="original">{TEMPLATE_LABELS.original}</option>
            <option value="custom_index">{TEMPLATE_LABELS.custom_index}</option>
            <option value="custom_date_index">{TEMPLATE_LABELS.custom_date_index}</option>
          </select>
        </div>

        {nameTemplate !== "original" && (
          <>
            <div className="export-field">
              <label className="export-label">名称前缀</label>
              <input
                className="export-input"
                type="text"
                value={namePrefix}
                onChange={(e) => setNamePrefix(e.target.value)}
                placeholder="例如：婚礼、新娘姓名..."
              />
            </div>
            <div className="export-field">
              <label className="export-label">起始序号</label>
              <input
                className="export-input"
                type="number"
                min={1}
                max={9999}
                value={startIndex}
                onChange={(e) => setStartIndex(Number(e.target.value) || 1)}
                style={{ width: 100 }}
              />
            </div>
            <div className="export-field">
              <label className="export-label">命名预览</label>
              <span className="export-name-preview">{preview}</span>
              <span className="export-name-hint">{FORMAT_HINTS[exportFormat]}</span>
            </div>
          </>
        )}

        <div className="export-field">
          <label className="export-label">导出格式</label>
          <select
            className="export-select"
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
          >
            <option value="original">{FORMAT_LABELS.original}</option>
            <option value="jpeg">{FORMAT_LABELS.jpeg}</option>
            <option value="png">{FORMAT_LABELS.png}</option>
          </select>
        </div>

        <div className="export-field">
          <label className="export-label">目标文件夹</label>
          <div className="export-folder-row">
            <input
              className="export-input"
              type="text"
              value={targetFolder}
              onChange={(e) => setTargetFolder(e.target.value)}
              placeholder="选择或输入导出目录..."
            />
            <button className="btn-small" onClick={handleBrowse}>浏览</button>
          </div>
        </div>

        <div className="export-field">
          <label className="export-label">导出数量</label>
          <span className="export-estimate">{exportCount} 张</span>
        </div>

        {error && <div className="export-error">{error}</div>}

        <div className="export-dialog-actions">
          <button className="btn-cancel" onClick={onClose}>取消</button>
          <button
            className="btn-primary"
            onClick={handleStart}
            disabled={!targetFolder || exportCount === 0}
          >
            开始导出
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExportDialog;
