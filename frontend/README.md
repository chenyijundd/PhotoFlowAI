# Frontend Module (Electron + React 图片浏览 UI)

## 模块作用

提供本地图片浏览桌面界面，通过 Electron 主进程与 Python 后端通信，从 SQLite 数据库读取图片元数据并以虚拟网格形式展示缩略图。

## 启动方式

```bash
# 1. 启动 Python 后端（终端 1）
cd PhotoFlowAI
python -m backend.api.server --port 8765

# 2. 启动前端开发模式（终端 2）
cd frontend
npm run dev
```

前端开发模式会同时启动：
- Vite 开发服务器（http://localhost:5173）
- Electron 窗口（自动加载 Vite 页面）

## Electron 架构说明

```
┌─────────────────────────────────────────────────┐
│                  Electron                        │
│  ┌───────────────────────────────────────────┐  │
│  │          Main Process (main.cjs)           │  │
│  │  - 创建窗口                               │  │
│  │  - 启动 Python 后端                       │  │
│  │  - IPC 处理 → HTTP → Python Backend       │  │
│  │  - 菜单（导入照片快捷键 Ctrl+O）          │  │
│  └──────────────┬────────────────────────────┘  │
│                 │ IPC (invoke/handle)            │
│  ┌──────────────▼────────────────────────────┐  │
│  │       Preload (preload.cjs)               │  │
│  │  - contextBridge.exposeInMainWorld        │  │
│  │  - contextIsolation = true                │  │
│  │  - nodeIntegration = false                │  │
│  └──────────────┬────────────────────────────┘  │
│                 │ window.electronAPI             │
│  ┌──────────────▼────────────────────────────┐  │
│  │       Renderer (React + TypeScript)       │  │
│  │  - App.tsx → BrowserPage                  │  │
│  │    ├─ ImageGrid (react-window) + ImageCard│  │
│  │    ├─ DetailPanel                         │  │
│  │    │  └─ FullsizePreview (fit/zoom100)    │  │
│  │    └─ useKeyboardNavigation               │  │
│  │  - PhotoSelectionContext                   │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
         │ HTTP (127.0.0.1:8765)
         ▼
┌─────────────────────────────────────────────────┐
│           Python Backend (FastAPI)               │
│  - /api/health                                  │
│  - /api/photos?limit=&offset=                   │
│  - /api/photo/{id}               (详情 + 星级)   │
│  - /api/photo/{id}/star  (PATCH 更新星级)       │
│  - /api/fullsize/{id}           (原图输出)       │
│  - /api/thumbnails/{filename}                   │
│  - /api/import                  (导入照片)       │
└──────────────┬──────────────────────────────────┘
               │ SQLite
               ▼
┌─────────────────────────────────────────────────┐
│           SQLite Database (photoflow.db)         │
│  - photos 表（含 star_rating 字段）             │
└─────────────────────────────────────────────────┘
```

## IPC 流程图

```
React Component
  │
  ├─ window.electronAPI.getPhotos(limit, offset)
  │     │
  │     ▼
  ├─ preload.cjs (ipcRenderer.invoke)
  │     │
  │     ▼
  ├─ main.cjs (ipcMain.handle)
  │     │
  │     ├─ HTTP GET → http://127.0.0.1:8765/api/photos
  │     │                  │
  │     │                  ▼
  │     │           FastAPI → PhotoRepository → SQLite
  │     │                  │
  │     │                  ▼
  │     └─ JSON response ←──┘
  │     │
  │     ▼
  └─ Response back to React
```

| 前端调用 | IPC Channel | 后端端点 |
|---|---|---|
| `getPhotos(limit, offset)` | `get-photos` | `GET /api/photos?limit=&offset=` |
| `getPhotoDetail(id)` | `get-photo-detail` | `GET /api/photo/{id}` |
| `updateStarRating(id, rating)` | `update-star-rating` | `PATCH /api/photo/{id}/star` |
| `selectDirectory()` | `select-directory` | (Electron dialog) |
| `importPhotos(dirPath)` | `import-photos` | `POST /api/import` |
| `getStarredPhotos(limit, offset)` | `get-starred-photos` | `GET /api/photos/starred?limit=&offset=` |
| `getStarredCount()` | `get-starred-count` | `GET /api/photos/starred/count` |
| `updateRejectStatus(id, reject)` | `update-reject-status` | `PATCH /api/photo/{id}/reject` |
| `getRejectedPhotos(limit, offset)` | `get-rejected-photos` | `GET /api/photos/rejected?limit=&offset=` |
| `getRejectedCount()` | `get-rejected-count` | `GET /api/photos/rejected/count` |

