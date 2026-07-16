# Front-End GUI Plan and Handoff

## Purpose

Build a browser-based proof-of-concept interface that lets nontechnical users
run the Decision Intelligence Platform demos without using a terminal.

The GUI should surface the existing guided chat workflow, PDF intake flow,
optimizer execution, solver selection, governance status, scenario analysis,
and result exports in a polished, easy-to-demo experience.

The first version should not replace the Python optimization framework. It
should wrap the current deterministic orchestration layer and make it usable
through a friendly web interface.

---

## Local Demo Run Guide

Use the React/Vite app for browser-based demos.

Open two terminals from the project root.

Terminal 1 starts the Python API:

```bash
cd "/Users/joshualutkemuller/Documents/Quant Sandbox/opt-intelligence"
source .venv/bin/activate
uvicorn decision_intelligence.api.app:app --host 127.0.0.1 --port 8000
```

Terminal 2 starts the browser UI:

```bash
cd "/Users/joshualutkemuller/Documents/Quant Sandbox/opt-intelligence/frontend/app"
npm install
npm run dev
```

Open the demo at:

```text
http://127.0.0.1:5173/
```

Quick backend health check:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status":"ok"}
```

Recommended chat demo flow:

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

Additional operator notes live in `frontend/app/README.md`.

---

## Current Backend Capabilities

The repository already supports the core capabilities needed for a GUI:

- Guided chat workflow through `decision_intelligence.chat.ChatSession`
- Terminal command through `di chat`
- Domain optimizers:
  - `collateral`
  - `money_market`
  - `financing`
- Solver abstraction:
  - `scipy/lp`
  - `scipy/milp`
  - `cvxpy/lp`
- PDF intake:
  - offline heuristic backend
  - configurable LLM backend
- Governance status for execution modes
- Result models with:
  - objective value
  - baseline value
  - improvement
  - allocations
  - binding constraints
  - sensitivities
  - scenarios
  - solver metadata
- Export support:
  - JSON
  - CSV
  - HTML report

The GUI should use these existing Python objects rather than reimplementing
optimization logic in JavaScript.

---

## Target User

Primary users are business stakeholders, product reviewers, and demo audiences
who do not know the command line.

They should be able to:

- Start a guided optimization workflow from a browser.
- Answer simple business questions one at a time.
- Choose a domain, scenario, and solver engine without knowing Python flags.
- See what the system understood before running.
- Run the optimizer.
- Review the recommendation visually.
- Export or share the output.

The user should not need to know:

- `di` commands
- Python virtual environments
- request schemas
- solver APIs
- internal package structure

---

## Recommended MVP Architecture

Use a thin web app over the existing Python backend.

```text
Browser UI
  |
  | HTTP / WebSocket
  v
Python API Server
  |
  | uses existing package
  v
ChatSession -> OptimizationRequest -> Orchestrator -> Optimizer -> Solver
  |
  v
OptimizationResult
  |
  v
Browser UI result dashboard
```

Recommended first implementation:

```text
backend: FastAPI
frontend: React + TypeScript + Vite
styling: Tailwind CSS or a small component library
charts: Recharts or lightweight SVG/HTML tables
```

Reasoning:

- FastAPI fits the existing Python package and Pydantic models.
- React/Vite is enough for a polished local demo without heavy framework setup.
- The API can be run locally beside the existing `.venv`.
- The GUI can later move to Next.js or a deployed app if needed.

---

## Proposed Project Structure

```text
src/decision_intelligence/
├── api/
│   ├── app.py
│   ├── chat_routes.py
│   ├── optimize_routes.py
│   └── schemas.py
│
frontend/
├── package.json
├── vite.config.ts
├── src/
│   ├── App.tsx
│   ├── api/
│   │   └── client.ts
│   ├── components/
│   │   ├── ChatPanel.tsx
│   │   ├── WorkflowSidebar.tsx
│   │   ├── ResultDashboard.tsx
│   │   ├── AllocationTable.tsx
│   │   ├── SensitivityTable.tsx
│   │   ├── SolverSelector.tsx
│   │   ├── ScenarioSelector.tsx
│   │   ├── GovernanceBadge.tsx
│   │   └── ExportActions.tsx
│   ├── pages/
│   │   └── DemoWorkspace.tsx
│   └── styles/
│       └── index.css
```

For the first POC, the API can keep in-memory chat sessions keyed by a
generated `session_id`. Persistent storage is not required.

---

## Core User Experience

The first screen should be the actual demo workspace, not a marketing landing
page.

### Layout

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Top Bar: Decision Intelligence Demo | Domain | Solver | Export       │
├─────────────────────┬────────────────────────────────────────────────┤
│ Workflow Sidebar    │ Chat and Results Workspace                     │
│                     │                                                │
│ Domain              │ ┌────────────────────────────────────────────┐ │
│ Scenario            │ │ Guided Chat                               │ │
│ Solver Engine       │ │ user and assistant messages                │ │
│ Request Summary     │ └────────────────────────────────────────────┘ │
│ Governance Status   │                                                │
│                     │ ┌────────────────────────────────────────────┐ │
│                     │ │ Result Dashboard                          │ │
│                     │ │ allocation, metrics, constraints, export   │ │
│                     │ └────────────────────────────────────────────┘ │
└─────────────────────┴────────────────────────────────────────────────┘
```

