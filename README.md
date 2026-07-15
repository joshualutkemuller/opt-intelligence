# Decision Intelligence Platform

A reusable optimization framework for financial decision intelligence.
Combines deterministic LP optimization, a common interface contract, an
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
 ┌──────┼──────────┐
 ▼      ▼          ▼
Collateral  MoneyMarket  Financing
Optimizer   Optimizer    Optimizer
        │
        ▼
validate_request → prepare_problem → solve (HiGHS LP)
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
| **Collateral** | Minimize funding cost | Asset-to-obligation fractions | Eligibility, haircut coverage, inventory, concentration |
| **Money Market** | Maximize net yield | Fund weights | Daily/weekly liquidity, WAM, prime fraction, single-fund limit |
| **Financing** | Minimize spread cost | Counterparty-to-need amounts | Tenor compatibility, capacity, concentration, capital budget |

All three use `scipy.optimize.linprog` with the HiGHS solver.

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

```bash
python examples/run_demo.py
```

Produces a rich terminal output showing:
- Optimal allocations per domain
- Baseline vs optimized objective value and % improvement  
- Sensitivity / shadow-price analysis
- Scenario analysis (stress, downside)
- Audit log entry count

---

## PDF Ingestion (Intake Agent)

The framework can ingest a document (a desk memo, mandate, or optimization
brief) and turn it into a validated `OptimizationRequest` that flows through the
same orchestrator → optimizer pipeline as any other request.

```bash
pip install -e ".[ingest]"          # pypdf + anthropic + reportlab

python examples/make_sample_pdf.py  # writes examples/sample_brief.pdf
di ingest examples/sample_brief.pdf
```

Two extraction backends:

| Backend | When used | How it works |
|---|---|---|
| `llm` | `ANTHROPIC_API_KEY` is set | Claude (`claude-opus-4-8`) reads the PDF natively and returns a schema-validated extraction via structured outputs |
| `heuristic` | offline fallback (default when no key) | `pypdf` text extraction + regex/keyword rules — deterministic, no network |

`di ingest` auto-selects the backend (`--backend llm|heuristic|auto`), prints
what the intake agent understood (domain, objective, constraints, scenarios),
then solves. Useful flags: `--dry-run` (parse only), `--no-show-extraction`,
`--output result.json|allocs.csv|report.html`.

The pipeline is: **PDF → `ExtractedRequest` (loose) → mapper → `OptimizationRequest` (strict) → orchestrator**.
Keeping the loose extraction schema separate from the strict contract lets the
parse step be best-effort while the optimizer still receives a fully-validated
request.

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
│   └── pdf_ingest.py   #   llm (Claude native PDF) + heuristic backends
├── export/             # JSON / CSV / self-contained HTML report
└── data/               # Configurable data-provider layer
    └── loaders.py      #   simulated (default) + CSV; returns optimizer dataclasses
tests/
examples/run_demo.py
examples/make_sample_pdf.py   # generates a sample brief PDF
```
