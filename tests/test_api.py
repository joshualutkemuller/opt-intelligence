"""Tests for the browser-facing FastAPI wrapper."""

from fastapi.testclient import TestClient

from decision_intelligence.api.app import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_session_completes_money_market_workflow():
    response = client.post("/api/chat/sessions", json={"seed": 42})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    messages = [
        "I want to optimize money market cash",
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
        "lp",
        "stress",
    ]

    for message in messages:
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"message": message},
        )
        assert response.status_code == 200
        assert response.json()["result"] is None

    assert response.json()["state"]["plan"]["domain"] == "money_market"

    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"message": "yes"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["status"] == "optimal"
    assert body["request"]["domain"] == "money_market"
    assert body["request"]["context"]["solver_backend"] == "scipy"
    assert body["request"]["context"]["problem_type"] == "lp"
    assert body["trace"][-1]["event"] == "request_compiled"
    assert body["result"]["agent_trace"][-1]["event"] == "request_compiled"


def test_direct_optimization_endpoint():
    response = client.post(
        "/api/optimizations/run",
        json={
            "domain": "money_market",
            "portfolio_id": "PORT_204",
            "context": {
                "seed": 42,
                "total_cash": 500_000_000,
                "daily_liquidity_req": 0.30,
                "weekly_liquidity_req": 0.60,
                "solver_backend": "scipy",
                "problem_type": "lp",
            },
            "scenarios": ["stress"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["status"] == "optimal"
    assert body["result"]["allocations"]
    assert body["request"]["portfolio_id"] == "PORT_204"


def test_workflow_catalog_endpoint_lists_registered_workflows():
    response = client.get("/api/workflows")

    assert response.status_code == 200
    body = response.json()
    assert [item["workflow_id"] for item in body["workflows"]] == [
        "collateral_liquidity_review",
        "funding_capacity_shock",
        "liquidity_stress_funding_workflow"
    ]
    assert body["workflows"][-1]["domains"] == [
        "financing",
        "collateral",
        "money_market",
    ]


def test_workflow_endpoint_runs_liquidity_stress_workflow():
    response = client.post(
        "/api/workflows/run",
        json={
            "workflow": "liquidity_stress_funding_workflow",
            "portfolio_id": "PORT_204",
            "seed": 7,
            "context": {
                "money_market": {
                    "total_cash": 250_000_000,
                    "weekly_liquidity_req": 0.65,
                }
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["workflow_id"] == "liquidity_stress_funding_workflow"
    assert body["result"]["status"] == "complete"
    assert [step["domain"] for step in body["result"]["step_results"]] == [
        "financing",
        "collateral",
        "money_market",
    ]
    assert body["result"]["validation_summary"]["passed"] is True
    assert body["result"]["dependency_summary"]["total_effects"] == 4
    assert body["result"]["step_results"][-1]["dependency_effects"]
    assert body["result"]["trace"][-1]["event"] == "workflow_completed"


def test_unknown_workflow_returns_400():
    response = client.post(
        "/api/workflows/run",
        json={"workflow": "missing_workflow"},
    )

    assert response.status_code == 400
    assert "Unknown workflow" in response.json()["detail"]


def test_unknown_chat_session_returns_404():
    response = client.post("/api/chat/sessions/missing/messages", json={"message": "hello"})
    assert response.status_code == 404