### Chat Flow

The user should be able to start with plain business intent:

```text
I want to optimize money market cash
```

The GUI should then guide the user:

```text
What portfolio ID should I use?
How much cash are you allocating?
Minimum daily liquidity?
Minimum weekly liquidity?
Maximum prime fund concentration?
Maximum WAM?
Maximum single-fund concentration?
Which solver engine should I use?
Which scenario should I include?
Confirm and run?
```

When the user confirms, the backend builds an `OptimizationRequest` and runs the
existing orchestrator.

---

## MVP Screens

### 1. Demo Workspace

Primary screen for all POC demos.

Required UI:

- Left sidebar with current workflow state
- Main chat panel
- Result dashboard below or beside chat
- Solver selector
- Scenario selector
- Export buttons

Expected behavior:

- User starts a chat workflow.
- GUI renders each assistant question.
- User answers in a text input.
- Sidebar updates as fields are collected.
- User confirms.
- Result dashboard appears.

### 2. Result Dashboard

Shows the optimization recommendation in a stakeholder-friendly way.

Required sections:

- Status card:
  - optimal, infeasible, error, pending approval
- Objective comparison:
  - optimized value
  - baseline value
  - improvement
- Allocation table:
  - asset/source
  - allocated amount
  - allocation percentage
  - metadata such as yield, spread, haircut, tenor
- Binding constraints:
  - concise labels
- Sensitivity analysis:
  - parameter
  - shadow price
  - plain-English interpretation
- Scenario results:
  - scenario
  - objective
  - delta from base
  - improvement percentage
- Solver details:
  - backend
  - problem type
  - solver method

### 3. PDF Intake Demo

Required UI:

- PDF upload or sample PDF button
- Backend selector:
  - heuristic
  - LLM provider, if configured
- Extracted request preview:
  - domain
  - objective
  - constraints
  - scenarios
- Run optimization button
- Result dashboard

For the first version, support the existing sample brief:

```text
examples/sample_brief.pdf
```

### 4. Solver Comparison View

Useful for technical and semi-technical demos, but still visual.

Required UI:

- Domain selector
- Solver backend selector:
  - SciPy LP
  - SciPy MILP
  - CVXPY LP
- Scenario selector
- Run comparison button
- Comparison table:
  - solver
  - problem type
  - objective
  - runtime if available
  - status
  - number of allocations

This can be a second-phase feature if the main chat demo needs to stay focused.

---

## API Design

### Create Chat Session

```http
POST /api/chat/sessions
```

Response:

```json
{
  "session_id": "abc123",
  "message": "Tell me which workflow you want: collateral, money market, or financing."
}
```

### Send Chat Message

```http
POST /api/chat/sessions/{session_id}/messages
```

Request:

```json
{
  "message": "I want to optimize money market cash"
}
```

Response:

```json
{
  "assistant_message": "What portfolio ID should I use? [default: PORT_001]",
  "state": {
    "domain": "money_market",
    "collected": {},
    "next_field": "portfolio_id",
    "awaiting_confirmation": false
  },
  "result": null
}
```

When the user confirms:

```json
{
  "assistant_message": "Confirmed. Running optimization...",
  "state": {
    "domain": null,
    "collected": {},
    "awaiting_confirmation": false
  },
  "result": {
    "status": "optimal",
    "objective_value": 5.2284,
    "baseline_value": 5.0291,
    "improvement_pct": 3.96,
    "allocations": [],
    "sensitivities": [],
    "scenario_results": {},
    "solver_metadata": {}
  }
}
```

### Run Direct Optimization

```http
POST /api/optimizations/run
```

Request:

```json
{
  "domain": "money_market",
  "portfolio_id": "PORT_204",
  "context": {
    "total_cash": 500000000,
    "daily_liquidity_req": 0.30,
    "weekly_liquidity_req": 0.60,
    "max_prime_fraction": 0.40,
    "solver_backend": "scipy",
    "problem_type": "lp"
  },
  "scenarios": ["stress"]
}
```

Response:

```json
{
  "result": {}
}
```

### Ingest PDF

```http
POST /api/ingest/pdf
```

Use `multipart/form-data` for uploaded files.

Request fields:

```text
backend=heuristic | llm | auto
provider=anthropic | openai | optional
model=optional
seed=42
```

