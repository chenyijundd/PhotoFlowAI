# Duplicate Detection Module

## Description
Groups near-duplicate images from burst shots using perceptual hashing (dHash)
and structural similarity (SSIM). Recommends the best photo to keep from each
duplicate group.

## Algorithm

```
1. Compute dHash (difference hash) for each image
2. Group photos with Hamming distance <= threshold
3. Within each group, compute SSIM for fine-grained comparison
4. Flag duplicates as is_duplicate = 1, assign duplicate_group UUID
```

## Difference from Burst Grouper
- **Duplicate Detection**: Finds visually similar photos (same composition, angle, scene). Works on any photos regardless of capture time.
- **Burst Grouper**: Groups photos by EXIF timestamp proximity (<= 2s apart). A burst may contain dissimilar photos.

These are complementary: duplicates remove redundancy, bursts enable best-frame selection.

## CLI Usage
```bash
python duplicate_detector.py --input ./photos
```

## Example Output
```json
{
    "groups": [
        {"best": "burst_001.jpg", "duplicates": ["burst_002.jpg"], "similarity": 0.95}
    ]
}
```

## API Integration
Available as a background-thread service:
```python
from backend.ai.duplicate_detector.service import start_duplicate_detection, get_duplicate_progress

task_id = start_duplicate_detection(photo_ids=["id1", "id2"])
# Poll: get_duplicate_progress(task_id)
```

## Dependencies
- OpenCV (v4.10+)
- NumPy
