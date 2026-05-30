/**
 * PhotoFlow AI - Photo API Client
 *
 * Provides functions to fetch photo data from the backend.
 * In Electron, requests are routed through IPC; in the browser
 * (dev mode), requests go directly to the FastAPI backend.
 */

import type { GetPhotosResponse, PhotoDetailResponse, StarResponse, StarredCountResponse, BlurCountResponse, TaskStartResponse, DetectionProgressResponse, RejectResponse, RejectedCountResponse, DuplicateCountResponse, GetPhotosByGroupResponse, GenerateSuggestionsResponse, ExportStartResponse, ExportProgressResponse, ExportSummaryResponse } from "../../types";

/** Backend API base URL. */
const BACKEND_URL = "http://127.0.0.1:8765";

/** Build the URL for a full-size original image by image_id. */
export function fullsizeUrl(imageId: string): string {
  return `${BACKEND_URL}/api/fullsize/${encodeURIComponent(imageId)}`;
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

/** Fetch the count of blur photos. */
export async function fetchBlurCount(): Promise<BlurCountResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getBlurCount();
  }
  const url = `${BACKEND_URL}/api/photos/blur/count`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Start blur detection (async — returns task_id). */
export async function runBlurDetection(
  photoIds: string[]
): Promise<TaskStartResponse> {
  if (window.electronAPI) {
    return window.electronAPI.runBlurDetection(photoIds);
  }
  const url = `${BACKEND_URL}/api/ai/blur-detect`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds }),
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Poll blur detection progress. */
export async function blurProgress(taskId: string): Promise<DetectionProgressResponse> {
  if (window.electronAPI) {
    return window.electronAPI.blurProgress(taskId);
  }
  const url = `${BACKEND_URL}/api/ai/blur-progress/${taskId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Cancel blur detection. */
export async function blurCancel(taskId: string): Promise<{ status: string }> {
  if (window.electronAPI) {
    return window.electronAPI.blurCancel(taskId);
  }
  const url = `${BACKEND_URL}/api/ai/blur-cancel/${taskId}`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Fetch the count of starred photos. */
export async function fetchStarredCount(): Promise<StarredCountResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getStarredCount();
  }
  const url = `${BACKEND_URL}/api/photos/starred/count`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
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

/** Fetch the count of rejected photos. */
export async function fetchRejectedCount(): Promise<RejectedCountResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getRejectedCount();
  }
  const url = `${BACKEND_URL}/api/photos/rejected/count`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Start duplicate detection (async — returns task_id). */
export async function runDuplicateDetection(
  photoIds: string[]
): Promise<TaskStartResponse> {
  if (window.electronAPI) {
    return window.electronAPI.runDuplicateDetection(photoIds);
  }
  const url = `${BACKEND_URL}/api/ai/duplicate-detect`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds }),
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Poll duplicate detection progress. */
export async function duplicateProgress(taskId: string): Promise<DetectionProgressResponse> {
  if (window.electronAPI) {
    return window.electronAPI.duplicateProgress(taskId);
  }
  const url = `${BACKEND_URL}/api/ai/duplicate-progress/${taskId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Cancel duplicate detection. */
export async function duplicateCancel(taskId: string): Promise<{ status: string }> {
  if (window.electronAPI) {
    return window.electronAPI.duplicateCancel(taskId);
  }
  const url = `${BACKEND_URL}/api/ai/duplicate-cancel/${taskId}`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
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

/** Fetch the count of duplicate photos. */
export async function fetchDuplicateCount(): Promise<DuplicateCountResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getDuplicateCount();
  }
  const url = `${BACKEND_URL}/api/photos/duplicate/count`;
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

/** Generate AI suggestions for all photos (or a subset). */
export async function generateSuggestions(
  photoIds?: string[]
): Promise<GenerateSuggestionsResponse> {
  if (window.electronAPI) {
    return window.electronAPI.generateSuggestions(photoIds);
  }
  const url = `${BACKEND_URL}/api/ai/generate-suggestions`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds || null }),
  });
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Fetch photos with AI suggestions with pagination. */
export async function fetchSuggestedPhotos(
  limit: number = 100,
  offset: number = 0
): Promise<GetPhotosResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getSuggestedPhotos(limit, offset);
  }
  const url = `${BACKEND_URL}/api/photos/suggested?limit=${limit}&offset=${offset}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json();
}

/** Fetch the count of photos with AI suggestions. */
export async function fetchSuggestedCount(): Promise<{ count: number }> {
  if (window.electronAPI) {
    return window.electronAPI.getSuggestedCount();
  }
  const url = `${BACKEND_URL}/api/photos/suggested/count`;
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
  photoIds?: string[]
): Promise<ExportStartResponse> {
  if (window.electronAPI) {
    return window.electronAPI.exportStart(targetFolder, mode, photoIds);
  }
  const url = `${BACKEND_URL}/api/export/start`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_folder: targetFolder, mode, photo_ids: photoIds || null }),
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
