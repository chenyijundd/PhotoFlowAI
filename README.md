# PhotoFlow AI

本地 AI 智能选片工具 — 面向中国婚礼摄影工作室与职业摄影师。

## 产品使命

让摄影师把时间花在创作，而不是机械劳动。

## 技术栈

| 模块   | 技术                   |
| ------ | ---------------------- |
| 客户端 | Electron               |
| UI     | React + Vite           |
| 后端   | Python + FastAPI       |
| AI处理 | OpenCV                 |
| 人脸检测 | MediaPipe            |
| 数据库 | SQLite                 |
| 图片处理 | Pillow               |
| 模型格式 | ONNX（后续预留）       |

## 项目结构

```
PhotoFlowAI/
├── frontend/              # Electron + React 前端
│   ├── electron/
│   │   ├── main.cjs      # Electron 主进程（IPC + 菜单）
│   │   └── preload.cjs   # IPC 桥接（contextBridge）
│   ├── src/
│   │   ├── api/          # API 客户端
│   │   ├── components/   # UI 组件
│   │   ├── context/      # 状态管理（选中、对比模式）
│   │   ├── hooks/        # 自定义 Hook（键盘导航、键盘管理、Lazy Load、数据加载）
│   │   ├── pages/        # 页面组件
│   │   ├── ui/           # 样式文件
│   │   ├── App.tsx       # 根组件（含 ErrorBoundary）
│   │   └── main.tsx      # 入口
│   ├── types/            # TypeScript 类型定义
│   └── package.json
├── backend/               # Python 后端
│   ├── api/              # FastAPI 服务
│   ├── ai/               # AI 模块
│   │   ├── image_loader/       # 图片扫描
│   │   ├── blur_detection/     # 模糊检测
│   │   ├── eye_detection/      # 闭眼检测
│   │   ├── duplicate_detection/ # 重复图检测
│   │   └── scoring/            # 综合评分
│   ├── importer/         # 照片导入工作流
│   ├── thumbnail_cache/  # 缩略图缓存
│   ├── export/           # 导出模块
│   └── logging_config.py # 集中化日志配置（RotatingFileHandler）
├── database/              # SQLite 数据库
├── cache/                 # 缓存目录
├── logs/                  # 日志目录（轮转：10MB × 5）
├── tests/                 # 测试
└── main.py                # 项目入口
```

## 快速开始

### 1. 后端

```bash
# 安装依赖
cd backend
pip install -r requirements.txt

# 启动后端服务（自动初始化 SQLite）
python -m backend.api.server --port 8765
```

### 2. 前端

```bash
cd frontend
npm install

# 开发模式（Vite dev server + Electron 窗口）
npm run dev

# 仅构建 React
npm run build
```

## 开发规范

- 一次只实现一个模块
- 所有模块可独立 CLI 运行
- 模块间完全解耦，互不依赖
- 每个模块包含 README、示例输入/输出
- 先跑通，再优化

## 已实现功能

- [x] 本地文件夹导入（JPG/PNG）— 通过 Electron 目录选择器 + 后端扫描
- [x] 缩略图缓存系统 — 自动生成缩略图并缓存
- [x] 键盘快速选片 — ← → 切图、Space 切换星标、X 标记废片、Enter 切换缩放、Home/End 首尾跳转
- [x] 照片详情面板 — 文件名、尺寸、文件大小、创建时间、星标状态、废片标记
- [x] 全尺寸图片预览 — Fit 模式 / 100% 模式（Enter 切换）
- [x] 星标评级 — 0★/1★ 切换，持久化到 SQLite
- [x] 废片标记工作流 — X 标记/取消废片，废片筛选模式，当前图片失效自动切换
- [x] 筛选工作流 — 全部照片 / 已选照片 / 模糊照片 / 废片 / 重复照片切换浏览
- [x] AI 模糊检测 — Laplacian Variance 算法，检测结果持久化，模糊筛选模式
- [x] AI 重复照片检测 — Perceptual Hash (pHash) 算法，DUP 标签，Compare Mode 对比浏览
- [x] Compare Mode — 重复组内双图对比，← → 切换对、Tab 切换激活侧、Space/X 标星/废片
- [x] Cull Workflow — 自动推进、智能下一张、跳过废片、状态浮层、键盘安全
- [x] 性能稳定性改造 (v1) — 详见下方性能章节
- [x] AI 建议系统 (v1) — 规则驱动的辅助选片建议，AI 只建议不决策

