# Image Scanner Module

## 模块作用

递归扫描本地目录中的图片文件（JPG / JPEG / PNG），提取文件元信息（尺寸、大小、创建时间），返回结构化 JSON 数据。**不加载像素数据到内存**，支持 5000+ 图片目录。

## CLI 运行方式

```bash
# 基本扫描
python image_scanner.py --input "D:/Photos"

# 格式化输出
python image_scanner.py --input "D:/Photos" --pretty

# 限制输出条数
python image_scanner.py --input "D:/Photos" --limit 5
```

## 示例输入

```
D:/Wedding_Photos/
├── ceremony/
│   ├── img_001.jpg
│   ├── img_002.jpg
│   └── img_003.png
├── reception/
│   ├── img_010.jpeg
│   └── img_011.jpg
└── notes.txt          ← 自动跳过
```

## 示例输出

```json
{
  "total_count": 5,
  "errors": [],
  "photos": [
    {
      "id": "a1b2c3d4e5f6",
      "file_name": "img_001.jpg",
      "file_path": "D:/Wedding_Photos/ceremony/img_001.jpg",
      "file_size": 4256789,
      "created_time": "2026-05-20T14:30:00+00:00",
      "width": 6000,
      "height": 4000
    }
  ]
}
```

## 返回字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 基于相对路径的 MD5 前12位，同一文件跨扫描稳定 |
| file_name | string | 文件名（含扩展名） |
| file_path | string | 文件的绝对路径 |
| file_size | int | 文件大小（字节） |
| created_time | string | 文件创建时间（ISO-8601 UTC） |
| width | int | 图像宽度（像素，仅读头部） |
| height | int | 图像高度（像素，仅读头部） |

## 当前限制

- 仅支持 JPG / JPEG / PNG 格式
- 不支持 RAW / GIF / WEBP / TIFF
- 不读取 EXIF 元数据
- 不生成缩略图
- 不写入数据库
- 不支持网络路径 / NAS 自动挂载

## 后续扩展点

- RAW 格式支持
- EXIF 元数据读取
- 增量扫描（仅扫描新文件）
- 文件监视（自动检测新文件）
- 数据库持久化

## 模块依赖

- Python 标准库：os, hashlib, json, argparse, pathlib
- Pillow：仅读取图片头部信息（不加载像素数据）
