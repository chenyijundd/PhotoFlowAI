# Duplicate Detection Module

## Description
Groups near-duplicate images from burst shots and recommends the best photo to keep.

## CLI Usage
```bash
python duplicate_detector.py --input ./photos
```

## Example Input
```
./photos/
  burst_001.jpg
  burst_002.jpg  (similar composition)
  unique.jpg     (different scene)
```

## Example Output
```json
{
    "groups": [
        {"best": "burst_001.jpg", "duplicates": ["burst_002.jpg"], "similarity": 0.95}
    ]
}
```

## Dependencies
- OpenCV (v4.10+)
- NumPy
