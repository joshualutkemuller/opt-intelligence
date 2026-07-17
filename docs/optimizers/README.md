# Optimizer Technical Documentation

This directory documents the domain optimizers currently enabled in the
platform. These are the optimizers registered by the CLI/API bootstrap layer and
used by the workflow engine:

| Domain | Optimizer | Problem family | Primary decision |
|---|---|---|---|
| `asset_allocation` | Asset Allocation MVO Optimizer | Convex QP via SciPy SLSQP | Allocate capital across major asset classes |
| `money_market` | Money Market Optimizer | LP, optional MILP | Allocate cash across money market funds |
| `collateral` | Collateral Optimizer | LP | Allocate collateral inventory to obligations |
| `financing` | Financing Optimizer | LP | Source funding from counterparties |

The solver abstraction is documented separately in
[solver_backends.md](../models/solver_backends.md). In short, optimizers build a
`LinearProblem` with objective coefficients, constraints, bounds, and optional
integrality. The solver backend is selected through request context:

```python
context = {
    "solver_backend": "scipy",
    "problem_type": "lp",
    "solver_method": "highs",
}
```

The asset allocation optimizer uses SciPy SLSQP for a constrained
mean-variance objective. The money market optimizer can also build a true MILP when
`problem_type = "milp"` so it can enforce fund-selection binary variables. The
collateral and financing optimizers currently build continuous LPs.

## Pages

- [Asset Allocation MVO Optimizer](asset_allocation.md)
- [Money Market Optimizer](money_market.md)
- [Collateral Optimizer](collateral.md)
- [Financing Optimizer](financing.md)

## Shared Output Pattern

Each optimizer returns:

- `status`: solver status, usually `optimal` for successful demos.
- `objective_value`: optimized objective in domain-specific units.
- `allocations`: user-facing allocation rows with labels, values, fractions,
  and metadata.
- `binding_constraints`: constraints that are approximately active at the
  solution.
- `metadata`: solver backend, problem type, method, raw solver status, and
  domain-specific counts.

Each optimizer also has an `explain(...)` method that translates the result into
a narrative summary for chat/API demos.
