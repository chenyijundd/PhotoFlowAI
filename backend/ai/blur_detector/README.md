# Blur Detection Module

检测照片模糊程度，基于传统的 **Laplacian Variance** 算法。

## Laplacian Variance 原理

1. 将原图转为灰度图
2. 对灰度图应用 Laplacian 算子（二阶导数），提取图像中的高频信息
3. 计算 Laplacian 响应值的方差（variance）

**直觉**：清晰的图像包含丰富的边缘/纹理信息 → Laplacian 响应值方差大。模糊图像缺少高频细节 → 方差小。

## Threshold 规则

- `variance >= 100` → 清晰（`is_blur = 0`）
- `variance < 100` → 模糊（`is_blur = 1`）

Threshold 当前写死为 100，后续可改为可调参数。

## 数据流

```
用户点击「检测模糊照片」
         │
         ▼
POST /api/ai/blur-detect  { photo_ids: [...] }
         │
         ▼
service.run_blur_detection()
         │
         ├── 逐一读取原图（禁止用缩略图）
         ├── detector.calculate_blur()
         │     ├── cv2.imread()
         │     ├── cv2.cvtColor(gray)
         │     ├── cv2.Laplacian().var()
         │     └── return (score, is_blur)
         ├── repo.update_blur_status(id, score, is_blur)
         └── 日志记录到 logs/blur_detection.log
```

## API 说明

### `POST /api/ai/blur-detect`

请求：
```json
{ "photo_ids": ["id1", "id2", ...] }
```

响应：
```json
{ "processed": 100, "blurred": 12 }
```

### `GET /api/photos/blur?limit=100&offset=0`

返回 `is_blur == 1` 的照片，分页格式与 `/api/photos` 一致。

## 当前限制

- Threshold 写死 100，不可调
- 单线程顺序处理（大图较多时较慢）
- 不处理黑白/特殊色调照片
- 不区分运动模糊和失焦模糊
- 不支持 GPU 加速

## 后续扩展点

- Threshold 可调参数（UI 滑块）
- 多线程/异步批量处理
- 运动模糊 vs 失焦模糊分类
- 与闭眼检测、重复检测联合评分
- ONNX 深度学习模型升级路径
