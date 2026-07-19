# Production Optimizer Adapter Handoff

## Purpose

Build a production-ready optimizer integration layer that lets the platform run
firm-developed models while preserving a consistent user experience, governance
model, evidence trail, and API contract.

The production integration layer should not assume every optimizer is a small
Python class. It must support optimizers that are Python packages, compiled
libraries, REST/gRPC services, vendor solver jobs, cloud batch workflows, or
containerized applications.

## Target Code Home

All production optimizer framework code should be easy to find in:

`src/decision_intelligence/production_optimizers/`

Initial scaffold:

- `adapter.py`: formal adapter lifecycle.
- `adapters/asset_allocation`: production wrapper for Asset Allocation MVO.
- `adapters/collateral`: production wrapper for Collateral Optimization.
- `adapters/financing`: production wrapper for Financing Optimization.
- `adapters/money_market`: production wrapper for Money Market Optimization.
- `adapters/cash_movement`: production scaffold for operational treasury cash
  routing.
- `adapters/margin_call`: production scaffold for operational margin-call
  workflow prioritization.
- `contracts.py`: typed model config, data contract, result, preflight, and
  evidence schemas.
- `execution.py`: execution-isolation boundary.
- `registry.py`: adapter registry.
- `README.md`: developer orientation.

Domain implementations should eventually sit under identifiable subfolders,
for example:

```text
src/decision_intelligence/production_optimizers/
  adapters/
    asset_allocation/
    money_market/
    collateral/
    financing/
  runtime/
  evidence/
  config/
```

## Core Design Principle

Separate the platform contract from the native model implementation.

The platform should care about:

- what inputs the optimizer requires;
- what objective and constraints are configured;
- what execution mode is being used;
- what evidence is required;
- what normalized result sections are available.

The native optimizer should remain free to care about:

- internal factor models;
- proprietary objective terms;
- vendor solver APIs;
- dense diagnostic structures;
- specialized data pipelines;
- production deployment mechanics.

## Production Adapter Lifecycle

Every production optimizer adapter should implement:

```python
validate_inputs(request)
build_problem(request)
solve(problem)
explain_outputs(request, problem, native_solution)
serialize_evidence(request, problem, native_solution, normalized_result)
```

The platform calls `run(request)` as the canonical lifecycle. `run()` performs
preflight validation, blocks invalid requests before solve, runs the native
optimizer, normalizes the output, and attaches evidence.

## Rich Model Config Schema

Production models need explicit configuration sections for:

- objective terms;
- constraint families;
- limit sources;
- scenario knobs;
- data requirements;
- solver and backend options;
- execution isolation;
- model and config lineage.

This keeps demos understandable while giving production quants the precision
needed to represent real model behavior.

## Data Contract Layer

Before solve, the adapter should validate all required data:

- holdings and portfolio state;
- curves and market data;
- reference data;
- risk model inputs;
- eligibility rules;
- limits and policy rules;
- data freshness and snapshot IDs.

Preflight validation should fail closed when required data is missing or stale.
Warnings are acceptable only when the optimizer owner has declared the dataset
optional or nonblocking.

## Result Contract Normalization

Production optimizers may emit dense outputs. The platform should normalize
them into common result sections:

- status and objective value;
- baseline comparison;
- allocations or recommended actions;
- binding constraints;
- duals and shadow prices;
- infeasibility diagnostics;
- frontier curves;
- scenario grids;
- turnover and transaction costs;
- diagnostics;
- domain-specific attachments.

This lets the API, UI, audit exports, and demo packages show consistent panels
while still preserving model-specific detail.

## Execution Isolation

Adapters should support these execution patterns:

- in-process Python;
- subprocess;
- REST;
- gRPC;
- batch or job queue;
- containerized execution.

The same adapter lifecycle should work regardless of where the native optimizer
runs.

## Governance And Versioning

Every run should capture:

- model ID and model version;
- config version;
- data snapshot ID;
- solver/backend version;
- execution mode;
- approval state;
- reproducibility fingerprint;
- evidence artifacts.

