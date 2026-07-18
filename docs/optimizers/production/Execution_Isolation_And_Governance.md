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
