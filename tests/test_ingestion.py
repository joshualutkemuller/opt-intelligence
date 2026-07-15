"""Tests for the PDF ingestion layer (heuristic backend + mapper)."""

import pytest

from decision_intelligence.contracts import ObjectiveDirection, OptimizationRequest
from decision_intelligence.contracts.constraints import ConstraintType
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.ingestion import (
    ExtractedConstraint,
    ExtractedRequest,
    ExtractedScenario,
    IngestionError,
    ingest_pdf,
    to_optimization_request,
)

pytest.importorskip("pypdf")
pytest.importorskip("reportlab")


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory):
    """Build the sample money-market brief PDF once for the module."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
    from make_sample_pdf import build  # type: ignore

    path = tmp_path_factory.mktemp("pdf") / "brief.pdf"
    build(path)
    return path


# --------------------------------------------------------------------------- #
# Mapper (no PDF needed)
# --------------------------------------------------------------------------- #
def test_mapper_produces_valid_request():
    extracted = ExtractedRequest(
        domain="money_market",
        portfolio_id="PORT_9",
        objective_metric="net_yield",
        objective_direction="maximize",
        constraints=[
            ExtractedConstraint(
                name="max_prime_fraction",
                constraint_type="concentration",
                parameters={"limit": 0.4},
            )
        ],
        scenarios=[ExtractedScenario(name="liquidity_stress", scenario_type="stress")],
    )
    req = to_optimization_request(extracted)
    assert isinstance(req, OptimizationRequest)
    assert req.domain == "money_market"
    assert req.portfolio_id == "PORT_9"
    assert req.objective.direction == ObjectiveDirection.MAXIMIZE
    assert req.constraints[0].constraint_type == ConstraintType.CONCENTRATION
    # simulated-data context is injected for the optimizer
    assert "total_cash" in req.context
    assert req.context["ingest_source"] == "pdf"


def test_mapper_defaults_direction_from_domain():
    # No direction given → falls back to the domain's canonical direction.
    req = to_optimization_request(ExtractedRequest(domain="collateral"))
    assert req.objective.direction == ObjectiveDirection.MINIMIZE
    assert req.objective.metric == "funding_cost"


def test_mapper_coerces_unknown_enums_to_safe_defaults():
    extracted = ExtractedRequest(
        domain="financing",
        execution_mode="not_a_mode",
        constraints=[ExtractedConstraint(name="c", constraint_type="nonsense")],
        scenarios=[ExtractedScenario(name="s", scenario_type="nonsense")],
    )
    req = to_optimization_request(extracted)
    assert req.execution_mode == ExecutionMode.RECOMMENDATION
    assert req.constraints[0].constraint_type == ConstraintType.CUSTOM


def test_mapper_infers_domain_from_keywords():
    extracted = ExtractedRequest(
        notes="Desk wants to optimize the repo book funding spread across each counterparty."
    )
    req = to_optimization_request(extracted)
    assert req.domain == "financing"


def test_mapper_raises_when_domain_undeterminable():
    with pytest.raises(IngestionError):
        to_optimization_request(ExtractedRequest(notes="hello world"))


def test_mapper_seed_override():
    req = to_optimization_request(ExtractedRequest(domain="collateral"), seed=7)
    assert req.context["seed"] == 7


# --------------------------------------------------------------------------- #
# Heuristic PDF backend (end-to-end from a generated PDF)
# --------------------------------------------------------------------------- #
def test_ingest_pdf_heuristic(sample_pdf):
    req, extracted = ingest_pdf(sample_pdf, backend="heuristic")
    assert req.domain == "money_market"
    assert req.portfolio_id == "PORT_204"
    assert req.objective.direction == ObjectiveDirection.MAXIMIZE
    names = {c.name for c in req.constraints}
    assert {"max_prime_fraction", "daily_liquidity_req", "single_fund_limit"} <= names
    # prime limit parsed as a fraction
    prime = next(c for c in req.constraints if c.name == "max_prime_fraction")
    assert prime.parameters["limit"] == pytest.approx(0.40)
    assert any(s.name == "liquidity_stress" for s in req.scenarios)


def test_ingest_pdf_missing_file():
    with pytest.raises(IngestionError):
        ingest_pdf("does_not_exist.pdf", backend="heuristic")


def test_ingested_request_solves(sample_pdf):
    """The ingested request must flow cleanly through the orchestrator."""
    from decision_intelligence.contracts.results import SolveStatus
    from decision_intelligence.governance.audit import AuditLog
    from decision_intelligence.optimization import (
        OptimizationOrchestrator,
        OptimizerRegistry,
    )
    from decision_intelligence.optimizers import (
        CollateralOptimizer,
        FinancingOptimizer,
        MoneyMarketOptimizer,
    )

    req, _ = ingest_pdf(sample_pdf, backend="heuristic")
    reg = OptimizerRegistry()
    reg.register(CollateralOptimizer())
    reg.register(MoneyMarketOptimizer())
    reg.register(FinancingOptimizer())
    orch = OptimizationOrchestrator(reg, AuditLog())
    result = orch.run(req)
    assert result.status == SolveStatus.OPTIMAL
    assert result.allocations


# --------------------------------------------------------------------------- #
# LLM backend — mock round-trip (no network / API key required)
# --------------------------------------------------------------------------- #
class _FakeParsed:
    """Stands in for anthropic.types.ParsedMessage — only .parsed_output is read."""

    def __init__(self, parsed_output):
        self.parsed_output = parsed_output


class _FakeMessages:
    def __init__(self, sink, parsed_output):
        self._sink = sink
        self._parsed = parsed_output

    def parse(self, **kwargs):
        # Record exactly what extract_with_llm sent to the API.
        self._sink.update(kwargs)
        return _FakeParsed(self._parsed)


class _FakeClient:
    def __init__(self, sink, parsed_output):
        self.messages = _FakeMessages(sink, parsed_output)


def test_llm_backend_roundtrip(monkeypatch, sample_pdf):
    """Exercise the real extract_with_llm body against a stubbed Anthropic client.

    Verifies request construction (native PDF document block, model, schema) and
    that the parsed output flows through the mapper to a valid request — without
    a network call or API key.
    """
    import base64

    import anthropic

    from decision_intelligence.ingestion import pdf_ingest

    # What "Claude" returns from the document.
    returned = ExtractedRequest(
        domain="money_market",
        portfolio_id="PORT_204",
        objective_metric="net_yield",
        objective_direction="maximize",
        constraints=[
            ExtractedConstraint(
                name="max_prime_fraction",
                constraint_type="concentration",
                parameters={"limit": 0.4},
            )
        ],
        scenarios=[ExtractedScenario(name="liquidity_stress", scenario_type="stress")],
    )

    sink: dict = {}
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: _FakeClient(sink, returned))

    extracted = pdf_ingest.extract_with_llm(sample_pdf)
    assert extracted == returned

    # --- assert what was actually sent to the API ---
    assert sink["model"] == "claude-opus-4-8"
    assert sink["output_format"] is ExtractedRequest
    assert "system" in sink and "intake agent" in sink["system"].lower()

    content = sink["messages"][0]["content"]
    doc_block = next(b for b in content if b["type"] == "document")
    assert doc_block["source"]["type"] == "base64"
    assert doc_block["source"]["media_type"] == "application/pdf"
    # the base64 payload is the actual PDF bytes, faithfully encoded
    expected_b64 = base64.standard_b64encode(sample_pdf.read_bytes()).decode("ascii")
    assert doc_block["source"]["data"] == expected_b64
    assert any(b["type"] == "text" for b in content)


def test_ingest_pdf_llm_backend_via_public_api(monkeypatch, sample_pdf):
    """ingest_pdf(backend='llm') maps the LLM extraction to a valid request."""
    import anthropic

    returned = ExtractedRequest(
        domain="financing",
        objective_metric="funding_spread",
        objective_direction="minimize",
    )
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: _FakeClient({}, returned))

    req, extracted = ingest_pdf(sample_pdf, backend="llm")
    assert isinstance(req, OptimizationRequest)
    assert req.domain == "financing"
    assert req.objective.direction == ObjectiveDirection.MINIMIZE
    assert req.context["ingest_source"].startswith("pdf:")


def test_llm_backend_raises_on_empty_parse(monkeypatch, sample_pdf):
    import anthropic

    from decision_intelligence.ingestion import pdf_ingest

    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: _FakeClient({}, None))
    with pytest.raises(IngestionError):
        pdf_ingest.extract_with_llm(sample_pdf)