These fields are the bridge between quant research, production operations,
model risk governance, and client-facing demo credibility.

## Acceptance Criteria

- A new production optimizer can be registered without changing workflow or UI
  code beyond exposing a template.
- Preflight validation blocks missing data before solve.
- Native results are normalized into platform evidence sections.
- Dense native attachments remain available for domain-specific review.
- Runs produce reproducibility metadata.
- Execution can move from in-process to service/container without changing the
  API response shape.

## Current Implementation Status

Implemented:

- Asset Allocation MVO production adapter and `ModelConfigSpec`.
- Collateral production adapter and `ModelConfigSpec`.
- Financing production adapter and `ModelConfigSpec`.
- Money Market production adapter and `ModelConfigSpec`.
- Treasury cash movement production adapter and `ModelConfigSpec`.
- Margin-call workflow production adapter and `ModelConfigSpec`.
- Default production registry containing all current production adapters.
- Orchestrator runtime switch via `context["optimizer_runtime"]`.
- Normalization bridge from `NormalizedOptimizerResult` into the existing
  `OptimizationResult` shape.
- Direct API and workflow API runtime fields.
- Production optimizer catalog endpoint for UI discovery.
- Front-end production-runtime controls, adapter selection, catalog fallback,
  and evidence-oriented summary panels.
- Production workflow templates and demo presets for asset allocation,
  collateral, money market, treasury cash movement, and margin-call workflow.
- Focused tests for successful runs, blocked preflight, evidence attachment,
  and registry discovery.

## Current Adapter Inventory

| Adapter ID | Domain | Native model | Status | Primary production value |
|---|---|---|---|---|
| `production.asset_allocation.mvo` | `asset_allocation` | Asset Allocation MVO | Implemented | Shows quant portfolio construction through the production adapter lifecycle. |
| `production.collateral.allocation` | `collateral` | Collateral Optimizer | Implemented | Connects eligibility, haircuts, obligations, and concentration constraints to evidence. |
| `production.financing.allocation` | `financing` | Financing Optimizer | Implemented | Sources funding across counterparties under capacity, tenor, concentration, and capital limits. |
| `production.money_market.allocation` | `money_market` | Money Market Optimizer | Implemented | Allocates cash under yield, daily/weekly liquidity, WAM, prime, and single-fund constraints. |
| `production.treasury.cash_movement` | `treasury_operations` | Operational scaffold | Implemented | Demonstrates payment-routing, cutoff, account-buffer, and rail-cost workflow optimization. |
| `production.margin_call.workflow` | `margin_operations` | Operational scaffold | Implemented | Demonstrates queue prioritization under SLA, materiality, dispute, and ops-capacity constraints. |

## Completion Checklist

For tonight's closeout, the adapter handoff should be considered complete when:

- ✅ Every currently enabled optimizer has a production adapter ID, config spec,
  data contract, preflight, normalized output, and evidence serialization.
- ✅ The orchestrator can run production mode via
  `context["optimizer_runtime"] = "production"` without per-domain special
  handling.
- ✅ API catalog discovery returns all production adapters.
- ✅ The front-end can select production runtime and render adapter facts,
  evidence, and result attachments for every current adapter.
- ✅ Tests cover adapter lifecycle, registry discovery, orchestrator production
  runtime, and API catalog exposure.
- ✅ Documentation identifies the remaining firm-integration work separately
  from the POC-ready platform contract.

## Remaining Production-Hardening Work

These items are intentionally outside the POC adapter closeout, but they are
the next credible path from demo to firm integration:

- Replace phase-1 native optimizer calls with firm production engines where
  available.
- Add real data adapters for holdings, risk models, curves, collateral
  schedules, funding facilities, counterparty limits, and policy repositories.
- Add execution-isolation examples for subprocess, REST/gRPC, batch, and
  containerized optimizer runtimes.
- Persist evidence artifacts to controlled storage with immutable run IDs.
- Add model-risk approval metadata, config promotion workflow, and versioned
  data-snapshot lineage.
- Expand duals, shadow prices, infeasibility diagnostics, and scenario grids
  where the native optimizer emits those dense outputs.
