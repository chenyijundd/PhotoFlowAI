# Export Module

职业摄影导出工作流 — 流式文件复制，支持协作取消。

## 核心原则

- **仅复制原文件** — 不转码、不加水印、不重命名模板
- **流式处理** — 逐文件处理，不全部加载到内存
- **协作取消** — 文件间检查取消标志，即时停止
- **单文件容错** — 单张失败不中止整个导出

## 模块结构

```
backend/exporter/
├── __init__.py    # 模块入口
├── models.py      # 数据模型（ExportMode 枚举、请求/响应）
├── utils.py       # 工具函数（安全复制、重名处理）
├── service.py     # 编排服务（取消支持）
└── README.md      # 本文件
```

## 导出模式

### Picked
- `star_rating == 1 AND is_rejected == 0`
- 输出目录：`{target}/Picked/`

### Rejected
- `is_rejected == 1`
- 输出目录：`{target}/Rejected/`

### Current Filter
- 前端传入的 photo_id 列表
- 输出目录：`{target}/CurrentFilter/`

### Compare
- 当前重复组的全部照片
- 输出目录：`{target}/CompareExport/`

## 文件名安全

同名文件自动追加序号：
```
IMG_0001.JPG  →  IMG_0001.JPG（不存在则直接用）
IMG_0001.JPG  →  IMG_0001_1.JPG（已存在则追加 _1）
IMG_0001.JPG  →  IMG_0001_2.JPG（_1 也存在则继续递增）
```

最多尝试 999 次，超过报错。

## 取消机制

协作式取消（cooperative cancel）：
1. 启动导出 → 返回 `export_id`
2. 导出逐文件循环，每文件前检查取消标志
3. 前端发 `POST /api/export/cancel/{export_id}` 设置标志
4. 后台检测到标志 → 立即停止，状态设为 "cancelled"

## API

### POST /api/export/start
启动导出。返回 `export_id`。

### GET /api/export/progress/{export_id}
轮询进度。返回当前处理数/总数/当前文件名。

### POST /api/export/cancel/{export_id}
取消运行中的导出。

### GET /api/export/summary/{export_id}
获取最终统计（已完成/已取消导出）。

## 日志

记录到 `logs/export.log`：
- 导出开始（模式、总数、目标目录）
- 导出取消
- 导出完成（成功/失败/跳过/耗时）
- 文件错误详情

## 当前限制

- 仅复制原文件（不转码）
- 无水印、无重命名模板
- 无 RAW 处理
- 无 GPU 加速
- 无多线程
- 无增量导出（每次全量）
- `.current_file` 在取消后可能为空
- 按 Ctrl+C 杀进程会丢失取消状态（内存存储）

## 后续扩展点

- 导出格式转换（JPEG 压缩质量、尺寸）
- 自定义文件名模板
- 水印叠加
- 导出预设（保存/加载设置）
- 后台任务队列（取消后不清除状态）
- RAW 文件处理
- Lightroom 目录导出
- 云同步导出
- 导出历史管理
