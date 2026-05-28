# Scoring Module

## Description
Computes a composite 1-5 star rating for each photo by combining clarity, face status, exposure, and composition scores.

## CLI Usage
```bash
python scorer.py --input ./photos
```

## Example Output
```json
{
    "photo_001.jpg": {"overall": 4, "clarity": 5, "face": 4, "exposure": 4, "composition": 3}
}
```

## Scoring Dimensions
- **clarity**: Sharpness and focus quality (from blur detection)
- **face**: Eye open status and expression (from eye detection)
- **exposure**: Basic exposure quality
- **composition**: Basic composition assessment
- **overall**: Weighted composite of all dimensions

## Dependencies
- Pillow
