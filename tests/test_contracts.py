"""Tests for shared contracts."""

import pytest

from decision_intelligence.contracts import (
    Constraint,
    ConstraintType,
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
    OptimizationResult,
    Scenario,
    ScenarioType,
)
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.contracts.results import SolveStatus, ValidationResult


def make_objective(**kwargs):
    defaults = dict(
        name="minimize_cost",
        direction=ObjectiveDirection.MINIMIZE,
        metric="funding_cost",
    )
    return Objective(**{**defaults, **kwargs})


def test_objective_defaults():
    obj = make_objective()
    assert obj.weight == 1.0
    assert obj.direction == ObjectiveDirection.MINIMIZE


def test_objective_immutable():
    obj = make_objective()
    with pytest.raises(Exception):
        obj.weight = 2.0  # type: ignore


def test_constraint_construction():
    c = Constraint(
        name="max_equity",
        constraint_type=ConstraintType.CONCENTRATION,
        parameters={"max_fraction": 0.25},
    )
    assert c.is_hard is True
    assert c.parameters["max_fraction"] == 0.25


def test_scenario_construction():
    s = Scenario(
        name="stress",
        scenario_type=ScenarioType.STRESS,
        parameter_overrides={"obligation_scale": 1.5},
    )
    assert s.scenario_type == ScenarioType.STRESS


def test_optimization_request_defaults():
    req = OptimizationRequest(
        domain="collateral",
        portfolio_id="PORT_001",
        objective=make_objective(),
    )
    assert req.execution_mode == ExecutionMode.RECOMMENDATION
    assert req.request_id  # auto-generated
    assert req.timestamp is not None
    assert req.constraints == []
    assert req.scenarios == []


def test_optimization_request_with_constraints():
    req = OptimizationRequest(
        domain="collateral",
        portfolio_id="PORT_001",
        objective=make_objective(),
        constraints=[
            Constraint(
                name="elig",
                constraint_type=ConstraintType.ELIGIBILITY,
            )
        ],
    )
    assert len(req.constraints) == 1


def test_validation_result_defaults():
    vr = ValidationResult(passed=True)
    assert vr.checks == []
    assert vr.violations == []


def test_optimization_result_error():
    result = OptimizationResult(
        request_id="test-123",
        domain="collateral",
        status=SolveStatus.ERROR,
        objective_value=0.0,
        baseline_value=0.0,
        improvement=0.0,
        improvement_pct=0.0,
        validation=ValidationResult(passed=False, violations=["domain mismatch"]),
    )
    assert result.status == SolveStatus.ERROR
    assert not result.validation.passed
