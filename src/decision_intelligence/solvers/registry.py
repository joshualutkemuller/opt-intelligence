"""Registry for mathematical solver backends."""

from __future__ import annotations

from .base import OptimizationSolver
from .cvxpy_lp import CvxpyLPSolver
from .scipy_lp import ScipyLPSolver
from .scipy_milp import ScipyMILPSolver
from .types import LinearProblem, SolverResult, SolverSpec


class SolverConfigError(ValueError):
    """Raised when a requested solver backend/problem type is unsupported."""


class SolverRegistry:
    def __init__(self) -> None:
        self._solvers: dict[tuple[str, str], OptimizationSolver] = {}

    def register(self, solver: OptimizationSolver) -> None:
        key = (solver.backend.lower(), solver.problem_type.lower())
        self._solvers[key] = solver

    def get(self, spec: SolverSpec) -> OptimizationSolver:
        key = (spec.backend.lower(), spec.problem_type.lower())
        if key not in self._solvers:
            available = ", ".join(f"{b}/{p}" for b, p in sorted(self._solvers))
            raise SolverConfigError(
                f"Unsupported solver '{spec.backend}' for problem type "
                f"'{spec.problem_type}'. Available: {available}"
            )
        return self._solvers[key]

    def list_solvers(self) -> list[str]:
        return [f"{backend}/{problem_type}" for backend, problem_type in sorted(self._solvers)]


def default_solver_registry() -> SolverRegistry:
    registry = SolverRegistry()
    registry.register(ScipyLPSolver())
    registry.register(ScipyMILPSolver())
    registry.register(CvxpyLPSolver())
    return registry


def solve_linear_problem(problem: LinearProblem, spec: SolverSpec) -> SolverResult:
    solver = default_solver_registry().get(spec)
    return solver.solve(problem, spec)
