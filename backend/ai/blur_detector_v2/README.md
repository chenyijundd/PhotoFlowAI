# Blur Detection V2 — Multi-Patch Laplacian

## Description
Content-aware blur detection that correctly handles bokeh portraits and plain backgrounds.
Uses a 4x4 grid of Laplacian variance patches with center weighting and top-50% median
to focus on the sharpest regions of the image.

> **Pipeline role (L2)**: Runs second in the cascade after eye detection. Blur is
> flagged for manual review — NOT auto-rejected. Closed-eye photos are skipped.
> See the cascade design doc for full context.

## Algorithm

```
1. Divide image into 4x4 = 16 patches
2. Compute Laplacian variance for each patch
3. Apply center-weighting (x1.5 for center 4 patches)
4. Take median of top 50% patches (ignore plain background regions)
5. Composite score: weighted x 0.4 + top_median x 0.6
6. Threshold: score < 55 -> blurry
```

## Why V2 beats V1
- **Bokeh portraits**: Sharp subject in center -> center patches score high -> not flagged as blurry
- **Plain backgrounds**: Edge patches ignored by top-50% median -> not flagged as blurry
- **True blur**: All 16 patches score low -> correctly flagged

## CLI Usage
```bash
# Analyze a directory of photos
python -m backend.ai.blur_detector_v2.cli --input ./photos

# Custom threshold (default 55)
python -m backend.ai.blur_detector_v2.cli --input ./photos --threshold 60

# Custom grid size (default 4)
python -m backend.ai.blur_detector_v2.cli --input ./photos --grid 5
```

## Example Output
```json
{
    "wedding_001.jpg": {"final_score": 78.5, "is_blur": false, "weighted": 72.3, "top_median": 82.1},
    "wedding_002.jpg": {"final_score": 42.3, "is_blur": true,  "weighted": 38.1, "top_median": 45.0},
    "wedding_003.jpg": {"final_score": 91.2, "is_blur": false, "weighted": 88.7, "top_median": 92.5}
}
```

## API Integration
The detector is available as a background-thread service:
```python
from backend.ai.blur_detector_v2.service import start_blur_detection_v2, get_blur_progress_v2

task_id = start_blur_detection_v2(photo_ids=["id1", "id2"], threshold=55.0)
# Poll: get_blur_progress_v2(task_id)
```

## Scoring
- >= 55: Sharp (content-aware)
- < 55: Blurry

## Threshold Tuning
- Default: 55 (tested optimal for wedding photography)
- Lower (30-40): Only flag severely blurred photos
- Higher (70-80): Be more aggressive, flag slightly soft photos
- Valid range: 20-200

## Dependencies
- OpenCV (v4.10+)
- NumPy
