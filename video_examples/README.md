# Video Examples

This folder stores presentation-ready demo clips for the Decision Intelligence
platform.

## Files

| File | Purpose |
|---|---|
| `audit/policy-to-audit-evidence-example.mp4` | 68 second silent presentation clip showing policy ingestion through audit evidence packaging. |
| `collateral/collateral-hqla-frontend-orchestration-demo.mp4` | 102 second real front-end browser capture with burned-in dynamic captions showing collateral schedule ingestion, bilateral/CCP/exchange obligations, production runtime, scenario comparison, workflow execution, traceability, analytics, governance, and evidence room review. |
| `collateral/collateral-liquidity-hqla-orchestration-example.mp4` | 88 second silent collateral stress clip showing schedule upload, local LLM chat, orchestration, before/after liquidity analytics, HQLA tier exposure, allocation stats, and governance review. |
| `collateral/collateral-schedule-ingestion-stress-example.mp4` | 82 second silent collateral clip showing schedule ingestion, haircut and concentration-limit extraction, preflight, optimization, and before/after HQLA analytics. |
| `collateral/liquidity-stress-orchestration-example.mp4` | 72 second silent presentation clip showing a cross-workflow liquidity stress story. |
| `money_market/money-market-pdf-policy-optimization-demo.mp4` | 104 second MP4 with burned-in dynamic captions showing a visible first-page PDF preview, money-market PDF upload, ingestion, Ollama-assisted discussion, optimization, before/after analytics, traceability, governance, and evidence review. |
| `mvo/governed-mvo-presentation-example.mp4` | Short alternate presentation clip for the governed MVO asset-allocation workflow. |
| `mvo/ips-pdf-upload-optimization-workflow-example.mp4` | 84 second silent clip showing a full IPS PDF upload, ingestion review, optimization workflow, and before/after analytics. |
| `mvo/ips-to-optimization-workflow-example.mp4` | 78 second silent clip showing IPS ingestion, before analytics, optimization, and after analytics. |
| `mvo/mvo-constraint-negotiation-example.mp4` | 76 second silent presentation clip showing MVO tradeoff exploration and constraint negotiation. |

## Regenerate Compelling WebM Examples

```bash
node scripts/generate_compelling_video_examples.mjs
```

The WebM generator uses local Playwright Chromium to record deterministic
1280x720 canvas animations. Convert generated WebM files to MP4 before checking
them into `video_examples/`. Each clip is designed for a 1 to 1.5 minute
presentation slot and uses a compressed 1.25x demo pacing.

## Regenerate Collateral MP4 Examples

```bash
.venv/bin/python scripts/generate_collateral_video_examples.py
```

This generator renders deterministic 1280x720 Pillow frames and encodes them
with the bundled FFmpeg binary from `frontend/app/node_modules`. The two
outputs are:

- `video_examples/collateral/collateral-schedule-ingestion-stress-example.mp4`
- `video_examples/collateral/collateral-liquidity-hqla-orchestration-example.mp4`

The React demo workspace now has a matching **Load Collateral HQLA** path. Start
the UI with `make demo-ui`, click **Load Collateral HQLA**, ingest the sample
collateral schedule, use **Ollama Chat** for the live explanation, then run the
collateral liquidity workflow and show **Collateral HQLA Analytics** for
before/after liquidity, HQLA tier exposure, and allocation stats.

## Record Real Front-End Collateral HQLA Demo

```bash
node scripts/record_collateral_hqla_frontend_video.mjs
```

This recorder starts the local FastAPI backend and Vite React app when they are
not already running, drives the actual browser UI with Playwright, records the
collateral HQLA schedule path, and converts the captured browser video to:

- `video_examples/collateral/collateral-hqla-frontend-orchestration-demo.mp4`

The clip is intentionally paced for a 1:30 to 2:00 presentation slot and shows
the live UI rather than a rendered storyboard. It burns in dynamic captions with
stage number, stage title, plain-English explanation, current action, and
progress bar.

The workflow shown is `collateral_liquidity_review`:

1. `collateral_001` runs the collateral optimizer against bilateral CSA,
   clearing-house, and exchange margin obligations.
2. `money_market_001` then runs the money-market optimizer using the downstream
   liquidity context from the collateral step.

The schedule ingestion path is configured for auto mode: local Ollama-assisted
extraction can be used when available, and deterministic extraction/validation
keeps the converted fields structured before they become optimizer inputs.

## Record Real Front-End Money-Market PDF Demo

```bash
.venv/bin/python scripts/generate_sample_money_market_policy_pdf.py
node scripts/record_money_market_policy_frontend_video.mjs
```

This recorder starts the local FastAPI backend and Vite React app when needed,
loads the **Treasury MMF Policy Optimization** path, uploads
`examples/policies/sample_money_market_policy.pdf`, ingests the document,
optionally asks local Ollama for a plain-English policy explanation, runs the
money-market optimizer, and records:

- `video_examples/money_market/money-market-pdf-policy-optimization-demo.mp4`

The workflow shown is `money_market_policy_optimization`:

1. `money_market_001` runs the money-market optimizer against PDF-derived cash,
   liquidity, WAM, prime exposure, and single-fund concentration controls.
2. The UI shows before/after yield, daily and weekly liquidity, WAM, prime
   exposure, top-fund concentration, recommended fund count, document-to-
   constraint traceability, governance, and evidence-room metadata.

The ingestion path uses auto mode: local Ollama-assisted extraction can be used
when available, while deterministic validation keeps the converted fields
structured and repeatable before solve.

If local browser recording is unavailable, generate the deterministic MP4
directly:

```bash
.venv/bin/python scripts/generate_money_market_video_examples.py
```

This writes the same checked-in MP4 path under `video_examples/money_market/`
using real local money-market optimizer output and presentation-safe rendered
captions. The opening stage renders the first page of
`examples/policies/sample_money_market_policy.pdf` into the frame so audiences
can see that a real PDF document is being ingested.

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

## Regenerate LLM-Assisted IPS Interaction MP4

```bash
node scripts/generate_llm_ips_interactive_workflow_video.mjs
```

This generator shows the LLM-assisted IPS backend configured for a local
Ollama model through the OpenAI-compatible provider, then shows the user
interaction, proposed fields, deterministic validator review, optimization run,
and before/after portfolio analytics.

## Regenerate Governed MVO Example

```bash
.venv/bin/python scripts/generate_presentation_video_example.py
```

The generator uses real local optimizer output and renders an animated GIF with
Pillow. Encode the generated GIF to MP4 before checking the presentation clip
into `video_examples/`.
