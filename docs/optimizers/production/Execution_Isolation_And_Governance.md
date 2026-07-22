# Execution Isolation And Governance

Production optimizers should be executable through multiple isolation modes
while preserving the same platform adapter contract.

## Execution Modes

### In-Process Python

Best for:

- early migrations;
- lightweight internal Python optimizers;
- local demos;
- deterministic unit tests.

Risks:

- dependency collisions;
- memory pressure;
- limited isolation from native failures.

### Subprocess

Best for:

- command-line model packages;
- dependency isolation with virtual environments;
- non-Python wrappers.

Controls:

- command allowlist;
- timeout;
- stdout/stderr capture;
- structured JSON input/output.

Implementation status:

- `SubprocessExecutionBackend` sends a JSON payload containing the isolation
  spec and problem to stdin.
- The subprocess must return one JSON object on stdout.
- Nonzero return codes, missing stdout, and invalid JSON are normalized as
  execution errors.

### REST

Best for:

- optimizer services already deployed behind HTTP;
- cloud or internal platform services;
- versioned service endpoints.

Controls:

- request ID and idempotency key;
- timeout;
- retry policy;
- response schema validation;
- service version capture.

Implementation status:

- `RestExecutionBackend` posts the same spec/problem JSON shape to the
  configured endpoint.
- Timeout and retry count come from `ExecutionIsolationSpec`.
- HTTP errors and invalid JSON are normalized as execution errors.

### gRPC

Best for:

- lower-latency internal services;
- strongly typed service contracts;
- large structured payloads.

Controls:

- protobuf schema version;
- deadline;
- retry policy;
- metadata propagation.

### Batch Or Job Queue

Best for:

- long-running optimizers;
- large scenario grids;
- overnight portfolio construction;
- heavy risk model dependencies.

Controls:

- job ID;
- queue name;
- polling policy;
- checkpoint artifacts;
- terminal status normalization.

### Containerized Execution

Best for:

- compiled libraries;
- vendor solver stacks;
- heavyweight dependencies;
- reproducible production environments.

Controls:

- container image digest;
- resource profile;
- mounted data snapshots;
- network policy;
- artifact path.

## Governance Metadata

Each run should capture:

- optimizer ID;
- model name;
- model version;
- config version;
- solver/backend name and version;
- execution isolation mode;
- data snapshot ID;
- reproducibility fingerprint;
- request ID;
- requestor;
- timestamp;
- approvals.

## Reproducibility Fingerprint

The fingerprint should be deterministic for the inputs that define a run.

Candidate fields:

- model version;
- config version;
- solver version;
- data snapshot ID;
- objective and constraint config;
- scenario knobs;
- request context;
- relevant policy limits;
- code package version or container digest.

The fingerprint is not a replacement for storing evidence. It is a compact way
to detect whether two runs are expected to be equivalent.

## Approval Integration

Approval thresholds should consider:

- execution mode;
- notional materiality;
- estimated PnL impact;
- policy or constraint changes;
- model approval status;
- data quality warnings;
- infeasibility or override conditions.

Tier 5 governance changes should require explicit evidence that the model,
config, data, and approving user are all valid for production use.

## Model-Risk And Config Promotion

Production runtime now includes a local-first model/config governance scaffold
in:

`src/decision_intelligence/production_optimizers/governance.py`

The scaffold defines:

- `ModelRiskApprovalRecord`: optimizer ID, model version, config version,
  promotion status, approved execution modes, approver, approval time, change
  ticket, and notes;
- `ProductionModelGovernanceRegistry`: in-memory registry for model/config
  approval records;
- `evaluate_model_governance(...)`: adapter lifecycle check that runs before
  data preflight, problem build, or solve.

Behavior:

- approved recommendation/scenario/explain runs proceed and attach the
  model-risk approval record to production evidence;
- requests for execution modes outside `ModelLineageSpec.approved_for` fail
  closed with `status = blocked`;
- blocked model/config runs do not call the native optimizer;
- the evidence packet includes `artifacts.model_governance` and an approval
  record under `ProductionOptimizerEvidence.approvals`.

This is intentionally a POC governance registry. Production integration should
replace or back it with firm model inventory, SSO identities, role/authority
policies, durable approval records, and formal config promotion workflow.

## Audit Evidence Package

Minimum contents:

- normalized result JSON;
- model config JSON;
- preflight report;
- data snapshot reference;
- solver/backend metadata;
- governance review summary;
- approval records;
- native output attachment when allowed;
- before/after analytics when relevant.

For Excel/CSV export, the platform should write evidence into tabular sections:

- `run_metadata`;
- `objectives`;
- `constraints`;
- `preflight_checks`;
- `allocations`;
- `binding_constraints`;
- `duals`;
- `scenario_grid`;
- `approvals`;
- `artifacts`.

## Local Evidence Persistence

Production runtime now supports opt-in local evidence persistence:

```json
{
  "optimizer_runtime": "production",
  "persist_production_evidence": true,
  "evidence_artifact_root": "artifacts/evidence"
}
```

When enabled, `LocalProductionEvidenceStore` writes a deterministic run
directory using the request ID, optimizer ID, and reproducibility fingerprint.
Each run directory contains:

- `manifest.json`;
- `evidence.json`;
- `normalized_result.json`;
- `summary.csv`;
- `allocations.csv`;
- `summary.xlsx`.

The orchestrator attaches the storage manifest under:

```text
result.solver_metadata.production_evidence.artifacts.persistent_evidence
```

This is intentionally a local-first implementation. The production version
should replace the local path with firm-controlled object storage, immutable run
IDs, retention policy, access control, and lineage links to model and data
catalogs.
