"""Tests for IPS / policy ingestion into workflow input patches."""

from pathlib import Path

import pytest

from decision_intelligence.ingestion import IngestionError, ingest_policy_document

REPO_ROOT = Path(__file__).resolve().parents[1]


class FakePolicyProvider:
    name = "fake"
    model = "fake-policy-model"
    supports_native_pdf = False

    def __init__(self, fields):
        self.fields = fields

    def extract(self, schema, *, instruction, system=None, pdf_path=None, text=None):
        assert "portfolio_rebalance_mvo" in instruction
        assert "Allowed fields" in instruction
        assert system
        assert text
        return schema(fields=self.fields, notes="fake extraction")

    def generate(self, prompt, *, system=None, max_tokens=1024):
        return "not used"


def test_policy_ingestion_extracts_mvo_workflow_inputs():
    result = ingest_policy_document(
        workflow_id="portfolio_rebalance_mvo",
        text=(
            "Portfolio PORT_MVO_900 has portfolio notional $250 million. "
            "Target annual return should be 5.25%. Risk aversion lambda is 3.5. "
            "Single asset exposure must not exceed 40%. Cash floor at least 3%. "
            "Materiality notional $250 million. This is a production constraint change."
        ),
        filename="sample_ips.pdf",
    )

    assert result.workflow_id == "portfolio_rebalance_mvo"
    assert result.review_summary["ready"] is True
    assert result.input_values["portfolio_id"] == "PORT_MVO_900"
    assert result.input_values["asset_allocation.target_return"] == "0.0525"
    assert result.context_patch["asset_allocation"]["portfolio_notional"] == 250_000_000
    assert result.context_patch["asset_allocation"]["max_single_asset_weight"] == 0.40
    assert result.context_patch["governance"]["production_constraint_change"] is True
    assert result.context_patch["policy_ingestion"]["filename"] == "sample_ips.pdf"
    assert result.extracted_fields[0].evidence


def test_policy_ingestion_extracts_liquidity_workflow_inputs():
    result = ingest_policy_document(
        workflow_id="liquidity_stress_funding_workflow",
        text=(
            "Account PORT_204 has total cash $500 million. Daily liquidity must be "
            "at least 40%. Weekly liquidity minimum 70%. Prime funds may not exceed "
            "35%. WAM must stay below 55 days. Single-fund limit may not exceed 50%."
        ),
    )

    assert result.review_summary["ready"] is True
    assert result.context_patch["money_market"]["total_cash"] == 500_000_000
    assert result.context_patch["money_market"]["daily_liquidity_req"] == 0.40
    assert result.context_patch["money_market"]["weekly_liquidity_req"] == 0.70
    assert result.context_patch["money_market"]["max_wam_days"] == 55


def test_policy_ingestion_reports_missing_required_fields():
    result = ingest_policy_document(
        workflow_id="funding_capacity_shock",
        text="Available capacity is 45%.",
    )

    assert result.review_summary["ready"] is False
    assert "portfolio_id" in result.review_summary["missing_required"]
    assert "financing.total_funding_need" in result.review_summary["missing_required"]


def test_policy_ingestion_rejects_unknown_workflow():
    with pytest.raises(IngestionError):
        ingest_policy_document(workflow_id="unknown", text="Portfolio PORT_1.")


