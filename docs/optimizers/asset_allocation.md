# Asset Allocation MVO Optimizer

## Purpose

The `asset_allocation` optimizer builds a simple long-only multi-asset
portfolio using mean-variance optimization. It is intended for portfolio
construction demos where stakeholders want to see how expected return, risk,
and concentration limits shape a recommended strategic allocation.

## Decision Variables

For each asset class `i`:

```text
w_i = portfolio weight allocated to asset class i
```

The default simulated universe includes:

- US Equity
- International Equity
- Core Bonds
- High Yield Credit
- Real Assets
- Cash

## Objective Function

Default metric: `utility`

```text
maximize  expected_return(w) - lambda * variance(w)
```

Where:

```text
expected_return(w) = mu' w
variance(w)        = w' Sigma w
lambda             = risk_aversion
```

Supported objective metrics:

- `utility`
- `risk_adjusted_return`
- `sharpe`
- `volatility`

The default guided demo uses:

```text
risk_aversion = 3.0
problem_type  = qp
solver        = scipy / SLSQP
```

## Constraints

The optimizer enforces:

```text
sum_i w_i = 1
min_weight_i <= w_i <= max_weight_i
w' mu >= target_return       optional
sum_{i in class c} w_i >= min_class_weight_c
sum_{i in class c} w_i <= max_class_weight_c
```

Common context controls:

```python
context = {
    "portfolio_notional": 250_000_000,
    "risk_aversion": 3.0,
    "target_return": 0.05,
    "max_single_asset_weight": 0.45,
    "min_cash_weight": 0.02,
    "solver_backend": "scipy",
    "problem_type": "qp",
}
```

## Factors Considered

Each asset class carries:

- expected annual return
- annualized volatility
- current portfolio weight
- min/max allocation bounds
- covariance to every other asset class
- asset-class metadata such as liquidity or duration profile

The simulated covariance matrix uses intuitive cross-asset relationships:

- equities are highly correlated with one another
- core bonds are negatively correlated with equities
- high yield credit has moderate equity beta
- cash has near-zero volatility and low correlation

## Scenarios

Scenario overrides adjust the assumption set before optimization:

| Scenario | Effect |
|---|---|
| `stress` | lower equity returns, higher volatility, higher cash floor |
| `credit_stress` | larger equity/credit pressure and volatility shock |
| `downside` | broad return haircut and moderate volatility increase |

## Output

The optimizer returns:

- allocation by asset class
- expected portfolio return
- volatility
- variance
- Sharpe ratio
- binding min/max weight constraints
- risk and return contribution metadata by asset class

Allocation metadata includes:

```text
expected_return
volatility
current_weight
min_weight
max_weight
return_contribution
risk_contribution
```

## Interpretation

This optimizer is intentionally simple. It is useful for demonstrating the
platform’s ability to route a market-facing portfolio construction request into
a deterministic optimizer, validate the result, and explain the allocation in
business terms.

Production extensions would include:

- historical or forward-looking covariance estimation
- Black-Litterman views
- factor exposure limits
- turnover and transaction-cost penalties
- tax-aware constraints
- benchmark-relative tracking error
- CVaR or drawdown-aware risk measures
