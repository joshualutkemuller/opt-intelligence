# Collateral Optimizer

## Purpose

The collateral optimizer allocates eligible collateral inventory to counterparty
obligations at minimum funding cost while satisfying post-haircut coverage,
inventory, eligibility, and asset-class concentration constraints.

Enabled domain: `collateral`

Implementation:
`src/decision_intelligence/optimizers/collateral/optimizer.py`

## Data Inputs

Asset-level variables:

| Field | Meaning | Used as |
|---|---|---|
| `asset_id`, `label` | Asset identity and display fields | Output metadata |
| `asset_class` | `govt_bond`, `corp_bond`, `equity`, or `cash` | Eligibility and concentration |
| `market_value` | Asset market value in USD | Objective, coverage, inventory value |
| `haircut` | Haircut fraction | Coverage and haircut objective |
| `funding_cost_bps` | Annual funding/opportunity cost in basis points | Funding-cost objective |
| `eligible` | Inventory-level eligibility flag | Pre-solve filter |
| `currency` | Asset currency | Stored; not in current constraints |
| `rating` | Rating label | Stored; not in current constraints |
| `maturity_years` | Asset maturity | Stored; not in current constraints |

Obligation-level variables:

| Field | Meaning | Used as |
|---|---|---|
| `obligation_id` | Obligation identity | Constraint labels and outputs |
| `counterparty` | Counterparty name | Output metadata and explanation |
| `required_value` | Required post-haircut collateral value in USD | Coverage constraint |
| `eligible_asset_classes` | Accepted asset classes | Eligibility bounds |

## Decision Variables

```text
x_i_j = fraction of asset i allocated to obligation j
```

The fraction is applied to the asset's full market value. A value of `0.25`
means 25% of that asset is pledged to the obligation.

Variable indexing follows:

```text
index(i, j) = i + j * n_assets
```

## Objective Function

For the default `funding_cost` objective:

```text
minimize sum_i sum_j funding_cost_bps_i * market_value_i * x_i_j / 10000
```

Supported objective metrics:

| Metric | Coefficient used |
|---|---|
| `funding_cost` | `funding_cost_bps_i * market_value_i / 10000` |
| `haircut_cost` | `haircut_i * market_value_i` |
| `opportunity_cost` | Same proxy as `funding_cost` in current implementation |

Current implementation note: `opportunity_cost` is accepted as a metric name,
but it currently uses the same coefficient as `funding_cost`.

## Constraints

Inventory limit for each asset:

```text
sum_j x_i_j <= 1
```

Post-haircut coverage for each obligation:

```text
sum_i x_i_j * market_value_i * (1 - haircut_i) >= required_value_j
```

Eligibility by obligation:

```text
x_i_j = 0 when asset_class_i is not in eligible_asset_classes_j
```

This is implemented through variable bounds:

```text
0 <= x_i_j <= 1       when eligible
0 <= x_i_j <= 0       when ineligible
```

Asset-class concentration for each obligation:

```text
sum_{i in class c} x_i_j * market_value_i
  <= concentration_limit * sum_i x_i_j * market_value_i
```

The implementation linearizes this as:

```text
sum_i indicator(asset_class_i = c) * x_i_j * market_value_i
  - concentration_limit * sum_i x_i_j * market_value_i <= 0
```

Non-negativity:

```text
x_i_j >= 0
```

## Tunable Limits and Defaults

| Context key | Default | Meaning |
|---|---:|---|
| `concentration_limit` | `0.60` | Maximum share from any one asset class per obligation |
| `n_assets` | Loader-dependent, simulated as `20` | Number of simulated assets |
| `seed` | Loader-dependent | Deterministic simulation seed |
| `inventory_scale` | `1.0` | Multiplier on simulated market values |
| `obligation_scale` | `1.0` | Multiplier on simulated obligation requirements |

Solver keys:

| Context key | Common values |
|---|---|
| `solver_backend` | `scipy`, `cvxpy` |
| `problem_type` | `lp` |
| `solver_method` | `highs` for SciPy LP |
| `solver_options` | Backend-specific options dictionary |

## Factors Considered

The current optimizer explicitly considers:

- Funding cost: lower-cost assets are preferred under `funding_cost`.
- Haircuts: lower-haircut assets provide more post-haircut coverage per dollar.
- Market value: asset size determines how much collateral can be pledged.
- Eligibility: obligations can accept only configured asset classes.
- Inventory use: no asset can be allocated beyond 100% of its inventory.
- Asset-class concentration: one class cannot dominate a single obligation.

The current optimizer stores but does not yet constrain on:

- Currency matching.
- Rating minimums.
- Maturity buckets.
- Counterparty-specific haircut schedules.

## Result Fields

Allocation metadata includes:

- `obligation_id`
- `counterparty`
- `asset_class`
- `haircut`
- `funding_cost_bps`
- `post_haircut_value`

Binding constraints can include:

- `inventory:<asset_id>`
- `coverage:<obligation_id>`

Sensitivity analysis re-solves the LP after reducing each obligation's required
value by 10% and reports approximate savings per $1 million of relaxation.
