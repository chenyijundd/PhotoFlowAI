# PhotoFlow AI — 导入模块

## 导入流程图

```
用户点击 "导入照片目录"
        │
        ▼
┌─────────────────┐
│  Electron        │  dialog.showOpenDialog()
│  文件夹选择      │  仅允许目录选择
└────────┬────────┘
         │ 用户选择目录
         ▼
┌─────────────────┐
│  IPC invoke     │  preload → main → HTTP POST /api/import
│  import-photos  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  import_service.py  →  workflow.import_directory()   │
└────────┬────────────────────────────────────────────┘
         │
    ┌────┴────┐
    │ Step 1  │  collect_scan(directory)
    │ 扫描    │  image_loader.utils
    └────┬────┘
         │ PhotoInfo 列表
         ▼
    ┌────┴────┐
    │ Step 2  │  generate_single_thumbnail()
    │ 缩略图   │  thumbnail_cache.utils
    └────┬────┘
         │ 200px JPEG → cache/thumbnails/
         ▼
    ┌────┴────┐
    │ Step 3  │  repo.insert_photos()
    │ 写库     │  INSERT OR IGNORE
    └────┬────┘
         │ SQLite → database/photoflow.db
         ▼
    ┌────┴────┐
    │ Step 4  │  {total, imported, skipped, errors}
    │ 统计     │
    └────┬────┘
         │
         ▼
┌─────────────────┐
│  React 页面     │  自动调用 refresh() → 显示新照片
│  显示结果       │
└─────────────────┘
```

## 模块调用关系

```
importer/
├── __init__.py         日志配置（logs/import.log）
├── workflow.py         编排 4 步流程（核心）
├── import_service.py   FastAPI 路由 /api/import
└── README.md           本文档

workflow.py 调用：
  ├── backend.image_loader.utils.collect_scan()
  ├── backend.thumbnail_cache.utils.generate_single_thumbnail()
  ├── backend.thumbnail_cache.cache_manager.DEFAULT_CACHE_DIR
  └── database.repository.PhotoRepository.insert_photos()
```

## 错误处理机制

| 场景 | 处理方式 |
|------|----------|
| 目录不存在 | HTTP 400，返回详细错误信息 |
| 单张图片缩略图生成失败 | 记录 warning 到 logs/import.log，继续处理其他图片 |
| 数据库写入失败 | HTTP 500，终止导入 |
| 重复导入同一目录 | INSERT OR IGNORE 跳过已存在的 image_id；缩略图已存在则不重新生成 |

所有导入操作记录到 `logs/import.log`，包含每步的时间戳和结果。

## 当前限制

- 单线程顺序处理（大目录可能需要数秒）
- 无 WebSocket 实时进度推送
- 无导入暂停/取消功能
- 不支持嵌套目录选择（仅单次选择）

## 后续扩展点

- 多线程/异步缩略图生成
- 实时进度推送（Server-Sent Events）
- 导入队列 + 批量目录导入
- 增量扫描（仅处理新增/修改文件）
