# Best Selector — Best-in-Burst Recommendation

## Description
For each burst group, automatically selects the single best photo using a
multi-criteria ranking algorithm. The selected photo is flagged as
`is_best_in_burst` for use in the one-click cull workflow.

## Algorithm

```
For each burst group:
  1. Exclude rejected photos
  2. Exclude closed-eye photos (is_closed_eye = 1) — L1 fatal
  3. Exclude blurry photos (is_blur = 1)
  4. Exclude photos without blur_score
  5. Rank remaining by blur_score DESC
  6. If top scores are within 10% of each other -> tie-break by file_size DESC
  7. If file sizes are within 20% of each other -> tie-break by resolution (width x height)
```

## Tie-Breaking Rationale
- **blur_score**: Primary criterion — the sharpest photo is usually the best
- **file_size**: When sharpness is similar, larger file = more detail (less compression artifacts)
- **resolution**: Final tie-breaker — higher resolution preferred

## CLI Usage
```bash
# Select best for all burst groups
python -m backend.ai.best_selector.cli --db ./photos.db
```

## Example Output
```
Burst group 20240518_A7M3_001:
  1. DSC04221.jpg  score=87.3  12.4MB  6000x4000  << RECOMMENDED
  2. DSC04222.jpg  score=85.1  11.8MB  6000x4000
  3. DSC04223.jpg  score=82.7  12.1MB  6000x4000
  4. DSC04224.jpg  (blurry - excluded)
  5. DSC04225.jpg  (rejected - excluded)

Summary: 12 groups, 12 recommended, 0 no-candidate, 0 skipped
```

## API Integration
```python
from backend.ai.best_selector.service import select_best_for_all_bursts

repo = PhotoRepository()
summary = select_best_for_all_bursts(repo)
# summary.recommended_count -> number of photos flagged as best-in-burst
```

## Parameters
- **BLUR_TIE_PCT** (0.10): Top scores within 10% are considered tied
- **SIZE_TIE_PCT** (0.20): File sizes within 20% are considered tied

## Dependencies
- Python standard library
- SQLite (via PhotoRepository)
