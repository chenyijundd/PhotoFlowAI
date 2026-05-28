# Eye Detection Module

## Description
Detects closed eyes and obvious facial expression issues in portrait photos.

## CLI Usage
```bash
python eye_detector.py --input ./photos
```

## Example Input
- Portrait with both eyes open
- Portrait with eyes closed
- Portrait with squinting

## Example Output
```json
{
    "portrait_open_eyes.jpg": {"eyes_open": true, "score": 0.98},
    "portrait_closed_eyes.jpg": {"eyes_open": false, "score": 0.12}
}
```

## Scoring
- 0.0 - 0.3: Eyes closed
- 0.3 - 0.6: Partially closed
- 0.6 - 1.0: Eyes open

## Dependencies
- MediaPipe (v0.10+)
- OpenCV (v4.10+)