## 开发中 / 待实现

- [ ] AI 闭眼检测
- [ ] AI 综合评分（1-5星）
- [ ] AI 选片报告
- [ ] 精选照片导出
- [ ] 手动微调
- [ ] 多选 + 批量操作

---

## AI 建议系统 (AI Suggestion Layer)

### 核心哲学

**AI 只能 Suggest，永远不 Decide。** AI 建议是辅助信息，不是自动决策。用户始终拥有最终控制权。

### 建议类型

| 类型 | 规则 | 接受行为 |
|------|------|---------|
| `POSSIBLE_BLUR` | `is_blur == 1` | 自动 Reject |
| `POSSIBLE_DUPLICATE` | `duplicate_group != null` | 无操作（仅提示） |
| `POSSIBLE_BEST` | 同重复组中 `blur_score` 最大 且 非废片 | 自动 Star |

每张照片最多一条建议，优先级：POSSIBLE_BEST > POSSIBLE_BLUR > POSSIBLE_DUPLICATE。

### 规则引擎

纯 Python 规则驱动（`backend/ai/suggestions/rules.py`），无机器学习依赖。

- `evaluate_suggestion(photo, best_in_group)` — 评估单张照片
- `compute_best_in_groups(photos)` — 为每个重复组选出最佳照片

### 键盘工作流

| 按键 | 行为 |
|------|------|
| `A` | 接受当前照片的 AI 建议 |
| 接受后 | 显示 "AI ACCEPTED" 浮层 500ms，自动重新生成建议 |

### Compare Mode 集成

当 Compare Mode 的左/右照片存在 `POSSIBLE_BEST` 建议时，顶部 Header 显示橙色 `AI Suggested` 标签。

### 筛选模式

顶部新增 `[AI Suggestions]` 筛选按钮，显示所有 `ai_suggestion != null` 的照片。

### 建议安全 (Suggestion Safety)

以下操作会自动触发建议重新生成（失效旧建议）：

- 运行模糊检测
- 运行重复检测
- 手动 Star（Space）/ Reject（X）
- 接受 AI 建议（A 键）

**文件：** `backend/ai/suggestions/`

### 未来 AI 扩展

- ML 模型替代规则引擎
- 建议置信度评分
- 增量更新（非全量重新生成）
- 用户反馈学习
- 更多建议类型（闭眼、表情、构图）

---

## 性能与稳定性 (v1)

> **目标负载：5,000–20,000 张照片。** 第一轮性能稳定性改造。

### Lazy Load 策略

**基于 IntersectionObserver 的真正懒加载**（无第三方库依赖）。

- 每张 `ImageCard` 使用 `useIntersectionObserver` hook (`src/hooks/useIntersectionObserver.ts`)
- 缩略图 `<img>` 仅当卡片进入视口 **300px 范围内**时才插入 DOM
- 加载后保持可见 (`freezeOnceVisible: true`)，回滚时不闪烁
- `rootMargin: "300px"` 提供足够缓冲，快速滚动也不露白

**文件：** [useIntersectionObserver.ts](frontend/src/hooks/useIntersectionObserver.ts)

### Re-render 优化

**精准局部更新** — 标星/Reject 不会触发整个 Grid 重新渲染。

| 技术 | 位置 | 目的 |
|------|------|------|
| `React.memo` 自定义比较器 | `ImageCard.tsx` | 仅在 photo 数据或选中状态实际变化时渲染 |
| `useMemo` Cell 渲染器 | `ImageGrid.tsx` | Cell 组件引用在渲染间保持稳定 |
| `useCallback` 全面使用 | 全部组件 | 稳定回调引用防止子组件重渲染 |
| `useRef` 存最新值 | `useKeyboardNavigation.ts`, `BrowserPage.tsx` | 无需重新注册即可避免闭包过期 |

