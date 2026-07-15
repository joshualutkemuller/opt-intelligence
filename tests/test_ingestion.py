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
