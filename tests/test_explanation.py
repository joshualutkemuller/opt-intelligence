"""Tests for structured optimization explanation reports."""

from decision_intelligence.contracts import (
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
    Scenario,
    ScenarioType,
)
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.governance import (
    ApprovalPolicy,
    ApprovalStore,
    AuditLog,
    GovernanceController,
)
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import CollateralOptimizer, MoneyMarketOptimizer


def _registry() -> OptimizerRegistry:
    registry = OptimizerRegistry()
    registry.register(CollateralOptimizer())
    registry.register(MoneyMarketOptimizer())
    return registry


def test_structured_explanation_report_is_attached():
    orchestrator = OptimizationOrchestrator(_registry())
    request = OptimizationRequest(
        domain="money_market",
        portfolio_id="PORT_001",
        objective=Objective(
            name="max_yield",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="yield",
        ),
        context={"seed": 42},
    )

    result = orchestrator.run(request)

    report = result.explanation_report
    assert report is not None
    assert report.summary
    assert report.source_explanation == result.explanation
    assert report.what_changed
    assert report.rationale
    assert report.economic_impact["objective_value"] == result.objective_value
    assert report.binding_constraints == result.binding_constraints
    assert report.risks
    assert report.alternatives


def test_structured_explanation_includes_scenarios_and_governance():
    audit = AuditLog()
    governance = GovernanceController(ApprovalPolicy(), ApprovalStore(), audit)
    orchestrator = OptimizationOrchestrator(_registry(), audit, governance)
    request = OptimizationRequest(
        domain="collateral",
        portfolio_id="PORT_001",
        objective=Objective(
            name="min_cost",
            direction=ObjectiveDirection.MINIMIZE,
            metric="funding_cost",
        ),
        scenarios=[
            Scenario(
                name="stress",
                scenario_type=ScenarioType.STRESS,
                parameter_overrides={"obligation_scale": 1.5},
            )
        ],
        execution_mode=ExecutionMode.SCENARIO_ANALYSIS,
        context={"seed": 42},
    )

    result = orchestrator.run(request)

    report = result.explanation_report
    assert report is not None
    assert report.governance is not None
    assert "not_required" in report.governance
    assert report.scenarios
    assert report.scenarios[0]["name"] == "stress"
    assert "delta_vs_base" in report.scenarios[0]
