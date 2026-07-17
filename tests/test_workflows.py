"""Tests for deterministic multi-optimizer workflows."""

import pytest

from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)
from decision_intelligence.workflows import (
    COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID,
    DEFAULT_WORKFLOW_REGISTRY,
    FUNDING_CAPACITY_SHOCK_WORKFLOW_ID,
    LIQUIDITY_STRESS_WORKFLOW_ID,
    SequentialWorkflowRunner,
    WorkflowRegistry,
    WorkflowTemplate,
    build_liquidity_stress_funding_workflow,
    load_workflow_config,
    load_workflow_configs,
)

WORKFLOW_CONFIG_DIR = "config/workflows"


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


def test_default_workflow_registry_lists_and_builds_liquidity_workflow():
    catalog = DEFAULT_WORKFLOW_REGISTRY.list_catalog()

    assert [item["workflow_id"] for item in catalog] == [
        COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID,
        FUNDING_CAPACITY_SHOCK_WORKFLOW_ID,
        LIQUIDITY_STRESS_WORKFLOW_ID,
    ]
    assert catalog[-1]["domains"] == ["financing", "collateral", "money_market"]
    assert catalog[-1]["default_context"]["scenario"] == "stress"
    assert "liquidity" in catalog[-1]["tags"]

    plan = DEFAULT_WORKFLOW_REGISTRY.build(
        LIQUIDITY_STRESS_WORKFLOW_ID,
        portfolio_id="PORT_204",
        seed=7,
    )
    assert plan.workflow_id == LIQUIDITY_STRESS_WORKFLOW_ID
    assert plan.context["portfolio_id"] == "PORT_204"
    assert plan.context["scenario"] == "stress"


def test_default_workflow_registry_builds_all_templates():
    expected_domains = {
        COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID: ["collateral", "money_market"],
        FUNDING_CAPACITY_SHOCK_WORKFLOW_ID: ["financing", "money_market"],
        LIQUIDITY_STRESS_WORKFLOW_ID: ["financing", "collateral", "money_market"],
    }

    for workflow_id, domains in expected_domains.items():
        plan = DEFAULT_WORKFLOW_REGISTRY.build(workflow_id, portfolio_id="PORT_204", seed=7)
        assert plan.workflow_id == workflow_id
        assert [step.domain for step in plan.steps] == domains


def test_loads_workflow_template_configs():
    configs = load_workflow_configs(WORKFLOW_CONFIG_DIR)

    assert [config.workflow_id for config in configs] == [
        COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID,
        FUNDING_CAPACITY_SHOCK_WORKFLOW_ID,
        LIQUIDITY_STRESS_WORKFLOW_ID,
    ]
    liquidity = next(
        config for config in configs if config.workflow_id == LIQUIDITY_STRESS_WORKFLOW_ID
    )
    assert liquidity.version == 1
    assert liquidity.default_context["scenario"] == "stress"
    assert [step.domain for step in liquidity.steps] == [
        "financing",
        "collateral",
        "money_market",
    ]
    assert liquidity.steps[-1].dependency_rules[0].rule_type == (
        "funding_pressure_liquidity_buffer"
    )


def test_load_workflow_config_rejects_invalid_dependency(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
workflow_id: bad
version: 1
name: Bad Workflow
description: Invalid dependency demo
domains: [money_market]
steps:
  - step_id: money_market_001
    domain: money_market
    name: Money Market
    objective_metric: yield
    objective_direction: maximize
    depends_on: [missing_step]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown step ids"):
        load_workflow_config(path)


def test_workflow_registry_rejects_duplicate_ids():
    registry = WorkflowRegistry()
    template = WorkflowTemplate(
        workflow_id="demo",
        name="Demo",
        description="Demo workflow",
        domains=("money_market",),
        builder=build_liquidity_stress_funding_workflow,
    )

    registry.register(template)

    with pytest.raises(ValueError):
        registry.register(template)


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
    assert result.explanation_report is not None
    assert result.explanation_report.summary == result.explanation
    assert result.explanation_report.overall_recommendation.startswith("Ready")
    assert result.explanation_report.dependency_changes
    assert result.explanation_report.economic_impact["dependency_effect_count"] == 4
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


def test_workflow_explanation_report_for_all_registered_workflows(orchestrator):
    for workflow_id in DEFAULT_WORKFLOW_REGISTRY.list_ids():
        plan = DEFAULT_WORKFLOW_REGISTRY.build(workflow_id, portfolio_id="PORT_204", seed=7)
        result = SequentialWorkflowRunner(orchestrator).run(plan)

        report = result.explanation_report
        assert report is not None
        assert plan.name in report.summary
        assert report.overall_recommendation
        assert report.key_drivers
        assert report.dependency_changes
        assert report.economic_impact["steps"]
        assert report.next_actions
        assert len(report.step_summaries) == len(result.step_results)


@pytest.mark.parametrize(
    ("workflow_id", "expected_effects"),
    [
        (COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID, 2),
        (FUNDING_CAPACITY_SHOCK_WORKFLOW_ID, 2),
    ],
)
def test_sequential_runner_completes_additional_workflows(
    orchestrator,
    workflow_id,
    expected_effects,
):
    plan = DEFAULT_WORKFLOW_REGISTRY.build(workflow_id, portfolio_id="PORT_204", seed=7)

    result = SequentialWorkflowRunner(orchestrator).run(plan)

    assert result.status == "complete"
    assert all(step.status == "optimal" for step in result.step_results)
    assert result.dependency_summary["total_effects"] == expected_effects
    money_market_step = result.step_results[-1]
    assert money_market_step.domain == "money_market"
    assert len(money_market_step.dependency_effects) == expected_effects
