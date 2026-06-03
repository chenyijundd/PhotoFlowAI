/**
 * PhotoFlow AI - ProjectPicker Component
 *
 * Landing page shown when no project is open.  Allows the photographer to:
 *   - Create a new project (name + optional photo directory)
 *   - Open an existing project from the recent list
 *   - Archive / delete projects via the context menu
 *
 * Once a project is opened, the parent (App) switches to BrowserPage.
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import type { ProjectInfo } from "../api/projectApi";
import {
  fetchProjects,
  createProject,
  openProject,
  archiveProject,
  deleteProject,
} from "../api/projectApi";

interface ProjectPickerProps {
  onProjectOpened: (project: ProjectInfo) => void;
}

const ProjectPicker: React.FC<ProjectPickerProps> = ({ onProjectOpened }) => {
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---- Create dialog state ----
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // ---- Confirm dialog state (replaces blocking window.confirm) ----
  const [confirmMsg, setConfirmMsg] = useState<string | null>(null);
  const confirmResolveRef = useRef<((ok: boolean) => void) | null>(null);

  // ---- Context menu state ----
  const [menuProjectId, setMenuProjectId] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);

  const nameInputRef = useRef<HTMLInputElement>(null);

  // Reset form state and focus input when dialog opens
  useEffect(() => {
    if (showCreate) {
      setNewName("");
      setCreateError(null);
      const id = setTimeout(() => nameInputRef.current?.focus(), 100);
      return () => clearTimeout(id);
    }
  }, [showCreate]);

  /** Non-blocking confirmation — replaces window.confirm() which freezes
   *  the browser event loop and breaks focus/rendering on return. */
  const requestConfirm = useCallback((msg: string): Promise<boolean> => {
    return new Promise((resolve) => {
      confirmResolveRef.current = resolve;
      setConfirmMsg(msg);
    });
  }, []);

  const loadProjects = useCallback(async () => {
    try {
      setError(null);
      const list = await fetchProjects(showArchived);
      setProjects(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载项目列表失败");
    } finally {
      setLoading(false);
    }
  }, [showArchived]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  // Close context menu on outside click
  useEffect(() => {
    if (!menuProjectId) return;
    const close = () => setMenuProjectId(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [menuProjectId]);

  const handleCreate = useCallback(async () => {
    // Guard against double-submit (replaces disabled prop on button/input)
    if (creating) return;
    const name = newName.trim();
    if (!name) {
      setCreateError("请输入项目名称");
      return;
    }
    // Duplicate name check — must include archived projects so a
    // new project cannot reuse the name of an archived one.
    const all = await fetchProjects(true);
    if (all.some((p) => p.name === name)) {
      setCreateError("项目名称已存在（含已归档项目），请使用其他名称。");
      return;
    }
    // Limit to 5 projects (excluding archived)
    const activeCount = projects.filter((p) => !p.archived).length;
    if (activeCount >= 5) {
      setCreateError("最多允许创建 5 个项目。请归档或删除旧项目后再创建新项目。");
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const project = await createProject(name);
      // Must call openProject so the backend switches to the new project's
      // database BEFORE BrowserPage mounts and starts fetching photos.
      // Without this, PhotoRepository falls back to the legacy default db.
      const opened = await openProject(project.id);
      setShowCreate(false);
      setNewName("");
      onProjectOpened(opened);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreating(false);
    }
  }, [newName, onProjectOpened, projects, creating]);

  const handleOpen = useCallback(
    async (projectId: string) => {
      try {
        const project = await openProject(projectId);
        onProjectOpened(project);
      } catch (err) {
        setError(err instanceof Error ? err.message : "打开项目失败");
      }
    },
    [onProjectOpened],
  );

  const handleArchive = useCallback(
    async (projectId: string, archive: boolean) => {
      try {
        // Optimistic: toggle archived flag locally so the
        // 5-project limit check is immediately accurate.
        setProjects((prev) =>
          prev.map((p) => (p.id === projectId ? { ...p, archived: archive } : p)),
        );
        await archiveProject(projectId, archive);
        setMenuProjectId(null);
        loadProjects();  // sync with server
      } catch (err) {
        loadProjects();  // revert on error
        setError(err instanceof Error ? err.message : "操作失败");
      }
    },
    [loadProjects],
  );

  const handleDelete = useCallback(
    async (projectId: string) => {
      const project = projects.find((p) => p.id === projectId);
      const name = project?.name || projectId;
      const ok = await requestConfirm(
        `确定要删除项目「${name}」吗？\n\n项目数据库文件也将被删除，此操作不可撤销。`,
      );
      if (!ok) return;
      try {
        // Optimistic: remove from local state immediately so the
        // 5-project limit check sees the freed slot right away.
        setProjects((prev) => prev.filter((p) => p.id !== projectId));
        await deleteProject(projectId, true);
        setMenuProjectId(null);
        loadProjects();  // sync with server to catch any edge cases
      } catch (err) {
        setError(err instanceof Error ? err.message : "删除失败");
      }
    },
    [projects, loadProjects],
  );

  const formatDate = (iso: string | null) => {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  };

  // ---- Loading skeleton ----
  if (loading) {
    return (
      <div className="state-screen loading-state">
        <div className="spinner" />
        <p>正在加载项目列表...</p>
      </div>
    );
  }

  // ---- Error state ----
  if (error && projects.length === 0) {
    return (
      <div className="state-screen error-state">
        <div className="state-icon">⚠️</div>
        <h2>加载失败</h2>
        <p>{error}</p>
        <button className="btn-primary" onClick={loadProjects}>
          重试
        </button>
      </div>
    );
  }

  return (
    <div className="project-picker">
      <div className="project-picker-header">
        <h1 className="project-picker-title">PhotoFlow AI</h1>
        <p className="project-picker-subtitle">选择或创建项目以开始筛选照片</p>
      </div>

      {/* ---- Create new project button ---- */}
      <div className="project-picker-actions">
        <button
          className="btn-primary btn-create-project"
          onClick={() => setShowCreate(true)}
        >
          ＋ 新建项目
        </button>
      </div>

      {/* ---- Create dialog ---- */}
      {showCreate && (
        <div
          className="project-create-dialog"
          onClick={() => nameInputRef.current?.focus()}
        >
          <div className="project-create-card" onClick={(e) => e.stopPropagation()}>
            <h2>新建项目</h2>
            <label className="project-create-label">
              项目名称
              <input
                ref={nameInputRef}
                type="text"
                className="project-create-input"
                placeholder="例如：张家婚礼、2026 春季写真"
                value={newName}
                onChange={(e) => {
                  setNewName(e.target.value);
                  setCreateError(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                  if (e.key === "Escape") setShowCreate(false);
                }}
                maxLength={100}
              />
            </label>
            <p className="project-create-hint">
              每个项目拥有独立的照片库和 AI 分析结果。
              <br />
              创建后可在主界面导入照片。
            </p>
            {createError && (
              <p className="project-create-error">{createError}</p>
            )}
            <div className="project-create-buttons">
              <button
                className="btn-primary"
                onClick={handleCreate}
              >
                {creating ? "创建中..." : "创建并打开"}
              </button>
              <button
                className="btn-cancel"
                onClick={() => setShowCreate(false)}
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Project list ---- */}
      <div className="project-list-section">
        <div className="project-list-header">
          <h2>
            {showArchived ? "已归档项目" : "最近项目"}
          </h2>
          <label className="project-archive-toggle">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
            />
            {" "}显示已归档
          </label>
        </div>

        {projects.length === 0 ? (
          <div className="project-list-empty">
            <p>{showArchived ? "没有已归档的项目" : "暂无项目，点击上方按钮创建第一个项目"}</p>
          </div>
        ) : (
          <div className="project-list">
            {projects.map((p) => (
              <div
                key={p.id}
                className={`project-card${p.archived ? " project-card--archived" : ""}`}
                onClick={() => handleOpen(p.id)}
                title={p.archived ? "点击打开已归档项目" : "点击打开项目"}
              >
                <div className="project-card-icon">
                  {p.archived ? "📦" : "📁"}
                </div>
                <div className="project-card-body">
                  <div className="project-card-name">{p.name}</div>
                  <div className="project-card-meta">
                    <span>{p.photo_count} 张照片</span>
                    {p.picked_count > 0 && (
                      <span> · ⭐ {p.picked_count} 张已选</span>
                    )}
                    <span> · {formatDate(p.last_opened_at || p.created_at)}</span>
                    {p.archived && <span className="project-card-archived-tag">已归档</span>}
                  </div>
                </div>

                {/* Context menu button (stop click propagation) */}
                <button
                  className="project-card-menu-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuProjectId(menuProjectId === p.id ? null : p.id);
                  }}
                  title="更多操作"
                >
                  ⋯
                </button>

                {/* Dropdown menu */}
                {menuProjectId === p.id && (
                  <div
                    className="project-card-menu"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {p.archived ? (
                      <button
                        className="project-card-menu-item"
                        onClick={() => handleArchive(p.id, false)}
                      >
                        📂 取消归档
                      </button>
                    ) : (
                      <button
                        className="project-card-menu-item"
                        onClick={() => handleArchive(p.id, true)}
                      >
                        📦 归档
                      </button>
                    )}
                    <button
                      className="project-card-menu-item project-card-menu-item--danger"
                      onClick={() => handleDelete(p.id)}
                    >
                      🗑️ 删除
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Error toast (non-blocking) */}
      {error && projects.length > 0 && (
        <div className="project-picker-toast">{error}</div>
      )}

      {/* ---- Confirm dialog (React-based, avoids window.confirm blocking) ---- */}
      {confirmMsg && (
        <div className="project-create-dialog">
          <div className="project-create-card">
            <h2>确认操作</h2>
            <p style={{ color: "#ccc", fontSize: "14px", lineHeight: 1.6, whiteSpace: "pre-wrap", marginBottom: "20px" }}>
              {confirmMsg}
            </p>
            <div className="project-create-buttons">
              <button
                className="btn-primary"
                style={{ background: "#e94560" }}
                onClick={() => {
                  confirmResolveRef.current?.(true);
                  confirmResolveRef.current = null;
                  setConfirmMsg(null);
                }}
              >
                确认删除
              </button>
              <button
                className="btn-cancel"
                onClick={() => {
                  confirmResolveRef.current?.(false);
                  confirmResolveRef.current = null;
                  setConfirmMsg(null);
                }}
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectPicker;
