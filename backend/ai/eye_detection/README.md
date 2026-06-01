# Eye Detection Module

> **Pipeline role (L1 — first & highest priority)**: Runs first in the detection
> cascade. Closed-eye photos are auto-rejected and skip all subsequent detection
> (blur, burst, duplicate). This is the highest-confidence defect signal.

## Description

Detects closed / half-closed eyes in portrait and group photos using
**MediaPipe Face Mesh** + **Eye Aspect Ratio (EAR)**.

Algorithm reference: Soukupová & Čech, 2016 — *"Real-Time Eye Blink Detection using Facial Landmarks"*

## How It Works

```
Input image
    ↓
MediaPipe Face Detection (all faces, max 10)
    ↓
Face Mesh → 468 3D landmarks per face
    ↓
Extract 6 periocular landmarks per eye
    ↓
Compute Eye Aspect Ratio (EAR) for each eye
    ↓
EAR < 0.18 → CLOSED
0.18 ≤ EAR < 0.22 → HALF-CLOSED (flagged too)
EAR ≥ 0.22 → OPEN
    ↓
If ANY face has ANY eye closed → is_closed_eye = 1
No face detected → eyes_open = True, face_detected = False
```

## Eye Aspect Ratio (EAR)

```
         p1
    . . . . . .
 p2 .         . p3       EAR = (|p2-p6| + |p3-p5|) / (2 × |p1-p4|)
    .         .
 p4 .         . p5
    . . . . . .
         p6

Open eyes   → EAR ≈ 0.30–0.40
Half-closed → EAR ≈ 0.18–0.25
Closed      → EAR ≈ 0.08–0.18
```

## CLI Usage

```bash
# Single image
python -m backend.ai.eye_detection.cli --input ./test.jpg

# Directory batch
python -m backend.ai.eye_detection.cli --input ./photos

# Export results to JSON
python -m backend.ai.eye_detection.cli --input ./photos --output results.json
```

## Example Input

- Portrait with both eyes open
- Portrait with eyes closed / mid-blink
- Group wedding photo (multiple faces)
- Landscape / non-portrait (no face detected)

## Example Output

```json
{
    "file": "bride_open_eyes.jpg",
    "eyes_open": true,
    "score": 0.3521,
    "face_detected": true,
    "num_faces": 1,
    "closed_count": 0,
    "per_face": [
        {
            "face_index": 0,
            "left_ear": 0.3612,
            "right_ear": 0.3521,
            "min_ear": 0.3521,
            "is_closed": false
        }
    ],
    "processing_time_ms": 85.3
}
```

```json
{
    "file": "group_blink.jpg",
    "eyes_open": false,
    "score": 0.1123,
    "face_detected": true,
    "num_faces": 5,
    "closed_count": 1,
    "per_face": [
        {"face_index": 0, "left_ear": 0.3410, "right_ear": 0.3289, "min_ear": 0.3289, "is_closed": false},
        {"face_index": 1, "left_ear": 0.1201, "right_ear": 0.1123, "min_ear": 0.1123, "is_closed": true},
        ...
    ],
    "processing_time_ms": 112.7
}
```

## Scoring Thresholds

| EAR Range | State | Action |
|-----------|-------|--------|
| < 0.18 | Fully closed | Flagged (`is_closed_eye = 1`) |
| 0.18 – 0.22 | Half-closed / squinting | Flagged (`is_closed_eye = 1`) |
| > 0.22 | Open | Not flagged |

## Dependencies

- MediaPipe >= 0.10.0
- OpenCV >= 4.10
- NumPy

## Performance

- ~50–150 ms per photo (depends on resolution and face count)
- Face Mesh model is loaded once and cached across calls
- Memory: ~50 MB for the MediaPipe model

## Design Decisions

- **Why not dlib?**  dlib is difficult to install on Windows (requires CMake + Visual Studio build tools). MediaPipe is a pure pip install.
- **Why EAR and not a CNN classifier?**  EAR is deterministic, fast, and well-validated. No GPU needed. Results are interpretable (geometric measurement).
- **Why flag half-closed eyes?**  In wedding photography, a mid-blink or squinting expression is usually a reject. The photographer can always un-reject if it's actually a genuine smile.
- **Why max 10 faces?**  Covers wedding group photos (bridal party + family). Beyond 10 faces the photo is likely a crowd shot where individual eye state isn't the primary concern.
