# Decision Intelligence Demo UI

React/Vite browser demo for the Decision Intelligence guided optimization chat.

Use this app for nontechnical demos. It connects to the local FastAPI backend
and walks a user through the guided chat workflow, then renders optimization
results in the browser.

## Run Locally

From the project root, start the full local demo with one command:

```bash
make demo-ui
```

This starts:

- FastAPI API: `http://127.0.0.1:8000`
- React/Vite UI: `http://127.0.0.1:5173/`

Stop both servers with `Ctrl+C`.

Equivalent direct script:

```bash
./scripts/run_demo_ui.sh
```

The script uses the project `.venv`, installs frontend dependencies if
`frontend/app/node_modules` is missing, and cleans up both server processes
when it exits.

### Manual Fallback

Open two terminals from the project root.

#### Terminal 1: Python API

```bash
cd "/Users/joshualutkemuller/Documents/Quant Sandbox/opt-intelligence"
source .venv/bin/activate
uvicorn decision_intelligence.api.app:app --host 127.0.0.1 --port 8000
```

Quick health check:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status":"ok"}
```

#### Terminal 2: Browser UI

```bash
cd "/Users/joshualutkemuller/Documents/Quant Sandbox/opt-intelligence/frontend/app"
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173/
```

## Demo Script

Use this line-by-line flow in the chat panel:

```text
I want to optimize money market cash
PORT_204
$500 million
30%
60%
40%
60
50%
4
5%
scipy
lp
stress
yes
```

The app should update the workflow sidebar as fields are collected and render
the allocation dashboard after confirmation.

To demo the sequential workflow engine, choose a template in the
**Workflow Template** selector, then click **Workflow** in the chat header.
Registered workflows can be listed with:

```text
GET /api/workflows
```

For repeatable stakeholder walkthroughs, choose a named **Demo Preset** before
running the workflow. Presets package the workflow id, portfolio id, seed,
context overrides, talking points, and success criteria. Registered presets can
be listed with:

```text
GET /api/demo-presets
```

The sidebar renders editable **Preset Inputs** from the selected workflow's
catalog `inputs`. These values are prefilled from the selected preset and are
compiled into the workflow run payload before execution. Click **Review** to
open the presenter guardrail panel, confirm changed fields and warnings, then
click **Run Demo**.

Completed workflow demos are saved to browser-local run history. Use the
**Run History** selector to restore a prior result or replay the exact stored
payload against the local API. History is stored in `localStorage` and kept to
the most recent 12 runs.

After a workflow run, click **Export Package** to download a self-contained
HTML stakeholder package. The package includes the workflow summary,
recommendation, presenter talking points, success criteria, plan timeline,
validation summary, dependency changes, risks, next actions, and the embedded
audit payload needed to reproduce the run locally.

The run action calls:

```text
POST /api/workflows/run
```

The package action calls:

```text
POST /api/workflows/export-package
```

The UI renders the returned `step_results`, `trace`, and `validation_summary`
as a progress timeline for the financing → collateral → money-market workflow.
It also displays dependency effects, such as upstream funding or collateral
pressure increasing downstream money-market liquidity requirements.
After a run, the workflow explanation panel summarizes the overall
recommendation, key drivers, dependency changes, risks, and suggested next
actions from the top-level `explanation_report`.

Registered demo templates:

- Portfolio Rebalance MVO
- Liquidity Stress Funding Workflow
- Funding Capacity Shock
- Collateral Liquidity Review
- Money Market Policy Optimization
- Treasury Cash Movement
- Margin Call Workflow

The **Balanced MVO Rebalance** preset demonstrates the Asset Allocation MVO
optimizer in the same browser workflow shell, with editable inputs for
portfolio notional, target annual return, risk aversion, max single asset
weight, and minimum cash weight. MVO results show expected return, volatility,
and Sharpe in the recommendation metrics.

The **Collateral HQLA Schedule Stress** preset mirrors the collateral MP4 demo
path. Click **Load Collateral HQLA** to prefill the collateral schedule sample,
ingest the schedule, optionally ask local Ollama to explain the control changes,
then run the collateral liquidity workflow. The browser renders
**Collateral HQLA Analytics** with before/after liquidity profile, HQLA tier
exposure, concentration usage, allocation counts, and dependency effects.

The **Production Adapter** panel surfaces the production optimizer catalog from
`GET /api/production-optimizers`. Select **Balanced MVO Rebalance**, switch the
runtime from **Phase 1** to **Production**, then run the workflow to show model
version, config version, data snapshot ID, solver version, and reproducibility
fingerprint from the production adapter evidence. **Collateral HQLA Schedule
Stress** can run collateral and downstream money-market steps through production
adapters. **Treasury Cash Movement** and **Margin Call Workflow** are
production-only operational demos that surface transfer recommendations,
assigned/deferred queue actions, and reproducibility evidence.

The **Evidence Room** panel is the live audit viewer for the current workflow.
It combines document extraction evidence, model/runtime evidence, solver
metadata, validation checks, governance state, and workflow trace events before
the user downloads the JSON/PDF/CSV/XLSX evidence package.
For operational workflows, the exported evidence package includes an
`operational_actions` table for cash transfers or margin-call queue actions.

The corresponding YAML template configs live in:

```text
config/workflows/
```

Preset YAML configs live in:

```text
config/demo_presets/
```

`decision_intelligence.workflows.config_loader` validates those configs for
metadata, default context, inputs, steps, and dependency rules.
`decision_intelligence.workflows.demo_presets` validates the repeatable demo
walkthrough package.

## Build Check

```bash
cd "/Users/joshualutkemuller/Documents/Quant Sandbox/opt-intelligence/frontend/app"
npm run build
```

## Troubleshooting

- If the UI says the API is unavailable, confirm the FastAPI server is running
  on `http://127.0.0.1:8000`.
- If `npm run dev` says the port is already in use, stop the old Vite process
  or run `npm run dev -- --port 5174`.
- If the backend cannot import `decision_intelligence`, run it from the project
  root with the `.venv` activated.
