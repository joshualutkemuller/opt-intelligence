"""Common solver request/result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from decision_intelligence.contracts.results import SolveStatus

ProblemType = Literal["lp", "milp", "qp", "conic"]
ObjectiveSense = Literal["minimize", "maximize"]


@dataclass(frozen=True)
class SolverSpec:
    backend: str = "scipy"
    problem_type: ProblemType = "lp"
    method: str | None = "highs"
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_context(cls, context: dict[str, Any]) -> SolverSpec:
        problem_type = context.get("problem_type", context.get("solver_problem_type", "lp"))
        backend = str(context.get("solver_backend", "scipy")).lower()
        method = context.get("solver_method")
        if method is None and backend == "scipy":
            method = "highs"
        return cls(
            backend=backend,
            problem_type=str(problem_type).lower(),  # type: ignore[arg-type]
            method=method,
            options=dict(context.get("solver_options", {})),
        )


@dataclass(frozen=True)
class LinearProblem:
    c: np.ndarray
    A_ub: np.ndarray | None = None
    b_ub: np.ndarray | None = None
    A_eq: np.ndarray | None = None
    b_eq: np.ndarray | None = None
    bounds: list[tuple[float | None, float | None]] = field(default_factory=list)
    sense: ObjectiveSense = "minimize"
    integrality: np.ndarray | None = None


@dataclass(frozen=True)
class SolverResult:
    status: SolveStatus
    objective_value: float | None = None
    x: np.ndarray | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
