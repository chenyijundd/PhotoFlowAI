const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getPhotos: (limit, offset) => ipcRenderer.invoke("get-photos", limit, offset),
  getBackendUrl: () => ipcRenderer.invoke("get-backend-url"),
  getPhotoDetail: (imageId) => ipcRenderer.invoke("get-photo-detail", imageId),
  selectDirectory: () => ipcRenderer.invoke("select-directory"),
  importPhotos: (dirPath) => ipcRenderer.invoke("import-photos", dirPath),
  updateStarRating: (imageId, starRating) => ipcRenderer.invoke("update-star-rating", imageId, starRating),
  getStarredPhotos: (limit, offset) => ipcRenderer.invoke("get-starred-photos", limit, offset),
  getStarredCount: () => ipcRenderer.invoke("get-starred-count"),
  fetchCounts: () => ipcRenderer.invoke("fetch-counts"),
  getBlurPhotos: (limit, offset) => ipcRenderer.invoke("get-blur-photos", limit, offset),
  getBlurCount: () => ipcRenderer.invoke("get-blur-count"),
  runBlurDetectionV2: (photoIds, threshold) => ipcRenderer.invoke("run-blur-detection-v2", photoIds, threshold),
  blurProgressV2: (taskId) => ipcRenderer.invoke("blur-progress-v2", taskId),
  blurCancelV2: (taskId) => ipcRenderer.invoke("blur-cancel-v2", taskId),
  runEyeDetection: (photoIds) => ipcRenderer.invoke("run-eye-detection", photoIds),
  eyeProgress: (taskId) => ipcRenderer.invoke("eye-progress", taskId),
  eyeCancel: (taskId) => ipcRenderer.invoke("eye-cancel", taskId),
  getClosedEyePhotos: (limit, offset) => ipcRenderer.invoke("get-closed-eye-photos", limit, offset),
  getClosedEyeCount: () => ipcRenderer.invoke("get-closed-eye-count"),
  runBurstGrouping: (gapSeconds) => ipcRenderer.invoke("run-burst-grouping", gapSeconds),
  burstProgress: (taskId) => ipcRenderer.invoke("burst-progress", taskId),
  burstCancel: (taskId) => ipcRenderer.invoke("burst-cancel", taskId),
  getBurstGroups: () => ipcRenderer.invoke("get-burst-groups"),
  getBurstPhotos: (groupId) => ipcRenderer.invoke("get-burst-photos", groupId),
  getBurstCount: () => ipcRenderer.invoke("get-burst-count"),
  getBurstPhotosList: (limit, offset) => ipcRenderer.invoke("get-burst-photos-list", limit, offset),
  analyzeAll: (photoIds, filterMode) => ipcRenderer.invoke("analyze-all", photoIds, filterMode),
  analyzeProgress: (taskId) => ipcRenderer.invoke("analyze-progress", taskId),
  getUnprocessedPhotos: (limit, offset) => ipcRenderer.invoke("get-unprocessed-photos", limit, offset),
  getUnprocessedCount: () => ipcRenderer.invoke("get-unprocessed-count"),
  getBestPhotosList: (limit, offset) => ipcRenderer.invoke("get-best-photos-list", limit, offset),
  getBestCount: () => ipcRenderer.invoke("get-best-count"),
  burstAcceptBest: (groupId) => ipcRenderer.invoke("burst-accept-best", groupId),
  burstAcceptAll: (groupId) => ipcRenderer.invoke("burst-accept-all", groupId),
  burstRejectAll: (groupId) => ipcRenderer.invoke("burst-reject-all", groupId),
  cullAll: () => ipcRenderer.invoke("cull-all"),
  cullProgress: (taskId) => ipcRenderer.invoke("cull-progress", taskId),
  updateRejectStatus: (imageId, isRejected) => ipcRenderer.invoke("update-reject-status", imageId, isRejected),
  getRejectedPhotos: (limit, offset) => ipcRenderer.invoke("get-rejected-photos", limit, offset),
  getRejectedCount: () => ipcRenderer.invoke("get-rejected-count"),
  getDuplicateCount: () => ipcRenderer.invoke("get-duplicate-count"),
  runDuplicateDetection: (photoIds) => ipcRenderer.invoke("run-duplicate-detection", photoIds),
  duplicateProgress: (taskId) => ipcRenderer.invoke("duplicate-progress", taskId),
  duplicateCancel: (taskId) => ipcRenderer.invoke("duplicate-cancel", taskId),
  getDuplicatePhotos: (limit, offset) => ipcRenderer.invoke("get-duplicate-photos", limit, offset),
  getPhotosByGroup: (groupId) => ipcRenderer.invoke("get-photos-by-group", groupId),
  exportStart: (targetFolder, mode, photoIds, filterMode, nameTemplate, namePrefix, startIndex, exportFormat) => ipcRenderer.invoke("export-start", targetFolder, mode, photoIds, filterMode, nameTemplate, namePrefix, startIndex, exportFormat),
  exportProgress: (exportId) => ipcRenderer.invoke("export-progress", exportId),
  exportCancel: (exportId) => ipcRenderer.invoke("export-cancel", exportId),
  exportSummary: (exportId) => ipcRenderer.invoke("export-summary", exportId),
  // Trash / Photo Deletion
  trashPhoto: (imageId) => ipcRenderer.invoke("trash-photo", imageId),
  restorePhoto: (imageId) => ipcRenderer.invoke("restore-photo", imageId),
  batchTrash: (photoIds) => ipcRenderer.invoke("batch-trash", photoIds),
  batchRestore: (photoIds) => ipcRenderer.invoke("batch-restore", photoIds),
  permanentDeletePhoto: (imageId, includePaired) => ipcRenderer.invoke("permanent-delete-photo", imageId, includePaired),
  getTrashedPhotos: (limit, offset) => ipcRenderer.invoke("get-trashed-photos", limit, offset),
  getTrashedCount: () => ipcRenderer.invoke("get-trashed-count"),
  // Menu
  onMenuImport: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("menu-import", handler);
    return () => ipcRenderer.removeListener("menu-import", handler);
  },
  onMenuClearPhotos: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("menu-clear-photos", handler);
    return () => ipcRenderer.removeListener("menu-clear-photos", handler);
  },
  // Sensitivity presets
  getPresets: () => ipcRenderer.invoke("get-presets"),
  getActivePreset: () => ipcRenderer.invoke("get-active-preset"),
  setActivePreset: (presetId) => ipcRenderer.invoke("set-active-preset", presetId),
});
