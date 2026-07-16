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


def test_unknown_chat_session_returns_404():
    response = client.post("/api/chat/sessions/missing/messages", json={"message": "hello"})
    assert response.status_code == 404
