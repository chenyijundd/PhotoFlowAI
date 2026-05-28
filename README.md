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
- [x] 筛选工作流 — 全部照片 / 已选照片（star_rating==1）/ 模糊照片 / 废片切换浏览

## 开发中 / 待实现

- [ ] AI 闭眼检测
- [ ] AI 重复照片检测
- [ ] AI 综合评分（1-5星）
- [ ] AI 选片报告
- [ ] 精选照片导出
- [ ] 手动微调
- [ ] 多选 + 批量操作

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
