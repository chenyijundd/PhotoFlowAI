/**
 * PhotoFlow AI - Detail Panel Component
 *
 * Displays metadata and a full-size preview for the currently
 * selected photo.  Handles loading, error, and empty states.
 * Supports fit / zoom100 preview modes.
 */

import React, { useEffect, useState, useCallback, useRef } from "react";
import FullsizePreview from "./FullsizePreview";
import BurstFilmstrip from "./BurstFilmstrip";
import { fetchPhotoDetail } from "../api/photoApi";
import type { PhotoDetailResponse, PhotoFilterMode, RawJpegPairMember, ZoomMode } from "../../types";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Format ISO-8601 date string to YYYY-MM-DD hh:mm:ss. */
function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "未知";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso; // fallback to raw value
    const yyyy = d.getFullYear();
    const MM = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    return `${yyyy}-${MM}-${dd} ${hh}:${mm}:${ss}`;
  } catch {
    return iso;
  }
}

interface DetailPanelProps {
  imageId: string | null;
  zoomMode?: ZoomMode;
  refreshKey: number;
  /** Called after a burst group action so the parent can refresh grid & counts. */
  onBurstAction?: () => void;
  /** Current photo filter mode — controls trash vs normal buttons. */
  filterMode?: PhotoFilterMode;
  /** Called to trigger moving a photo to trash (parent handles API + advance). */
  onTrashRequest?: (imageId: string) => void;
  /** Called to trigger restoring a photo (parent handles API + advance). */
  onRestoreRequest?: (imageId: string) => void;
  /** Called to trigger permanent delete confirmation dialog (parent shows dialog). */
  onPermanentDeleteRequest?: (imageId: string) => void;
  /** When true, all action buttons are disabled (e.g. during multi-select). */
  actionsDisabled?: boolean;
}

const DetailPanel: React.FC<DetailPanelProps> = ({ imageId, zoomMode = "fit", refreshKey, onBurstAction, filterMode, onTrashRequest, onRestoreRequest, onPermanentDeleteRequest, actionsDisabled }) => {
  const [detail, setDetail] = useState<PhotoDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLElement>(null);

  // Scroll detail panel to top whenever the selected photo changes
  useEffect(() => {
    if (panelRef.current) {
      panelRef.current.scrollTop = 0;
    }
  }, [imageId]);

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
    <aside className="detail-panel" ref={panelRef}>
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
          <span className="detail-value">{formatDateTime(detail?.created_time)}</span>
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
        {detail?.raw_jpeg_pair_id && detail.raw_jpeg_pair_members && detail.raw_jpeg_pair_members.length > 1 && (
          <div className="detail-field">
            <span className="detail-label">RAW+JPEG 配对</span>
            <span className="detail-value">
              {detail.raw_jpeg_pair_members.map((m: RawJpegPairMember, i: number) => (
                <span key={m.image_id} className={`rawpair-member${m.image_id === detail.image_id ? " rawpair-member--current" : ""}`}>
                  {i > 0 && " · "}
                  <span className={`rawpair-tag${m.is_raw ? " rawpair-tag--raw" : " rawpair-tag--jpg"}`}>
                    {m.is_raw ? "RAW" : "JPG"}
                  </span>
                  {" "}{m.file_name}
                </span>
              ))}
            </span>
          </div>
        )}
        {detail?.burst_group && (
          <div className="detail-field">
            <span className="detail-label">连拍组</span>
            <span className="detail-value">
              {detail.burst_group}{detail.burst_position != null ? `（第 ${detail.burst_position + 1}/${detail.burst_total ?? "?"} 张）` : ""}
            </span>
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
        {detail?.eye_score != null && (
          <div className="detail-field">
            <span className="detail-label">闭眼检测</span>
            <span className="detail-value" style={{ color: detail.is_closed_eye === 1 ? "#e94560" : "#1dd1a1" }}>
              {detail.is_closed_eye === 1
                ? `闭眼（EAR: ${detail.eye_score.toFixed(4)}）`
                : `睁眼（EAR: ${detail.eye_score.toFixed(4)}）`
              }
            </span>
          </div>
        )}
      </div>

      {/* Trash/Restore action buttons */}
      {imageId && filterMode === "trash" ? (
        <div className="detail-actions">
          <button
            className="btn-small"
            style={{ background: "#1dd1a1", color: "#111", width: "100%", marginBottom: 6, opacity: actionsDisabled ? 0.4 : 1 }}
            onClick={() => onRestoreRequest?.(imageId)}
            disabled={actionsDisabled}
          >
            ↩️ 还原照片
          </button>
          <button
            className="btn-small"
            style={{ background: "#e94560", color: "#fff", width: "100%", opacity: actionsDisabled ? 0.4 : 1 }}
            onClick={() => onPermanentDeleteRequest?.(imageId)}
            disabled={actionsDisabled}
          >
            🔥 彻底删除
          </button>
        </div>
      ) : (
        imageId && filterMode !== "trash" && (
          <div className="detail-actions">
            <button
              className="btn-small btn-trash"
              style={{ opacity: actionsDisabled ? 0.4 : 1 }}
              onClick={() => onTrashRequest?.(imageId)}
              disabled={actionsDisabled}
              title={actionsDisabled ? "多选模式下不可用" : "移到回收站 (Ctrl+Delete)"}
            >
              🗑️ 移到回收站
            </button>
          </div>
        )
      )}

      {/* Burst group filmstrip */}
      {detail?.burst_group && (
        <BurstFilmstrip
          currentImageId={imageId}
          burstGroupId={detail.burst_group}
          onAction={onBurstAction}
          actionsDisabled={actionsDisabled}
        />
      )}
    </aside>
  );
};

export default DetailPanel;
