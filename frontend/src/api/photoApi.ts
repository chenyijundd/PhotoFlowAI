/**
 * PhotoFlow AI - Photo API Client
 *
 * Provides functions to fetch photo data from the backend.
 * In Electron, requests are routed through IPC; in the browser
 * (dev mode), requests go directly to the FastAPI backend.
 */

import type { GetPhotosResponse, PhotoDetailResponse, StarResponse, StarredCountResponse, BlurCountResponse, CountsResponse, TaskStartResponse, DetectionProgressResponse, RejectResponse, RejectedCountResponse, DuplicateCountResponse, GetPhotosByGroupResponse, BurstCountResponse, BurstGroupsResponse, BestCountResponse, BurstOpResponse, OneClickCullResponse, CullProgressResponse, ExportStartResponse, ExportProgressResponse, ExportSummaryResponse, EyeClosedCountResponse, AISummaryResponse, BatchUpdateRequest, BatchUpdateResponse } from "../../types";

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

/** Start blur detection (multi-patch, content-aware). */
export async function runBlurDetectionV2(
  photoIds: string[],
  threshold?: number
): Promise<TaskStartResponse> {
  if (window.electronAPI) {
    return window.electronAPI.runBlurDetectionV2(photoIds, threshold);
  }
  const url = `${BACKEND_URL}/api/ai/blur-detect-v2`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds, threshold: threshold ?? null }),
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Poll blur detection V2 progress. */
export async function blurProgressV2(taskId: string): Promise<DetectionProgressResponse> {
  if (window.electronAPI) {
    return window.electronAPI.blurProgressV2(taskId);
  }
  const url = `${BACKEND_URL}/api/ai/blur-progress-v2/${taskId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Cancel blur detection V2. */
export async function blurCancelV2(taskId: string): Promise<{ status: string }> {
  if (window.electronAPI) {
    return window.electronAPI.blurCancelV2(taskId);
  }
  const url = `${BACKEND_URL}/api/ai/blur-cancel-v2/${taskId}`;
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
  console.log("[exportStart] JSON body:", body);
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

/** Start burst grouping (async — returns task_id). */
export async function runBurstGrouping(
  gapSeconds?: number
): Promise<TaskStartResponse> {
  if (window.electronAPI) {
    return window.electronAPI.runBurstGrouping(gapSeconds);
  }
  const url = `${BACKEND_URL}/api/ai/burst-group`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gap_seconds: gapSeconds ?? null }),
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Poll burst grouping progress. */
export async function burstProgress(taskId: string): Promise<DetectionProgressResponse> {
  if (window.electronAPI) {
    return window.electronAPI.burstProgress(taskId);
  }
  const url = `${BACKEND_URL}/api/ai/burst-progress/${taskId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Cancel burst grouping. */
export async function burstCancel(taskId: string): Promise<{ status: string }> {
  if (window.electronAPI) {
    return window.electronAPI.burstCancel(taskId);
  }
  const url = `${BACKEND_URL}/api/ai/burst-cancel/${taskId}`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Fetch all burst groups summary. */
export async function fetchBurstGroups(): Promise<BurstGroupsResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getBurstGroups();
  }
  const url = `${BACKEND_URL}/api/photos/bursts`;
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

/** Fetch burst group count. */
export async function fetchBurstCount(): Promise<BurstCountResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getBurstCount();
  }
  const url = `${BACKEND_URL}/api/photos/bursts/count`;
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

/** Fetch unprocessed count. */
export async function fetchUnprocessedCount(): Promise<{ count: number }> {
  if (window.electronAPI) return window.electronAPI.getUnprocessedCount();
  const res = await fetch(`${BACKEND_URL}/api/photos/unprocessed/count`);
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

/** Fetch best-in-burst count. */
export async function fetchBestCount(): Promise<BestCountResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getBestCount();
  }
  const url = `${BACKEND_URL}/api/photos/best/count`;
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
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
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

/** Fetch the count of closed-eye photos. */
export async function fetchClosedEyeCount(): Promise<EyeClosedCountResponse> {
  if (window.electronAPI) {
    return window.electronAPI.getClosedEyeCount();
  }
  const url = `${BACKEND_URL}/api/photos/closed-eye/count`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Start eye detection (closed / half-closed eyes). */
export async function runEyeDetection(
  photoIds: string[]
): Promise<TaskStartResponse> {
  if (window.electronAPI) {
    return window.electronAPI.runEyeDetection(photoIds);
  }
  const url = `${BACKEND_URL}/api/ai/eye-detect`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds }),
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Poll eye detection progress. */
export async function eyeProgress(taskId: string): Promise<DetectionProgressResponse> {
  if (window.electronAPI) {
    return window.electronAPI.eyeProgress(taskId);
  }
  const url = `${BACKEND_URL}/api/ai/eye-progress/${taskId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

/** Cancel eye detection. */
export async function eyeCancel(taskId: string): Promise<{ status: string }> {
  if (window.electronAPI) {
    return window.electronAPI.eyeCancel(taskId);
  }
  const url = `${BACKEND_URL}/api/ai/eye-cancel/${taskId}`;
  const res = await fetch(url, { method: "POST" });
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

