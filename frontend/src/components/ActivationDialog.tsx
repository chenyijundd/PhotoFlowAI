/**
 * PhotoFlow AI - Activation Dialog
 *
 * Shown on first launch when the software is not yet activated.
 * The user enters their name and the 16-character license key
 * they received after purchase.
 */

import React, { useState, useRef, useEffect } from "react";
import { fetchLicenseStatus, activateLicense, startTrial } from "../api/licenseApi";

interface ActivationDialogProps {
  onActivated: (userName: string) => void;
}

const ActivationDialog: React.FC<ActivationDialogProps> = ({ onActivated }) => {
  const [userName, setUserName] = useState("");
  const [licenseKey, setLicenseKey] = useState("");
  const [activating, setActivating] = useState(false);
  const [startingTrial, setStartingTrial] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const userNameRef = useRef<HTMLInputElement>(null);

  // Auto-focus the first input on mount
  useEffect(() => {
    userNameRef.current?.focus();
  }, []);

  const handleActivate = async () => {
    // Basic validation
    const trimmedName = userName.trim();
    const trimmedKey = licenseKey.trim();

    if (!trimmedName) {
      setError("请输入您的姓名");
      userNameRef.current?.focus();
      return;
    }
    if (!trimmedKey) {
      setError("请输入16位激活码");
      return;
    }
    if (trimmedKey.length !== 16) {
      setError("激活码应为16位字符，请检查后重试");
      return;
    }

    setError(null);
    setActivating(true);

    try {
      const result = await activateLicense(trimmedName, trimmedKey);
      if (result.success) {
        setSuccess(true);
        // Brief delay so the user sees the success message
        setTimeout(() => {
          onActivated(result.user_name || trimmedName);
        }, 1500);
      } else {
        // Backend may return `detail` (FastAPI HTTPException) or `message` (our own response)
        setError(result.detail || result.message || "激活失败，请重试");
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "激活失败，请检查网络连接后重试";
      setError(msg);
    } finally {
      setActivating(false);
    }
  };

  const handleStartTrial = async () => {
    setError(null);
    setStartingTrial(true);

    try {
      const result = await startTrial();
      if (result.success) {
        setSuccess(true);
        setTimeout(() => {
          onActivated(result.user_name || "试用用户");
        }, 1500);
      } else {
        setError(result.message || "试用开启失败，请重试");
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "试用开启失败，请检查网络连接后重试";
      setError(msg);
    } finally {
      setStartingTrial(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleActivate();
    }
  };

  // Format license key to uppercase and limit to 16 chars
  const handleLicenseKeyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "");
    setLicenseKey(value.slice(0, 16));
  };

  if (success) {
    return (
      <div className="state-screen activation-success">
        <div className="state-icon">✅</div>
        <h2>激活成功！</h2>
        <p>感谢使用 PhotoFlow AI，正在进入软件...</p>
      </div>
    );
  }

  return (
    <div className="state-screen activation-dialog">
      <div className="activation-card">
        <div className="activation-header">
          <h2>PhotoFlow AI</h2>
          <p>智能摄影辅助工具 — 激活您的许可证</p>
        </div>

        <div className="activation-form">
          <div className="form-group">
            <label htmlFor="act-user-name">用户名</label>
            <input
              id="act-user-name"
              ref={userNameRef}
              type="text"
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="请输入购买时提供的用户名"
              disabled={activating}
              autoComplete="name"
            />
          </div>

          <div className="form-group">
            <label htmlFor="act-license-key">激活码</label>
            <input
              id="act-license-key"
              type="text"
              value={licenseKey}
              onChange={handleLicenseKeyChange}
              onKeyDown={handleKeyDown}
              placeholder="XXXX-XXXX-XXXX-XXXX"
              disabled={activating}
              maxLength={16}
              autoComplete="off"
              className="license-key-input"
            />
          </div>

          {error && <div className="form-error">{error}</div>}

          <button
            className="btn-primary btn-activate"
            onClick={handleActivate}
            disabled={activating}
          >
            {activating ? "正在验证..." : "激活"}
          </button>
        </div>

        <div className="activation-footer">
          <button
            className="btn-secondary btn-trial"
            onClick={handleStartTrial}
            disabled={activating || startingTrial}
          >
            {startingTrial ? "正在开启试用..." : "🎁 免费试用 30 天"}
          </button>
          <p style={{ marginTop: 12 }}>
            还没有激活码？
            {" "}
            <span className="activation-footer-link">
              请访问官网购买
            </span>
          </p>
        </div>
      </div>
    </div>
  );
};

export default ActivationDialog;