def test_policy_ingestion_llm_backend_validates_supported_fields():
    provider = FakePolicyProvider(
        [
            {
                "key": "portfolio_id",
                "label": "Portfolio ID",
                "value": "PORT-MVO-901",
                "confidence": 0.91,
                "evidence": "Portfolio PORT-MVO-901.",
            },
            {
                "key": "asset_allocation.portfolio_notional",
                "label": "Portfolio notional",
                "value": "$250 million",
                "confidence": 0.89,
                "evidence": "portfolio value is $250 million",
            },
            {
                "key": "asset_allocation.target_return",
                "label": "Target annual return",
                "value": "5.25%",
                "confidence": 0.88,
                "evidence": "target annual return should be 5.25%",
            },
            {
                "key": "asset_allocation.max_single_asset_weight",
                "label": "Single asset max",
                "value": "40%",
                "confidence": 0.87,
                "evidence": "single asset class exposure must not exceed 40%",
            },
            {
                "key": "asset_allocation.min_cash_weight",
                "label": "Cash floor",
                "value": 0.03,
                "confidence": 0.86,
                "evidence": "cash floor must be at least 3%",
            },
            {
                "key": "asset_allocation.unapproved_limit",
                "label": "Unsupported field",
                "value": "10%",
                "confidence": 0.75,
                "evidence": "model invented a field",
            },
            {
                "key": "asset_allocation.risk_aversion",
                "label": "Risk aversion",
                "value": -2,
                "confidence": 0.80,
                "evidence": "invalid negative risk aversion",
            },
        ]
    )

    result = ingest_policy_document(
        workflow_id="portfolio_rebalance_mvo",
        text="Messy IPS text that the fake LLM interprets.",
        backend="llm",
        provider=provider,
        filename="messy_ips.pdf",
    )

    assert result.review_summary["ready"] is True
    assert result.review_summary["backend"] == "llm"
    assert result.review_summary["applied_count"] == 5
    assert result.review_summary["extracted_count"] == 7
    assert result.review_summary["llm_notes"] == "fake extraction"
    assert result.input_values["portfolio_id"] == "PORT_MVO_901"
    assert result.input_values["asset_allocation.target_return"] == "0.0525"
    assert result.context_patch["asset_allocation"]["portfolio_notional"] == 250_000_000
    assert result.context_patch["asset_allocation"]["max_single_asset_weight"] == 0.4
    assert result.context_patch["asset_allocation"]["min_cash_weight"] == 0.03
    assert "asset_allocation.unapproved_limit" not in result.input_values
    assert "asset_allocation.risk_aversion" not in result.input_values
    rejected = [field for field in result.extracted_fields if not field.applied]
    assert [field.key for field in rejected] == [
        "asset_allocation.unapproved_limit",
        "asset_allocation.risk_aversion",
    ]
    assert any(
        "Rejected unsupported or invalid fields" in warning
        for warning in result.review_summary["warnings"]
    )


def test_policy_ingestion_auto_uses_passed_provider():
    provider = FakePolicyProvider(
        [
            {
                "key": "portfolio_id",
                "label": "Portfolio ID",
                "value": "PORT_MVO_777",
                "confidence": 0.91,
                "evidence": "Portfolio PORT_MVO_777.",
            },
            {
                "key": "asset_allocation.portfolio_notional",
                "label": "Portfolio notional",
                "value": 100_000_000,
                "confidence": 0.89,
                "evidence": "portfolio notional is $100 million",
            },
            {
                "key": "asset_allocation.target_return",
                "label": "Target annual return",
                "value": 0.05,
                "confidence": 0.88,
                "evidence": "target annual return should be 5%",
            },
        ]
    )

    result = ingest_policy_document(
        workflow_id="portfolio_rebalance_mvo",
        text="Auto backend should prefer the explicit provider.",
        backend="auto",
        provider=provider,
    )

    assert result.review_summary["backend"] == "llm"
    assert result.review_summary["ready"] is True


def test_bundled_policy_demo_samples_are_ingestable():
    samples = [
        (
            "portfolio_rebalance_mvo",
            "examples/policies/sample_mvo_ips.txt",
            {
                "portfolio_id": "PORT_MVO_900",
                "asset_allocation.target_return": "0.0525",
                "asset_allocation.max_single_asset_weight": "0.4",
                "asset_allocation.min_cash_weight": "0.03",
                "governance.production_constraint_change": "true",
            },
        ),
        (
            "liquidity_stress_funding_workflow",
            "examples/policies/sample_liquidity_ips.txt",
            {
                "portfolio_id": "PORT_204",
                "money_market.total_cash": "500000000",
                "money_market.daily_liquidity_req": "0.4",
                "money_market.weekly_liquidity_req": "0.7",
                "money_market.max_single_fund": "0.5",
            },
        ),
        (
            "collateral_liquidity_review",
            "examples/policies/sample_collateral_policy.txt",
            {
                "portfolio_id": "PORT_COLL_210",
                "collateral.obligation_scale": "1.65",
                "collateral.concentration_limit": "0.48",
                "money_market.total_cash": "420000000",
                "money_market.daily_liquidity_req": "0.35",
                "money_market.max_prime_fraction": "0.3",
                "money_market.max_wam_days": "50",
            },
        ),
    ]

    for workflow_id, relative_path, expected_values in samples:
        path = REPO_ROOT / relative_path
        result = ingest_policy_document(
            workflow_id=workflow_id,
            text=path.read_text(encoding="utf-8"),
            filename=path.name,
        )

        assert result.review_summary["ready"] is True
        assert result.context_patch["policy_ingestion"]["filename"] == path.name
        for key, expected in expected_values.items():
            assert result.input_values[key] == expected
