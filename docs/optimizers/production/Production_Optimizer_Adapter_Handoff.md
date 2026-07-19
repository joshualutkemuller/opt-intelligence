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
- Default production registry containing both adapters.
- Orchestrator runtime switch via `context["optimizer_runtime"]`.
- Normalization bridge from `NormalizedOptimizerResult` into the existing
  `OptimizationResult` shape.
- Direct API and workflow API runtime fields.
- Production optimizer catalog endpoint for UI discovery.
- Focused tests for successful runs, blocked preflight, evidence attachment,
  and registry discovery.

Next:

- Surface model config, data contract, and evidence sections in the UI.
- Add front-end controls for `optimizer_runtime` and production adapter
  selection.
- Add production adapters for money market and financing when those models are
  ready for the same contract.
