# Operational Optimizer Expansion

## Purpose

This handoff expands the production optimizer adapter layer beyond portfolio,
collateral, and money-market allocation. The goal is to show that the Decision
Intelligence platform can support operational optimization workflows that are
valuable across treasury, operations, middle office, and control functions.

The first two operational production adapters are:

1. `production.treasury.cash_movement`
2. `production.margin_call.workflow`

These are deliberately implemented as production-facing adapter scaffolds. They
exercise the same lifecycle as model-backed optimizers: preflight, problem
build, solve, normalization, evidence, config lineage, and registry discovery.

## Optimizer 1: Treasury Cash Movement

### Business Problem

Treasury and operations teams often need to move cash across entities,
accounts, currencies, and payment rails before market or payment cutoffs. The
workflow must balance cost, timing, source liquidity buffers, available rails,
and funding requirements.

The opportunity is operational rather than portfolio-driven: reduce failed or
late funding movements while preserving liquidity buffers and minimizing
transfer costs.

### Decision Variables

- Source account selected for each transfer
- Target funding requirement served
- Payment rail selected
- Transfer amount
- Residual unmet funding, if any

### Objective

Minimize total transfer cost:

```text
sum(amount * fee_bps / 10000 + fixed_fee + cutoff_penalty)
```

The current scaffold uses a deterministic least-cost, cutoff-feasible routing
rule. A production implementation could replace this with LP/MILP routing,
payment-rail simulation, or a vendor payment engine.

### Constraints

- Funding requirements must be satisfied.
- Source accounts must retain operating buffers.
- Payment rails must be open before cutoff.
- Rail capacity and per-transfer limits must be respected.
- Currency must match between source, requirement, and rail.

### Data Contract

Required datasets:

- `cash_balances`
- `funding_requirements`
- `payment_rails`

Optional datasets:

- `holiday_calendar`
- `entity_transfer_limits`

### Production Integration Notes

This adapter is a natural bridge to existing treasury systems, payment hubs,
cash ledgers, and intraday liquidity platforms. Execution isolation could move
from in-process adapter logic to REST, batch, or container execution once the
firm optimizer or payment simulator is available.

## Optimizer 2: Margin Call Workflow

### Business Problem

Margin operations teams receive margin calls with different exposure sizes,
counterparties, due times, dispute probabilities, operational effort, and
approval requirements. During stress, the team may not have enough capacity to
process everything immediately.

The opportunity is to prioritize operational work based on exposure, SLA risk,
dispute risk, and available capacity while producing a clear evidence trail for
why certain calls were processed, escalated, or deferred.

### Decision Variables

- Which margin calls are assigned in the current work window
- Processing order
- Recommended action for each call
- Deferred calls and escalation reasons
- Capacity usage

### Objective

Minimize residual queue risk:

```text
residual_risk = total_queue_risk - assigned_risk_reduction
```

Priority score combines:

- Call amount versus materiality threshold
- SLA urgency
- Dispute probability
- Counterparty risk tier

### Constraints

- Assigned calls must fit available team capacity.
- Calls near SLA cutoff receive priority.
- High-dispute or high-risk calls require escalation evidence.
- Material calls above threshold require supervisor review.

### Data Contract

Required datasets:

- `margin_call_queue`
- `ops_capacity`

Optional datasets:

- `counterparty_risk_scores`
- `holiday_calendar`

### Production Integration Notes

This adapter can evolve into a workflow-routing optimizer connected to margin
systems, case-management queues, SLA dashboards, and approval tooling. The
production backend could be a custom scoring model, MILP assignment engine,
workflow queue service, or batch scheduler.

## Why These Matter

These two optimizers demonstrate that the platform is not limited to investment
allocation. The same architecture can support operational decisions where
business value comes from speed, controls, explainability, and repeatable
decisioning.

They also make the platform more credible for enterprise production use:

- Business users can see the platform solving familiar operational problems.
- Risk and control teams get evidence, validation, and approval metadata.
- Quant and engineering teams get a stable adapter interface for replacing the
  scaffold with firm-developed engines.
- The UI and API can surface operational recommendations without changing the
  optimizer contract.

## Next Build Steps

1. ✅ Add workflow templates and demo presets for both operational adapters.
2. ✅ Surface the adapters in the front-end workflow selector.
3. ✅ Extend evidence export with operational queue tables and action logs.
4. Add document ingestion examples for payment policies, SLA rules, and margin
   call procedures.
5. Replace scaffold solve logic with firm production engines when available.

## Implementation Update: Workflow And Evidence Demo Layer

The two operational adapters are now runnable through the same workflow,
preset, API, UI selector, and evidence-export pattern as the portfolio,
collateral, and money-market demos.

New workflow templates:

- `treasury_cash_movement`
- `margin_call_workflow`

New demo presets:

- `treasury_cash_movement_cutoff`
- `margin_call_capacity_triage`

The browser workflow selector receives these from `GET /api/workflows` and
`GET /api/demo-presets`. The React fallback catalog also includes both demos so
the interface remains intelligible if the API catalog is temporarily
unavailable.

Evidence export now includes an `operational_evidence` section plus
`operational_actions.csv` / XLSX worksheet rows. For treasury cash movement,
the action rows describe transfer amount, source, target, rail, cost, and
recommendation. For margin-call workflow, the action rows describe assigned and
deferred calls, priority score, capacity minutes, recommended action, and
deferral/escalation reason.

Remaining production-hardening work:

- Add document ingestion examples for payment policies, SLA rules, and margin
  call procedures.
- Add richer front-end tables for operational actions before export, not only
  inside the evidence package.
- Replace scaffold solve logic with firm production engines when available.
