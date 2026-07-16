"""Tests for solver backend abstraction."""

import numpy as np
import pytest

from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.contracts.results import SolveStatus
from decision_intelligence.optimizers import MoneyMarketOptimizer
from decision_intelligence.solvers import LinearProblem, SolverSpec, solve_linear_problem


def test_scipy_lp_solver_solves_linear_problem():
    problem = LinearProblem(
        c=np.array([1.0, 2.0]),
        A_ub=np.array([[-1.0, -1.0]]),
        b_ub=np.array([-1.0]),
        bounds=[(0.0, None), (0.0, None)],
    )

    result = solve_linear_problem(problem, SolverSpec(backend="scipy", problem_type="lp"))

    assert result.status == SolveStatus.OPTIMAL
    assert result.objective_value == 1.0
    assert result.x is not None
    assert result.metadata["solver_backend"] == "scipy"
    assert result.metadata["problem_type"] == "lp"


def test_scipy_milp_solver_solves_linear_problem_relaxation():
    problem = LinearProblem(
        c=np.array([1.0, 2.0]),
        A_ub=np.array([[-1.0, -1.0]]),
        b_ub=np.array([-1.0]),
        bounds=[(0.0, None), (0.0, None)],
    )

    result = solve_linear_problem(problem, SolverSpec(backend="scipy", problem_type="milp"))

    assert result.status == SolveStatus.OPTIMAL
    assert result.objective_value == 1.0
    assert result.metadata["solver_backend"] == "scipy"
    assert result.metadata["problem_type"] == "milp"


def test_cvxpy_lp_solver_solves_linear_problem():
    problem = LinearProblem(
        c=np.array([1.0, 2.0]),
        A_ub=np.array([[-1.0, -1.0]]),
        b_ub=np.array([-1.0]),
        bounds=[(0.0, None), (0.0, None)],
    )

    result = solve_linear_problem(problem, SolverSpec(backend="cvxpy", problem_type="lp"))

    assert result.status == SolveStatus.OPTIMAL
    assert result.objective_value == pytest.approx(1.0)
    assert result.metadata["solver_backend"] == "cvxpy"
    assert result.metadata["problem_type"] == "lp"


def test_money_market_milp_enforces_fund_selection_limits():
    req = OptimizationRequest(
        domain="money_market",
        portfolio_id="TEST_PORT",
        objective=Objective(
            name="maximize_yield",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="yield",
        ),
        context={
            "seed": 42,
            "solver_backend": "scipy",
            "problem_type": "milp",
            "max_funds": 3,
            "min_allocation_fraction": 0.10,
        },
    )

    result = MoneyMarketOptimizer().run(req)

    assert result.status == SolveStatus.OPTIMAL
    assert result.solver_metadata["problem_type"] == "milp"
    assert result.solver_metadata["n_funds_used"] <= 3
    assert all(a.allocated_fraction >= 0.10 for a in result.allocations)
    assert all(a.metadata["selected"] for a in result.allocations)


def test_optimizer_reports_unsupported_solver_pair():
    req = OptimizationRequest(
        domain="money_market",
        portfolio_id="TEST_PORT",
        objective=Objective(
            name="maximize_yield",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="yield",
        ),
        context={
            "seed": 42,
            "solver_backend": "scipy",
            "problem_type": "qp",
        },
    )

    result = MoneyMarketOptimizer().run(req)

    assert result.status == SolveStatus.ERROR
    assert "Unsupported solver" in result.explanation
