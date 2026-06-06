/**
 * PhotoFlow AI - Auto-Updater Module
 *
 * Uses electron-updater to check GitHub Releases for new versions.
 * On update-available → prompts the user to download.
 * On update-downloaded → prompts the user to restart.
 *
 * Before release, update the `owner` and `repo` fields below
 * to point to your actual GitHub repository.
 */

const { autoUpdater } = require("electron-updater");
const { dialog, app } = require("electron");

// ── Update Source (CHANGE BEFORE RELEASE) ────────────────────────────────
autoUpdater.setFeedURL({
  provider: "github",
  owner: "chenyijundd",
  repo: "PhotoFlowAI",
});

const log = (...args) => console.log("[Updater]", ...args);

/**
 * Set up auto-update checking.
 * Call once after the main window is created.
 */
function setupAutoUpdater(mainWindow) {
  // Auto-update only works in production (packaged) builds
  if (process.env.NODE_ENV === "development") {
    log("Development mode — auto-update disabled");
    return;
  }

  // ── Scheduled checks ──────────────────────────────────────────────

  // Initial check 10 seconds after app start
  setTimeout(() => {
    autoUpdater.checkForUpdatesAndNotify().catch((err) => {
      log("Initial update check failed:", err.message);
    });
  }, 10_000);

  // Periodic check every 6 hours
  setInterval(() => {
    autoUpdater.checkForUpdatesAndNotify().catch((err) => {
      log("Periodic update check failed:", err.message);
    });
  }, 6 * 60 * 60 * 1000);

  // ── Event handlers ────────────────────────────────────────────────

  autoUpdater.on("update-available", (info) => {
    log(`Update available: v${info.version}`);
    dialog
      .showMessageBox(mainWindow, {
        type: "info",
        title: "发现新版本",
        message: `PhotoFlow AI v${info.version} 已发布！`,
        detail: `当前版本：${app.getVersion()}\n\n是否立即下载更新？`,
        buttons: ["立即下载", "稍后提醒"],
        defaultId: 0,
        cancelId: 1,
      })
      .then(({ response }) => {
        if (response === 0) {
          autoUpdater.downloadUpdate().catch((err) => {
            log("Download failed:", err.message);
          });
        }
      });
  });

  autoUpdater.on("update-downloaded", () => {
    log("Update downloaded — ready to install");
    dialog
      .showMessageBox(mainWindow, {
        type: "info",
        title: "下载完成",
        message: "更新已下载，重启后生效。",
        detail: "点击「立即重启」关闭当前窗口并安装更新。",
        buttons: ["立即重启", "稍后"],
        defaultId: 0,
        cancelId: 1,
      })
      .then(({ response }) => {
        if (response === 0) {
          autoUpdater.quitAndInstall();
        }
      });
  });

  autoUpdater.on("update-not-available", () => {
    log("No update available");
  });

  autoUpdater.on("error", (err) => {
    log("Update error:", err.message);
  });
}

/**
 * Manually triggered update check (menu / IPC).
 * In dev mode, shows an informational dialog.
 */
function manualCheck(mainWindow) {
  if (process.env.NODE_ENV === "development") {
    dialog.showMessageBox(mainWindow, {
      type: "info",
      title: "检查更新",
      message: "开发模式",
      detail: "自动更新仅在正式发布的版本中可用。",
      buttons: ["确定"],
    });
    return;
  }

  autoUpdater.checkForUpdatesAndNotify().catch((err) => {
    log("Manual update check failed:", err.message);
    dialog
      .showMessageBox(mainWindow, {
        type: "info",
        title: "检查更新",
        message: "当前已是最新版本",
        detail: "没有发现可用的更新。",
        buttons: ["确定"],
      })
      .catch(() => {});
  });
}

module.exports = { setupAutoUpdater, manualCheck };
