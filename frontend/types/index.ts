/**
 * PhotoFlow AI - TypeScript Type Definitions
 */

/** A single photo record returned from the backend API. */
export interface PhotoInfo {
  image_id: string;
  file_name: string;
  file_path: string;
  thumbnail_url: string | null;
  width: number;
  height: number;
  file_size: number;
  star_rating: number | null;
  blur_score: number | null;
  is_blur: number;
  is_rejected: number;
  is_duplicate: number;
  duplicate_group: string | null;
  ai_suggestion: string | null;
}

/** Paginated response from GET /api/photos. */
export interface GetPhotosResponse {
  total: number;
  limit: number;
  offset: number;
  photos: PhotoInfo[];
}

/** Response from GET /api/photo/{image_id}. */
export interface PhotoDetailResponse {
  image_id: string;
  file_name: string;
  file_path: string;
  width: number;
  height: number;
  file_size: number;
  created_time: string;
  thumbnail_path: string | null;
  star_rating: number | null;
  blur_score: number | null;
  is_blur: number;
  is_rejected: number;
  is_duplicate: number;
  duplicate_group: string | null;
  ai_suggestion: string | null;
}

/** Response from PATCH /api/photo/{image_id}/star. */
export interface StarResponse {
  status: string;
  image_id: string;
  star_rating: number;
}

/** Response from POST /api/import. */
export interface ImportResponse {
  success: boolean;
  total: number;
  imported: number;
  skipped: number;
  errors: number;
}

/** Response from GET /api/photos/starred/count. */
export interface StarredCountResponse {
  count: number;
}

/** Response from GET /api/photos/blur/count. */
export interface BlurCountResponse {
  count: number;
}

/** Response from POST /api/ai/blur-detect (now async — returns task_id). */
export interface TaskStartResponse {
  task_id: string;
  total: number;
}

/** Response from GET /api/ai/{blur,duplicate}-progress/{task_id}. */
export interface DetectionProgressResponse {
  task_id: string;
  status: "running" | "completed" | "cancelled" | "error";
  phase: string;
  total: number;
  progress: number;
  current_file: string;
  blurred: number;
  duplicate_groups: number;
  duplicate_count: number;
  failed: number;
}

/** Response from PATCH /api/photo/{image_id}/reject. */
export interface RejectResponse {
  status: string;
  image_id: string;
  is_rejected: number;
}

/** Response from GET /api/photos/rejected/count. */
export interface RejectedCountResponse {
  count: number;
}

/** Response from POST /api/ai/duplicate-detect. */
export interface DuplicateDetectResponse {
  processed: number;
  duplicate_groups: number;
  duplicates: number;
}

/** Response from GET /api/photos/duplicate/count. */
export interface DuplicateCountResponse {
  count: number;
}

/** Response from GET /api/photos/duplicate/group/{group_id}. */
export interface GetPhotosByGroupResponse {
  photos: PhotoInfo[];
  group_id: string;
  total: number;
}

/** Filter mode for the photo grid. */
export type PhotoFilterMode = "all" | "starred" | "blur" | "rejected" | "duplicate" | "suggested";

/** Zoom mode for full-size image preview. */
export type ZoomMode = "fit" | "zoom100";

/** Export mode. */
export type ExportMode = "picked" | "rejected" | "current_filter" | "compare";

/** Response from POST /api/export/start. */
export interface ExportStartResponse {
  export_id: string;
}

/** Response from GET /api/export/progress/{export_id}. */
export interface ExportProgressResponse {
  export_id: string;
  status: "running" | "completed" | "cancelled" | "error";
  total: number;
  succeeded: number;
  failed: number;
  skipped: number;
  current_file: string;
  duration_seconds: number;
}

/** Response from GET /api/export/summary/{export_id}. */
export interface ExportSummaryResponse {
  export_id: string;
  status: string;
  total: number;
  succeeded: number;
  failed: number;
  skipped: number;
  duration_seconds: number;
  errors: string[];
}

/** Response from POST /api/ai/generate-suggestions. */
export interface GenerateSuggestionsResponse {
  processed: number;
  suggestions_generated: number;
  suggestion_counts: Record<string, number>;
}

/** API exposed to the renderer via preload contextBridge. */
export interface ElectronAPI {
  getPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getBackendUrl: () => Promise<string>;
  getPhotoDetail: (imageId: string) => Promise<PhotoDetailResponse>;
  selectDirectory: () => Promise<string | null>;
  importPhotos: (dirPath: string) => Promise<ImportResponse>;
  onMenuImport: (callback: () => void) => (() => void) | undefined;
  updateStarRating: (imageId: string, starRating: number) => Promise<StarResponse>;
  getStarredPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getStarredCount: () => Promise<StarredCountResponse>;
  getBlurPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getBlurCount: () => Promise<BlurCountResponse>;
  runBlurDetection: (photoIds: string[]) => Promise<TaskStartResponse>;
  blurProgress: (taskId: string) => Promise<DetectionProgressResponse>;
  blurCancel: (taskId: string) => Promise<{ status: string }>;
  updateRejectStatus: (imageId: string, isRejected: number) => Promise<RejectResponse>;
  getRejectedPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getRejectedCount: () => Promise<RejectedCountResponse>;
  runDuplicateDetection: (photoIds: string[]) => Promise<TaskStartResponse>;
  duplicateProgress: (taskId: string) => Promise<DetectionProgressResponse>;
  duplicateCancel: (taskId: string) => Promise<{ status: string }>;
  getDuplicatePhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getDuplicateCount: () => Promise<DuplicateCountResponse>;
  getPhotosByGroup: (groupId: string) => Promise<GetPhotosByGroupResponse>;
  generateSuggestions: (photoIds?: string[]) => Promise<GenerateSuggestionsResponse>;
  getSuggestedPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getSuggestedCount: () => Promise<{ count: number }>;
  exportStart: (targetFolder: string, mode: string, photoIds?: string[]) => Promise<ExportStartResponse>;
  exportProgress: (exportId: string) => Promise<ExportProgressResponse>;
  exportCancel: (exportId: string) => Promise<{ status: string }>;
  exportSummary: (exportId: string) => Promise<ExportSummaryResponse>;
}

/** Augment the global Window interface. */
declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
