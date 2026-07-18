"""Tests for the browser-facing FastAPI wrapper."""

import base64
import importlib

from fastapi.testclient import TestClient

from decision_intelligence.api.app import app
from decision_intelligence.ingestion import PolicyIngestionResult

api_app = importlib.import_module("decision_intelligence.api.app")

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


def test_llm_chat_endpoint_uses_configured_provider(monkeypatch):
    class FakeProvider:
        name = "openai"
        model = "local-test"

        def generate(self, prompt, *, system=None, max_tokens=1024):
            assert prompt == "Explain this run."
            assert system == "Use plain English."
            assert max_tokens == 80
            return "This is a local model response."

    def fake_resolve_provider(name=None, *, model=None, base_url=None, api_key=None):
        assert name == "openai"
        assert model == "local-test"
        assert base_url == "http://localhost:11434/v1"
        assert api_key is None
        return FakeProvider()

    monkeypatch.setattr(api_app, "resolve_provider", fake_resolve_provider)

    response = client.post(
        "/api/llm/chat",
        json={
            "message": "Explain this run.",
            "system": "Use plain English.",
            "provider": "openai",
            "model": "local-test",
            "base_url": "http://localhost:11434/v1",
            "max_tokens": 80,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "provider": "openai",
        "model": "local-test",
        "base_url": "http://localhost:11434/v1",
        "response": "This is a local model response.",
    }


def test_policy_ingestion_endpoint_returns_workflow_patch():
    response = client.post(
        "/api/policy/ingest",
        json={
            "workflow_id": "portfolio_rebalance_mvo",
            "text": (
                "Portfolio PORT_MVO_900 has portfolio notional $250 million. "
                "Target annual return should be 5%. Risk aversion lambda is 3."
            ),
            "filename": "ips.txt",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == "portfolio_rebalance_mvo"
    assert body["input_values"]["portfolio_id"] == "PORT_MVO_900"
    assert body["context_patch"]["asset_allocation"]["target_return"] == 0.05
    assert body["context_patch"]["policy_ingestion"]["filename"] == "ips.txt"
    assert body["review_summary"]["ready"] is True


def test_policy_ingestion_endpoint_accepts_llm_configuration(monkeypatch):
    captured = {}

    def fake_ingest_policy_document(**kwargs):
        captured.update(kwargs)
        return PolicyIngestionResult(
            workflow_id=kwargs["workflow_id"],
            source_type="text",
            input_values={"portfolio_id": "PORT_MVO_900"},
            context_patch={"policy_ingestion": {"backend": kwargs["backend"]}},
            extracted_fields=[],
            review_summary={"ready": True, "backend": kwargs["backend"]},
        )

    monkeypatch.setattr(api_app, "ingest_policy_document", fake_ingest_policy_document)

    response = client.post(
        "/api/policy/ingest",
        json={
            "workflow_id": "portfolio_rebalance_mvo",
            "text": "Portfolio PORT_MVO_900.",
            "backend": "llm",
            "provider": "openai",
            "model": "llama3.1:8b",
            "base_url": "http://localhost:11434/v1",
            "api_key": "not-needed",
        },
    )

    assert response.status_code == 200
    assert captured["backend"] == "llm"
    assert captured["llm_provider"] == "openai"
    assert captured["model"] == "llama3.1:8b"
    assert captured["base_url"] == "http://localhost:11434/v1"
    assert captured["api_key"] == "not-needed"
    assert response.json()["review_summary"]["backend"] == "llm"


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
            "options": [],
        },
        {
            "key": "collateral.obligation_scale",
            "label": "Obligation scale",
            "type": "fraction",
            "default": 1.65,
            "required": True,
            "options": [],
        },
        {
            "key": "money_market.total_cash",
            "label": "Money-market cash",
            "type": "currency",
            "default": 450_000_000,
            "required": True,
            "options": [],
        },
        {
            "key": "execution_mode",
            "label": "Execution mode",
            "type": "select",
            "default": "recommendation",
            "required": True,
            "options": ["recommendation", "stage", "execute", "change_constraints"],
        },
        {
            "key": "governance.materiality_notional",
            "label": "Materiality notional",
            "type": "currency",
            "default": 450_000_000,
            "required": True,
            "options": [],
        },
        {
            "key": "governance.estimated_pnl_impact",
            "label": "Estimated PnL impact",
            "type": "currency",
            "default": 0,
            "required": True,
            "options": [],
        },
        {
            "key": "governance.production_constraint_change",
            "label": "Production constraint change",
            "type": "boolean",
            "default": False,
            "required": True,
            "options": [],
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
        "execution_mode",
        "governance.materiality_notional",
        "governance.estimated_pnl_impact",
        "governance.production_constraint_change",
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
        "governed_recommendation_baseline",
        "institutional_csv_liquidity_base",
        "institutional_csv_liquidity_stress",
        "large_notional_approval_review",
        "production_constraint_change_review",
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
    large = next(
        item for item in body["presets"] if item["preset_id"] == "large_notional_approval_review"
    )
    assert large["context"]["governance"]["materiality_notional"] == 1_500_000_000
    tier5 = next(item for item in body["presets"] if item["preset_id"] == (
        "production_constraint_change_review"
    ))
    assert tier5["context"]["governance"]["production_constraint_change"] is True
    csv_preset = next(
        item for item in body["presets"] if item["preset_id"] == (
            "institutional_csv_liquidity_base"
        )
    )
    assert csv_preset["context"]["money_market"]["daily_liquidity_req"] == 0.25
    assert csv_preset["context"]["financing"]["data_source"]["type"] == "csv"
    csv_preset = next(
        item for item in body["presets"] if item["preset_id"] == (
            "institutional_csv_liquidity_stress"
        )
    )
    assert csv_preset["context"]["money_market"]["problem_type"] == "milp"
    assert csv_preset["context"]["money_market"]["data_source"]["type"] == "csv"


def test_demo_data_packet_catalog_endpoint_lists_csv_packet():
    response = client.get("/api/demo-data-packets")

    assert response.status_code == 200
    body = response.json()
    assert [item["packet_id"] for item in body["packets"]] == [
        "institutional_liquidity_base",
        "institutional_liquidity_stress"
    ]
    packet = next(
        item for item in body["packets"] if item["packet_id"] == "institutional_liquidity_stress"
    )
    assert packet["source_type"] == "csv"
    assert packet["preset_id"] == "institutional_csv_liquidity_stress"
    assert packet["domains"] == ["financing", "collateral", "money_market"]
    assert "money_market_funds" in packet["files"]
    base_packet = next(
        item for item in body["packets"] if item["packet_id"] == "institutional_liquidity_base"
    )
    assert base_packet["preset_id"] == "institutional_csv_liquidity_base"


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
    assert body["result"]["visual_summary"]["chart_kind"] == "improvement_bar"
    assert body["result"]["visual_summary"]["total_dependency_effects"] == 4
    assert [point["domain"] for point in body["result"]["visual_summary"]["points"]] == [
        "financing",
        "collateral",
        "money_market",
    ]
    assert body["result"]["explanation_report"]["overall_recommendation"].startswith("Ready")
    assert body["result"]["explanation_report"]["dependency_changes"]
    assert body["result"]["step_results"][-1]["dependency_effects"]
    assert body["result"]["trace"][-1]["event"] == "workflow_completed"


def test_workflow_compare_endpoint_returns_scenario_deltas():
    base = client.post(
        "/api/workflows/run",
        json={
            "workflow": "portfolio_rebalance_mvo",
            "portfolio_id": "PORT_MVO_BASE",
            "seed": 42,
            "context": {"asset_allocation": {"target_return": 0.05}},
        },
    )
    stress = client.post(
        "/api/workflows/run",
        json={
            "workflow": "portfolio_rebalance_mvo",
            "portfolio_id": "PORT_MVO_STRESS",
            "seed": 42,
            "context": {"asset_allocation": {"target_return": 0.055}},
        },
    )
    assert base.status_code == 200
    assert stress.status_code == 200

    response = client.post(
        "/api/workflows/compare",
        json={
            "runs": [base.json()["result"], stress.json()["result"]],
            "labels": ["Base", "Higher return target"],
            "run_ids": ["base", "higher_return"],
        },
    )

    assert response.status_code == 200
    comparison = response.json()["comparison"]
    assert comparison["comparison_ready"] is True
    assert comparison["baseline_run_id"] == "base"
    assert comparison["run_count"] == 2
    assert comparison["runs"][1]["deltas"]["final_improvement_pct"] is not None
    assert comparison["runs"][0]["expected_return"] is not None


def test_workflow_endpoint_runs_institutional_csv_liquidity_stress_preset():
    preset = next(
        item for item in client.get("/api/demo-presets").json()["presets"]
        if item["preset_id"] == "institutional_csv_liquidity_stress"
    )
    response = client.post(
        "/api/workflows/run",
        json={
            "workflow": preset["workflow_id"],
            "portfolio_id": preset["portfolio_id"],
            "seed": preset["seed"],
            "context": preset["context"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["status"] == "complete"
    assert body["result"]["validation_summary"]["passed"] is True
    assert body["result"]["dependency_summary"]["total_effects"] == 4
    final = body["result"]["step_results"][-1]["result"]
    assert final["domain"] == "money_market"
    assert final["solver_metadata"]["solver_backend"] == "scipy"
    assert final["solver_metadata"]["problem_type"] == "milp"
    assert final["solver_metadata"]["n_funds_used"] <= 3


def test_workflow_endpoint_runs_institutional_csv_liquidity_base_preset():
    presets = client.get("/api/demo-presets").json()["presets"]
    base = next(
        item for item in presets if item["preset_id"] == "institutional_csv_liquidity_base"
    )
    stress = next(
        item for item in presets if item["preset_id"] == "institutional_csv_liquidity_stress"
    )

    base_response = client.post(
        "/api/workflows/run",
        json={
            "workflow": base["workflow_id"],
            "portfolio_id": base["portfolio_id"],
            "seed": base["seed"],
            "context": base["context"],
        },
    )
    stress_response = client.post(
        "/api/workflows/run",
        json={
            "workflow": stress["workflow_id"],
            "portfolio_id": stress["portfolio_id"],
            "seed": stress["seed"],
            "context": stress["context"],
        },
    )

    assert base_response.status_code == 200
    assert stress_response.status_code == 200
    base_body = base_response.json()
    stress_body = stress_response.json()
    base_delta = sum(
        effect["delta"]
        for effect in base_body["result"]["dependency_summary"]["context_changes"]
    )
    stress_delta = sum(
        effect["delta"]
        for effect in stress_body["result"]["dependency_summary"]["context_changes"]
    )
    assert base_body["result"]["status"] == "complete"
    assert base_body["result"]["validation_summary"]["passed"] is True
    assert base_delta < stress_delta
    final = base_body["result"]["step_results"][-1]["result"]
    assert final["solver_metadata"]["problem_type"] == "milp"
    assert final["solver_metadata"]["n_funds_used"] <= 4


def test_chat_endpoint_runs_multi_domain_workflow_from_prompt():
    response = client.post(
        "/api/chat/sessions",
        json={"seed": 7, "default_portfolio": "PORT_CHAT_API"},
    )
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"message": "run the full liquidity stress funding workflow"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_plan"]["workflow_id"] == "liquidity_stress_funding_workflow"
    assert body["workflow_result"]["status"] == "complete"
    assert [step["domain"] for step in body["workflow_result"]["step_results"]] == [
        "financing",
        "collateral",
        "money_market",
    ]
    assert body["result"]["domain"] == "money_market"
    assert body["state"]["plan"]["action"] == "multi_domain_workflow"
    assert body["workflow_result"]["agent_trace"][-1]["event"] == (
        "workflow_request_compiled"
    )


def test_workflow_endpoint_surfaces_governance_threshold_escalation():
    api_app._APPROVAL_STORE.clear()
    response = client.post(
        "/api/workflows/run",
        json={
            "workflow": "funding_capacity_shock",
            "portfolio_id": "PORT_GOV",
            "seed": 29,
            "execution_mode": "recommendation",
            "context": {
                "governance": {
                    "materiality_notional": 1_500_000_000,
                    "estimated_pnl_impact": 2_500_000,
                    "production_constraint_change": False,
                },
                "financing": {"total_funding_need": 375_000_000},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    governance = body["result"]["step_results"][0]["result"]["governance"]
    assert governance["status"] == "pending"
    assert governance["base_tier"] == 2
    assert governance["tier"] == 4
    assert governance["escalated"] is True
    assert "notional exposure exceeds $1B" in governance["escalation_reason"]
    assert governance["governance_factors"]["large_notional"] == 1_500_000_000


def test_approval_decision_endpoint_approves_pending_workflow_on_rerun():
    api_app._APPROVAL_STORE.clear()
    payload = {
        "workflow": "funding_capacity_shock",
        "portfolio_id": "PORT_APPROVE",
        "seed": 29,
        "execution_mode": "recommendation",
        "context": {
            "governance": {
                "materiality_notional": 1_500_000_000,
                "estimated_pnl_impact": 2_500_000,
                "production_constraint_change": False,
            },
            "financing": {"total_funding_need": 375_000_000},
        },
    }

    first = client.post("/api/workflows/run", json=payload)
    assert first.status_code == 200
    pending_ids = _pending_approval_ids(first.json())
    assert len(pending_ids) == 2

    pending_response = client.get("/api/approvals/pending")
    assert pending_response.status_code == 200
    assert {item["approval_id"] for item in pending_response.json()["approvals"]} >= set(
        pending_ids
    )

    for approval_id in pending_ids:
        decision_response = client.post(
            "/api/approvals/decisions",
            json={
                "approval_id": approval_id,
                "approver": "jane",
                "reason": "Materiality reviewed.",
                "granted": True,
            },
        )
        assert decision_response.status_code == 200
        assert decision_response.json()["status"] == "approved"

    second = client.post("/api/workflows/run", json=payload)
    assert second.status_code == 200
    governance_records = _governance_records(second.json())
    assert [record["status"] for record in governance_records] == ["approved", "approved"]
    assert all(record["action_performed"] is True for record in governance_records)


def test_approval_decision_endpoint_rejects_pending_workflow_on_rerun():
    api_app._APPROVAL_STORE.clear()
    payload = {
        "workflow": "funding_capacity_shock",
        "portfolio_id": "PORT_REJECT",
        "seed": 31,
        "execution_mode": "recommendation",
        "context": {
            "governance": {
                "materiality_notional": 1_500_000_000,
                "estimated_pnl_impact": 2_500_000,
                "production_constraint_change": False,
            },
            "financing": {"total_funding_need": 375_000_000},
        },
    }

    first = client.post("/api/workflows/run", json=payload)
    assert first.status_code == 200
    pending_ids = _pending_approval_ids(first.json())
    assert len(pending_ids) == 2

    for approval_id in pending_ids:
        decision_response = client.post(
            "/api/approvals/decisions",
            json={
                "approval_id": approval_id,
                "approver": "jane",
                "reason": "Rejecting materiality.",
                "granted": False,
            },
        )
        assert decision_response.status_code == 200
        assert decision_response.json()["status"] == "rejected"

    second = client.post("/api/workflows/run", json=payload)
    assert second.status_code == 200
    governance_records = _governance_records(second.json())
    assert [record["status"] for record in governance_records] == ["rejected", "rejected"]
    assert all(record["action_performed"] is False for record in governance_records)


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
            "comparison": _sample_comparison_payload(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "funding-capacity-shock-demo-package.html"
    assert body["content_type"] == "text/html"
    assert "<!doctype html>" in body["html"]
    assert "Funding Capacity Shock" in body["html"]
    assert "Workflow Timeline" in body["html"]
    assert "Comparison Evidence" in body["html"]
    assert "Base vs Stress" in body["html"]
    assert "Audit Payload" in body["html"]
    assert "PORT_EXPORT" in body["html"]


def test_workflow_export_evidence_endpoint_returns_json_and_pdf():
    run_response = client.post(
        "/api/workflows/run",
        json={
            "workflow": "liquidity_stress_funding_workflow",
            "portfolio_id": "PORT_EVIDENCE",
            "seed": 17,
            "context": {
                "scenario": "institutional_csv_liquidity_stress",
                "solver_backend": "scipy",
                "problem_type": "lp",
                "money_market": {
                    "total_cash": 500_000_000,
                    "daily_liquidity_req": 0.4,
                    "weekly_liquidity_req": 0.7,
                    "max_prime_fraction": 0.35,
                    "max_wam_days": 55,
                    "max_funds": 3,
                    "min_allocation_fraction": 0.1,
                    "problem_type": "milp",
                },
            },
        },
    )
    assert run_response.status_code == 200
    run_body = run_response.json()

    response = client.post(
        "/api/workflows/export-evidence",
        json={
            "response": run_body,
            "payload": {
                "workflow": "liquidity_stress_funding_workflow",
                "portfolio_id": "PORT_EVIDENCE",
                "seed": 17,
                "context": {
                    "governance": {"production_constraint_change": True},
                    "policy_ingestion": {
                        "filename": "sample_ips.pdf",
                        "backend": "deterministic",
                    },
                },
                "policy_ingestion": {
                    "workflow_id": "liquidity_stress_funding_workflow",
                    "source_type": "pdf",
                    "input_values": {
                        "portfolio_id": "PORT_EVIDENCE",
                        "governance.production_constraint_change": "true",
                    },
                    "context_patch": {
                        "governance": {"production_constraint_change": True},
                        "policy_ingestion": {
                            "filename": "sample_ips.pdf",
                            "backend": "deterministic",
                        },
                    },
                    "extracted_fields": [
                        {
                            "key": "governance.production_constraint_change",
                            "label": "Production constraint change",
                            "value": True,
                            "confidence": 0.86,
                            "evidence": "Constraint policy changes require approval.",
                            "applied": True,
                        }
                    ],
                    "review_summary": {
                        "ready": True,
                        "backend": "deterministic",
                        "warnings": [],
                        "missing_required": [],
                    },
                },
            },
            "preset": {
                "preset_id": "institutional_csv_liquidity_stress",
                "name": "Institutional CSV Liquidity Stress",
                "audience": "Treasury stakeholders",
                "talking_points": ["Show CSV provenance."],
                "success_criteria": ["Evidence packet includes solver metadata."],
            },
            "workflow": {
                "workflow_id": "liquidity_stress_funding_workflow",
                "name": "Liquidity Stress Funding Workflow",
            },
            "comparison": _sample_comparison_payload(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["json_filename"] == "liquidity-stress-funding-workflow-evidence.json"
    assert body["pdf_filename"] == "liquidity-stress-funding-workflow-evidence.pdf"
    packet = body["json_payload"]
    assert packet["packet_type"] == "workflow_run_evidence"
    assert packet["overview"]["portfolio_id"] == "PORT_EVIDENCE"
    assert packet["overview"]["dependency_effect_count"] == 4
    assert packet["solver_evidence"][-1]["solver_backend"] == "scipy"
    assert packet["solver_evidence"][-1]["problem_type"] == "milp"
    assert packet["allocation_evidence"][-1]["allocation_count"] == 3
    assert packet["overview"]["source_policy"] == "sample_ips.pdf"
    assert packet["policy_ingestion_evidence"]["summary"]["present"] is True
    assert packet["policy_ingestion_evidence"]["extracted_fields"][0]["key"] == (
        "governance.production_constraint_change"
    )
    assert packet["governance_evidence"]["summary"]["policy_driven_constraint_change"] is True
    assert packet["comparison_evidence"]["summary"]["name"] == "Base vs Stress"
    assert packet["comparison_evidence"]["runs"][1]["label"] == "Stress"
    csv_files = body["csv_files"]
    assert {item["filename"] for item in csv_files} >= {
        "overview.csv",
        "comparison.csv",
        "governance.csv",
    }
    comparison_csv = next(item for item in csv_files if item["filename"] == "comparison.csv")
    assert "Base vs Stress" in comparison_csv["content"]
    xlsx_bytes = base64.b64decode(body["xlsx_base64"])
    assert body["xlsx_filename"] == "liquidity-stress-funding-workflow-evidence.xlsx"
    assert xlsx_bytes.startswith(b"PK")
    pdf_bytes = base64.b64decode(body["pdf_base64"])
    assert pdf_bytes.startswith(b"%PDF")


def test_audit_narrative_endpoint_returns_markdown_sections():
    run_response = client.post(
        "/api/workflows/run",
        json={
            "workflow": "liquidity_stress_funding_workflow",
            "portfolio_id": "PORT_AUDIT",
            "seed": 7,
        },
    )
    assert run_response.status_code == 200

    response = client.post(
        "/api/audit/narrative",
        json={
            "response": run_response.json(),
            "payload": {
                "workflow": "liquidity_stress_funding_workflow",
                "portfolio_id": "PORT_AUDIT",
            },
            "preset": {"preset_id": "audit_demo"},
        },
    )

    assert response.status_code == 200
    narrative = response.json()["narrative"]
    assert "PORT_AUDIT" in narrative["decision_summary"]
    assert "## Constraint Context" in narrative["markdown"]
    assert narrative["json_payload"]["workflow_id"] == "liquidity_stress_funding_workflow"


def test_constraint_negotiation_endpoint_returns_ranked_proposals():
    run_response = client.post(
        "/api/optimizations/run",
        json={
            "domain": "money_market",
            "portfolio_id": "PORT_NEGOTIATE",
            "context": {
                "seed": 42,
                "total_cash": 500_000_000,
                "daily_liquidity_req": 0.30,
                "weekly_liquidity_req": 0.60,
                "max_prime_fraction": 0.40,
                "max_wam_days": 60,
                "solver_backend": "scipy",
                "problem_type": "lp",
            },
        },
    )
    assert run_response.status_code == 200

    response = client.post(
        "/api/constraints/negotiate",
        json={
            "result": run_response.json()["result"],
            "target_improvement": 5.0,
            "target_units": "bps",
        },
    )

    assert response.status_code == 200
    negotiation = response.json()["negotiation"]
    assert negotiation["domain"] == "money_market"
    assert negotiation["proposals"]
    assert negotiation["proposals"][0]["governance_tier"] >= 2
    assert negotiation["recommendation"].startswith("Start with")


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


def _governance_records(body):
    return [
        step["result"]["governance"]
        for step in body["result"]["step_results"]
        if step["result"].get("governance")
    ]


def _pending_approval_ids(body):
    return [
        record["approval_id"]
        for record in _governance_records(body)
        if record["status"] == "pending" and record["approval_id"]
    ]


def _sample_comparison_payload():
    return {
        "name": "Base vs Stress",
        "comparison": {
            "baseline_run_id": "base",
            "best_run_id": "stress",
            "run_count": 2,
            "comparison_ready": True,
            "runs": [
                {
                    "run_id": "base",
                    "label": "Base",
                    "workflow_id": "liquidity_stress_funding_workflow",
                    "status": "complete",
                    "step_count": 3,
                    "final_domain": "money_market",
                    "final_objective_value": 0.05,
                    "final_improvement_pct": 1.0,
                    "average_improvement_pct": 0.5,
                    "total_dependency_effects": 1,
                    "warning_count": 0,
                    "violation_count": 0,
                    "validation_passed": True,
                    "deltas": {},
                },
                {
                    "run_id": "stress",
                    "label": "Stress",
                    "workflow_id": "liquidity_stress_funding_workflow",
                    "status": "complete",
                    "step_count": 3,
                    "final_domain": "money_market",
                    "final_objective_value": 0.06,
                    "final_improvement_pct": 2.0,
                    "average_improvement_pct": 1.0,
                    "total_dependency_effects": 4,
                    "warning_count": 1,
                    "violation_count": 0,
                    "validation_passed": False,
                    "deltas": {"final_improvement_pct": 1.0},
                },
            ],
            "insights": ["Stress has the strongest final-step improvement."],
        },
    }
