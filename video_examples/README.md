# Video Examples

This folder stores presentation-ready demo clips for the Decision Intelligence
platform.

## Files

| File | Purpose |
|---|---|
| `decision-intelligence-demo.mp4` | Primary proof-of-concept video path. |
| `decision-intelligence-demo.webm` | Browser-friendly copy of the primary demo. |
| `governed-mvo-presentation-example.gif` | Short alternate presentation clip for the governed MVO asset-allocation workflow. |

## Regenerate Governed MVO Example

```bash
.venv/bin/python scripts/generate_presentation_video_example.py
```

The generator uses real local optimizer output, renders an animated GIF with
Pillow, and attempts to convert the GIF to MP4 with macOS `avconvert` when that
local tool accepts the generated source format.
