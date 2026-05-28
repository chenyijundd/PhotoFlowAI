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
│   │   ├── context/      # 选中图片状态管理
│   │   ├── hooks/        # 自定义 Hook（键盘导航、数据加载）
│   │   ├── pages/        # 页面组件
│   │   ├── ui/           # 样式文件
│   │   ├── App.tsx       # 根组件
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
│   └── export/           # 导出模块
├── database/              # SQLite 数据库
├── cache/                 # 缓存目录
├── logs/                  # 日志目录
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
- [x] 筛选工作流 — 全部照片 / 已选照片（star_rating==1）/ 模糊照片 / 废片 / 重复照片切换浏览
- [x] AI 模糊检测 — Laplacian Variance 算法，检测结果持久化，模糊筛选模式
- [x] AI 重复照片检测 — Perceptual Hash (pHash) 算法，DUP 标签，Compare Mode 对比浏览
- [x] Compare Mode — 重复组内双图对比，← → 切换对、Tab 切换激活侧、Space/X 标星/废片
- [x] Cull Workflow — 自动推进、智能下一张、跳过废片、状态浮层、键盘安全

## 开发中 / 待实现

- [ ] AI 闭眼检测
- [ ] AI 综合评分（1-5星）
- [ ] AI 选片报告
- [ ] 精选照片导出
- [ ] 手动微调
- [ ] 多选 + 批量操作

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

实现位置: [useKeyboardNavigation.ts:61-77](frontend/src/hooks/useKeyboardNavigation.ts#L61-L77)

### 跳过废片 (Skip Rejected)

`←` `→` 导航时自动跳过 is_rejected==1 的照片，减少无效浏览。在"废片"筛选模式下不跳过（因为用户主动选择查看废片）。

实现位置: [useKeyboardNavigation.ts:41-55](frontend/src/hooks/useKeyboardNavigation.ts#L41-L55)

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

实现位置: [CompareModeContext.tsx:103-141](frontend/src/context/CompareModeContext.tsx#L103-L141)

### 状态优先级 (State Priority)

键盘事件处理优先级（从高到低）：

1. **Compare Mode 键盘** — 进入 Compare Mode 后，BrowserPage 键盘事件完全禁用（`active: !isCompareMode`）
2. **INPUT/TEXTAREA/SELECT** — 所有键盘 handler 执行前检查 `e.target.tagName`，输入框中不触发快捷键
3. **BrowserPage 键盘** — 仅当 Compare Mode 未激活时生效

### 筛选模式下的失效处理

| 筛选模式 | 取消操作 | 行为 |
|----------|---------|------|
| 已选照片 (starred) | 取消标星 | 照片从列表消失，自动选下一张 |
| 废片 (rejected) | 取消废片 | 照片从列表消失，自动选下一张 |
| 全部照片 (all) | 标星/废片 | 照片保留在列表，自动推进 |

实现位置: [BrowserPage.tsx:114-143](frontend/src/pages/BrowserPage.tsx#L114-L143) `getNextIdAfterAction()`

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
