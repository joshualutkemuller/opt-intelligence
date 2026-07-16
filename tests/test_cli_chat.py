"""Tests for the deterministic chat CLI helpers."""

from decision_intelligence.cli import _detect_domain, _detect_scenarios, _extract_pdf_path


def test_chat_detects_domain_aliases():
    assert _detect_domain("optimize money market under stress") == "money_market"
    assert _detect_domain("show repo funding options") == "financing"
    assert _detect_domain("tell me about collateral") == "collateral"


def test_chat_detects_scenarios():
    assert _detect_scenarios("run financing with credit stress") == ["credit_stress"]
    assert _detect_scenarios("collateral inventory squeeze downside") == [
        "downside",
        "inventory",
    ]
    assert _detect_scenarios("money market stress") == ["stress"]


def test_chat_extracts_pdf_path_or_uses_sample():
    assert _extract_pdf_path("ingest examples/sample_brief.pdf and solve") == (
        "examples/sample_brief.pdf"
    )
    assert _extract_pdf_path("parse the sample brief") == "examples/sample_brief.pdf"
