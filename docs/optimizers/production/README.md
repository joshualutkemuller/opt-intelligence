# Production Optimizer Integration

This folder is the handoff package for turning firm-developed optimizers into
pluggable, governed back-end services inside the Decision Intelligence
platform.

The matching code scaffold lives in:

`src/decision_intelligence/production_optimizers/`

## Implemented Production Adapters

- `production.asset_allocation.mvo`: wraps the phase 1 Asset Allocation MVO
  optimizer with production config, preflight, normalized output, and evidence.
- `production.collateral.allocation`: wraps the phase 1 Collateral optimizer
  with production config, data preflight, normalized output, and evidence.

## Documents

- [Production Optimizer Adapter Handoff](Production_Optimizer_Adapter_Handoff.md)
- [Engineering Cycle Spec](Engineering_Cycle_Spec.md)
- [Adapter Interface Spec](Adapter_Interface_Spec.md)
- [Model Config and Data Contracts](Model_Config_And_Data_Contracts.md)
- [Execution Isolation and Governance](Execution_Isolation_And_Governance.md)

## Build Objective

Production optimizers should be attachable without rewriting the platform. Each
model should publish a stable adapter, a typed model configuration, typed data
contracts, normalized result sections, execution-isolation settings, and
governance evidence.

The integration target is deliberately boring and explicit:

1. Validate inputs and data readiness before solve.
2. Build the native optimizer problem payload.
3. Execute through an isolation backend.
4. Normalize results into common evidence sections.
5. Serialize model, data, solver, config, and approval evidence.
6. Hand the normalized result to workflows, API, UI, exports, and audit.
