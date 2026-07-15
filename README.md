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

## Extension Points

| What to extend | Where |
|---|---|
| Real data | Replace `data.py` in each optimizer package |
| New optimizer domain | Subclass `OptimizationCapability`, register in `OptimizerRegistry` |
| Production solver | Replace `scipy.optimize.linprog` calls in `optimizer.py` per domain |
| LLM / document intake | `ingestion/` — swap rules or the extraction schema; both backends produce `OptimizationRequest` objects |
| REST API | Wire `OptimizationOrchestrator` into FastAPI routes in `api/` |
| Approval workflow | Extend `AuditLog` and add approval state in `governance/` |

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
├── governance/         # AuditLog
├── ingestion/          # PDF → OptimizationRequest (intake agent)
│   ├── schema.py       #   loose LLM-friendly extraction schema
│   ├── mapper.py       #   loose extraction → strict validated request
│   └── pdf_ingest.py   #   llm (Claude native PDF) + heuristic backends
├── export/             # JSON / CSV / self-contained HTML report
└── data/               # Data layer stubs
tests/
examples/run_demo.py
examples/make_sample_pdf.py   # generates a sample brief PDF
```
