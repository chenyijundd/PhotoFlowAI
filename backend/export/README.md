# Export Module

## Description
Copies selected photos to an output directory while preserving original folder structure.

## CLI Usage
```bash
python exporter.py --input ./photos --selected ./selected_list.txt --output ./exports
```

## Example Input
- Source directory with original photos
- Text file listing selected photo paths (one per line)

## Example Output
```
./exports/
  wedding_001.jpg
  wedding_003.jpg
```

## Dependencies
None (uses Python standard library).