全尺寸图片使用直接 HTTP 请求加载：`<img src="/api/fullsize/{id}">`，不经过 Electron IPC。

## 安全配置

- `contextIsolation: true` — 渲染进程无法直接访问 Node.js API
- `nodeIntegration: false` — 禁用 Node 集成
- `preload.cjs` — 通过 `contextBridge` 暴露最小 API

## 项目结构

```
frontend/
├── electron/
│   ├── main.cjs             # Electron 主进程（IPC 处理 + 菜单）
│   └── preload.cjs          # IPC 桥接（contextBridge 安全 API）
├── src/
│   ├── api/
│   │   └── photoApi.ts      # 照片 API 客户端
│   ├── components/
│   │   ├── DetailPanel.tsx   # 右侧详情面板（元数据 + 大图预览）
│   │   ├── FullsizePreview.tsx  # 全尺寸图片预览（fit/zoom100 模式）
│   │   ├── ImageCard.tsx     # 图片卡片（缩略图 + 星标显示）
│   │   └── ImageGrid.tsx    # 虚拟化图片网格（react-window）
│   ├── context/
│   │   └── PhotoSelectionContext.tsx  # 选中图片 ID 状态管理
│   ├── hooks/
│   │   ├── useKeyboardNavigation.ts  # 键盘快捷键导航（← → Space Enter Home End）
│   │   └── usePhotos.ts     # 数据获取 Hook（分页加载）
│   ├── pages/
│   │   └── BrowserPage.tsx  # 主浏览页面（集成 grid + 详情 + 键盘导航）
│   ├── ui/
│   │   └── global.css       # 全局样式
│   ├── App.tsx              # 根组件（后端连接检测）
│   └── main.tsx             # 入口
├── types/
│   └── index.ts             # TypeScript 类型定义（含 ElectronAPI）
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

## 键盘快捷键

支持摄影师全键盘高速选片工作流。快捷键仅在无 `<input>` / `<textarea>` / `<select>` 聚焦时生效。

| 按键 | 功能 | 行为 |
|---|---|---|
| `←` | 上一张 | 选中前一张图片，网格自动滚动定位 |
| `→` | 下一张 | 选中后一张图片，网格自动滚动定位 |
| `Space` | 切换星标 | 当前图片在 0★ 和 1★ 之间切换 |
| `X` | 切换废片 | 当前图片在已标记和未标记之间切换（0 ↔ 1）|
| `Enter` | 切换缩放 | FullsizePreview 在 Fit 模式和 100% 模式间切换 |
| `Home` | 跳至首张 | 选中网格中第一张图片 |
| `End` | 跳至末张 | 选中网格中最后一张图片 |

## 筛选工作流

顶部筛选栏支持在「全部照片」「已选照片」「模糊照片」「废片」之间切换。

### 筛选栏

```
[全部照片] [已选照片] [模糊照片] [废片]    已选：128    废片：5
```

- 默认状态为「全部照片」
- 点击按钮切换筛选模式
- 右侧实时显示已选照片总数
- 切换模式时网格自动刷新，并选中第一张照片

### 已选照片逻辑

- `star_rating == 1` 的照片视为已选
- 按 `Space` 打星 → 照片进入已选列表
- 再次按 `Space` 取消星标 → 照片自动从已选列表消失

### 当前图片失效处理

当用户在「已选照片」模式下取消星标，或在「废片」模式下取消废片标记时：

1. 系统在刷新前预先计算下一张照片的 ID
2. 调用 `updateStarRating()` / `updateRejectStatus()` 更新数据库
3. 调用 `refresh()` 重新加载列表
4. 自动切换到预先计算的下一张照片
5. 如果当前是最后一张，则切换到上一张
6. 如果列表为空，不执行任何切换（避免空引用崩溃）

### 废片工作流

废片标记（Reject）是专业摄影软件的核心功能，专门用于标记需要删除或排除的照片。

- **标记废片**：选中图片后按 `X` 键，图片卡片左上角显示 `REJECT` 标识
- **取消废片**：再次按 `X` 键可取消废片标记
- **废片筛选**：点击「废片」按钮切换到废片筛选模式，只显示已标记废片的照片
- **废片计数**：筛选栏右侧实时显示废片数量
- **与星标共存**：一张照片允许同时被「已选 + 废片」（当前阶段不互斥）
- **自动迁移**：旧数据库首次启动时自动添加 `is_rejected` 列，无需迁移操作
- **详情面板**：选中废片时，详情面板显示 `Status: REJECT`

### react-window 兼容

- 筛选模式切换时，`usePhotos` hook 重置内部状态（清空照片列表、重置 offset）
- 调用对应的 API 端点（`/api/photos` 或 `/api/photos/starred`）
- 数据加载完成后，第一张照片自动被选中
- `ImageGrid` 通过 `scrollToIndex` 自动定位到当前照片
- 虚拟化网格在任何筛选模式下均保持流畅滚动

### 空状态

当已选照片为 0 时，显示：

```
⭐
暂无已选照片
按 Space 可标记照片
```

当废片为 0 时，显示：

```
🗑️
暂无废片
按 X 可标记废片
```

### 架构流程

```
用户点击「已选照片」
          │
          ▼