Response:

```json
{
  "extracted": {},
  "request": {},
  "result": {}
}
```

### Export Result

```http
POST /api/exports/result
```

Request:

```json
{
  "format": "json | csv | html",
  "result": {},
  "request": {}
}
```

Response:

```json
{
  "download_url": "/api/exports/files/report-123.html"
}
```

---

## Front-End State Model

Suggested client state:

```ts
type DemoState = {
  sessionId: string | null;
  messages: ChatMessage[];
  workflow: WorkflowState | null;
  requestPreview: OptimizationRequestPreview | null;
  result: OptimizationResult | null;
  isRunning: boolean;
  error: string | null;
};
```

Chat message:

```ts
type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
};
```

Workflow state:

```ts
type WorkflowState = {
  domain: "collateral" | "money_market" | "financing" | null;
  collected: Record<string, unknown>;
  nextField: string | null;
  awaitingConfirmation: boolean;
};
```

Optimization result:

```ts
type OptimizationResult = {
  status: string;
  objective_value: number;
  baseline_value: number;
  improvement: number;
  improvement_pct: number;
  allocations: Allocation[];
  binding_constraints: string[];
  sensitivities: Sensitivity[];
  scenario_results: Record<string, OptimizationResult>;
  solver_metadata: Record<string, unknown>;
  explanation: string;
};
```

---

## Design Guidance

The interface should feel like an enterprise decision-support tool, not a
marketing page.

Design principles:

- Use a dense, calm dashboard layout.
- Keep the chat prominent but not oversized.
- Show request state visibly so users trust what the system understood.
- Use tables for allocations and sensitivities.
- Use small status badges for solver, scenario, and governance.
- Avoid decorative hero sections.
- Avoid large gradient-heavy cards.
- Use clear labels instead of internal model names where possible.

Suggested visual language:

- Light or neutral background
- Strong table readability
- Subtle borders
- Compact cards for metrics only
- Left workflow sidebar
- Main result workspace

Important: nontechnical users need confidence. Always show:

- what was asked
- what was understood
- what changed
- why the optimizer chose the recommendation
- which constraints were binding

---

## Demo Script for Nontechnical Users

### Demo 1: Guided Money Market Optimization

1. Open the GUI.
2. Type:

```text
I want to optimize money market cash
```

3. Answer:

```text
PORT_204
$500 million
30%
60%
40%
60
50%
stress
yes
```

4. Show:

- optimized allocation
- improvement versus baseline
- binding constraints
- stress scenario output
- solver metadata

### Demo 2: PDF Intake

1. Click sample PDF.
2. Click parse.
3. Show extracted request:

- domain
- objective
- constraints
- scenarios

4. Click run optimization.
5. Show result dashboard.

### Demo 3: Solver Selection

1. Start money market workflow.
2. Choose:

```text
SciPy LP
```

3. Run.
4. Repeat with:

```text
SciPy MILP
```

5. Show that the same business request can be solved by different mathematical
engines and problem formulations.

---

## Implementation Phases

### Phase 1 - Local API Wrapper

Goal: expose current Python features over HTTP.

Tasks:

- Add FastAPI dependency or optional extra.
- Implement `/api/chat/sessions`.
- Implement `/api/chat/sessions/{id}/messages`.
- Implement direct optimization endpoint.
- Implement PDF intake endpoint using existing ingestion layer.
- Return Pydantic-safe JSON responses.
- Add API tests with FastAPI `TestClient`.

Definition of done:

- Local API can run with:

```bash
uvicorn decision_intelligence.api.app:app --reload
```

- Chat session can complete a money market workflow over HTTP.
- API returns the same result as `di chat`.

### Phase 2 - Front-End Shell

Goal: build the browser workspace.

Tasks:

- Create `frontend/` React app.
- Build static layout:
  - sidebar
  - chat panel
  - result dashboard
- Add API client.
- Connect chat session flow.
- Render request summary and results.
- Add loading, error, empty, and success states.

Definition of done:

- Nontechnical user can complete the money market demo in the browser.

### Phase 3 - PDF Intake and Export

Goal: support document-driven demos and downloadable output.

Tasks:

- Add PDF upload/sample PDF UI.
- Render extracted request preview.
- Add run button.
- Add JSON/CSV/HTML export actions.

Definition of done:

- User can parse `examples/sample_brief.pdf`, inspect extraction, run optimizer,
  and download output.

### Phase 4 - Solver Selection and Comparison

Goal: make the solver abstraction visible.

Tasks:

- Add solver selector:
  - SciPy LP
  - SciPy MILP
  - CVXPY LP
- Add problem-type selector where relevant.
- Add solver metadata to result view.
- Add optional comparison table.

Definition of done:

- User can choose solver backend and see the selected engine in the result.

