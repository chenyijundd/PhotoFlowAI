# Image Loader Module

## Description
Scans local directories for supported image files (JPG, JPEG, PNG).

## CLI Usage
```bash
python loader.py --input ./photos
```

## Example Input
```
./photos/
  wedding_001.jpg
  wedding_002.png
  detail.jpeg
```

## Example Output
```
Found 150 images in ./photos
  ./photos/wedding_001.jpg
  ./photos/wedding_002.jpg
  ... and 148 more
```

## Dependencies
None (uses Python standard library).
