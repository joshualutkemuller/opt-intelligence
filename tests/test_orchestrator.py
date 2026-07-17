"""Tests for the deterministic orchestrator."""

import pytest

from decision_intelligence.contracts import (
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
    Scenario,
    ScenarioType,
)
from decision_intelligence.contracts.results import SolveStatus
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    AssetAllocationMVOOptimizer,
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)


@pytest.fixture
def orchestrator():
    reg = OptimizerRegistry()
    reg.register(AssetAllocationMVOOptimizer())
    reg.register(CollateralOptimizer())
    reg.register(MoneyMarketOptimizer())
    reg.register(FinancingOptimizer())
    return OptimizationOrchestrator(reg)


def _req(domain: str, metric: str = "funding_cost", **ctx):
    direction = (
        ObjectiveDirection.MAXIMIZE
        if domain in {"asset_allocation", "money_market"}
        else ObjectiveDirection.MINIMIZE
    )
    metric_map = {
        "asset_allocation": "utility",
        "money_market": "yield",
        "financing": "funding_spread",
    }
    actual_metric = metric_map.get(domain, metric)
    return OptimizationRequest(
        domain=domain,
        portfolio_id="TEST_PORT",
        objective=Objective(
            name="test_obj",
            direction=direction,
            metric=actual_metric,
        ),
        context={"seed": 42, **ctx},
    )


def test_unknown_domain_returns_error(orchestrator):
    req = _req("treasury")
    result = orchestrator.run(req)
    assert result.status == SolveStatus.ERROR
    assert not result.validation.passed


def test_collateral_optimal(orchestrator):
    result = orchestrator.run(_req("collateral"))
    assert result.status == SolveStatus.OPTIMAL
    assert result.objective_value > 0
    assert result.baseline_value > 0
    assert len(result.allocations) > 0
    assert result.validation.passed
    assert result.explanation


def test_money_market_optimal(orchestrator):
    result = orchestrator.run(_req("money_market"))
    assert result.status == SolveStatus.OPTIMAL
    assert result.objective_value > 0
    assert len(result.allocations) > 0
    assert result.validation.passed


def test_asset_allocation_mvo_optimal(orchestrator):
    result = orchestrator.run(
        _req(
            "asset_allocation",
            portfolio_notional=250_000_000,
            risk_aversion=3.0,
            target_return=0.05,
            max_single_asset_weight=0.45,
        )
    )
    assert result.status == SolveStatus.OPTIMAL
    assert result.objective_value > result.baseline_value
    assert len(result.allocations) == 6
    assert abs(sum(item.allocated_fraction for item in result.allocations) - 1.0) < 1e-5
    assert result.validation.passed
    assert result.solver_metadata["solver_method"] == "SLSQP"
    assert result.solver_metadata["expected_return"] >= 0.05


def test_financing_optimal(orchestrator):
    result = orchestrator.run(_req("financing"))
    assert result.status == SolveStatus.OPTIMAL
    assert result.objective_value >= 0
    assert len(result.allocations) > 0
    assert result.validation.passed


def test_collateral_improvement(orchestrator):
    result = orchestrator.run(_req("collateral"))
    # Optimizer should beat naive baseline
    assert result.improvement_pct > 0


def test_sensitivity_populated(orchestrator):
    result = orchestrator.run(_req("collateral"))
    assert len(result.sensitivities) > 0
    for s in result.sensitivities:
        assert s.parameter
        assert s.interpretation


def test_scenario_analysis(orchestrator):
    req = OptimizationRequest(
        domain="collateral",
        portfolio_id="TEST_PORT",
        objective=Objective(
            name="test_obj",
            direction=ObjectiveDirection.MINIMIZE,
            metric="funding_cost",
        ),
        scenarios=[
            Scenario(
                name="stress",
                scenario_type=ScenarioType.STRESS,
                parameter_overrides={"obligation_scale": 1.5},
            ),
            Scenario(
                name="base",
                scenario_type=ScenarioType.BASE,
                parameter_overrides={},
            ),
        ],
        context={"seed": 42},
    )
    result = orchestrator.run(req)
    assert result.status == SolveStatus.OPTIMAL
    assert "stress" in result.scenario_results
    assert "base" in result.scenario_results


def test_audit_log_populated(orchestrator):
    req = _req("collateral")
    orchestrator.run(req)
    history = orchestrator.audit.get_history(req.request_id)
    events = [e.event for e in history]
    assert "request_received" in events
    assert "optimization_complete" in events


def test_all_enabled_domains(orchestrator):
    for domain in ["asset_allocation", "collateral", "money_market", "financing"]:
        result = orchestrator.run(_req(domain))
        assert result.status == SolveStatus.OPTIMAL, f"Domain {domain} failed: {result.explanation}"
