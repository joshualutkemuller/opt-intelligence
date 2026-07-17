# Money Market Optimizer

## Purpose

The money market optimizer allocates a cash balance across eligible money market
funds to maximize annualized 7-day net yield while satisfying liquidity,
concentration, and weighted-average-maturity limits.

Enabled domain: `money_market`

Implementation:
`src/decision_intelligence/optimizers/money_market/optimizer.py`

## Data Inputs

Fund-level variables:

| Field | Meaning | Used as |
|---|---|---|
| `fund_id`, `label`, `provider` | Fund identity and display fields | Output metadata |
| `yield_7day` | Annualized 7-day net yield, percent | Objective coefficient |
| `expense_ratio_bps` | Expense ratio in basis points | Output metadata |
| `wam_days` | Weighted average maturity in days | WAM constraint |
| `daily_liquidity_pct` | Fraction redeemable T+0 | Daily liquidity floor |
| `weekly_liquidity_pct` | Fraction redeemable within the weekly window | Weekly liquidity floor |
| `min_investment` | Minimum investment in USD | Eligibility filter |
| `credit_quality` | `government`, `prime`, or `treasury` | Prime concentration constraint |
| `switching_cost_bps` | Cost to move between funds | Stored on data model; not in current objective |

Cash-position variables:

| Field | Meaning | Used as |
|---|---|---|
| `total_cash` | Total investable cash | Converts weights to USD allocations |
| `current_allocations` | Existing fund allocations | Baseline yield calculation |
| `daily_liquidity_requirement` | Minimum weighted daily liquidity | Default daily liquidity floor |
| `weekly_liquidity_requirement` | Minimum weighted weekly liquidity | Default weekly liquidity floor |

## Decision Variables

Continuous LP form:

```text
w_i = fraction of total cash allocated to fund i
```

MILP form:

```text
w_i = fraction of total cash allocated to fund i
z_i = 1 if fund i is selected, otherwise 0
```

Variable indexing is fund order after eligibility filtering.

## Objective Function

The optimizer maximizes weighted 7-day yield:

```text
maximize sum_i yield_7day_i * w_i
```

The solver layer minimizes by convention, so the implementation passes:

```text
minimize -sum_i yield_7day_i * w_i
c_i = -yield_7day_i
```

The reported `objective_value` is converted back to positive achieved yield.

Current implementation note: request validation accepts `yield`, `net_yield`,
and `expense_ratio`, but the objective vector currently uses `yield_7day` for
all accepted metric names. Expense ratio is surfaced in allocation metadata but
is not separately minimized.

## Constraints

Fully invested:

```text
sum_i w_i = 1
```

Daily liquidity floor:

```text
sum_i daily_liquidity_pct_i * w_i >= daily_liquidity_req
```

Weekly liquidity floor:

```text
sum_i weekly_liquidity_pct_i * w_i >= weekly_liquidity_req
```

Prime fund concentration:

```text
sum_i is_prime_i * w_i <= max_prime_fraction
```

Weighted average maturity cap:

```text
sum_i wam_days_i * w_i <= max_wam_days
```

Single-fund concentration:

```text
0 <= w_i <= max_single_fund
```

Eligibility filter:

```text
fund_i is eligible when
  min_investment_i <= min_investment_threshold
  or total_cash * 0.01 >= min_investment_i
```

## MILP Selection Constraints

When `problem_type = "milp"`, the model adds binary selection variables:

```text
w_i <= max_single_fund * z_i
w_i >= min_allocation_fraction * z_i
sum_i z_i <= max_funds
z_i in {0, 1}
```

This allows demos to show a realistic mandate such as "use no more than three
funds, and every selected fund must receive at least 10%."

## Tunable Limits and Defaults

| Context key | Default | Meaning |
|---|---:|---|
| `daily_liquidity_req` | Cash position default, simulated as `0.30` | Minimum T+0 redeemable fraction |
| `weekly_liquidity_req` | Cash position default, simulated as `0.60` | Minimum weekly redeemable fraction |
| `max_prime_fraction` | `0.40` | Maximum allocation to prime funds |
| `max_wam_days` | `60` | Maximum weighted average maturity |
| `max_single_fund` | `0.50` | Maximum allocation to one fund |
| `min_allocation_fraction` | `0.05` | MILP minimum allocation if selected |
| `max_funds` | `4` | MILP maximum selected funds |
| `min_investment_threshold` | `250000` | Eligibility threshold for fund minimums |
| `total_cash` | `500000000` in simulated data | Total cash to allocate |
| `n_funds` | Loader-dependent | Number of simulated candidate funds |
| `seed` | Loader-dependent | Deterministic simulation seed |
| `yield_shift` | `1.0` | Simulated yield stress multiplier |

Solver keys:

| Context key | Common values |
|---|---|
| `solver_backend` | `scipy`, `cvxpy` |
| `problem_type` | `lp`, `milp` |
| `solver_method` | `highs` for SciPy LP |
| `solver_options` | Backend-specific options dictionary |

## Factors Considered

The current optimizer explicitly considers:

- Yield: higher `yield_7day` improves the objective.
- Liquidity: daily and weekly liquidity must clear portfolio-level floors.
- Fund type: `prime` funds are limited by a concentration cap.
- Maturity: higher WAM consumes the WAM limit.
- Fund concentration: no one fund can exceed `max_single_fund`.
- Minimum investment: high-minimum funds can be filtered out before solving.
- Current allocation: used only for the baseline comparison, not as a turnover
  penalty in the objective.

The current optimizer does not yet model:

- Explicit switching-cost minimization.
- Provider concentration.
- Rating tiers beyond the prime/government/treasury type split.
- Scenario-specific liquidity haircuts.

## Result Fields

Allocation metadata includes:

- `yield_7day`
- `expense_ratio_bps`
- `wam_days`
- `daily_liquidity_pct`
- `credit_quality`
- `contribution_to_yield_bps`
- `selected` for MILP runs

Binding constraints can include:

- `daily_liquidity`
- `weekly_liquidity`
- `prime_concentration`
- `wam_limit`
- `single_fund_limit:<fund_id>`

Sensitivity analysis is available for LP runs and skips MILP runs because MILP
shadow prices are not directly comparable to continuous LP duals.
