"""
PhotoFlow AI — 800 px AI Preview Cache

Provides pre-generated 800 px JPEG previews shared by multiple
AI analysis steps:

- **Blur detection**: single-global-Laplacian pre-screening on
  800 px preview avoids loading the full 24 MP original for ~80 %
  of photos (those that are clearly sharp or clearly blurry).
- **Eye detection**: MediaPipe face detection works accurately
  on 800 px images, allowing eye analysis to skip the expensive
  HEIC/RAW decode entirely when a preview is already on disk.

Previews are cached in ``<project>/cache/ai_previews/`` and are
generated lazily on first use.  Once cached, subsequent analysis
runs (e.g. threshold tuning) are dramatically faster.
"""
