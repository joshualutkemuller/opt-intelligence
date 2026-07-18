"""Tests for guided chat workflow state collection."""

from decision_intelligence.chat import ChatSession
from decision_intelligence.contracts.requests import ExecutionMode


def test_guided_money_market_workflow_builds_request():
    session = ChatSession(seed=7, default_portfolio="PORT_DEFAULT")

    response = session.reply("I want to optimize money market cash")
    assert "portfolio ID" in response.message
    assert response.request is None

    answers = [
        "PORT_204",
        "$500 million",
        "30%",
        "60%",
        "40%",
        "60",
        "50%",
        "4",
        "5%",
        "scipy",
        "milp",
        "stress",
    ]
    for answer in answers:
        response = session.reply(answer)

    assert "Confirm" in response.message
    response = session.reply("yes")

    req = response.request
    assert req is not None
    assert req.domain == "money_market"
    assert req.portfolio_id == "PORT_204"
    assert req.execution_mode == ExecutionMode.SCENARIO_ANALYSIS
    assert req.context["seed"] == 7
    assert req.context["total_cash"] == 500_000_000
    assert req.context["daily_liquidity_req"] == 0.30
    assert req.context["weekly_liquidity_req"] == 0.60
    assert req.context["max_prime_fraction"] == 0.40
    assert req.context["max_wam_days"] == 60
    assert req.context["max_single_fund"] == 0.50
    assert req.context["max_funds"] == 4
    assert req.context["min_allocation_fraction"] == 0.05
    assert req.context["solver_backend"] == "scipy"
    assert req.context["problem_type"] == "milp"
    assert req.scenarios[0].name == "stress"


def test_guided_asset_allocation_mvo_workflow_builds_request():
    session = ChatSession(seed=7, default_portfolio="PORT_DEFAULT")

    response = session.reply("optimize asset allocation with MVO")
    assert "portfolio ID" in response.message

    answers = [
        "PORT_MVO",
        "$250 million",
        "5%",
        "3",
        "45%",
        "2%",
        "scipy",
        "qp",
        "stress",
    ]
    for answer in answers:
        response = session.reply(answer)

    assert "Confirm" in response.message
    assert "portfolio notional: $250M" in response.message
    assert "risk aversion: 3" in response.message
    assert "risk aversion: 3%" not in response.message
    response = session.reply("yes")

    req = response.request
    assert req is not None
    assert req.domain == "asset_allocation"
    assert req.portfolio_id == "PORT_MVO"
    assert req.execution_mode == ExecutionMode.SCENARIO_ANALYSIS
    assert req.context["portfolio_notional"] == 250_000_000
    assert req.context["target_return"] == 0.05
    assert req.context["risk_aversion"] == 3.0
    assert req.context["max_single_asset_weight"] == 0.45
    assert req.context["min_cash_weight"] == 0.02
    assert req.context["solver_backend"] == "scipy"
    assert req.context["problem_type"] == "qp"
    assert req.scenarios[0].parameter_overrides["volatility_scale"] == 1.35


def test_guided_workflow_can_use_defaults_and_cancel():
    session = ChatSession(seed=42, default_portfolio="PORT_001")

    response = session.reply("guide a collateral optimization")
    assert "portfolio ID" in response.message

    response = session.reply("default")
    assert "collateral assets" in response.message

    response = session.reply("20")
    assert "concentration" in response.message

    response = session.reply("60%")
    assert "optimization engine" in response.message

    response = session.reply("scipy")
    assert "problem type" in response.message

    response = session.reply("lp")
    assert "Scenario" in response.message

    response = session.reply("none")
    assert "Confirm" in response.message

    response = session.reply("no")
    assert response.request is None
    assert "Cancelled" in response.message
    assert not session.active


def test_chat_can_build_multi_domain_workflow_plan_directly():
    session = ChatSession(seed=7, default_portfolio="PORT_CHAT")

    response = session.reply("run the full liquidity stress funding workflow")

    assert response.request is None
    assert response.workflow_plan is not None
    assert response.workflow_plan.workflow_id == "liquidity_stress_funding_workflow"
    assert response.workflow_plan.context["portfolio_id"] == "PORT_CHAT"
    assert [step.domain for step in response.workflow_plan.steps] == [
        "financing",
        "collateral",
        "money_market",
    ]


def test_chat_can_collect_registered_workflow_inputs_field_by_field():
    session = ChatSession(seed=7, default_portfolio="PORT_CHAT")

    response = session.reply("guide me through the MVO rebalance workflow")
    assert response.workflow_plan is None
    assert "Portfolio ID" in response.message

    answers = [
        "PORT_MVO_CHAT",
        "11",
        "$250 million",
        "5%",
        "3",
        "45%",
        "2%",
        "change constraints",
        "$1.5 billion",
        "$6 million",
        "yes",
    ]
    for answer in answers:
        response = session.reply(answer)

    assert "Confirm" in response.message
    response = session.reply("yes")

    plan = response.workflow_plan
    assert plan is not None
    assert plan.workflow_id == "portfolio_rebalance_mvo"
    assert plan.context["portfolio_id"] == "PORT_MVO_CHAT"
    assert plan.context["seed"] == 11
    request = plan.steps[0].request
    assert request.execution_mode == ExecutionMode.CHANGE_CONSTRAINTS
    assert request.context["target_return"] == 0.05
    assert request.context["governance"]["materiality_notional"] == 1_500_000_000
    assert request.context["governance"]["production_constraint_change"] is True
    snapshot = session.snapshot()
    assert snapshot["plan"]["action"] == "multi_domain_workflow"
    assert snapshot["plan"]["ready_to_run"] is True
    assert snapshot["trace"][-1]["event"] == "workflow_request_compiled"
