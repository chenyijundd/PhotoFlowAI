# Thumbnail Cache Module

## 模块作用

扫描本地图片目录，生成 200px 最大边 JPEG 缩略图，缓存至本地磁盘，避免重复生成。与 `image_loader` 模块配合使用，复用其稳定 ID 作为缩略图文件名。

## CLI 运行方式

```bash
# 基本用法：自动扫描并生成缩略图
python thumbnail_generator.py --input "D:/Photos"

# 指定自定义缓存目录
python thumbnail_generator.py --input "D:/Photos" --cache-dir ./my_cache

# 格式化 JSON 输出
python thumbnail_generator.py --input "D:/Photos" --pretty
```

## 示例输入

```
D:/Wedding_Photos/
├── ceremony/
│   ├── img_001.jpg    (6000x4000, 12MB)
│   └── img_002.png    (4000x6000, 8MB)
└── reception/
    └── img_003.jpeg   (3000x2000, 5MB)
```

## 示例输出

```json
{
  "summary": {
    "cache_dir": "D:/AI/PhotoFlowAI/cache/thumbnails",
    "generated": 3,
    "cached": 0,
    "errors": 0
  },
  "results": [
    {
      "image_id": "a1b2c3d4e5f6",
      "source_path": "D:/Wedding_Photos/ceremony/img_001.jpg",
      "thumbnail_path": "D:/AI/PhotoFlowAI/cache/thumbnails/a1b2c3d4e5f6.jpg",
      "success": true
    }
  ]
}
```

## 缓存目录说明

```
cache/
└── thumbnails/
    ├── a1b2c3d4e5f6.jpg    ← 缩略图
    └── f6e5d4c3b2a1.jpg
```

- 缓存路径：`{project_root}/cache/thumbnails/`
- 命名规则：`{image_id}.jpg`（与 `image_scanner` 的 ID 一致）
- 缩略图规格：200px 最大边，JPEG 格式，quality=85
- 宽高比保持不变，不裁切，不拉伸
- 已缓存的图片不会重复生成

## 当前限制

- 仅支持单线程顺序处理
- 不支持增量更新（检测文件变动）
- 不支持自定义缩略图尺寸（固定 200px）
- 无自动缓存清理机制

## 后续扩展点

- 多线程/异步批量生成
- 自定义缩略图尺寸参数
- 增量更新（仅处理新文件或修改过的文件）
- 缓存 LRU 清理策略
- WEBP 格式输出支持

## 依赖

- Pillow
- `backend.image_loader`（复用扫描和 ID 生成）
