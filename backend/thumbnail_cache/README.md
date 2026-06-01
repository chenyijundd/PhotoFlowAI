# Thumbnail Cache Module

## Description
Generates and caches thumbnail images for fast grid browsing. Produces
consistent-size JPEG thumbnails stored in a local cache directory with
automatic cache eviction.

## Features
- JPEG thumbnail generation with configurable size
- File-system-based cache with hash keys
- Cache eviction when exceeding max size
- Supports JPG, JPEG, PNG source formats

## CLI Usage
```bash
# Generate thumbnails for a directory
python -m backend.thumbnail_cache.thumbnail_generator --input ./photos --cache ./cache
```

## Cache Structure
```
cache/
  thumbnails/
    a1b2c3d4.jpg    # hash of original path -> thumbnail
    e5f6g7h8.jpg
```

## Architecture
- **thumbnail_generator.py**: Core generation logic (Pillow)
- **cache_manager.py**: Cache directory management, eviction, cleanup
- **models.py**: Data models for cache entries
- **utils.py**: Path hashing and file utilities

## Dependencies
- Pillow (PIL)
