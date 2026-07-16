"""SciPy/HiGHS mixed-integer linear-program solver backend."""

from __future__ import annotations

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from decision_intelligence.contracts.results import SolveStatus

from .types import LinearProblem, SolverResult, SolverSpec


class ScipyMILPSolver:
    backend = "scipy"
    problem_type = "milp"

    def solve(self, problem: LinearProblem, spec: SolverSpec) -> SolverResult:
        c = problem.c
        if problem.sense == "maximize":
            c = -c

        constraints = _constraints(problem)
        bounds = _bounds(problem)
        integrality = (
            problem.integrality
            if problem.integrality is not None
            else np.zeros(len(problem.c), dtype=int)
        )

        res = milp(
            c=c,
            integrality=integrality,
            bounds=bounds,
            constraints=constraints,
            options=spec.options or None,
        )

        metadata = {
            "solver_backend": self.backend,
            "problem_type": self.problem_type,
            "solver_method": "highs",
            "solver": "SciPy milp / HiGHS",
            "iterations": getattr(res, "mip_node_count", None),
            "message": res.message,
            "raw_status": res.status,
        }

        if res.status == 0:
            objective = float(res.fun)
            if problem.sense == "maximize":
                objective = -objective
            return SolverResult(
                status=SolveStatus.OPTIMAL,
                objective_value=objective,
                x=res.x,
                message=res.message,
                metadata=metadata,
            )

        status_map = {2: SolveStatus.INFEASIBLE, 3: SolveStatus.UNBOUNDED}
        return SolverResult(
            status=status_map.get(res.status, SolveStatus.ERROR),
            message=res.message,
            metadata=metadata,
        )


def _constraints(problem: LinearProblem) -> LinearConstraint | tuple[()]:
    rows = []
    lower = []
    upper = []
    if problem.A_ub is not None and problem.b_ub is not None:
        rows.append(problem.A_ub)
        lower.extend([-np.inf] * len(problem.b_ub))
        upper.extend(problem.b_ub)
    if problem.A_eq is not None and problem.b_eq is not None:
        rows.append(problem.A_eq)
        lower.extend(problem.b_eq)
        upper.extend(problem.b_eq)
    if not rows:
        return ()
    matrix = np.vstack(rows)
    return LinearConstraint(matrix, np.array(lower), np.array(upper))


def _bounds(problem: LinearProblem) -> Bounds:
    if not problem.bounds:
        return Bounds(np.full(len(problem.c), -np.inf), np.full(len(problem.c), np.inf))
    lower = np.array([-np.inf if lo is None else lo for lo, _hi in problem.bounds])
    upper = np.array([np.inf if hi is None else hi for _lo, hi in problem.bounds])
    return Bounds(lower, upper)
