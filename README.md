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

## Extension Points

| What to extend | Where |
|---|---|
| Real data | Replace `data.py` in each optimizer package |
| New optimizer domain | Subclass `OptimizationCapability`, register in `OptimizerRegistry` |
| Production solver | Replace `scipy.optimize.linprog` calls in `optimizer.py` per domain |
| LLM agent layer | Add `agents/` directory; agents produce `OptimizationRequest` objects |
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
└── data/               # Data layer stubs
tests/
examples/run_demo.py
```
