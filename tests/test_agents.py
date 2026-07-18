"""Tests for the deterministic agent layer."""

from decision_intelligence.agents import IntentAgent, PlanningAgent, ScenarioAgent
from decision_intelligence.chat import ChatSession


def test_intent_agent_detects_domain_action_and_scenarios():
    intent = IntentAgent().analyze("optimize money market under credit stress")

    assert intent.domain == "money_market"
    assert intent.action == "scenario_analysis"
    assert intent.scenarios == ["credit_stress"]
    assert intent.confidence >= 0.8
    assert "domain:money_market" in intent.signals


def test_intent_agent_detects_multi_domain_workflow():
    intent = IntentAgent().analyze("run the full liquidity stress funding workflow")

    assert intent.action == "multi_domain_workflow"
    assert intent.workflow_id == "liquidity_stress_funding_workflow"
    assert intent.missing_inputs == []
    assert "workflow:liquidity_stress_funding_workflow" in intent.signals


def test_planning_agent_builds_missing_field_plan():
    intent = IntentAgent().analyze("optimize money market cash under stress")
    plan = PlanningAgent().build_plan(
        intent,
        collected={"portfolio_id": "PORT_001", "scenario_names": ["stress"]},
    )

    assert plan.domain == "money_market"
    assert plan.execution_mode == "scenario_analysis"
    assert plan.ready_to_run is False
    assert "total_cash" in plan.missing_fields
    assert plan.scenario_suggestions[0]["selected"] is True


def test_planning_agent_marks_complete_plan_ready():
    intent = IntentAgent().analyze("optimize money market cash")
    collected = {
        "portfolio_id": "PORT_001",
        "total_cash": 500_000_000,
        "daily_liquidity_req": 0.3,
        "weekly_liquidity_req": 0.6,
        "max_prime_fraction": 0.4,
        "max_wam_days": 60,
        "max_single_fund": 0.5,
        "max_funds": 4,
        "min_allocation_fraction": 0.05,
        "solver_backend": "scipy",
        "problem_type": "lp",
        "scenario_names": [],
    }

    plan = PlanningAgent().build_plan(intent, collected=collected)

    assert plan.ready_to_run is True
    assert plan.missing_fields == []
    assert plan.steps[1].status == "complete"


def test_scenario_agent_suggests_domain_relevant_scenarios():
    suggestions = ScenarioAgent().suggest(
        domain="financing",
        text="run downside funding case",
    )

    selected = [item.name for item in suggestions if item.selected]
    assert selected == ["downside"]
    assert {item.name for item in suggestions} == {"stress", "downside"}


def test_chat_snapshot_includes_intent_and_plan():
    session = ChatSession(seed=42, default_portfolio="PORT_001")
    response = session.reply("optimize money market under stress")

    snapshot = session.snapshot()

    assert "Plan Money Market Optimization" in response.message
    assert snapshot["intent"]["domain"] == "money_market"
    assert snapshot["plan"]["domain"] == "money_market"
    assert snapshot["plan"]["scenario_names"] == ["stress"]
    assert "portfolio_id" in snapshot["plan"]["missing_fields"]
    assert snapshot["trace"][0]["event"] == "intent_detected"


def test_plan_driven_chat_skips_prefilled_scenario_and_completes():
    session = ChatSession(seed=42, default_portfolio="PORT_001")
    response = session.reply("optimize money market under stress")
    assert "portfolio ID" in response.message

    answers = [
        "PORT_001",
        "$500 million",
        "30%",
        "60%",
        "40%",
        "60",
        "50%",
        "4",
        "5%",
        "scipy",
        "lp",
    ]
    for answer in answers:
        response = session.reply(answer)

    assert "Confirm" in response.message
    snapshot = session.snapshot()
    assert snapshot["plan"]["ready_to_run"] is True
    assert snapshot["plan"]["missing_fields"] == []
    assert snapshot["plan"]["scenario_names"] == ["stress"]

    response = session.reply("yes")
    assert response.request is not None
    assert response.request.scenarios[0].name == "stress"
    final_snapshot = session.snapshot()
    assert final_snapshot["trace"][-1]["event"] == "request_compiled"
