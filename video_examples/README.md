# Video Examples

This folder stores presentation-ready demo clips for the Decision Intelligence
platform.

## Files

| File | Purpose |
|---|---|
| `decision-intelligence-demo.mp4` | Primary proof-of-concept video path. |
| `decision-intelligence-demo.webm` | Browser-friendly copy of the primary demo. |
| `governed-mvo-presentation-example.gif` | Short alternate presentation clip for the governed MVO asset-allocation workflow. |
| `liquidity-stress-orchestration-example.webm` | 72 second silent presentation clip showing a cross-workflow liquidity stress story. |
| `mvo-constraint-negotiation-example.webm` | 76 second silent presentation clip showing MVO tradeoff exploration and constraint negotiation. |
| `policy-to-audit-evidence-example.webm` | 68 second silent presentation clip showing policy ingestion through audit evidence packaging. |

## Regenerate Compelling WebM Examples

```bash
node scripts/generate_compelling_video_examples.mjs
```

The WebM generator uses local Playwright Chromium to record deterministic
1280x720 canvas animations. Each clip is designed for a 1 to 1.5 minute
presentation slot and uses a compressed 1.25x demo pacing.

## Regenerate Governed MVO Example

```bash
.venv/bin/python scripts/generate_presentation_video_example.py
```

The generator uses real local optimizer output, renders an animated GIF with
Pillow, and attempts to convert the GIF to MP4 with macOS `avconvert` when that
local tool accepts the generated source format.
