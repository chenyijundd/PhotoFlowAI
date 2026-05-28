/**
 * PhotoFlow AI - Detail Panel Component
 *
 * Displays metadata and a full-size preview for the currently
 * selected photo.  Handles loading, error, and empty states.
 * Supports fit / zoom100 preview modes.
 */

import React, { useEffect, useState, useCallback } from "react";
import FullsizePreview from "./FullsizePreview";
import { fetchPhotoDetail } from "../api/photoApi";
import type { PhotoDetailResponse } from "../../types";
import type { ZoomMode } from "../hooks/useKeyboardNavigation";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface DetailPanelProps {
  imageId: string | null;
  zoomMode: ZoomMode;
  refreshKey: number;
}

const DetailPanel: React.FC<DetailPanelProps> = ({ imageId, zoomMode, refreshKey }) => {
  const [detail, setDetail] = useState<PhotoDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    setDetail(null);
    try {
      const data = await fetchPhotoDetail(id);
      setDetail(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "加载详情失败";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (imageId) {
      loadDetail(imageId);
    } else {
      setDetail(null);
      setLoading(false);
      setError(null);
    }
  }, [imageId, loadDetail, refreshKey]);

  // ---- Empty state ----
  if (!imageId) {
    return (
      <aside className="detail-panel">
        <div className="detail-empty">
          <div className="detail-empty-icon">🖼️</div>
          <p>请选择一张照片</p>
        </div>
      </aside>
    );
  }

  // ---- Loading state ----
  if (loading) {
    return (
      <aside className="detail-panel">
        <div className="detail-loading">
          <div className="spinner" />
          <p>加载照片详情...</p>
        </div>
      </aside>
    );
  }

  // ---- Error state ----
  if (error) {
    return (
      <aside className="detail-panel">
        <div className="detail-empty">
          <div className="detail-empty-icon">⚠️</div>
          <p>加载详情失败</p>
          <span className="detail-error-msg">{error}</span>
        </div>
      </aside>
    );
  }

  // ---- Content state ----
  return (
    <aside className="detail-panel">
      {/* Full-size preview */}
      <FullsizePreview
        imageId={imageId}
        fileName={detail?.file_name ?? ""}
        zoomMode={zoomMode}
      />

      {/* Metadata */}
      <div className="detail-meta">
        <div className="detail-field">
          <span className="detail-label">文件名</span>
          <span className="detail-value" title={detail?.file_name}>{detail?.file_name}</span>
        </div>
        <div className="detail-field">
          <span className="detail-label">尺寸</span>
          <span className="detail-value">{detail?.width} × {detail?.height}</span>
        </div>
        <div className="detail-field">
          <span className="detail-label">文件大小</span>
          <span className="detail-value">{formatFileSize(detail?.file_size ?? 0)}</span>
        </div>
        <div className="detail-field">
          <span className="detail-label">创建时间</span>
          <span className="detail-value">{detail?.created_time || "未知"}</span>
        </div>
        <div className="detail-field">
          <span className="detail-label">星级</span>
          <span className="detail-value">{detail?.star_rating === 1 ? "★ 已标记" : "☆ 未标记"}</span>
        </div>
        {detail?.is_rejected !== undefined && detail.is_rejected === 1 && (
          <div className="detail-field">
            <span className="detail-label">状态</span>
            <span className="detail-value">REJECT</span>
          </div>
        )}
        {detail?.is_duplicate !== undefined && detail.is_duplicate === 1 && detail.duplicate_group && (
          <div className="detail-field">
            <span className="detail-label">重复分组</span>
            <span className="detail-value">{detail.duplicate_group}</span>
          </div>
        )}
        {detail?.blur_score != null && (
          <div className="detail-field">
            <span className="detail-label">模糊检测</span>
            <span className="detail-value">
              {detail.is_blur === 1
                ? `BLUR（分数：${detail.blur_score.toFixed(1)}）`
                : `清晰（分数：${detail.blur_score.toFixed(1)}）`
              }
            </span>
          </div>
        )}
        <div className="detail-field">
          <span className="detail-label">ID</span>
          <span className="detail-value detail-id" title={detail?.image_id}>{detail?.image_id}</span>
        </div>
      </div>
    </aside>
  );
};

export default DetailPanel;
