# Adapter Interface Spec

The adapter interface is the stable boundary between the platform and a
production optimizer.

## Interface

```python
class ProductionOptimizerAdapter:
    optimizer_id: str
    domain: str
    model_config: ModelConfigSpec

    def validate_inputs(self, request) -> PreflightReport: ...
    def build_problem(self, request) -> dict: ...
    def solve(self, problem) -> dict: ...
    def explain_outputs(self, request, problem, native_solution) -> NormalizedOptimizerResult: ...
    def serialize_evidence(self, request, problem, native_solution, normalized_result) -> ProductionOptimizerEvidence: ...
```

The platform should call `run(request)` unless a lower-level lifecycle method is
being tested directly.

## Method Responsibilities

### `validate_inputs(request)`

Validates everything that can be checked before solve.

Responsibilities:

- confirm request domain and execution mode;
- verify required context fields;
- verify required datasets are present;
- validate data freshness and snapshot IDs;
- validate limits and policy inputs;
- validate solver/backend availability;
- create a reproducibility fingerprint when possible.

Output:

- `passed`;
- `blocking_issues`;
- `warnings`;
- `checked_datasets`;
- `checked_limits`;
- `data_snapshot_id`;
- `reproducibility_fingerprint`.

### `build_problem(request)`

Translates platform inputs into the native optimizer payload.

Responsibilities:

- map platform objective terms into native coefficients or functions;
- map platform constraints into native bounds, matrices, penalties, or service
  inputs;
- attach scenario parameters;
- attach data snapshot references;
- attach run metadata needed by the execution backend.

The returned payload is intentionally a dictionary so it can hold native
structures during early migrations. Mature adapters can replace internal values
with typed payload models.

### `solve(problem)`

Runs the native optimizer through the configured execution path.

Responsibilities:

- select in-process, subprocess, REST, gRPC, batch, or container execution;
- enforce timeout and retry settings;
- capture raw status and diagnostics;
- preserve native output for evidence.

This method should not shape the result for the UI. It returns the native
solution payload.

### `explain_outputs(request, problem, native_solution)`

Normalizes native output into platform sections.

Responsibilities:

- set status and objective value;
- compute baseline comparison;
- produce allocations or actions;
- identify binding constraints;
- normalize duals, shadow prices, infeasibility diagnostics, frontier points,
  scenario grids, turnover, and transaction costs when available;
- place model-specific detail into `domain_attachments`;
- produce business-readable diagnostics.

### `serialize_evidence(...)`

Creates the audit packet for the run.

Responsibilities:

- capture model version and config version;
- capture data snapshot ID;
- capture solver/backend version;
- capture reproducibility fingerprint;
- attach approvals;
- attach native artifacts and normalized artifacts.

Evidence should be sufficient for another reviewer to understand what model
ran, what data it used, what configuration was active, and what output it
produced.

## Failure Semantics

Preflight failures should return `status = "blocked"` and should not call the
native optimizer.

Runtime failures should return `status = "error"` when they can be normalized.
Unexpected exceptions should be logged by the caller and converted into an API
error only at the orchestration boundary.

Infeasible optimizer solutions should return `status = "infeasible"` with
diagnostics whenever the native solver exposes enough information.

## Adapter Granularity

Prefer one adapter per production model/configuration family, not one adapter
per workflow demo. Workflows can reuse the same adapter with different request
context, scenario knobs, and governance tiers.