**核心逻辑：** `ImageCard` memo 比较器检查 7 个关键字段 (`image_id`, `star_rating`, `is_rejected`, `is_blur`, `is_duplicate`, `duplicate_group`, `style`)。只有实际数据变化的卡片才会重渲染。

**文件：** [ImageCard.tsx](frontend/src/components/ImageCard.tsx), [ImageGrid.tsx](frontend/src/components/ImageGrid.tsx)

### Preload 策略

**轻量级 Compare Mode 预加载**（无复杂缓存系统）。

Compare Mode 中：
- 下一对对比图 (currentIndex+1, currentIndex+2) 通过离屏 `new Image()` 预热浏览器 HTTP 缓存
- 用户切换到下一对时图片即时显示
- 旧预加载引用在 pair 变化时释放
- Performance Debug Overlay 显示为 "Preload: N"

**文件：** [ComparePage.tsx](frontend/src/components/ComparePage.tsx) — `preloadImage()` 函数

### 键盘管理器

**单一全局键盘监听器** — 所有键盘输入通过一个集中管理器流转。

设计：
- `window` 上**仅一个** `keydown` 事件监听器
- 组件按**优先级**注册处理器：
  - `COMPARE (100)` — Compare Mode 快捷键（最高优先级）
  - `GRID (50)` — 网格导航（← → Space X Enter Home End）
  - `APP (10)` — 应用级快捷键（C 进入对比模式）
- 高优先级处理器先消费事件，低优先级仅在事件未消费时触发
- 注册时返回清理函数 — 无监听器泄漏
- 基于 Ref 的处理器更新避免闭包过期

**文件：** [useKeyboardManager.ts](frontend/src/hooks/useKeyboardManager.ts)

**相比之前（3 个独立 `addEventListener` 调用）的优势：**
- 无重复绑定
- 无冲突处理器
- 无闭包过期 Bug
- 优先级系统防止 Compare Mode 和 Grid Mode 快捷键同时触发

### 内存安全

**切换照片时主动释放图片对象。**

| 组件 | 策略 |
|------|------|
| `FullsizePreview` | `imageId` 变化时 cleanup effect 中 `img.src = ""` + `removeAttribute("src")` |
| `ComparePreview` | 同样模式 — 跟踪 `prevImageIdRef`，变化时释放旧 src |
| `ComparePage` | Preload refs (`HTMLImageElement[]`) 在 pair 变化时清理 |

**核心模式：**
```typescript
useEffect(() => {
  return () => {
    if (imgRef.current) {
      imgRef.current.src = "";
      imgRef.current.removeAttribute("src");
    }
  };
}, [imageId]);
```

确保：
- 旧图片数据立即可被 GC 回收
- 快速切图时无内存累积（普通模式 + Compare Mode A→B→C 导航）
- 预加载图片无内存泄漏

**文件：** [FullsizePreview.tsx](frontend/src/components/FullsizePreview.tsx), [ComparePreview.tsx](frontend/src/components/ComparePreview.tsx)

### 日志轮转 (Log Rotation)

所有后端日志使用 `RotatingFileHandler`：
- **单文件最大：** 10 MB
- **备份数量：** 5 个文件（如 `import.log`, `import.log.1`, ..., `import.log.5`）
- **日志文件：** `import.log`, `blur_detection.log`, `duplicate_detection.log`, `app.log`
- 通过集中化 `logging_config.py` 在导入时配置
- 旧的动态 `FileHandler` 添加/移除模式已替换为持久轮转处理器

**文件：** [logging_config.py](backend/logging_config.py)

### 当前可扩展性限制

