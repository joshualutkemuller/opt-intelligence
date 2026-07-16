"""CVXPY linear-program solver backend.

CVXPY is optional. The backend is registered so callers can select it when the
package is installed, and it returns a clear solver error otherwise.
"""

from __future__ import annotations

import numpy as np

from decision_intelligence.contracts.results import SolveStatus

from .types import LinearProblem, SolverResult, SolverSpec


class CvxpyLPSolver:
    backend = "cvxpy"
    problem_type = "lp"

    def solve(self, problem: LinearProblem, spec: SolverSpec) -> SolverResult:
        if problem.integrality is not None:
            return SolverResult(
                status=SolveStatus.ERROR,
                message="CVXPY LP backend does not support integrality in this adapter.",
                metadata=self._metadata(spec),
            )

        try:
            import cvxpy as cp
        except ImportError:
            return SolverResult(
                status=SolveStatus.ERROR,
                message="CVXPY backend requested but cvxpy is not installed.",
                metadata=self._metadata(spec),
            )

        x = cp.Variable(len(problem.c))
        constraints = []

        if problem.A_ub is not None and problem.b_ub is not None:
            constraints.append(problem.A_ub @ x <= problem.b_ub)
        if problem.A_eq is not None and problem.b_eq is not None:
            constraints.append(problem.A_eq @ x == problem.b_eq)
        if problem.bounds:
            lower = np.array([
                -np.inf if lo is None else lo
                for lo, _hi in problem.bounds
            ])
            upper = np.array([
                np.inf if hi is None else hi
                for _lo, hi in problem.bounds
            ])
            constraints.append(x >= lower)
            constraints.append(x <= upper)

        objective_expr = problem.c @ x
        objective = (
            cp.Maximize(objective_expr)
            if problem.sense == "maximize"
            else cp.Minimize(objective_expr)
        )
        model = cp.Problem(objective, constraints)

        try:
            if spec.method:
                value = model.solve(solver=spec.method, **spec.options)
            else:
                value = model.solve(**spec.options)
        except Exception as exc:  # noqa: BLE001
            return SolverResult(
                status=SolveStatus.ERROR,
                message=f"CVXPY solve failed: {exc}",
                metadata=self._metadata(spec),
            )

        metadata = {
            **self._metadata(spec),
            "solver": model.solver_stats.solver_name,
            "iterations": model.solver_stats.num_iters,
            "raw_status": model.status,
        }

        if model.status in {"optimal", "optimal_inaccurate"} and x.value is not None:
            return SolverResult(
                status=SolveStatus.OPTIMAL,
                objective_value=float(value),
                x=np.asarray(x.value).reshape(-1),
                message=model.status,
                metadata=metadata,
            )
        if model.status in {"infeasible", "infeasible_inaccurate"}:
            status = SolveStatus.INFEASIBLE
        elif model.status in {"unbounded", "unbounded_inaccurate"}:
            status = SolveStatus.UNBOUNDED
        else:
            status = SolveStatus.ERROR
        return SolverResult(status=status, message=model.status, metadata=metadata)

    def _metadata(self, spec: SolverSpec) -> dict:
        return {
            "solver_backend": self.backend,
            "problem_type": self.problem_type,
            "solver_method": spec.method,
        }
