# Engineering Cycle Spec

This document applies a six-step engineering cycle to production optimizer
integration. The intent is to give quants, engineers, model validators, and demo
owners a shared path from idea to governed optimizer runtime.

## Step 1: Problem Framing And Requirements

Objective: define what decision the optimizer makes and what production
standard it must satisfy.

Key questions:

- What decision variables does the optimizer choose?
- What business outcome is optimized?
- What hard constraints must never be violated?
- What soft constraints can be traded off through objective penalties?
- What execution modes are allowed: explain, scenario analysis, recommendation,
  stage, execute, or constraint change?
- Who owns the model, inputs, approvals, and production incident response?

Deliverables:

- optimizer charter;
- domain and user personas;
- objective and constraint inventory;
- required data source inventory;
- governance tier mapping;
- acceptance metrics for correctness, speed, and explainability.

Exit criteria:

- model owner signs off on scope;
- engineering owner signs off on integration boundary;
- governance owner signs off on required evidence.

## Step 2: Contract And Data Specification

Objective: convert model assumptions into typed platform contracts before
implementation starts.

Deliverables:

- `ModelConfigSpec` defining objectives, constraints, limit sources, scenario
  knobs, solver options, execution isolation, and lineage;
- `DataContractSpec` defining required datasets, keys, required columns,
  quality checks, and snapshot requirements;
- result normalization map from native outputs to platform fields;
- sample request and expected normalized result;
- preflight validation checklist.

Exit criteria:

- required inputs can be validated without running the optimizer;
- missing or stale production inputs have explicit blocking behavior;
- every result section has an owner and source.

## Step 3: Architecture And Adapter Design

Objective: isolate native optimizer mechanics behind a stable platform adapter.

Design decisions:

- choose execution isolation mode;
- choose serialization format for native problem payload and native output;
- define idempotency and run correlation IDs;
- define timeout, retry, and failure behavior;
- define evidence artifacts and storage path;
- define how model-specific attachments are exposed.

Deliverables:

- adapter class implementing `ProductionOptimizerAdapter`;
- execution backend selection;
- model config file or factory;
- evidence artifact manifest;
- integration diagram for platform, data, native optimizer, and audit exports.

Exit criteria:

- adapter can run from a unit test with fixture data;
- failed preflight returns a normalized blocked result;
- successful solve returns a normalized result with evidence.

## Step 4: Implementation And Integration

Objective: connect the adapter to the platform workflow, API, and UI without
leaking native model complexity.

Build sequence:

1. Implement preflight validation.
2. Implement native problem construction.
3. Implement execution backend.
4. Implement result normalization.
5. Implement evidence serialization.
6. Register adapter and expose workflow template.
7. Surface result sections in API and front end.

Implementation notes:

- keep native optimizer wrappers thin;
- prefer typed Pydantic contracts at platform boundaries;
- treat proprietary dense output as an attachment, not as the primary result
  shape;
- keep governance metadata attached to every normalized result.

Exit criteria:

- adapter is registered;
- workflow can execute the adapter from the API;
- UI can show plan progress, normalized result, governance state, and evidence;
- export package includes run evidence.

## Step 5: Verification, Benchmarking, And Model Certification

Objective: prove that the adapter preserves model behavior and meets production
readiness standards.

Test layers:

- schema tests for model config and data contracts;
- preflight tests for missing data, stale data, and invalid limits;
- adapter lifecycle tests for blocked and successful runs;
- golden-result tests against known optimizer fixtures;
- native model parity tests against direct model execution;
- performance tests for timeout and retry thresholds;
- reproducibility tests for fingerprint stability;
- governance tests for approval thresholds.

Certification evidence:

- versioned test report;
- fixture data snapshot IDs;
- solver/backend versions;
- benchmark timings;
- known limitations and unsupported scenarios;
- model owner approval.

Exit criteria:

- golden fixtures pass;
- model owner accepts parity;
- model risk or governance reviewer accepts evidence;
- production rollout path is approved.

## Step 6: Deployment, Monitoring, And Governance Operations

Objective: operate the adapter as a durable production integration.

Operational controls:

- versioned model config deployment;
- data snapshot tracking;
- solver/backend version tracking;
- run logs and trace IDs;
- approval records;
- runtime health checks;
- alerting for preflight failures, solve failures, and drift;
- exportable evidence packages.

Monitoring views:

- run volume and status;
- preflight failure reasons;
- solve duration and timeout rate;
- objective value and constraint trends;
- approval tier distribution;
- data freshness and missing dataset rates;
- reproducibility fingerprint changes.

Exit criteria:

- production operators can diagnose failures without opening model internals;
- model owners can review run evidence;
- governance reviewers can reconstruct a run;
- demo owners can explain the optimizer in business terms.
