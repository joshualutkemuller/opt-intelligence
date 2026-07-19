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
- `production.money_market.allocation`: wraps the phase 1 Money Market
  optimizer with production config, liquidity preflight, normalized output, and
  reproducibility evidence.
- `production.treasury.cash_movement`: provides an operational treasury
  cash-movement adapter scaffold for routing cash across accounts, entities, and
  payment rails under cutoff and liquidity-buffer controls.
- `production.margin_call.workflow`: provides an operational margin-call
  workflow adapter scaffold for prioritizing calls by exposure, SLA urgency,
  dispute risk, counterparty risk, and available team capacity.

## Runtime Selection

Direct optimization and workflow API calls can opt into the production adapter
runtime with:

```json
{
  "optimizer_runtime": "production"
}
```

The default remains `"phase1"` for backward compatibility.

Supported production adapter discovery:

```text
GET /api/production-optimizers
```

Direct optimization example:

```json
{
  "domain": "collateral",
  "portfolio_id": "PORT_001",
  "optimizer_runtime": "production",
  "context": {
    "data_snapshot_id": "SNAP_COLLATERAL_001"
  }
}
```

Workflow example:

```json
{
  "workflow": "portfolio_rebalance_mvo",
  "portfolio_id": "PORT_MVO_001",
  "optimizer_runtime": "production",
  "context": {
    "asset_allocation": {
      "data_snapshot_id": "SNAP_MVO_001"
    }
  }
}
```

Multi-domain workflow example:

```json
{
  "workflow": "collateral_liquidity_review",
  "portfolio_id": "PORT_HQLA_224",
  "optimizer_runtime": "production",
  "context": {
    "collateral": {
      "data_snapshot_id": "SNAP_COLLATERAL_001"
    },
    "money_market": {
      "data_snapshot_id": "SNAP_MM_001"
    }
  }
}
```

When a production workflow spans multiple domains, omit
`production_optimizer_id` unless intentionally overriding a single-domain
workflow. The runner assigns the registered default adapter per domain.

Production results are normalized back into the existing `OptimizationResult`
shape. Adapter evidence is available under:

```text
result.solver_metadata.production_evidence
```

## Documents

- [Production Optimizer Adapter Handoff](Production_Optimizer_Adapter_Handoff.md)
- [Engineering Cycle Spec](Engineering_Cycle_Spec.md)
- [Adapter Interface Spec](Adapter_Interface_Spec.md)
- [Model Config and Data Contracts](Model_Config_And_Data_Contracts.md)
- [Execution Isolation and Governance](Execution_Isolation_And_Governance.md)
- [Operational Optimizer Expansion](Operational_Optimizer_Expansion.md)

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