| 指标 | 当前状态 | 备注 |
|------|---------|------|
| 照片数量 | 5,000–20,000 | 已测试 |
| 虚拟化网格 | react-window FixedSizeGrid | ✅ |
| 缩略图生成 | 顺序（单线程） | V1 可接受 |
| 后端分页 | 内存切片（全量加载后分页） | 未来需改为 SQL 级 LIMIT/OFFSET |
| 图片解码 | `decoding="async"` | ✅ |
| Compare Mode | 双图对比 | ✅ |
| 键盘处理器 | 单一全局监听器 | ✅ |
| 日志轮转 | 10 MB × 5 文件 | ✅ |
| GPU 加速 | 无 | 未来 |
| Worker 线程 | 无 | 未来 |
| RAW 格式 | 不支持 | 未来 |
| 多显示器 | 不支持 | 未来 |

### 已知限制 (V1)
- 缩略图为 200px 最大边长 — HiDPI 显示器上可能偏软
- 全尺寸预览加载原始文件无降采样 — 高分辨率照片可能消耗较大内存
- 图片端点无 HTTP `Cache-Control` 头 — 浏览器缓存仅为启发式
- 后端分页先加载全量到内存再切片 (`all_photos[offset:offset + limit]`)
- 重复检测为 O(n²) 两两比较 — 20K+ 照片可能较慢
- Performance Overlay 键盘监听器数量每秒更新一次（轮询）

---

## Cull Workflow（专业快速筛片工作流）

### 概述

Cull Workflow 是面向职业摄影师的快速筛片工作流。借鉴 Photo Mechanic 等专业工具的交互模式，在浏览模式下通过键盘一键完成标星/废片操作后自动推进到下一张未处理照片，最小化摄影师的手部移动和决策时间。

### 自动推进 (Auto Advance)

| 操作 | 按键 | 行为 |
|------|------|------|
| 标星 | `Space` | 标记 1★ 后自动选中下一张未处理照片 |
| 废片 | `X` | 标记 REJECT 后自动选中下一张未处理照片 |
| 取消标星 | `Space`（已标星照片）| 取消星标，不自动推进 |
| 取消废片 | `X`（已废片照片）| 取消废片标记，不自动推进 |

### 智能下一张 (Smart Next Selection)

`findNextUnprocessed()` 在 auto-advance 时优先选择"未处理"照片（star_rating==0 且 is_rejected==0），跳过已标星和已废片的照片。如果后方没有未处理照片，则选择下一张任意照片。

实现位置: [useKeyboardNavigation.ts](frontend/src/hooks/useKeyboardNavigation.ts)

### 跳过废片 (Skip Rejected)

`←` `→` 导航时自动跳过 is_rejected==1 的照片，减少无效浏览。在"废片"筛选模式下不跳过（因为用户主动选择查看废片）。

实现位置: [useKeyboardNavigation.ts](frontend/src/hooks/useKeyboardNavigation.ts)

### 状态浮层 (Status Overlay)

按 `Space` 或 `X` 时屏幕中央显示 500ms 短暂浮层：
- 标星：金色 "★ PICKED"
- 废片：红色 "✕ REJECTED"

实现位置: [StatusOverlay.tsx](frontend/src/components/StatusOverlay.tsx)

### Compare Mode 智能推进 (Compare Progression)

在 Compare Mode 中：

| 操作 | 行为 |
|------|------|
| 标星/废片激活侧照片 | 自动尝试推进到下一对（两张都非废片的 pair） |
| 组内非废片照片 < 2 张 | 自动退出 Compare Mode |
| 无有效 pair | 自动退出 Compare Mode |

实现位置: [CompareModeContext.tsx](frontend/src/context/CompareModeContext.tsx)

### 状态优先级 (State Priority)

键盘事件处理优先级（从高到低）：

1. **Compare Mode 键盘** — 进入 Compare Mode 后，Grid 键盘事件完全禁用
2. **INPUT/TEXTAREA/SELECT** — 所有键盘 handler 执行前检查 `e.target.tagName`，输入框中不触发快捷键
3. **Grid 键盘** — 仅当 Compare Mode 未激活时生效

### 筛选模式下的失效处理

