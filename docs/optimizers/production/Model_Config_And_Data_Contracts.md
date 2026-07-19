# Model Config And Data Contracts

Production optimizers need configuration that is explicit enough for quants and
safe enough for platform automation.

## Model Configuration Schema

`ModelConfigSpec` should contain:

- `optimizer_id`: stable platform identifier;
- `domain`: business domain;
- `lineage`: model name, model version, config version, owner, approvals, and
  change ticket;
- `objectives`: objective terms, direction, weights, units, and descriptions;
- `constraints`: constraint families, hardness, tolerances, and linked limit
  sources;
- `limit_sources`: policy, regulatory, market data, risk model, or manual
  sources;
- `scenario_knobs`: scenario controls exposed to workflows and UI;
- `data_contract`: required datasets, keys, columns, checks, and snapshot
  requirements;
- `solver`: backend, problem family, vendor, version, and parameters;
- `execution`: isolation mode, timeout, retry count, resource profile, endpoint,
  command, or container image;
- `metadata`: domain-specific extensions.

## Objective Terms

Objective terms should be decomposed enough that a reviewer can understand
tradeoffs.

Examples:

- maximize expected return;
- minimize variance;
- minimize funding cost;
- minimize liquidity shortfall;
- minimize turnover;
- penalize concentration;
- penalize transaction cost.

Each objective term should include a direction, weight, units, and description.
For multi-objective models, weights should be visible in evidence so a reviewer
can explain why the recommendation changed.

## Constraint Families

Constraint families should represent policy and model controls rather than raw
matrix rows.

Examples:

- budget;
- bounds;
- liquidity;
- risk;
- turnover;
- regulatory;
- custom domain logic.

Each family should identify whether it is hard, what tolerance applies, and
which limit source governs it.

## Limit Sources

Limit source metadata keeps constraints explainable.

Examples:

- IPS policy statement;
- regulatory rule;
- risk model;
- investment committee override;
- treasury policy limit;
- market data feed.

Limit sources should include ownership, refresh frequency, and whether evidence
is required.

## Scenario Knobs

Scenario knobs are business controls exposed to workflows and demos.

Examples:

- stress multiplier;
- target return;
- risk aversion;
- max turnover;
- cash floor;
- liquidity haircut;
- funding spread shock;
- benchmark tracking-error limit.

Knobs should declare type, default, allowed values when relevant, and business
description.

## Data Contract Layer

The data contract is the production guardrail before solve.

Required datasets can include:

- holdings;
- portfolio cash;
- security master;
- eligibility rules;
- curves;
- risk factors;
- covariance matrix;
- transaction cost model;
- market data;
- policy limits;
- approval state.

Each dataset should declare:

- primary keys;
- required columns;
- freshness expectations;
- quality checks;
- snapshot requirement;
- blocking behavior.

## Preflight Validation

Preflight should run before `build_problem()`.

Blocking examples:

- missing holdings;
- missing risk model;
- stale prices;
- missing policy limit;
- unsupported execution mode;
- optimizer version not approved for requested use;
- solver backend unavailable.

Warning examples:

- optional explanatory dataset unavailable;
- noncritical reference field missing;
- scenario knob using default rather than explicit user input.

## Result Normalization Map

Each production adapter should maintain a mapping from native outputs to
platform output sections:

| Native output | Platform section |
|---|---|
| optimal weights or trades | `allocations` |
| raw objective | `objective_value` |
| incumbent or benchmark objective | `baseline_value` |
| active constraints | `binding_constraints` |
| dual variables | `duals` |
| marginal values | `shadow_prices` |
| infeasibility report | `infeasibility_diagnostics` |
| efficient frontier | `frontier_points` |
| stress grid | `scenario_grid` |
| turnover | `turnover` |
| transaction costs | `transaction_costs` |
| proprietary dense output | `domain_attachments` |

## Current Production Adapter Contract Inventory

| Adapter | Objective terms | Constraint families | Required data contract | Solver family | Evidence emphasis |
|---|---|---|---|---|---|
| `production.asset_allocation.mvo` | Maximize mean-variance utility and target-return tradeoff. | Budget, target return, asset bounds, cash floor, concentration. | Asset universe and covariance matrix. | SciPy QP/SLSQP. | Portfolio assumptions, covariance shape, optimized weights, risk/return diagnostics, sensitivities. |
| `production.collateral.allocation` | Minimize collateral funding/opportunity cost. | Obligation coverage, eligible inventory, concentration, haircuts, venue eligibility. | Collateral inventory and margin obligations. | SciPy LP/HiGHS. | Posted collateral, counterparty obligations, venue mix, binding concentration/capacity limits. |
| `production.financing.allocation` | Minimize funding spread cost; optional capital-usage objective mode. | Funding coverage, counterparty capacity, tenor compatibility, single-counterparty concentration, capital budget. | Financing counterparties and funding needs. | SciPy LP/HiGHS. | Funding source allocations, instrument mix, counterparty usage, capital usage, binding capacity/concentration limits. |
| `production.money_market.allocation` | Maximize weighted money-market yield. | Cash budget, daily liquidity, weekly liquidity, prime concentration, WAM, single-fund bounds. | Money-market fund universe and cash position. | SciPy LP/HiGHS with optional MILP controls. | Fund allocations, liquidity profile, WAM, prime exposure, binding liquidity/concentration checks. |
| `production.treasury.cash_movement` | Minimize transfer cost and cutoff/buffer risk. | Account buffers, funding coverage, payment rail eligibility, cutoff windows, rail capacity. | Cash balances, funding requirements, payment rails. | Custom operational assignment scaffold. | Routed transfers, cash moved, rail mix, uncovered requirements, cutoff/capacity diagnostics. |
| `production.margin_call.workflow` | Minimize residual SLA/materiality/dispute risk under capacity. | Team capacity, call priority, due-time urgency, materiality, dispute probability. | Margin-call queue and ops capacity. | Custom operational prioritization scaffold. | Assigned calls, deferred calls, capacity usage, residual risk, SLA pressure. |

## Tonight Closeout Notes

The config and data-contract layer now covers the current optimizer inventory.
The remaining production work is not schema design; it is connecting these
contracts to firm data sources, firm model packages or services, immutable
evidence storage, and model-governance promotion controls.
