# Video Examples

This folder stores presentation-ready demo clips for the Decision Intelligence
platform.

## Files

| File | Purpose |
|---|---|
| `decision-intelligence-demo.mp4` | Primary proof-of-concept video path. |
| `governed-mvo-presentation-example.mp4` | Short alternate presentation clip for the governed MVO asset-allocation workflow. |
| `ips-pdf-upload-optimization-workflow-example.mp4` | 84 second silent clip showing a full IPS PDF upload, ingestion review, optimization workflow, and before/after analytics. |
| `ips-to-optimization-workflow-example.mp4` | 78 second silent clip showing IPS ingestion, before analytics, optimization, and after analytics. |
| `liquidity-stress-orchestration-example.mp4` | 72 second silent presentation clip showing a cross-workflow liquidity stress story. |
| `mvo-constraint-negotiation-example.mp4` | 76 second silent presentation clip showing MVO tradeoff exploration and constraint negotiation. |
| `policy-to-audit-evidence-example.mp4` | 68 second silent presentation clip showing policy ingestion through audit evidence packaging. |

## Regenerate Compelling WebM Examples

```bash
node scripts/generate_compelling_video_examples.mjs
```

The WebM generator uses local Playwright Chromium to record deterministic
1280x720 canvas animations. Convert generated WebM files to MP4 before checking
them into `video_examples/`. Each clip is designed for a 1 to 1.5 minute
presentation slot and uses a compressed 1.25x demo pacing.

## Regenerate IPS Analytics MP4

```bash
node scripts/generate_ips_optimization_analytics_video.mjs
```

This generator records a temporary browser canvas stream, converts it to MP4,
and removes the temporary source file. It focuses on before/after portfolio
analytics so the IPS ingestion workflow shows investment impact as well as
evidence controls.

## Regenerate Full IPS PDF Upload MP4

```bash
.venv/bin/python scripts/generate_sample_full_ips_pdf.py
node scripts/generate_ips_pdf_upload_workflow_video.mjs
```

This generator uses `examples/policies/sample_full_ips.pdf` as the visible
source document, shows the PDF upload and preview steps, then carries the
extracted IPS constraints into the optimization workflow and before/after
portfolio analytics.

## Regenerate Governed MVO Example

```bash
.venv/bin/python scripts/generate_presentation_video_example.py
```

The generator uses real local optimizer output and renders an animated GIF with
Pillow. Encode the generated GIF to MP4 before checking the presentation clip
into `video_examples/`.
