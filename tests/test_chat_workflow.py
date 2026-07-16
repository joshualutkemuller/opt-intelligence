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
        "scipy",
        "lp",
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
    assert req.context["solver_backend"] == "scipy"
    assert req.context["problem_type"] == "lp"
    assert req.scenarios[0].name == "stress"


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
