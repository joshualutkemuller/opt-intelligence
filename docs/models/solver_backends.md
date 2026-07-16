# Solver Backends

The platform has a small solver layer so optimizers can request a backend and
problem type without embedding vendor-specific calls in each domain optimizer.
The selected solver is supplied through request context, CLI flags, or the
guided chat workflow.

## Supported Combinations

| Backend | Problem type | Status | Notes |
|---|---:|---|---|
| `scipy` | `lp` | Supported | Continuous linear programs via `scipy.optimize.linprog` and HiGHS |
| `scipy` | `milp` | Supported | Mixed-integer linear programs via `scipy.optimize.milp` and HiGHS |
| `cvxpy` | `lp` | Supported | Continuous linear programs via CVXPY; install with `.[solver-cvxpy]` |

Unsupported combinations fail fast with a clear configuration error that lists
the available pairs. This is intentional: adding `cvxpy/milp`, `scipy/qp`, or a
commercial solver should be done by registering a new adapter, not by adding
conditional logic inside a domain optimizer.

## CLI Usage

```bash
di run money_market --solver scipy --problem-type lp
di run money_market --solver scipy --problem-type milp
di run money_market --solver cvxpy --problem-type lp
```

For the money-market optimizer, `scipy/milp` activates true fund-selection
modeling with binary decision variables:

```text
w[i] = allocation weight for fund i
z[i] = 1 when fund i is selected, else 0

w[i] <= max_single_fund * z[i]
w[i] >= min_allocation_fraction * z[i]
sum(z[i]) <= max_funds
```

The guided chat workflow asks for `max_funds` and
`min_allocation_fraction` before solver selection. In code or JSON requests,
set them in `OptimizationRequest.context`.

```python
context = {
    "solver_backend": "scipy",
    "problem_type": "milp",
    "max_funds": 3,
    "min_allocation_fraction": 0.10,
}
```

Sensitivity analysis is skipped for MILP results because shadow prices are not
interpretable in the same direct way as continuous LP duals.

## Runnable Example

Run the focused solver demo:

```bash
python examples/run_solver_demo.py
```

It compares:

1. `scipy/lp` continuous money-market allocation.
2. `scipy/milp` with a maximum number of selected funds and a minimum allocation
   for each selected fund.
3. `cvxpy/lp` continuous allocation through CVXPY.

The example prints status, objective, improvement, selected fund count, and top
allocations for each run.
