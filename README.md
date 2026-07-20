# Decision Intelligence Platform

A reusable optimization framework for financial decision intelligence.
Combines deterministic LP/MILP optimization, a common interface contract, an
optimizer registry, and a deterministic orchestrator — ready to be extended
with real data adapters, additional domains, and an LLM agent layer.

---

## Architecture

```
OptimizationRequest
        │
        ▼
OptimizationOrchestrator
        │  (routes by domain)
        ▼
OptimizerRegistry
        │
 ┌──────┼────────────┬──────────┐
 ▼      ▼            ▼          ▼
Asset   Collateral   Money      Financing
MVO     Optimizer    Market     Optimizer
                    Optimizer
        │
        ▼
validate_request → prepare_problem → solve (registered solver backend)
→ validate_solution → run_sensitivity → explain
        │
        ▼
OptimizationResult
  (allocations, sensitivities, explanation, scenario_results)
        │
        ▼
AuditLog
```

---

## Optimization Domains (POC)

| Domain | Objective | Variables | Key Constraints |
|---|---|---|---|
| **Asset Allocation** | Maximize mean-variance utility | Asset-class weights | Full investment, long-only bounds, target return, class exposure limits |
| **Collateral** | Minimize funding cost | Asset-to-obligation fractions | Eligibility, haircut coverage, inventory, concentration |
| **Money Market** | Maximize net yield | Fund weights | Daily/weekly liquidity, WAM, prime fraction, single-fund limit |
| **Financing** | Minimize spread cost | Counterparty-to-need amounts | Tenor compatibility, capacity, concentration, capital budget |

The asset allocation optimizer uses SciPy SLSQP for a constrained
mean-variance objective. The other domains support the default continuous LP
path through SciPy/HiGHS. The money-market optimizer also supports a true MILP
fund-selection model through SciPy/HiGHS with binary selected/not-selected
variables.

---

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.11+. No cloud, LLM, or solver license needed for the POC.

---

## Run Tests

```bash
pytest
```

---

## Run the Demo

Start the browser-based demo workspace with one command:

```bash
make demo-ui
```

This launches the local FastAPI backend at `http://127.0.0.1:8000` and the
React/Vite UI at `http://127.0.0.1:5173/`. Stop both with `Ctrl+C`.
The browser workflow selector includes the **Portfolio Rebalance MVO** demo
alongside the funding, collateral, and money-market workflows.

### LLM Settings — one place to configure every LLM feature

The **LLM Settings** panel (above the LLM Chat panel in the sidebar)
controls every LLM call in the browser UI from a single location:

| Feature | Reads from LLM Settings |
|---|---|
| LLM Chat | ✓ |
| IPS / collateral schedule ingestion (LLM-assisted mode) | ✓ |
| Audit narrative polishing ("Polish with LLM" in Evidence Room) | ✓ |

The panel has four free-form fields:

| Field | What to put here |
|---|---|
| **Protocol** | `openai-compatible` for any OpenAI-API-speaking endpoint (Ollama, vLLM, Azure, most gateways); `anthropic` for the Anthropic SDK path |
| **Model** | Any model string your endpoint accepts — the field is free-form and is passed through verbatim |
| **Base URL** | Your gateway or local server URL (e.g. `https://llm-gateway.corp/v1`). Leave blank to use the protocol's default hosted endpoint |
| **API Key** | Your gateway token. Leave blank to fall back to the environment variable (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) |

**Gateway example** — point at a corporate LLM gateway that routes to many
models and requires a shared gateway token:

```
Protocol : openai-compatible
Model    : gpt-4o-corp   (or whatever string your gateway expects)
Base URL : https://llm-gateway.corp/v1
API Key  : <gateway-token>
```

Switch models at any time by editing the Model field — no restart needed.

**Common configurations:**

```
# Local Ollama — any model pulled with `ollama pull`
Protocol : openai-compatible
Model    : llama3.1:8b          (or mistral, gemma2, phi3, …)
Base URL : http://localhost:11434/v1
API Key  : (blank)

# Hosted Anthropic
Protocol : anthropic
Model    : claude-sonnet-5
Base URL : (blank)
API Key  : sk-ant-…  (or set ANTHROPIC_API_KEY in env)

# Hosted OpenAI
Protocol : openai-compatible
Model    : gpt-4o
Base URL : (blank)
API Key  : sk-…  (or set OPENAI_API_KEY in env)
```

For the original terminal demo:

```bash
python examples/run_demo.py
```

Produces a rich terminal output showing:
- Optimal allocations per domain
- Baseline vs optimized objective value and % improvement  
- Sensitivity / shadow-price analysis
- Scenario analysis (stress, downside)
- Audit log entry count

For a presenter-ready proof-of-concept recording:

```bash
make demo-video
```

This runs a deterministic terminal story covering guided chat intake, true MILP
money-market fund selection, solver backend comparison, and a CSV-backed
institutional liquidity-stress workflow. The companion shot list is in
`docs/demo_video_runbook.md`.

