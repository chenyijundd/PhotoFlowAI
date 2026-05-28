# Blur Detection Module

## Description
Detects blurred images caused by misfocus, motion blur, or camera shake.

## CLI Usage
```bash
python blur_detector.py --input ./photos
```

## Example Input
- A sharp portrait photo
- A motion-blurred action shot
- An out-of-focus image

## Example Output
```json
{
    "wedding_001.jpg": {"score": 0.95, "is_blurry": false},
    "wedding_002.jpg": {"score": 0.32, "is_blurry": true}
}
```

## Scoring
- 0.0 - 0.4: Blurry
- 0.4 - 0.7: Acceptable
- 0.7 - 1.0: Sharp

## Dependencies
- OpenCV (v4.10+)
- NumPy
