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


def test_direct_asset_allocation_endpoint():
    response = client.post(
        "/api/optimizations/run",
        json={
            "domain": "asset_allocation",
            "portfolio_id": "PORT_MVO",
            "objective_metric": "utility",
            "context": {
                "seed": 42,
                "portfolio_notional": 250_000_000,
                "risk_aversion": 3.0,
                "target_return": 0.05,
                "max_single_asset_weight": 0.45,
                "solver_backend": "scipy",
                "problem_type": "qp",
            },
            "scenarios": ["stress"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["domain"] == "asset_allocation"
    assert body["result"]["status"] == "optimal"
    assert len(body["result"]["allocations"]) == 6
    assert body["result"]["solver_metadata"]["solver_method"] == "SLSQP"
    assert body["result"]["solver_metadata"]["expected_return"] >= 0.05
    assert body["request"]["context"]["risk_aversion"] == 3.0


def test_workflow_catalog_endpoint_lists_registered_workflows():
    response = client.get("/api/workflows")

    assert response.status_code == 200
    body = response.json()
    assert [item["workflow_id"] for item in body["workflows"]] == [
        "collateral_liquidity_review",
        "funding_capacity_shock",
        "liquidity_stress_funding_workflow",
        "portfolio_rebalance_mvo",
    ]
    assert body["workflows"][0]["version"] == 1
    assert body["workflows"][0]["inputs"] == [
        {
            "key": "portfolio_id",
            "label": "Portfolio ID",
            "type": "string",
            "default": "PORT_001",
            "required": True,
        },
        {
            "key": "collateral.obligation_scale",
            "label": "Obligation scale",
            "type": "fraction",
            "default": 1.65,
            "required": True,
        },
        {
            "key": "money_market.total_cash",
            "label": "Money-market cash",
            "type": "currency",
            "default": 450_000_000,
            "required": True,
        },
    ]
    assert body["workflows"][2]["domains"] == [
        "financing",
        "collateral",
        "money_market",
    ]
    mvo = body["workflows"][-1]
    assert mvo["domains"] == ["asset_allocation"]
    assert mvo["default_context"]["problem_type"] == "qp"
    assert [item["key"] for item in mvo["inputs"]] == [
        "portfolio_id",
        "seed",
        "asset_allocation.portfolio_notional",
        "asset_allocation.target_return",
        "asset_allocation.risk_aversion",
        "asset_allocation.max_single_asset_weight",
        "asset_allocation.min_cash_weight",
    ]


def test_demo_preset_catalog_endpoint_lists_repeatable_walkthroughs():
    response = client.get("/api/demo-presets")

    assert response.status_code == 200
    body = response.json()
    assert [item["preset_id"] for item in body["presets"]] == [
        "balanced_mvo_rebalance",
        "collateral_pressure_review",
        "executive_liquidity_stress",
        "funding_capacity_crisis",
    ]
    mvo = body["presets"][0]
    assert mvo["workflow_id"] == "portfolio_rebalance_mvo"
    assert mvo["context"]["asset_allocation"]["target_return"] == 0.05
    executive = next(
        item for item in body["presets"] if item["preset_id"] == "executive_liquidity_stress"
    )
    assert executive["workflow_id"] == "liquidity_stress_funding_workflow"
    assert executive["portfolio_id"] == "PORT_EXEC_001"
    assert executive["context"]["financing"]["capacity_scale"] == 0.55
    assert executive["talking_points"]
    assert executive["success_criteria"]


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
    assert body["result"]["explanation_report"]["overall_recommendation"].startswith("Ready")
    assert body["result"]["explanation_report"]["dependency_changes"]
    assert body["result"]["step_results"][-1]["dependency_effects"]
    assert body["result"]["trace"][-1]["event"] == "workflow_completed"


def test_workflow_export_package_endpoint_returns_shareable_html():
    run_response = client.post(
        "/api/workflows/run",
        json={
            "workflow": "funding_capacity_shock",
            "portfolio_id": "PORT_EXPORT",
            "seed": 11,
            "context": {
                "money_market": {
                    "total_cash": 300_000_000,
                    "weekly_liquidity_req": 0.64,
                }
            },
        },
    )
    assert run_response.status_code == 200
    run_body = run_response.json()

    response = client.post(
        "/api/workflows/export-package",
        json={
            "response": run_body,
            "payload": {
                "workflow": "funding_capacity_shock",
                "portfolio_id": "PORT_EXPORT",
                "seed": 11,
                "context": {},
            },
            "preset": {
                "name": "Export Test",
                "audience": "Stakeholders",
                "talking_points": ["Show workflow progress."],
                "success_criteria": ["Package contains audit payload."],
            },
            "workflow": {
                "workflow_id": "funding_capacity_shock",
                "name": "Funding Capacity Shock",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "funding-capacity-shock-demo-package.html"
    assert body["content_type"] == "text/html"
    assert "<!doctype html>" in body["html"]
    assert "Funding Capacity Shock" in body["html"]
    assert "Workflow Timeline" in body["html"]
    assert "Audit Payload" in body["html"]
    assert "PORT_EXPORT" in body["html"]


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
