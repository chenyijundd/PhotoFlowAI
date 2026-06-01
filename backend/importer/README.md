# Photo Import Module

## Description
Scans a directory for supported image files and imports them into the PhotoFlow AI
database. Handles duplicate detection (by file path), metadata extraction,
and triggers thumbnail generation.

## Supported Formats
- JPG / JPEG
- PNG

## Import Workflow
```
1. Scan directory recursively for image files
2. Filter to supported extensions
3. Check for duplicates (same file_path already in DB)
4. Extract metadata (dimensions, file_size, EXIF created_time)
5. Insert into SQLite database
6. Trigger thumbnail generation for new imports
```

## CLI Usage
```bash
# Import photos from a directory
python -m backend.importer.workflow --input ./photos
```

## API Usage
```http
POST /api/import
Body: { "directory": "/path/to/photos" }
```

## Response
```json
{
    "success": true,
    "total": 500,
    "imported": 495,
    "skipped": 5,
    "errors": 0
}
```

## Architecture
- **workflow.py**: Orchestrates the full import pipeline
- **import_service.py**: Database operations for import

## Dependencies
- Pillow (metadata extraction)
- SQLite (via database module)