BrowserPage 设置 filterMode = "starred"
          │
          ▼
usePhotos(filterMode) 检测到 filterMode 变化
          │
          ├── 重置 offset = 0, photos = []
          ├── 调用 fetchStarredPhotos(limit, offset)
          │       │
          │       ├── Electron → IPC → main.cjs → HTTP GET /api/photos/starred
          │       │              或
          │       └── 浏览器直接 → HTTP GET /api/photos/starred
          │
          ▼
返回结果 → setPhotos(data.photos) → 网格刷新
          │
          ▼
BrowserPage 选中第一张照片（如果存在）
          │
          ▼
ImageGrid.scrollToIndex(0) → 自动定位
```

```
用户按下 ← / → / Home / End
          │
          ▼
useKeyboardNavigation hook 拦截 keydown 事件
          │
          ▼
selectPhoto(newId) → PhotoSelectionContext 更新选中状态
          │
          ├──→ DetailPanel 重新获取详情 + FullsizePreview 更新大图
          │
          └──→ ImageGrid.scrollToIndex() 自动滚动网格至选中卡片
```

## 虚拟列表说明

使用 `react-window` 的 `FixedSizeGrid` 实现虚拟化网格：

- 每个网格项 200×260px（含间距 12px）
- 只渲染可视区域 + overscan（4 行缓冲区）
- 5000+ 张图片可流畅滚动
- 通过 `ResizeObserver` 自适应容器尺寸变化
- 滚动到底部时自动触发 `loadMore` 加载下一页

### 键盘自动定位

`ImageGrid` 通过 `forwardRef` + `useImperativeHandle` 暴露 `scrollToIndex(index)` 方法：

- 键盘切换图片时，`useKeyboardNavigation` 自动调用该方法
- 内部使用 `scrollToItem({ rowIndex, columnIndex, align: "center" })` 将目标卡片定位到可视区域中央
- 列数通过 `columnCountRef` 保持最新，避免闭包陈旧值
- **无性能退化** — react-window 的虚拟化不受影响

## 当前限制

- 已选/全部筛选不支持星级范围选择（仅 0/1 切换）
- 无 AI 分析结果展示
- 无图片删除/编辑功能
- 无导出功能
- 缩略图由后端独立生成（需先运行 thumbnail_cache）
- 星标仅支持 0/1 切换，不支持多星级
- 键盘快捷键不支持自定义
- 仅支持单击选中，无多选/批量操作
- 筛选切换时重置选中状态到第一张照片（不记忆上次位置）
- 已选照片数量需手动触发刷新（打星或导入时自动更新）
- 废片标记无批量操作（仅单张 X 键切换）
- 废片与星标不互斥（已选 + 废片可同时存在）

## 后续扩展点

- AI 分析结果可视化（模糊标签、闭眼标签、综合评分）
- 多选 + 批量操作（批量标星、批量标记）
- 全屏浏览模式
- 自定义快捷键绑定
- 鼠标滚轮缩放（当前仅支持 Enter 切换 Fit / 100%）
- EXIF 元数据显示（光圈、ISO、快门速度、镜头信息）
- 键盘导航首尾循环（最后一张按 → 回到第一张）
- 响应式卡片尺寸
- 筛选模式切换时记忆滚动位置
- 星级范围筛选（2★+、3★+）
- 导出时排除废片
- 批量标记/取消废片（多选）
- AI 自动废片标记（基于模糊、闭眼、重复检测）
- 真删除文件 / 回收站
