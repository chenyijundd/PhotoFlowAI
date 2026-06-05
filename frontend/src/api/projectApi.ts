/**
 * PhotoFlow AI - Project API Client
 *
 * Functions for multi-project management (list, create, open, close, etc.).
 */

const BACKEND_URL = "http://127.0.0.1:8765";

/** A project record returned from the backend. */
export interface ProjectInfo {
  id: string;
  name: string;
  db_path: string;
  photo_dir: string | null;
  created_at: string;
  last_opened_at: string | null;
  archived: boolean;
  photo_count: number;
  picked_count: number;
}

/** List all projects (excludes archived by default). */
export async function fetchProjects(
  includeArchived: boolean = false,
): Promise<ProjectInfo[]> {
  const url = `${BACKEND_URL}/api/projects?include_archived=${includeArchived}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  const data = await res.json();
  return data.projects;
}

/** Create a new project with an independent database. */
export async function createProject(
  name: string,
  photoDir?: string,
): Promise<ProjectInfo> {
  const url = `${BACKEND_URL}/api/projects`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, photo_dir: photoDir || null }),
  });
  if (!res.ok) {
    const detail = await res.json().then((b) => b.detail).catch(() => null);
    throw new Error(detail || `Backend returned ${res.status}`);
  }
  return res.json();
}

/** Open a project — subsequent API calls use this project's database. */
export async function openProject(projectId: string): Promise<ProjectInfo> {
  const url = `${BACKEND_URL}/api/projects/${encodeURIComponent(projectId)}/open`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const detail = await res.json().then((b) => b.detail).catch(() => null);
    throw new Error(detail || `Backend returned ${res.status}`);
  }
  return res.json();
}

/** Close the current project — reverts to default database. */
export async function closeProject(): Promise<void> {
  const url = `${BACKEND_URL}/api/projects/close`;
  await fetch(url, { method: "POST" });
}

/** Archive or un-archive a project. */
export async function archiveProject(
  projectId: string,
  archive: boolean,
): Promise<void> {
  const url = `${BACKEND_URL}/api/projects/${encodeURIComponent(projectId)}/archive?archive=${archive}`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
}

/** Delete a project. Set deleteDb=true to also remove the database file. */
export async function deleteProject(
  projectId: string,
  deleteDb: boolean = false,
): Promise<void> {
  const url = `${BACKEND_URL}/api/projects/${encodeURIComponent(projectId)}?delete_db=${deleteDb}`;
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.json().then((b) => b.detail).catch(() => null);
    throw new Error(detail || `Backend returned ${res.status}`);
  }
}

/** Clear all photos from a project. Does NOT delete local image files. */
export async function clearProjectPhotos(
  projectId: string,
): Promise<{ deleted: number; thumbnails_removed: number }> {
  const url = `${BACKEND_URL}/api/projects/${encodeURIComponent(projectId)}/clear`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const detail = await res.json().then((b) => b.detail).catch(() => null);
    throw new Error(detail || `Backend returned ${res.status}`);
  }
  return res.json();
}

/** Clear all photos from the currently-open project. Does NOT delete local image files. */
export async function clearCurrentProjectPhotos(): Promise<{ deleted: number; thumbnails_removed: number }> {
  const url = `${BACKEND_URL}/api/projects/current/clear`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const detail = await res.json().then((b) => b.detail).catch(() => null);
    throw new Error(detail || `Backend returned ${res.status}`);
  }
  return res.json();
}

/** Get the currently-open project, or null. */
export async function fetchCurrentProject(): Promise<ProjectInfo | null> {
  const url = `${BACKEND_URL}/api/projects/current`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  const data = await res.json();
  return data.project;
}
