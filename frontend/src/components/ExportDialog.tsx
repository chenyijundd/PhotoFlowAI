/**
 * PhotoFlow AI — Export Dialog Component
 *
 * Professional export dialog with mode selection, progress tracking,
 * and cancel support. Displays export summary on completion.
 */

import React, { useState, useCallback, useRef, useEffect } from "react";
import { exportStart, exportProgress, exportCancel, exportSummary } from "../api/photoApi";
import type { ExportMode, ExportProgressResponse, ExportSummaryResponse } from "../../types";

interface ExportDialogProps {
  /** Pre-set export mode. */
  defaultMode: ExportMode;
  /** For current_filter / compare mode: list of photo IDs. */
  photoIds?: string[];
  /** Estimated count shown before export starts. */
  estimatedCount: number;
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

const ExportDialog: React.FC<ExportDialogProps> = ({
  defaultMode,
  photoIds,
  estimatedCount,
  onClose,
}) => {
  const [phase, setPhase] = useState<DialogPhase>("config");
  const [mode, setMode] = useState<ExportMode>(defaultMode);
  const [targetFolder, setTargetFolder] = useState("");
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
      const result = await exportStart(targetFolder, mode, photoIds);
      setExportId(result.export_id);
      setPhase("exporting");
      startPolling(result.export_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "导出启动失败");
    }
  }, [targetFolder, mode, photoIds, startPolling]);

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

  // ---- Config Phase ----
  return (
    <div className="export-overlay">
      <div className="export-dialog">
        <h3 className="export-dialog-title">导出照片</h3>

        <div className="export-field">
          <label className="export-label">导出模式</label>
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
          <label className="export-label">预计数量</label>
          <span className="export-estimate">{estimatedCount} 张</span>
        </div>

        {error && <div className="export-error">{error}</div>}

        <div className="export-dialog-actions">
          <button className="btn-cancel" onClick={onClose}>取消</button>
          <button
            className="btn-primary"
            onClick={handleStart}
            disabled={!targetFolder || estimatedCount === 0}
          >
            开始导出
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExportDialog;