## Solver Backends

Run the focused solver comparison:

```bash
python examples/run_solver_demo.py
```

Or select a backend directly from the CLI:

```bash
di run money_market --solver scipy --problem-type lp
di run money_market --solver scipy --problem-type milp
di run money_market --solver cvxpy --problem-type lp
```

`scipy/milp` enables money-market fund selection with binary variables, a
maximum selected-fund count, and a minimum allocation per selected fund. See
`docs/solver_backends.md` for the modeling details and extension points.

---

## PDF Ingestion (Intake Agent)

The framework can ingest a document (a desk memo, mandate, or optimization
brief) and turn it into a validated `OptimizationRequest` that flows through the
same orchestrator → optimizer pipeline as any other request.

```bash
pip install -e ".[ingest]"          # pypdf + reportlab (backends below add SDKs)

python examples/make_sample_pdf.py  # writes examples/sample_brief.pdf
di ingest examples/sample_brief.pdf
```

Two extraction backends:

| Backend | When used | How it works |
|---|---|---|
| `llm` | an LLM provider is configured | A **provider-agnostic** extractor (see below) returns a schema-validated extraction |
| `heuristic` | offline fallback (default when no provider) | `pypdf` text extraction + regex/keyword rules — deterministic, no network |

`di ingest` auto-selects the backend (`--backend llm|heuristic|auto`), prints
what the intake agent understood (domain, objective, constraints, scenarios),
then solves. Useful flags: `--provider`, `--model`, `--dry-run` (parse only),
`--no-show-extraction`, `--output result.json|allocs.csv|report.html`.

The pipeline is: **PDF → `ExtractedRequest` (loose) → mapper → `OptimizationRequest` (strict) → orchestrator**.
Keeping the loose extraction schema separate from the strict contract lets the
parse step be best-effort while the optimizer still receives a fully-validated
request.

### LLM provider (vendor-agnostic, configurable, offline-capable)

The intake agent never imports a vendor SDK directly — all model access goes
through one `LLMProvider` interface (`decision_intelligence.llm`), selected by
configuration. This is the single seam every future LLM agent will reuse.

```bash
pip install -e ".[llm-anthropic]"   # Claude (native PDF)
pip install -e ".[llm-openai]"      # OpenAI / Azure / any OpenAI-compatible endpoint
```

Selection is by environment or flags:

