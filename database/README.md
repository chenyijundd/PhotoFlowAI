# Database Module (SQLite 图片索引系统)

## 模块作用

维护本地 SQLite 图片索引库，持久化图片元数据和 AI 分析结果。与 `image_loader` 配合使用，复用其扫描结果和稳定 ID。其他 AI 模块（模糊检测、闭眼检测、重复判断）通过此模块写入分析结果，UI 层通过此模块查询图片数据。

## 表结构说明

### photos 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `image_id` | TEXT PRIMARY KEY | 图片唯一 ID（由 image_loader 生成） |
| `file_name` | TEXT | 文件名 |
| `file_path` | TEXT | 文件绝对路径 |
| `thumbnail_path` | TEXT | 缩略图路径 |
| `file_size` | INTEGER | 文件大小（字节） |
| `width` | INTEGER | 图片宽度（像素） |
| `height` | INTEGER | 图片高度（像素） |
| `created_time` | TEXT | 文件创建时间（ISO-8601） |
| `blur_score` | REAL | 模糊检测得分 |
| `eye_score` | REAL | 闭眼检测得分 |
| `duplicate_group` | TEXT | 重复图分组 ID |
| `is_blur` | INTEGER | 是否模糊（0/1） |
| `is_closed_eye` | INTEGER | 是否闭眼（0/1） |
| `is_duplicate` | INTEGER | 是否重复（0/1） |
| `is_rejected` | INTEGER | 是否废片（0/1） |
| `star_rating` | INTEGER | 星级评分（NULL/0/1） |
| `burst_group` | TEXT | 连拍分组 ID（NULL=非连拍） |
| `burst_position` | INTEGER | 连拍组内序号（0-based） |
| `is_best_in_burst` | INTEGER | 是否为连拍组最佳（0/1） |
| `is_best_in_duplicate` | INTEGER | 是否为重复组最佳（0/1） |
| `manually_operated_at` | TEXT | 最后手动操作时间 |
| `created_at` | TEXT | 记录创建时间 |
| `updated_at` | TEXT | 记录更新时间 |

## CLI 运行方式

```bash
# 初始化数据库（自动创建表）
python -m database.db_manager --init

# 扫描目录并导入图片元数据
python -m database.db_manager --import "D:/Photos"

# 使用自定义数据库路径
python -m database.db_manager --db-path ./custom.db --init
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

```bash
# --init
{"status": "ok", "db_path": "D:/AI/PhotoFlowAI/database/photoflow.db"}

# --import
{"status": "ok", "imported": 3, "total_scanned": 3}
```

## 数据库位置

```
database/
├── db_manager.py      # CLI 入口
├── models.py          # 数据模型
├── repository.py      # Repository 模式 CRUD
├── connection.py      # 连接管理（Context Manager）
├── README.md
└── photoflow.db       # SQLite 数据库文件
```

- 默认路径：`{project_root}/database/photoflow.db`
- 创建策略：首次调用自动创建目录和表
- 连接管理：Context Manager 自动提交/回滚/关闭，无连接泄漏

## 与现有模块关系

- 依赖 `image_loader` 的 `collect_scan()` 获取图片元数据
- AI 模块（后续开发）通过 repository 写入分析结果
- UI 模块（后续开发）通过 repository 查询图片数据

## 当前限制

- 仅支持单文件 SQLite，不支持分布式
- 无增量更新检测（每次 --import 全量扫描）
- 无分页查询（大结果集需手动 LIMIT）

## 已实现特性

- ✅ 自动数据库迁移（新增字段自动 ALTER TABLE）
- ✅ Repository 模式 CRUD
- ✅ 批量事务支持
- ✅ Burst 组清空方法 `clear_burst_group()`（级联管道使用）
- ✅ 多条件筛选查询（按状态/评分/AI标签）