| 筛选模式 | 取消操作 | 行为 |
|----------|---------|------|
| 已选照片 (starred) | 取消标星 | 照片从列表消失，自动选下一张 |
| 废片 (rejected) | 取消废片 | 照片从列表消失，自动选下一张 |
| 全部照片 (all) | 标星/废片 | 照片保留在列表，自动推进 |

实现位置: [BrowserPage.tsx](frontend/src/pages/BrowserPage.tsx) — `getNextIdAfterAction()`

### 已知限制 (Known Limitations)

- 自动推进不支持撤销（单次操作不可逆，需手动回退后重新标记）
- 智能下一张仅向前查找，不循环到列表开头
- Compare Mode 仅支持同一 duplicate_group 内的照片对比
- 同一张照片可同时处于"已选"和"废片"状态（当前阶段不互斥）
- 无批量标星/废片操作（Shift/Ctrl 多选暂不支持）
- 无真删文件功能（废片仅为标记，不删除原文件）
- 无导出时过滤废片功能

## Reject 工作流

### 概述

Reject（废片标记）是专业摄影软件的核心工作流。摄影师在浏览照片时，可以一键标记废片，随后在废片筛选模式下集中处理。

### 键盘流程

| 按键 | 功能 | 行为 |
|---|---|---|
| `←` | 上一张 | 选中前一张图片，网格自动滚动定位 |
| `→` | 下一张 | 选中后一张图片，网格自动滚动定位 |
| `Space` | 切换星标 | 当前图片在 0★ 和 1★ 之间切换 |
| `X` | 切换废片 | 当前图片在已标记和未标记之间切换（0 ↔ 1）|
| `Enter` | 切换缩放 | FullsizePreview 在 Fit 模式和 100% 模式间切换 |
| `Home` | 跳至首张 | 选中网格中第一张图片 |
| `End` | 跳至末张 | 选中网格中最后一张图片 |

### 筛选栏

```
[全部照片] [已选照片] [模糊照片] [废片]    已选：128    废片：5
```

- 点击「废片」按钮切换到废片筛选模式
- 实时显示废片数量
- 一张照片允许同时处于「已选 + Reject」状态（当前阶段不互斥）

### 废片标记

- 选中一张照片，按 `X` 标记为废片（is_rejected = 1）
- 再次按 `X` 取消废片标记（is_rejected = 0）
- 图片卡片左上角显示 `REJECT` 标识
- 详情面板显示 `Status: REJECT`

### 当前图片失效处理

当用户在「废片」模式下取消废片标记时：

1. 系统在刷新前预先计算下一张照片的 ID
2. 调用 `updateRejectStatus()` 更新数据库
3. 调用 `refresh()` 重新加载废片列表
4. 自动切换到预先计算的下一张照片
5. 如果当前是最后一张，则切换到上一张
6. 如果列表为空，不执行任何切换（避免空引用崩溃）

### 空状态

当废片为 0 时，显示：

```
🗑️
暂无废片
按 X 可标记废片
```

### Migration 方案

**is_rejected 字段自动迁移**（v0.3.0）：

- 首次启动时，`init_database()` 检查 `photos` 表是否包含 `is_rejected` 列
- 如不存在，自动执行 `ALTER TABLE photos ADD COLUMN is_rejected INTEGER DEFAULT 0`
- 无需用户删库重建，兼容旧数据库
- 新数据库在 `CREATE TABLE` 时直接包含该列

```sql
is_rejected INTEGER DEFAULT 0
```

### 当前限制

- 无非真实删除文件功能
- 无回收站机制
- 无 AI 自动 Reject
- 无多标签/颜色标记
- 废片标记与星标不互斥（允许已选 + 废片同时存在）
- 无批量操作（Shift/Ctrl 多选暂不支持）
- 无导出时过滤废片功能

### 后续扩展点

- 真删文件 / 回收站
- AI 自动 Reject（基于模糊、闭眼、重复检测）
- 批量标记废片
- 导出时排除废片
- 废片统计报告

## License

MIT
