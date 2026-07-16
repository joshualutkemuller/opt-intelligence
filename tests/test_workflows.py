"""Tests for deterministic multi-optimizer workflows."""

import pytest

from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)
from decision_intelligence.workflows import (
    LIQUIDITY_STRESS_WORKFLOW_ID,
    SequentialWorkflowRunner,
    build_liquidity_stress_funding_workflow,
)


@pytest.fixture
def orchestrator():
    registry = OptimizerRegistry()
    registry.register(CollateralOptimizer())
    registry.register(MoneyMarketOptimizer())
    registry.register(FinancingOptimizer())
    return OptimizationOrchestrator(registry)


def test_liquidity_stress_workflow_plan_is_ordered():
    plan = build_liquidity_stress_funding_workflow(portfolio_id="PORT_204", seed=7)

    assert plan.workflow_id == LIQUIDITY_STRESS_WORKFLOW_ID
    assert [step.domain for step in plan.steps] == [
        "financing",
        "collateral",
        "money_market",
    ]
    assert plan.steps[1].depends_on == ["financing_001"]
    assert plan.steps[2].depends_on == ["financing_001", "collateral_001"]
    assert [rule.rule_type for rule in plan.steps[2].dependency_rules] == [
        "funding_pressure_liquidity_buffer",
        "collateral_pressure_liquidity_buffer",
    ]
    assert plan.steps[0].request.context["spread_shift"] == 1.5
    assert plan.steps[2].request.context["daily_liquidity_req"] == 0.40


def test_sequential_runner_completes_liquidity_stress_workflow(orchestrator):
    plan = build_liquidity_stress_funding_workflow(
        portfolio_id="PORT_204",
        seed=7,
        context={"money_market": {"total_cash": 250_000_000}},
    )

    result = SequentialWorkflowRunner(orchestrator).run(plan)

    assert result.status == "complete"
    assert [step.domain for step in result.step_results] == [
        "financing",
        "collateral",
        "money_market",
    ]
    assert all(step.status == "optimal" for step in result.step_results)
    assert result.validation_summary["passed"] is True
    assert result.validation_summary["total_steps"] == 3
    assert result.trace[0].event == "workflow_started"
    assert result.trace[-1].event == "workflow_completed"
    assert result.dependency_summary["total_effects"] == 4
    assert "Liquidity Stress Funding Workflow finished" in result.explanation
    money_market_step = result.step_results[-1]
    assert money_market_step.request.context["workflow_inputs"]["financing_001"]
    assert money_market_step.request.context["total_cash"] == 250_000_000
    assert money_market_step.request.context["daily_liquidity_req"] > 0.40
    assert money_market_step.request.context["weekly_liquidity_req"] > 0.70
    assert len(money_market_step.dependency_effects) == 4
    assert {
        effect.source_step_id for effect in money_market_step.dependency_effects
    } == {"financing_001", "collateral_001"}
    assert any(event.event == "dependencies_applied" for event in result.trace)
