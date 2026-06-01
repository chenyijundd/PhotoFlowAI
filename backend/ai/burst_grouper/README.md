# Burst Grouper — EXIF Time-Clustering

## Description
Detects continuous-shooting (burst) sequences by clustering photos based on their
EXIF capture timestamps. A sliding window groups photos shot within 2 seconds
of each other into burst groups.

> **Pipeline role (L3)**: Runs third in the cascade after eye and blur detection.
> Closed-eye and blurry photos are cleared from burst groups so they don't
> influence group recommendations. Only clean photos participate in burst grouping.

## Algorithm

```
1. Sort all photos by EXIF created_time
2. Slide a window: if time_gap to previous photo <= 2s, same group
3. If gap > 2s, start a new group
4. Filter out groups with < 2 photos
5. Assign sequential burst_position within each group
```

## Why This Matters for Photographers
Wedding and event photographers shoot in bursts — holding the shutter for 3-10
rapid frames of the same moment. Identifying these groups lets the software:
- Show burst sequences together for comparison
- Recommend the sharpest frame in each group
- Batch-accept or batch-reject entire burst sequences

## CLI Usage
```bash
# Group by time gap (default 2.0 seconds)
python -m backend.ai.burst_grouper.cli --db ./photos.db

# Custom gap threshold
python -m backend.ai.burst_grouper.cli --db ./photos.db --gap 1.5
```

## Example Output
```
Found 12 burst groups from 500 photos
  Group sizes: min=2, max=8, avg=3.2
  Photos in bursts: 38 (7.6%)
  Photos not in bursts: 462 (92.4%)

Group size distribution:
  2 photos: 6 groups
  3 photos: 3 groups
  4 photos: 2 groups
  8 photos: 1 group
```

## API Integration
```python
from backend.ai.burst_grouper.service import start_burst_grouping, get_burst_progress

repo = PhotoRepository()
task_id = start_burst_grouping(repo, gap_seconds=2.0)
# Poll: get_burst_progress(task_id)
```

## Parameters
- **gap_seconds** (default 2.0): Maximum time gap to consider photos part of the same burst
- **MIN_BURST_SIZE** (2): Minimum photos to form a valid burst group

## Dependencies
- Python standard library (datetime, itertools)
- SQLite (via PhotoRepository)
