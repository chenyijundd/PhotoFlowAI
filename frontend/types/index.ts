/**
 * PhotoFlow AI - TypeScript Type Definitions
 */

/** A single photo record returned from the backend API. */
export interface PhotoInfo {
  image_id: string;
  file_name: string;
  file_path: string;
  raw_preview_path: string | null;
  thumbnail_url: string | null;
  width: number;
  height: number;
  file_size: number;
  star_rating: number | null;
  blur_score: number | null;
  is_blur: number;
  eye_score: number | null;
  is_closed_eye: number;
  is_rejected: number;
  is_duplicate: number;
  duplicate_group: string | null;
  burst_group: string | null;
  burst_position: number | null;
  burst_total: number | null;
  is_best_in_burst: number;
  is_best_in_duplicate: number;
  raw_jpeg_pair_id: string | null;
  deleted_at: string | null;
}

/** Response from POST /api/photo/{id}/trash or /restore. */
export interface TrashResponse {
  status: string;
  image_id: string;
  deleted?: boolean;
  restored?: boolean;
  message?: string;
}

/** Response from DELETE /api/photo/{id}/permanent. */
export interface PermanentDeleteResponse {
  status: string;
  deleted_ids: string[];
  files_trashed: number;
  thumbnails_removed: number;
  error?: string | null;
}

/** Paginated response from GET /api/photos. */
export interface GetPhotosResponse {
  total: number;
  limit: number;
  offset: number;
  photos: PhotoInfo[];
}

/** A single member entry in a RAW+JPEG pair group. */
export interface RawJpegPairMember {
  image_id: string;
  file_name: string;
  is_raw: boolean;
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
  eye_score: number | null;
  is_closed_eye: number;
  is_rejected: number;
  is_duplicate: number;
  duplicate_group: string | null;
  burst_group: string | null;
  burst_position: number | null;
  burst_total: number | null;
  is_best_in_burst: number;
  is_best_in_duplicate: number;
  raw_jpeg_pair_id: string | null;
  raw_jpeg_pair_members: RawJpegPairMember[] | null;
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
  removed?: number;
  raw_count?: number;
  pair_count?: number;
}

/** Response from GET /api/photos/starred/count. */
export interface StarredCountResponse {
  count: number;
}

/** Response from GET /api/photos/blur/count. */
export interface BlurCountResponse {
  count: number;
}

