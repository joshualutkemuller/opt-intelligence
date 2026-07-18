"""Tests for IPS / policy ingestion into workflow input patches."""

import pytest

from decision_intelligence.ingestion import IngestionError, ingest_policy_document


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
