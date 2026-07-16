"""SciPy/HiGHS linear-program solver backend."""

from __future__ import annotations

from scipy.optimize import linprog

from decision_intelligence.contracts.results import SolveStatus

from .types import LinearProblem, SolverResult, SolverSpec


class ScipyLPSolver:
    backend = "scipy"
    problem_type = "lp"

    def solve(self, problem: LinearProblem, spec: SolverSpec) -> SolverResult:
        if problem.integrality is not None:
            return SolverResult(
                status=SolveStatus.ERROR,
                message="SciPy LP backend does not support integer variables. Use a MILP backend.",
                metadata=self._metadata(spec),
            )

        c = problem.c
        if problem.sense == "maximize":
            c = -c

        res = linprog(
            c=c,
            A_ub=problem.A_ub,
            b_ub=problem.b_ub,
            A_eq=problem.A_eq,
            b_eq=problem.b_eq,
            bounds=problem.bounds,
            method=spec.method or "highs",
            options=spec.options or None,
        )

        metadata = {
            **self._metadata(spec),
            "iterations": getattr(res, "nit", None),
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

    def _metadata(self, spec: SolverSpec) -> dict:
        return {
            "solver_backend": self.backend,
            "problem_type": self.problem_type,
            "solver_method": spec.method or "highs",
            "solver": "SciPy linprog / HiGHS",
        }
