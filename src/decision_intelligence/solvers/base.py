"""Solver interface."""

from __future__ import annotations

from typing import Protocol

from .types import LinearProblem, SolverResult, SolverSpec


class OptimizationSolver(Protocol):
    backend: str
    problem_type: str

    def solve(self, problem: LinearProblem, spec: SolverSpec) -> SolverResult:
        """Solve a mathematical optimization problem."""
