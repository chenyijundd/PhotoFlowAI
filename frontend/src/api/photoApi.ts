/**
 * PhotoFlow AI - Photo API Client
 *
 * Provides functions to fetch photo data from the backend.
 * In Electron, requests are routed through IPC; in the browser
 * (dev mode), requests go directly to the FastAPI backend.
 */

import type { GetPhotosResponse, PhotoDetailResponse, StarResponse, CountsResponse, TaskStartResponse, DetectionProgressResponse, RejectResponse, GetPhotosByGroupResponse, BurstOpResponse, OneClickCullResponse, CullProgressResponse, ExportStartResponse, ExportProgressResponse, ExportSummaryResponse, AISummaryResponse, BatchUpdateRequest, BatchUpdateResponse, TrashResponse, PermanentDeleteResponse, AnalyzeStreamCallbacks, AnalyzeStepStartData, AnalyzeProgressData, AnalyzeStepCompleteData, AnalyzeTaskCompleteData, CullStreamCallbacks } from "../../types";

/** Backend API base URL. */
const BACKEND_URL = "http://127.0.0.1:8765";

/** Build the URL for a full-size image by image_id.
 *  When `width` is provided, the backend resizes on-the-fly (≈200 KB
 *  instead of 10 MB for a typical 24 MP JPEG).  Omit `width` for the
 *  full original (e.g. export). */
export function fullsizeUrl(imageId: string, width?: number): string {
  const base = `${BACKEND_URL}/api/fullsize/${encodeURIComponent(imageId)}`;
  if (width && width > 0) {
    return `${base}?width=${width}`;
  }
  return base;
}

/** Fetch paginated photos from the backend. */
export async function fetchPhotos(
  limit: number = 100,
  offset: number = 0
): Promise<GetPhotosResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getPhotos(limit, offset);
  }
  const url = `${BACKEND_URL}/api/photos?limit=${limit}&offset=${offset}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Fetch a single photo's detail from the backend. */
export async function fetchPhotoDetail(
  imageId: string
): Promise<PhotoDetailResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getPhotoDetail(imageId);
  }
  const url = `${BACKEND_URL}/api/photo/${encodeURIComponent(imageId)}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Update star rating (0 or 1) for a photo. */
export async function updateStarRating(
  imageId: string,
  starRating: number
): Promise<StarResponse> {
  if (window.electronAPI) {
    return window.electronAPI.updateStarRating(imageId, starRating);
  }
  const url = `${BACKEND_URL}/api/photo/${encodeURIComponent(imageId)}/star`;
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ star_rating: starRating }),
  });
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Fetch starred photos (star_rating == 1) with pagination. */
export async function fetchStarredPhotos(
  limit: number = 100,
  offset: number = 0
): Promise<GetPhotosResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getStarredPhotos(limit, offset);
  }
  const url = `${BACKEND_URL}/api/photos/starred?limit=${limit}&offset=${offset}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Fetch blur photos (is_blur == 1) with pagination. */
export async function fetchBlurPhotos(
  limit: number = 100,
  offset: number = 0
): Promise<GetPhotosResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getBlurPhotos(limit, offset);
  }
  const url = `${BACKEND_URL}/api/photos/blur?limit=${limit}&offset=${offset}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Fetch all filter counts in a single request. */
export async function fetchCounts(): Promise<CountsResponse> {
  if (window.electronAPI) {
    return window.electronAPI.fetchCounts();
  }
  const url = `${BACKEND_URL}/api/photos/counts`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Update reject status (0 or 1) for a photo. */
export async function updateRejectStatus(
  imageId: string,
  isRejected: number
): Promise<RejectResponse> {
  if (window.electronAPI) {
    return window.electronAPI.updateRejectStatus(imageId, isRejected);
  }
  const url = `${BACKEND_URL}/api/photo/${encodeURIComponent(imageId)}/reject`;
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_rejected: isRejected }),
  });
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Fetch rejected photos (is_rejected == 1) with pagination. */
export async function fetchRejectedPhotos(
  limit: number = 100,
  offset: number = 0
): Promise<GetPhotosResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getRejectedPhotos(limit, offset);
  }
  const url = `${BACKEND_URL}/api/photos/rejected?limit=${limit}&offset=${offset}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Fetch duplicate photos (is_duplicate == 1) with pagination. */
export async function fetchDuplicatePhotos(
  limit: number = 100,
  offset: number = 0
): Promise<GetPhotosResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getDuplicatePhotos(limit, offset);
  }
  const url = `${BACKEND_URL}/api/photos/duplicate?limit=${limit}&offset=${offset}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Fetch all photos in a specific duplicate group. */
