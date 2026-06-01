/**
 * PhotoFlow AI — AI Analysis Summary Modal
 *
 * Shown automatically after AI analysis completes. Gives the
 * photographer a one-glance summary of what the AI found before
 * they proceed to "一键选片" or manual review.
 */

import React, { useEffect } from "react";
import type { AISummaryResponse } from "../../types";

interface AnalysisSummaryModalProps {
  summary: AISummaryResponse;
  onCull: () => void;
  onClose: () => void;
}

const AnalysisSummaryModal: React.FC<AnalysisSummaryModalProps> = ({
  summary,
  onCull,
  onClose,
}) => {
  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Click outside to close
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const {
    total_analyzed,
    closed_eye_count,
    blur_count,
    burst_group_count,
    burst_photo_count,
    duplicate_group_count,
    duplicate_photo_count,
    best_count,
    clean_count,
  } = summary;

  return (
    <div className="ai-summary-overlay" onClick={handleOverlayClick}>
      <div className="ai-summary-dialog">
        {/* Header */}
        <div className="ai-summary-header">
          <h2 className="ai-summary-title">🤖 AI 分析完成</h2>
          <p className="ai-summary-subtitle">
            共分析 <strong>{total_analyzed}</strong> 张照片，以下是 AI 发现的结果
          </p>
        </div>

        {/* Stats Grid — two columns */}
        <div className="ai-summary-grid">
          {/* Row 1: Closed Eye + Blur */}
          <div className={`ai-summary-card${closed_eye_count > 0 ? " ai-summary-card--danger" : " ai-summary-card--ok"}`}>
            <div className="ai-summary-card-icon">😵</div>
            <div className="ai-summary-card-value">{closed_eye_count}</div>
            <div className="ai-summary-card-label">闭眼（致命缺陷）</div>
          </div>

          <div className={`ai-summary-card${blur_count > 0 ? " ai-summary-card--warn" : " ai-summary-card--ok"}`}>
            <div className="ai-summary-card-icon">🌫️</div>
            <div className="ai-summary-card-value">{blur_count}</div>
            <div className="ai-summary-card-label">模糊（质量缺陷）</div>
          </div>

          {/* Row 2: Burst Groups + Duplicate Groups */}
          <div className={`ai-summary-card${burst_group_count > 0 ? " ai-summary-card--info" : " ai-summary-card--ok"}`}>
            <div className="ai-summary-card-icon">📸</div>
            <div className="ai-summary-card-value">
              {burst_group_count > 0
                ? `${burst_group_count} 组 / ${burst_photo_count} 张`
                : "0"}
            </div>
            <div className="ai-summary-card-label">连拍</div>
          </div>

          <div className={`ai-summary-card${duplicate_group_count > 0 ? " ai-summary-card--info" : " ai-summary-card--ok"}`}>
            <div className="ai-summary-card-icon">🔄</div>
            <div className="ai-summary-card-value">
              {duplicate_group_count > 0
                ? `${duplicate_group_count} 组 / ${duplicate_photo_count} 张`
                : "0"}
            </div>
            <div className="ai-summary-card-label">重复</div>
          </div>

          {/* Row 3: Best + Clean */}
          <div className={`ai-summary-card${best_count > 0 ? " ai-summary-card--best" : " ai-summary-card--ok"}`}>
            <div className="ai-summary-card-icon">⭐</div>
            <div className="ai-summary-card-value">{best_count}</div>
            <div className="ai-summary-card-label">最佳推荐</div>
          </div>

          <div className={`ai-summary-card${clean_count > 0 ? " ai-summary-card--clean" : " ai-summary-card--ok"}`}>
            <div className="ai-summary-card-icon">✅</div>
            <div className="ai-summary-card-value">{clean_count}</div>
            <div className="ai-summary-card-label">无缺陷（清晰）</div>
          </div>
        </div>

        {/* Footer actions */}
        <div className="ai-summary-actions">
          <button className="btn-secondary" onClick={onClose}>
            查看详情
          </button>
          <button className="btn-cull-primary" onClick={onCull}>
            ⚡ 一键选片
          </button>
        </div>

        <p className="ai-summary-hint">
          提示：点击「查看详情」可手动逐张筛选，点击「一键选片」让 AI 自动处理
        </p>
      </div>
    </div>
  );
};

export default AnalysisSummaryModal;