### Phase 5 - Polish and Demo Packaging

Goal: make the POC reliable for stakeholder demos.

Tasks:

- Add seed reset button.
- Add sample prompt buttons.
- Add clear session button.
- Add friendly error messages.
- Add responsive layout.
- Add startup script:

```bash
make demo-ui
```

or:

```bash
./scripts/run_demo_ui.sh
```

Definition of done:

- One command starts backend and frontend locally.
- Demo script can be run end to end without terminal knowledge beyond startup.

---

## Back-End Implementation Notes

The API server should not shell out to `di`.

Use the package directly:

```python
from decision_intelligence.chat import ChatSession
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import CollateralOptimizer, FinancingOptimizer, MoneyMarketOptimizer
```

Keep an in-memory session store:

```python
CHAT_SESSIONS: dict[str, ChatSession] = {}
```

For multi-user or deployed use, replace this with Redis, a database, or a
session service.

Important response-shaping note:

Pydantic models can be returned directly by FastAPI if they are JSON
serializable. If NumPy arrays appear in internal metadata, convert them before
returning.

---

## Front-End Component Responsibilities

### `ChatPanel`

- Render messages.
- Accept user input.
- Submit messages.
- Disable input while optimizer is running.
- Support sample prompt buttons.

### `WorkflowSidebar`

- Show current domain.
- Show collected inputs.
- Show missing input.
- Show selected solver.
- Show scenario.
- Show governance status.

### `ResultDashboard`

- Render high-level metrics.
- Render status and governance.
- Render solver details.
- Render explanation.

### `AllocationTable`

- Sort by allocated value descending.
- Format dollars and percentages.
- Show metadata in expandable row details.

### `SensitivityTable`

- Show parameter, shadow price, interpretation.
- Use concise business labels.

### `SolverSelector`

- Show only supported solver/problem combinations.
- Disable unavailable options with explanation.

### `ExportActions`

- Download JSON.
- Download CSV.
- Download HTML report.

---

## Validation and Testing Plan

### Backend Tests

- Create chat session.
- Complete money market workflow.
- Confirm optimization result returned.
- Cancel workflow.
- PDF heuristic intake returns extracted request.
- Direct optimization endpoint returns valid result.
- Unsupported solver returns friendly error.

### Front-End Tests

- Chat panel renders messages.
- User can submit a message.
- Workflow sidebar updates after each answer.
- Result dashboard renders optimal result.
- Error state renders backend failure.
- Export buttons call correct endpoints.

### End-to-End Demo Test

Scripted browser test:

1. Open app.
2. Type money market intent.
3. Answer all guided questions.
4. Confirm.
5. Assert result dashboard shows optimal status.
6. Assert allocation table has rows.
7. Assert solver metadata is visible.

---

## Risks and Open Questions

### Session State

MVP can use in-memory sessions. Deployed use needs persistence or sticky
sessions.

### Long-Running Solves

Current solves are fast. Future MILP or production solvers may need async job
handling.

Recommended future model:

```text
POST /api/optimizations/jobs
GET  /api/optimizations/jobs/{id}
```

### Data Uploads

CSV/PDF uploads require file validation, size limits, and cleanup policy.

### LLM Use

The GUI should work fully offline with deterministic parsing. If an LLM provider
is configured, show it as an optional intake mode, not a hard requirement.

### Governance

The GUI can show advisory modes as auto-allowed. Stage/execute modes should
require explicit approval controls before any future state-changing action.

---

## Recommended First Build Ticket

Title:

```text
Build local FastAPI wrapper for guided chat optimization sessions
```

Scope:

- Add FastAPI optional dependency.
- Add API app under `src/decision_intelligence/api/app.py`.
- Add chat session endpoints.
- Add direct optimization endpoint.
- Add tests proving the browser-facing API can complete a money-market guided
  workflow.

Acceptance criteria:

- `uvicorn decision_intelligence.api.app:app --reload` starts locally.
- `POST /api/chat/sessions` creates a session.
- Repeated `POST /api/chat/sessions/{id}/messages` calls collect fields.
- Confirming with `yes` returns an optimization result.
- `pytest` passes.

---

## Summary

The GUI should be a thin, polished, browser-based demo surface over the existing
Python platform. It should make the guided chat workflow the primary experience,
show what the platform understood, run deterministic optimizers, and present the
recommendation in a clear dashboard.

The highest-value MVP is:

```text
Guided chat -> request summary -> run optimizer -> result dashboard -> export
```

That gives nontechnical users an appealing way to understand the platform
without learning terminal commands or internal schemas.

## Next Decisions

- Exact FastAPI request/response Pydantic schemas
- UI wireframe mockups or screenshots
- A prioritized backlog with individual tickets.
- Styling/design system decisions.
- Deployment/local startup instructions.
- Error-state examples and empty/loading states.