/** Response from GET /api/photos/counts (batch count endpoint — basic + AI category). */
export interface CountsResponse {
  all: number;
  starred: number;
  unprocessed: number;
  rejected: number;
  trash_count: number;
  blur_count: number;
  closed_eye_count: number;
  duplicate_count: number;
  burst_group_count: number;
  burst_photo_count: number;
  best_count: number;
  clean_count: number;
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
export type PhotoFilterMode = "all" | "starred" | "unprocessed" | "rejected" | "trash";

/** AI category filter for the photo grid (applied on top of filterMode).
 *  Order matches the detection cascade: closed_eye → blur → burst → duplicate → best */
export type AICategory = null | "closed_eye" | "blur" | "burst" | "duplicate" | "best";

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

/** Response from GET /api/photos/bursts/count. */
export interface BurstCountResponse {
  count: number;
}

/** Response from GET /api/photos/best/count. */
export interface BestCountResponse {
  count: number;
}

/** Summary entry for a single burst group. */
export interface BurstGroupEntry {
  group_id: string;
  photo_count: number;
  photo_ids: string[];
}

/** Response from GET /api/photos/bursts. */
export interface BurstGroupsResponse {
  burst_groups: BurstGroupEntry[];
  total: number;
}

/** Response from burst per-group operations. */
export interface BurstOpResponse {
  group_id: string;
  accepted: number;
  rejected: number;
  unchanged: number;
}

/** Response from GET /api/photos/closed-eye/count. */
export interface EyeClosedCountResponse {
  count: number;
}

/** Response from GET /api/ai/summary — AI analysis statistics snapshot. */
export interface AISummaryResponse {
  total_analyzed: number;
  closed_eye_count: number;
  blur_count: number;
  burst_group_count: number;
  burst_photo_count: number;
  duplicate_group_count: number;
  duplicate_photo_count: number;
  best_count: number;
  clean_count: number;
}

/** Request body for POST /api/photos/batch-update. */
export interface BatchUpdateRequest {
  photo_ids: string[];
  star_rating?: number;
  is_rejected?: number;
}

/** Response from POST /api/photos/batch-update. */
export interface BatchUpdateResponse {
  updated: number;
}

/** Response from POST /api/photos/cull-all (comprehensive one-click cull). */
export interface OneClickCullResponse {
  eye_closed_rejected: number;
  blur_flagged: number;
  duplicate_rejected: number;
  duplicate_best_kept: number;
  burst_accepted: number;
  burst_rejected: number;
  clean_accepted: number;
  total_accepted: number;
  total_rejected: number;
  untouched: number;
  total_photos: number;
}

/** Progress response from GET /api/photos/cull-progress/{task_id}. */
export interface CullProgressResponse {
  task_id: string;
  status: "running" | "completed" | "cancelled" | "error";
  phase: string;
  total: number;
  progress: number;
  result: OneClickCullResponse | null;
  error: string | null;
}

// ---- SSE stream event types ----

/** Single SSE event from /api/ai/analyze-stream/{task_id}. */
export interface AnalyzeStreamEvent {
  event: "step_start" | "progress" | "step_complete" | "task_complete" | "task_cancelled" | "task_error";
  data: AnalyzeStepStartData | AnalyzeProgressData | AnalyzeStepCompleteData | AnalyzeTaskCompleteData | Record<string, never>;
}

export interface AnalyzeStepStartData {
  step: string;
  phase: string;
  total: number;
}

export interface AnalyzeProgressData {
  step: string;
  phase: string;
  progress: number;
  total: number;
  current_file: string;
}

export interface AnalyzeStepCompleteData {
  step: string;
  closed_eye_count?: number;
  blur_count?: number;
  burst_group_count?: number;
  burst_photo_count?: number;
  duplicate_group_count?: number;
  duplicate_photo_count?: number;
  best_count?: number;
}

export interface AnalyzeTaskCompleteData {
  total_analyzed: number;
  closed_eye_count: number;
  blur_count: number;
  burst_group_count: number;
  burst_photo_count: number;
  duplicate_group_count: number;
  duplicate_photo_count: number;
  best_count: number;
  clean_count: number;
}

/** Callbacks for SSE analyze-all stream. */
export interface AnalyzeStreamCallbacks {
  onStepStart: (data: AnalyzeStepStartData) => void;
  onProgress: (data: AnalyzeProgressData) => void;
  onStepComplete: (data: AnalyzeStepCompleteData) => void;
  onTaskComplete: (data: AnalyzeTaskCompleteData) => void;
  onTaskCancelled: () => void;
  onTaskError: (error: string) => void;
}

/** SSE event data for cull step completion. */
export interface CullStepCompleteData {
  step: string;
  [key: string]: number | string;
}

/** Callbacks for SSE cull stream. */
export interface CullStreamCallbacks {
  onStepStart: (data: { step: string; phase: string; total: number }) => void;
  onProgress: (data: { step: string; phase: string; progress: number; total: number }) => void;
  onStepComplete: (data: CullStepCompleteData) => void;
  onTaskComplete: (data: OneClickCullResponse) => void;
  onTaskCancelled: () => void;
  onTaskError: (error: string) => void;
}

/** API exposed to the renderer via preload contextBridge. */
export interface ElectronAPI {
  getPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getBackendUrl: () => Promise<string>;
  getPhotoDetail: (imageId: string) => Promise<PhotoDetailResponse>;
  selectDirectory: () => Promise<string | null>;
  importPhotos: (dirPath: string) => Promise<ImportResponse>;
  onMenuImport: (callback: () => void) => (() => void) | undefined;
  onMenuClearPhotos: (callback: () => void) => (() => void) | undefined;
  updateStarRating: (imageId: string, starRating: number) => Promise<StarResponse>;
  getStarredPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getStarredCount: () => Promise<StarredCountResponse>;
  fetchCounts: () => Promise<CountsResponse>;
  getBlurPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getBlurCount: () => Promise<BlurCountResponse>;
  runBlurDetectionV2: (photoIds: string[], threshold?: number) => Promise<TaskStartResponse>;
  blurProgressV2: (taskId: string) => Promise<DetectionProgressResponse>;
  blurCancelV2: (taskId: string) => Promise<{ status: string }>;
  runEyeDetection: (photoIds: string[]) => Promise<TaskStartResponse>;
  eyeProgress: (taskId: string) => Promise<DetectionProgressResponse>;
  eyeCancel: (taskId: string) => Promise<{ status: string }>;
  getClosedEyePhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getClosedEyeCount: () => Promise<EyeClosedCountResponse>;
  runBurstGrouping: (gapSeconds?: number) => Promise<TaskStartResponse>;
  burstProgress: (taskId: string) => Promise<DetectionProgressResponse>;
  burstCancel: (taskId: string) => Promise<{ status: string }>;
  getBurstGroups: () => Promise<BurstGroupsResponse>;
  getBurstPhotos: (groupId: string) => Promise<GetPhotosByGroupResponse>;
  getBurstCount: () => Promise<BurstCountResponse>;
  getBurstPhotosList: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  analyzeAll: (photoIds?: string[], filterMode?: string) => Promise<TaskStartResponse>;
  analyzeProgress: (taskId: string) => Promise<DetectionProgressResponse>;
  getUnprocessedPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getUnprocessedCount: () => Promise<{ count: number }>;
  getBestPhotosList: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getBestCount: () => Promise<BestCountResponse>;
  burstAcceptBest: (groupId: string) => Promise<BurstOpResponse>;
  burstAcceptAll: (groupId: string) => Promise<BurstOpResponse>;
  burstRejectAll: (groupId: string) => Promise<BurstOpResponse>;
  cullAll: () => Promise<TaskStartResponse>;
  cullProgress: (taskId: string) => Promise<CullProgressResponse>;
  updateRejectStatus: (imageId: string, isRejected: number) => Promise<RejectResponse>;
  getRejectedPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getRejectedCount: () => Promise<RejectedCountResponse>;
  runDuplicateDetection: (photoIds: string[]) => Promise<TaskStartResponse>;
  duplicateProgress: (taskId: string) => Promise<DetectionProgressResponse>;
  duplicateCancel: (taskId: string) => Promise<{ status: string }>;
  getDuplicatePhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getDuplicateCount: () => Promise<DuplicateCountResponse>;
  getPhotosByGroup: (groupId: string) => Promise<GetPhotosByGroupResponse>;
  exportStart: (targetFolder: string, mode: string, photoIds?: string[], filterMode?: string, nameTemplate?: string, namePrefix?: string, startIndex?: number, exportFormat?: string) => Promise<ExportStartResponse>;
  exportProgress: (exportId: string) => Promise<ExportProgressResponse>;
  exportCancel: (exportId: string) => Promise<{ status: string }>;
  exportSummary: (exportId: string) => Promise<ExportSummaryResponse>;
  // Trash / Photo Deletion
  trashPhoto: (imageId: string) => Promise<TrashResponse>;
  restorePhoto: (imageId: string) => Promise<TrashResponse>;
  batchTrash: (photoIds: string[]) => Promise<BatchUpdateResponse>;
  batchRestore: (photoIds: string[]) => Promise<BatchUpdateResponse>;
  permanentDeletePhoto: (imageId: string, includePaired?: boolean) => Promise<PermanentDeleteResponse>;
  getTrashedPhotos: (limit?: number, offset?: number) => Promise<GetPhotosResponse>;
  getTrashedCount: () => Promise<{ count: number }>;
}

/** Augment the global Window interface. */
declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