| Variable | Purpose |
|---|---|
| `DI_LLM_PROVIDER` | `anthropic` \| `openai` \| a registered name (else auto-detected) |
| `DI_LLM_MODEL` | model id (provider default otherwise) |
| `DI_LLM_BASE_URL` | OpenAI-compatible endpoint — **local models**: Ollama / vLLM / llama.cpp |
| `DI_LLM_API_KEY` | generic key (falls back to `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) |

```bash
# hosted Claude
ANTHROPIC_API_KEY=sk-… di ingest examples/sample_brief.pdf --provider anthropic

# fully offline — a local model, no data leaves the host
DI_LLM_PROVIDER=openai DI_LLM_BASE_URL=http://localhost:11434/v1 \
  DI_LLM_MODEL=llama3.1 di ingest examples/sample_brief.pdf
```

To run the full local Ollama smoke test in one step:

```bash
ollama serve
ollama pull llama3.2:3b
python examples/run_ollama_smoke.py
```

The smoke test checks whether Ollama is reachable, picks an available
lightweight model, resolves the OpenAI-compatible provider, runs LLM PDF
ingestion as a dry-run, then routes the mapped request through the optimizer.
If Ollama or the optional packages are unavailable, it skips cleanly and prints
the missing setup. Use `--strict` when you expect Ollama to be installed and
want unavailable dependencies to fail the command.

Native-PDF providers (Anthropic) read the document directly; others receive
extracted text — the return type is identical either way. Structured-output
parity is handled per-provider (native schema decoding, else JSON-mode +
Pydantic validation). Register in-house/offline providers at runtime with
`decision_intelligence.llm.register_provider(...)`. With no provider configured,
ingestion falls back to the deterministic `heuristic` backend.

---

## Real Data (Configurable Data Sources)

Optimizers get their inputs through a **data-provider layer**
(`data/loaders.py`), selected per request via `context["data_source"]`. The
default is reproducible simulated data; point it at CSV files to run on real
data — no change to the LP formulation or optimizer code.

```bash
# generate sample CSVs from the simulator, then run on them
di run money_market --data examples/data/money_market_source.json
```

`--data` takes a JSON file describing the source:

```json
{
  "data_source": {
    "type": "csv",
    "funds": "examples/data/mmf_universe.csv",
    "position": "examples/data/cash_position.csv"
  }
}
```

Per domain, the CSV columns map 1:1 to the dataclass fields in each optimizer's
`data.py` (list fields like `eligible_asset_classes` are `;`-separated):

| Domain | Required CSVs (keys) |
|---|---|
| `collateral` | `assets`, `obligations` |
| `money_market` | `funds` (+ optional `position`) |
| `financing` | `counterparties`, `needs` |

`{"type": "simulated"}` (or omitting `data_source`) keeps the built-in
generator. Adding a new backend (Parquet, SQL, a REST feed) means implementing
one loader that returns the same dataclass tuple — the optimizers are unchanged.

The POC also includes anonymized institutional CSV packets for the video demo:
`institutional_csv_liquidity_base.yaml` provides a calmer comparison run, while
`institutional_csv_liquidity_stress.yaml` shows tighter funding, collateral, and
liquidity pressure. Both point financing, collateral, and money-market steps to
CSV inputs under `examples/data/`. See `docs/real_data_demo_packet.md`.

---

## Execution Modes & Approval Governance

Every request carries an **execution mode** that maps to a human-approval tier.
The optimization math runs identically in all modes; what the governance layer
enforces is whether the *action* the mode implies may proceed.

| Tier | Mode | Action | Gated? |
|---|---|---|---|
| 0 | `explain` | analysis | auto-allowed |
| 1 | `scenario_analysis` | what-if analysis | auto-allowed |
| 2 | `recommendation` | produce a recommendation | auto-allowed |
| 3 | `stage` | stage a transaction | **approval required** |
| 4 | `execute` | execute a transaction | **approval required** |

Advisory tiers (0–2) are auto-allowed. State-changing tiers (3–4) are
**withheld** (`pending`) until an authorized approver grants them — then the
action is performed (`approved`) or refused (`rejected`). Every transition is
written to the append-only audit log.

```bash
# gated — the recommendation is computed but the action is withheld
di run financing --mode execute
#   ⏳ GOVERNANCE  mode execute (tier 4)  → APPROVAL REQUIRED

# approve in one shot
di run financing --mode execute --approve-as jane.doe --reason "within limits"
#   ✓ GOVERNANCE  → APPROVED   (transaction_executed recorded in audit log)

# reject
di run financing --mode stage --approve-as risk.officer --reject --reason "over limit"
#   ✗ GOVERNANCE  → REJECTED
```

Programmatically, an `OptimizationOrchestrator` is gated by passing a
`GovernanceController`; results then carry a `governance` `ApprovalRecord`. A
two-phase flow (`controller.submit_decision(request, decision)` then re-run) is
supported for API-style approvals, and the policy accepts an approver allowlist.
An orchestrator built without a controller is ungoverned (backward compatible).

---

## Extension Points

| What to extend | Where |
|---|---|
| Real data | Add a loader in `data/loaders.py` returning the same dataclass tuple; select via `context["data_source"]` (CSV built in) |
| New optimizer domain | Subclass `OptimizationCapability`, register in `OptimizerRegistry` |
| Production solver | Replace `scipy.optimize.linprog` calls in `optimizer.py` per domain |
| LLM / document intake | `ingestion/` — swap rules or the extraction schema; both backends produce `OptimizationRequest` objects |
| LLM provider | `llm/` — add a provider or `register_provider(...)`; selected via `DI_LLM_*` config (hosted or local/offline) |
| REST API | Wire `OptimizationOrchestrator` into FastAPI routes in `api/` |
| Approval workflow | Implemented in `governance/approvals.py` (policy, store, controller) — extend the policy for notional/PnL thresholds or real approver identity |

---

## Project Structure

```
src/decision_intelligence/
├── contracts/          # Pydantic request/result/objective/constraint models
├── optimization/       # Base interface, registry, orchestrator
├── optimizers/
│   ├── collateral/     # LP: minimize funding cost
│   ├── money_market/   # LP: maximize yield
│   └── financing/      # LP: minimize spread
├── governance/         # AuditLog + execution-mode approval enforcement
│   └── approvals.py    #   ApprovalPolicy / ApprovalStore / GovernanceController
├── ingestion/          # PDF → OptimizationRequest (intake agent)
│   ├── schema.py       #   loose LLM-friendly extraction schema
│   ├── mapper.py       #   loose extraction → strict validated request
│   └── pdf_ingest.py   #   provider-agnostic llm + heuristic backends
├── llm/                # Vendor-agnostic LLM layer (config-driven)
│   ├── base.py         #   LLMProvider protocol (extract / generate)
│   ├── anthropic_provider.py  # Claude (native PDF)
│   ├── openai_provider.py     # OpenAI / Azure / local (Ollama, vLLM, llama.cpp)
│   └── config.py       #   resolve_provider / register_provider
├── export/             # JSON / CSV / self-contained HTML report
└── data/               # Configurable data-provider layer
    └── loaders.py      #   simulated (default) + CSV; returns optimizer dataclasses
tests/
examples/run_demo.py
examples/make_sample_pdf.py   # generates a sample brief PDF
```
