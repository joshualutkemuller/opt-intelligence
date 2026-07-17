# Financing Optimizer

## Purpose

The financing optimizer sources external funding for a set of positions at
minimum cost while satisfying funding needs, counterparty capacity, tenor
compatibility, capital budget, and counterparty concentration limits.

Enabled domain: `financing`

Implementation:
`src/decision_intelligence/optimizers/financing/optimizer.py`

## Data Inputs

Counterparty-level variables:

| Field | Meaning | Used as |
|---|---|---|
| `counterparty_id`, `name` | Counterparty identity and display fields | Output metadata |
| `instrument` | `repo`, `sec_lending`, `term_loan`, or `revolver` | Output and scenario mix |
| `spread_bps` | Spread over benchmark in basis points | Funding-cost objective |
| `capacity` | Maximum funding available in USD | Capacity constraint and bounds |
| `min_tenor_days` | Shortest supported tenor | Tenor compatibility |
| `max_tenor_days` | Longest supported tenor | Tenor compatibility |
| `capital_usage_pct` | Capital or balance-sheet use as percent of notional | Capital objective and budget |
| `eligible_collateral` | Accepted collateral classes | Stored; not in current constraints |

Funding-need variables:

| Field | Meaning | Used as |
|---|---|---|
| `position_id` | Position requiring funding | Equality constraint and outputs |
| `instrument_type` | Position type | Stored; not in current constraints |
| `notional` | Funding amount required in USD | Full-funding constraint |
| `required_tenor_days` | Required funding tenor | Tenor compatibility |
| `preferred_instrument` | Preferred funding instrument | Stored; not in current constraints |

## Decision Variables

```text
x_i_j = USD amount sourced from counterparty i for funding need j
```

Variable indexing follows:

```text
index(i, j) = i + j * n_counterparties
```

## Objective Function

For the default `funding_spread` or `funding_cost` objective:

```text
minimize sum_i sum_j spread_bps_i * x_i_j / 10000
```

For `capital_usage`:

```text
minimize sum_i sum_j capital_usage_pct_i * x_i_j / 10000
```

Current implementation note: the capital-usage objective uses the same basis
point-style scaling as spread. The capital budget constraint separately uses
`capital_usage_pct_i / 100`, which is the true percentage-of-notional budget
calculation.

## Constraints

Full funding for each need:

```text
sum_i x_i_j = notional_j
```

Counterparty capacity:

```text
sum_j x_i_j <= capacity_i
```

Capital budget:

```text
sum_i sum_j capital_usage_pct_i / 100 * x_i_j <= cap_budget
```

where:

```text
cap_budget = total_funding * capital_budget_pct / 100
```

Counterparty concentration:

```text
sum_j x_i_j <= max_cp_concentration * total_funding
```

Tenor compatibility:

```text
x_i_j = 0 unless min_tenor_days_i <= required_tenor_days_j <= max_tenor_days_i
```

This is implemented through variable bounds:

```text
0 <= x_i_j <= capacity_i   when tenor-compatible
0 <= x_i_j <= 0            when tenor-incompatible
```

Non-negativity:

```text
x_i_j >= 0
```

## Tunable Limits and Defaults

| Context key | Default | Meaning |
|---|---:|---|
| `max_cp_concentration` | `0.40` | Maximum share of total funding from one counterparty |
| `capital_budget_pct` | `5.0` | Maximum capital usage as percent of total funding |
| `n_counterparties` | Loader-dependent, simulated as `10` | Number of simulated funding sources |
| `seed` | Loader-dependent | Deterministic simulation seed |
| `total_funding_need` | `300000000` in simulated data | Total funding demand |
| `capacity_scale` | `1.0` | Multiplier on simulated counterparty capacities |
| `spread_shift` | `1.0` | Multiplier on simulated spreads |

Solver keys:

| Context key | Common values |
|---|---|
| `solver_backend` | `scipy`, `cvxpy` |
| `problem_type` | `lp` |
| `solver_method` | `highs` for SciPy LP |
| `solver_options` | Backend-specific options dictionary |

## Factors Considered

The current optimizer explicitly considers:

- Spread: lower-spread counterparties reduce objective cost.
- Capacity: each counterparty has a hard maximum funding amount.
- Tenor: a counterparty can fund only needs inside its tenor range.
- Capital usage: total capital consumption cannot exceed the configured budget.
- Counterparty concentration: no counterparty can exceed the portfolio share cap.
- Funding need size: each position must be fully funded.

The current optimizer stores but does not yet constrain on:

- Preferred instrument matching.
- Funding need `instrument_type`.
- Collateral eligibility by counterparty.
- Counterparty group or parent-level exposure limits.

## Result Fields

Allocation metadata includes:

- `position_id`
- `counterparty`
- `instrument`
- `spread_bps`
- `capital_usage_pct`
- `tenor_days`
- `cost_usd`

Binding constraints can include:

- `capacity:<counterparty_id>`
- `concentration:<counterparty_id>`
- `capital_budget`

Sensitivity analysis expands each counterparty's capacity by 25%, re-solves the
LP, and reports approximate savings per $1 million of added capacity.
