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
  runBlurDetection: (photoIds) => ipcRenderer.invoke("run-blur-detection", photoIds),
  updateRejectStatus: (imageId, isRejected) => ipcRenderer.invoke("update-reject-status", imageId, isRejected),
  getRejectedPhotos: (limit, offset) => ipcRenderer.invoke("get-rejected-photos", limit, offset),
  getRejectedCount: () => ipcRenderer.invoke("get-rejected-count"),
  getDuplicateCount: () => ipcRenderer.invoke("get-duplicate-count"),
  runDuplicateDetection: (photoIds) => ipcRenderer.invoke("run-duplicate-detection", photoIds),
  getDuplicatePhotos: (limit, offset) => ipcRenderer.invoke("get-duplicate-photos", limit, offset),
  getPhotosByGroup: (groupId) => ipcRenderer.invoke("get-photos-by-group", groupId),
  onMenuImport: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("menu-import", handler);
    return () => ipcRenderer.removeListener("menu-import", handler);
  },
});