export async function fetchPhotosByGroup(groupId: string): Promise<GetPhotosByGroupResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getPhotosByGroup(groupId);
  }
  const url = `${BACKEND_URL}/api/photos/duplicate/group/${encodeURIComponent(groupId)}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Start an export. Returns export_id for polling. */
export async function exportStart(
  targetFolder: string,
  mode: string,
  photoIds?: string[],
  filterMode?: string,
  nameTemplate?: string,
  namePrefix?: string,
  startIndex?: number,
  exportFormat?: string,
): Promise<ExportStartResponse> {
  if (window.electronAPI) {
    return window.electronAPI.exportStart(
      targetFolder, mode, photoIds, filterMode,
      nameTemplate, namePrefix, startIndex, exportFormat,
    );
  }
  const body = JSON.stringify({
    target_folder: targetFolder,
    mode,
    photo_ids: photoIds || null,
    filter_mode: filterMode || null,
    name_template: nameTemplate || null,
    name_prefix: namePrefix || null,
    start_index: startIndex ?? null,
    export_format: exportFormat || "original",
  });
  const url = `${BACKEND_URL}/api/export/start`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Poll export progress. */
export async function exportProgress(exportId: string): Promise<ExportProgressResponse> {
  if (window.electronAPI) {
    return window.electronAPI.exportProgress(exportId);
  }
  const url = `${BACKEND_URL}/api/export/progress/${exportId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Cancel a running export. */
export async function exportCancel(exportId: string): Promise<{ status: string }> {
  if (window.electronAPI) {
    return window.electronAPI.exportCancel(exportId);
  }
  const url = `${BACKEND_URL}/api/export/cancel/${exportId}`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Get final export summary. */
export async function exportSummary(exportId: string): Promise<ExportSummaryResponse> {
  if (window.electronAPI) {
    return window.electronAPI.exportSummary(exportId);
  }
  const url = `${BACKEND_URL}/api/export/summary/${exportId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Fetch photos in a specific burst group. */
export async function fetchBurstPhotos(groupId: string): Promise<GetPhotosByGroupResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getBurstPhotos(groupId);
  }
  const url = `${BACKEND_URL}/api/photos/burst/${encodeURIComponent(groupId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Fetch photos in any burst group (for burst filter mode). */
export async function fetchBurstPhotosList(
  limit: number = 100,
  offset: number = 0
): Promise<GetPhotosResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getBurstPhotosList(limit, offset);
  }
  const url = `${BACKEND_URL}/api/photos/burst?limit=${limit}&offset=${offset}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Start combined AI analysis (blur -> duplicate -> burst -> best).
 *  Pass photoIds to scope to specific photos, or filterMode for server-side resolution. */
export async function analyzeAll(photoIds?: string[], filterMode?: string): Promise<TaskStartResponse> {
  if (window.electronAPI) return window.electronAPI.analyzeAll(photoIds, filterMode);
  const res = await fetch(`${BACKEND_URL}/api/ai/analyze-all`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds ?? null, filter_mode: filterMode ?? null }),
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Poll analyze-all progress. */
export async function analyzeProgress(taskId: string): Promise<DetectionProgressResponse> {
  if (window.electronAPI) return window.electronAPI.analyzeProgress(taskId);
  const res = await fetch(`${BACKEND_URL}/api/ai/analyze-progress/${taskId}`);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Fetch unprocessed photos. */
export async function fetchUnprocessedPhotos(limit = 100, offset = 0): Promise<GetPhotosResponse> {
  if (window.electronAPI) return window.electronAPI.getUnprocessedPhotos(limit, offset);
  const res = await fetch(`${BACKEND_URL}/api/photos/unprocessed?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Fetch best-in-burst photos (for best filter mode). */
export async function fetchBestPhotosList(
  limit: number = 100,
  offset: number = 0
): Promise<GetPhotosResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getBestPhotosList(limit, offset);
  }
  const url = `${BACKEND_URL}/api/photos/best?limit=${limit}&offset=${offset}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Accept best photo in a burst group, reject the rest. */
export async function acceptBestInBurst(groupId: string): Promise<BurstOpResponse> {
  if (window.electronAPI) {
    return window.electronAPI.burstAcceptBest(groupId);
  }
  const url = `${BACKEND_URL}/api/burst/${encodeURIComponent(groupId)}/accept-best`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Accept all photos in a burst group. */
export async function acceptAllInBurst(groupId: string): Promise<BurstOpResponse> {
  if (window.electronAPI) {
    return window.electronAPI.burstAcceptAll(groupId);
  }
  const url = `${BACKEND_URL}/api/burst/${encodeURIComponent(groupId)}/accept-all`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Reject all photos in a burst group. */
export async function rejectAllInBurst(groupId: string): Promise<BurstOpResponse> {
  if (window.electronAPI) {
    return window.electronAPI.burstRejectAll(groupId);
  }
  const url = `${BACKEND_URL}/api/burst/${encodeURIComponent(groupId)}/reject-all`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Comprehensive one-click cull: blur + duplicate + burst (async). */
export async function cullAll(): Promise<TaskStartResponse> {
  if (window.electronAPI) {
    return window.electronAPI.cullAll();
  }
  const url = `${BACKEND_URL}/api/photos/cull-all`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    // Extract FastAPI error detail from the response body
    const detail = await res.json().then((b) => b.detail).catch(() => null);
    throw new Error(detail || `后端返回 ${res.status}`);
  }
  return res.json();
}

/** Poll one-click cull progress. */
export async function cullProgress(taskId: string): Promise<CullProgressResponse> {
  if (window.electronAPI) {
    return window.electronAPI.cullProgress(taskId);
  }
  const url = `${BACKEND_URL}/api/photos/cull-progress/${taskId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Fetch closed-eye photos (is_closed_eye == 1) with pagination. */
export async function fetchClosedEyePhotos(
  limit: number = 100,
  offset: number = 0
): Promise<GetPhotosResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getClosedEyePhotos(limit, offset);
  }
  const url = `${BACKEND_URL}/api/photos/closed-eye?limit=${limit}&offset=${offset}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Fetch AI analysis summary statistics. */
export async function fetchAISummary(): Promise<AISummaryResponse> {
  const url = `${BACKEND_URL}/api/ai/summary`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Batch update star_rating and/or is_rejected for multiple photos. */
export async function batchUpdate(body: BatchUpdateRequest): Promise<BatchUpdateResponse> {
  const url = `${BACKEND_URL}/api/photos/batch-update`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

// ---- SSE (Server-Sent Events) stream connections ----
// These bypass Electron IPC and connect directly to the backend
// because EventSource requires a persistent streaming HTTP connection.

/**
 * Connect to the analyze-all SSE stream.
 * Returns a cleanup function that closes the EventSource.
 */
export function connectAnalyzeStream(
  taskId: string,
  callbacks: AnalyzeStreamCallbacks,
): () => void {
  const es = new EventSource(`${BACKEND_URL}/api/ai/analyze-stream/${taskId}`);

  es.addEventListener("step_start", (e: MessageEvent) => {
    callbacks.onStepStart(JSON.parse(e.data) as AnalyzeStepStartData);
  });
  es.addEventListener("progress", (e: MessageEvent) => {
    callbacks.onProgress(JSON.parse(e.data) as AnalyzeProgressData);
  });
  es.addEventListener("step_complete", (e: MessageEvent) => {
    callbacks.onStepComplete(JSON.parse(e.data) as AnalyzeStepCompleteData);
  });
  es.addEventListener("task_complete", (e: MessageEvent) => {
    callbacks.onTaskComplete(JSON.parse(e.data) as AnalyzeTaskCompleteData);
    es.close();
  });
  es.addEventListener("task_cancelled", () => {
    callbacks.onTaskCancelled();
    es.close();
  });
  es.addEventListener("task_error", (e: MessageEvent) => {
    callbacks.onTaskError(JSON.parse(e.data).error || "Unknown error");
    es.close();
  });

  return () => es.close();
}

/**
 * Connect to the cull SSE stream.
 * Returns a cleanup function that closes the EventSource.
 */
export function connectCullStream(
  taskId: string,
  callbacks: CullStreamCallbacks,
): () => void {
  const es = new EventSource(`${BACKEND_URL}/api/photos/cull-stream/${taskId}`);

  es.addEventListener("step_start", (e: MessageEvent) => {
    callbacks.onStepStart(JSON.parse(e.data));
  });
  es.addEventListener("progress", (e: MessageEvent) => {
    callbacks.onProgress(JSON.parse(e.data));
  });
  es.addEventListener("step_complete", (e: MessageEvent) => {
    callbacks.onStepComplete(JSON.parse(e.data));
  });
  es.addEventListener("task_complete", (e: MessageEvent) => {
    callbacks.onTaskComplete(JSON.parse(e.data) as OneClickCullResponse);
    es.close();
  });
  es.addEventListener("task_cancelled", () => {
    callbacks.onTaskCancelled();
    es.close();
  });
  es.addEventListener("task_error", (e: MessageEvent) => {
    callbacks.onTaskError(JSON.parse(e.data).error || "Unknown error");
    es.close();
  });

  return () => es.close();
}

/** Cancel a running analyze-all task. */
export async function cancelAnalyze(taskId: string): Promise<{ status: string }> {
  const url = `${BACKEND_URL}/api/ai/analyze-cancel/${taskId}`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Cancel a running cull task. */
export async function cancelCull(taskId: string): Promise<{ status: string }> {
  const url = `${BACKEND_URL}/api/photos/cull-cancel/${taskId}`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

// ---- Trash / Photo Deletion ----

/** Move a photo to trash (soft delete). */
export async function trashPhoto(imageId: string): Promise<TrashResponse> {
  if (window.electronAPI) {
    return window.electronAPI.trashPhoto(imageId);
  }
  const url = `${BACKEND_URL}/api/photo/${encodeURIComponent(imageId)}/trash`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const detail = await res.json().then((b) => b.detail).catch(() => null);
    throw new Error(detail || `Backend returned ${res.status}`);
  }
  return res.json();
}

/** Restore a photo from trash. */
export async function restorePhoto(imageId: string): Promise<TrashResponse> {
  if (window.electronAPI) {
    return window.electronAPI.restorePhoto(imageId);
  }
  const url = `${BACKEND_URL}/api/photo/${encodeURIComponent(imageId)}/restore`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const detail = await res.json().then((b) => b.detail).catch(() => null);
    throw new Error(detail || `Backend returned ${res.status}`);
  }
  return res.json();
}

/** Batch move photos to trash. */
export async function batchTrash(photoIds: string[]): Promise<BatchUpdateResponse> {
  if (window.electronAPI) {
    return window.electronAPI.batchTrash(photoIds);
  }
  const url = `${BACKEND_URL}/api/photos/batch-trash`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds }),
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Batch restore photos from trash. */
export async function batchRestore(photoIds: string[]): Promise<BatchUpdateResponse> {
  if (window.electronAPI) {
    return window.electronAPI.batchRestore(photoIds);
  }
  const url = `${BACKEND_URL}/api/photos/batch-restore`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds }),
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Permanently delete a photo from trash (moves files to system recycle bin). */
export async function permanentDeletePhoto(
  imageId: string,
  includePaired: boolean = true,
): Promise<PermanentDeleteResponse> {
  if (window.electronAPI) {
    return window.electronAPI.permanentDeletePhoto(imageId, includePaired);
  }
  const url = `${BACKEND_URL}/api/photo/${encodeURIComponent(imageId)}/permanent?include_paired=${includePaired}`;
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.json().then((b) => b.detail).catch(() => null);
    throw new Error(detail || `Backend returned ${res.status}`);
  }
  return res.json();
}

/** Fetch trashed photos with pagination. */
export async function fetchTrashedPhotos(
  limit: number = 100,
  offset: number = 0,
): Promise<GetPhotosResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getTrashedPhotos(limit, offset);
  }
  const url = `${BACKEND_URL}/api/photos/trashed?limit=${limit}&offset=${offset}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

