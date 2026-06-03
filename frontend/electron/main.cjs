/**
 * PhotoFlow AI - Electron Main Process
 *
 * Manages the application window, spawns the Python backend,
 * and bridges IPC between renderer and backend API.
 */

const { app, BrowserWindow, ipcMain, dialog, Menu } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let mainWindow = null;
let pythonProcess = null;

const isDev = process.env.NODE_ENV === "development";
const PYTHON_PORT = 8765;

function startPythonBackend() {
  const projectRoot = path.join(__dirname, "..", "..");
  pythonProcess = spawn("python", ["-m", "backend.api.server", "--port", String(PYTHON_PORT)], {
    cwd: projectRoot,
    stdio: ["pipe", "pipe", "pipe"],
  });

  pythonProcess.stdout?.on("data", (data) => {
    console.log(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.stderr?.on("data", (data) => {
    console.error(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.on("error", (err) => {
    console.error(`[Python] Failed to spawn: ${err.message}`);
  });

  pythonProcess.on("close", (code) => {
    console.log(`[Python] Process exited with code ${code}`);
    pythonProcess = null;
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1200,
    minHeight: 800,
    title: "PhotoFlow AI",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

// ---- IPC Handlers ----

/** Fetch starred photos from the Python backend through IPC. */
ipcMain.handle("get-starred-photos", async (_event, limit = 100, offset = 0) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/starred?limit=${limit}&offset=${offset}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Fetch starred photos count from the Python backend through IPC. */
ipcMain.handle("get-starred-count", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/starred/count`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Fetch all filter counts in one request. */
ipcMain.handle("fetch-counts", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/counts`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Fetch photos from the Python backend through IPC. */
ipcMain.handle("get-photos", async (_event, limit = 100, offset = 0) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos?limit=${limit}&offset=${offset}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

ipcMain.handle("get-photo-detail", async (_event, imageId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photo/${encodeURIComponent(imageId)}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Update star rating for a photo through IPC. */
ipcMain.handle("update-star-rating", async (_event, imageId, starRating) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photo/${encodeURIComponent(imageId)}/star`;
  const response = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ star_rating: starRating }),
  });
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

ipcMain.handle("get-backend-url", () => {
  return `http://127.0.0.1:${PYTHON_PORT}`;
});

/** Open a directory picker dialog. Returns the selected path or null. */
ipcMain.handle("select-directory", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory"],
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

/** Fetch blur photos from the Python backend through IPC. */
ipcMain.handle("get-blur-photos", async (_event, limit = 100, offset = 0) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/blur?limit=${limit}&offset=${offset}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Fetch blur count from the Python backend through IPC. */
ipcMain.handle("get-blur-count", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/blur/count`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Start burst grouping through IPC. */
ipcMain.handle("run-burst-grouping", async (_event, gapSeconds) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/burst-group`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gap_seconds: gapSeconds ?? null }),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || `Backend returned ${response.status}`);
  }
  return response.json();
});

/** Poll burst grouping progress. */
ipcMain.handle("burst-progress", async (_event, taskId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/burst-progress/${taskId}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Cancel burst grouping. */
ipcMain.handle("burst-cancel", async (_event, taskId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/burst-cancel/${taskId}`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch burst groups summary. */
ipcMain.handle("get-burst-groups", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/bursts`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch photos in a specific burst group. */
ipcMain.handle("get-burst-photos", async (_event, groupId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/burst/${encodeURIComponent(groupId)}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch burst group count. */
ipcMain.handle("get-burst-count", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/bursts/count`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch photos in any burst group (for filter mode). */
ipcMain.handle("get-burst-photos-list", async (_event, limit, offset) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/burst?limit=${limit}&offset=${offset}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Start combined AI analysis (blur -> duplicate -> burst -> best). */
ipcMain.handle("analyze-all", async (_event, photoIds, filterMode) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/analyze-all`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds ?? null, filter_mode: filterMode ?? null }),
  });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Poll analyze-all progress. */
ipcMain.handle("analyze-progress", async (_event, taskId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/analyze-progress/${taskId}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch unprocessed photos. */
ipcMain.handle("get-unprocessed-photos", async (_event, limit, offset) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/unprocessed?limit=${limit}&offset=${offset}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch unprocessed count. */
ipcMain.handle("get-unprocessed-count", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/unprocessed/count`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch best-in-burst photos. */
ipcMain.handle("get-best-photos-list", async (_event, limit, offset) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/best?limit=${limit}&offset=${offset}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch best-in-burst count. */
ipcMain.handle("get-best-count", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/best/count`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Accept best photo in a burst group, reject the rest. */
ipcMain.handle("burst-accept-best", async (_event, groupId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/burst/${encodeURIComponent(groupId)}/accept-best`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Accept all photos in a burst group. */
ipcMain.handle("burst-accept-all", async (_event, groupId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/burst/${encodeURIComponent(groupId)}/accept-all`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Reject all photos in a burst group. */
ipcMain.handle("burst-reject-all", async (_event, groupId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/burst/${encodeURIComponent(groupId)}/reject-all`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Accept best in ALL burst groups. */
ipcMain.handle("burst-accept-all-best", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/burst/accept-all-best`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Reject all non-recommended photos across all burst groups. */
ipcMain.handle("burst-reject-all-rest", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/burst/reject-all-rest`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Comprehensive one-click cull: blur + duplicate + burst + AI suggestions (async). */
ipcMain.handle("cull-all", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/cull-all`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) {
    // Extract FastAPI error detail from the response body
    const detail = await response.json().then((b) => b.detail).catch(() => null);
    throw new Error(detail || `Backend returned ${response.status}`);
  }
  return response.json();
});

/** Poll one-click cull progress. */
ipcMain.handle("cull-progress", async (_event, taskId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/cull-progress/${taskId}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Start blur detection V2 (multi-patch, content-aware) through IPC. */
ipcMain.handle("run-blur-detection-v2", async (_event, photoIds, threshold) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/blur-detect-v2`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds, threshold: threshold ?? null }),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || `Backend returned ${response.status}`);
  }
  return response.json();
});

/** Poll blur detection V2 progress. */
ipcMain.handle("blur-progress-v2", async (_event, taskId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/blur-progress-v2/${taskId}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Cancel blur detection V2. */
ipcMain.handle("blur-cancel-v2", async (_event, taskId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/blur-cancel-v2/${taskId}`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Start eye detection (closed / half-closed eyes) through IPC. */
ipcMain.handle("run-eye-detection", async (_event, photoIds) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/eye-detect`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds }),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || `Backend returned ${response.status}`);
  }
  return response.json();
});

/** Poll eye detection progress. */
ipcMain.handle("eye-progress", async (_event, taskId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/eye-progress/${taskId}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Cancel eye detection. */
ipcMain.handle("eye-cancel", async (_event, taskId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/eye-cancel/${taskId}`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch closed-eye photos through IPC. */
ipcMain.handle("get-closed-eye-photos", async (_event, limit = 100, offset = 0) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/closed-eye?limit=${limit}&offset=${offset}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch closed-eye count through IPC. */
ipcMain.handle("get-closed-eye-count", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/closed-eye/count`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch rejected photos from the Python backend through IPC. */
ipcMain.handle("get-rejected-photos", async (_event, limit = 100, offset = 0) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/rejected?limit=${limit}&offset=${offset}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Update reject status for a photo through IPC. */
ipcMain.handle("update-reject-status", async (_event, imageId, isRejected) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photo/${encodeURIComponent(imageId)}/reject`;
  const response = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_rejected: isRejected }),
  });
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Fetch rejected photos count from the Python backend through IPC. */
ipcMain.handle("get-rejected-count", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/rejected/count`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Fetch duplicate photos from the Python backend through IPC. */
ipcMain.handle("get-duplicate-photos", async (_event, limit = 100, offset = 0) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/duplicate?limit=${limit}&offset=${offset}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Fetch duplicate photos count from the Python backend through IPC. */
ipcMain.handle("get-duplicate-count", async () => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/duplicate/count`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Start duplicate detection on a set of photo IDs through IPC. */
ipcMain.handle("run-duplicate-detection", async (_event, photoIds) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/duplicate-detect`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds }),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || `Backend returned ${response.status}`);
  }
  return response.json();
});

/** Poll duplicate detection progress. */
ipcMain.handle("duplicate-progress", async (_event, taskId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/duplicate-progress/${taskId}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Cancel duplicate detection. */
ipcMain.handle("duplicate-cancel", async (_event, taskId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/ai/duplicate-cancel/${taskId}`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Fetch photos in a specific duplicate group through IPC. */
ipcMain.handle("get-photos-by-group", async (_event, groupId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/photos/duplicate/group/${encodeURIComponent(groupId)}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
});

/** Start an export to a target folder. */
ipcMain.handle("export-start", async (_event, targetFolder, mode, photoIds, filterMode, nameTemplate, namePrefix, startIndex, exportFormat) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/export/start`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_folder: targetFolder,
      mode,
      photo_ids: photoIds || null,
      filter_mode: filterMode || null,
      name_template: nameTemplate || null,
      name_prefix: namePrefix || null,
      start_index: startIndex ?? null,
      export_format: exportFormat || null,
    }),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || `Backend returned ${response.status}`);
  }
  return response.json();
});

/** Poll export progress. */
ipcMain.handle("export-progress", async (_event, exportId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/export/progress/${exportId}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Cancel a running export. */
ipcMain.handle("export-cancel", async (_event, exportId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/export/cancel/${exportId}`;
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Get export summary. */
ipcMain.handle("export-summary", async (_event, exportId) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/export/summary/${exportId}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json();
});

/** Send a directory path to the backend for the full import workflow. */
ipcMain.handle("import-photos", async (_event, dirPath) => {
  const url = `http://127.0.0.1:${PYTHON_PORT}/api/import`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ directory: dirPath }),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || `Backend returned ${response.status}`);
  }
  return response.json();
});

// ---- App Menu ----

function buildAppMenu() {
  const template = [
    {
      label: "文件",
      submenu: [
        { label: "导入照片", accelerator: "CmdOrCtrl+O", click: () => mainWindow?.webContents.send("menu-import") },
        { type: "separator" },
        { label: "退出", accelerator: "CmdOrCtrl+Q", role: "quit" },
      ],
    },
    {
      label: "编辑",
      submenu: [
        { label: "撤销", accelerator: "CmdOrCtrl+Z", role: "undo" },
        { label: "重做", accelerator: "Shift+CmdOrCtrl+Z", role: "redo" },
        { type: "separator" },
        { label: "剪切", accelerator: "CmdOrCtrl+X", role: "cut" },
        { label: "复制", accelerator: "CmdOrCtrl+C", role: "copy" },
        { label: "粘贴", accelerator: "CmdOrCtrl+V", role: "paste" },
        { label: "全选", accelerator: "CmdOrCtrl+A", role: "selectAll" },
      ],
    },
    {
      label: "视图",
      submenu: [
        { label: "重新加载", accelerator: "CmdOrCtrl+R", role: "reload" },
        { label: "开发者工具", accelerator: "F12", role: "toggleDevTools" },
        { type: "separator" },
        { label: "放大", accelerator: "CmdOrCtrl+=", role: "zoomIn" },
        { label: "缩小", accelerator: "CmdOrCtrl+-", role: "zoomOut" },
        { label: "重置缩放", accelerator: "CmdOrCtrl+0", role: "resetZoom" },
      ],
    },
    {
      label: "窗口",
      submenu: [
        { label: "最小化", accelerator: "CmdOrCtrl+M", role: "minimize" },
        { label: "关闭", accelerator: "CmdOrCtrl+W", role: "close" },
      ],
    },
    {
      label: "帮助",
      submenu: [
        { label: "关于 PhotoFlow AI", click: () => {
          dialog.showMessageBox(mainWindow, {
            type: "info",
            title: "关于 PhotoFlow AI",
            message: "PhotoFlow AI",
            detail: "智能摄影辅助工具\n为婚纱摄影师打造",
          });
        }},
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// ---- App Lifecycle ----

app.whenReady().then(() => {
  buildAppMenu();
  startPythonBackend();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
});
