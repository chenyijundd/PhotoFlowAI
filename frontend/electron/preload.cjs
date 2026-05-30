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
  getBlurPhotos: (limit, offset) => ipcRenderer.invoke("get-blur-photos", limit, offset),
  getBlurCount: () => ipcRenderer.invoke("get-blur-count"),
  runBlurDetection: (photoIds) => ipcRenderer.invoke("run-blur-detection", photoIds),
  blurProgress: (taskId) => ipcRenderer.invoke("blur-progress", taskId),
  blurCancel: (taskId) => ipcRenderer.invoke("blur-cancel", taskId),
  updateRejectStatus: (imageId, isRejected) => ipcRenderer.invoke("update-reject-status", imageId, isRejected),
  getRejectedPhotos: (limit, offset) => ipcRenderer.invoke("get-rejected-photos", limit, offset),
  getRejectedCount: () => ipcRenderer.invoke("get-rejected-count"),
  getDuplicateCount: () => ipcRenderer.invoke("get-duplicate-count"),
  runDuplicateDetection: (photoIds) => ipcRenderer.invoke("run-duplicate-detection", photoIds),
  duplicateProgress: (taskId) => ipcRenderer.invoke("duplicate-progress", taskId),
  duplicateCancel: (taskId) => ipcRenderer.invoke("duplicate-cancel", taskId),
  getDuplicatePhotos: (limit, offset) => ipcRenderer.invoke("get-duplicate-photos", limit, offset),
  getPhotosByGroup: (groupId) => ipcRenderer.invoke("get-photos-by-group", groupId),
  generateSuggestions: (photoIds) => ipcRenderer.invoke("generate-suggestions", photoIds),
  getSuggestedPhotos: (limit, offset) => ipcRenderer.invoke("get-suggested-photos", limit, offset),
  getSuggestedCount: () => ipcRenderer.invoke("get-suggested-count"),
  exportStart: (targetFolder, mode, photoIds) => ipcRenderer.invoke("export-start", targetFolder, mode, photoIds),
  exportProgress: (exportId) => ipcRenderer.invoke("export-progress", exportId),
  exportCancel: (exportId) => ipcRenderer.invoke("export-cancel", exportId),
  exportSummary: (exportId) => ipcRenderer.invoke("export-summary", exportId),
  onMenuImport: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("menu-import", handler);
    return () => ipcRenderer.removeListener("menu-import", handler);
  },
});
