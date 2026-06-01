# Blur Detection Module (V1 — Legacy)

> ⚠️ **V1 已被 V2 取代。** 请使用 `backend/ai/blur_detector_v2/` 中的多区域拉普拉斯检测器。
> V1 保留仅用于对照测试。

## Description
V1 uses a global Laplacian variance approach — a single sharpness score for the entire image.
This works well for simple scenes but produces high false-positive rates on photos with
bokeh (blurred backgrounds behind sharp subjects) or plain backgrounds (white walls, sky).

## Problem with V1
- **Bokeh portraits**: Sharp subject + blurred background → flagged as blurry (false positive)
- **Plain backgrounds**: White/grey wall → low variance → flagged as blurry (false positive)
- **Overall accuracy**: Poor on professional photography with intentional background blur

## CLI Usage
```bash
python blur_detector.py --input ./photos
```

## Dependencies
- OpenCV (v4.10+)
- NumPy
