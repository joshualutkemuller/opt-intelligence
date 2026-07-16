# Decision Intelligence Demo UI

React/Vite browser demo for the Decision Intelligence guided optimization chat.

Use this app for nontechnical demos. It connects to the local FastAPI backend
and walks a user through the guided chat workflow, then renders optimization
results in the browser.

## Run Locally

Open two terminals from the project root.

### Terminal 1: Python API

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

### Terminal 2: Browser UI

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

To demo the sequential workflow engine, click **Workflow** in the chat header.
That calls:

```text
POST /api/workflows/run
```

The UI renders the returned `step_results`, `trace`, and `validation_summary`
as a progress timeline for the financing → collateral → money-market workflow.

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
