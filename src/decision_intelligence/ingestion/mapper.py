"""
Map a best-effort :class:`ExtractedRequest` onto a strict, validated
:class:`OptimizationRequest`.

This is where the loose natural-language extraction is reconciled with what the
optimizers actually accept: the domain is normalized, the objective direction is
defaulted to the domain's canonical direction, unknown constraint/scenario enum
values are coerced to safe defaults, and the simulated-data ``context`` that the
optimizers need is injected.
"""

from __future__ import annotations

from typing import Any

from decision_intelligence.contracts import (
    Constraint,
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
    Scenario,
)
from decision_intelligence.contracts.constraints import ConstraintType
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.contracts.scenarios import ScenarioType

from .schema import ExtractedConstraint, ExtractedRequest, ExtractedScenario

# Canonical per-domain defaults — kept in sync with the CLI's _DOMAIN_INFO.
_DOMAIN_DEFAULTS: dict[str, dict[str, Any]] = {
    "collateral": {
        "objective_metric": "funding_cost",
        "direction": ObjectiveDirection.MINIMIZE,
        "context": {"n_assets": 20, "seed": 42},
    },
    "money_market": {
        "objective_metric": "yield",
        "direction": ObjectiveDirection.MAXIMIZE,
        "context": {"n_funds": 8, "seed": 42, "total_cash": 500_000_000},
    },
    "financing": {
        "objective_metric": "funding_spread",
        "direction": ObjectiveDirection.MINIMIZE,
        "context": {"n_counterparties": 10, "seed": 42, "total_funding_need": 300_000_000},
    },
}

# Keyword hints used to infer a domain when the extraction did not name one.
_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "collateral": ("collateral", "haircut", "pledge", "margin", "eligibility schedule"),
    "money_market": ("money market", "mmf", "yield", "wam", "prime fund", "liquidity"),
    "financing": ("financing", "repo", "funding spread", "counterparty", "tenor"),
}


class IngestionError(ValueError):
    """Raised when an extraction cannot be mapped to a valid request."""


def _infer_domain(extracted: ExtractedRequest) -> str:
    if extracted.domain:
        d = extracted.domain.strip().lower().replace("-", "_").replace(" ", "_")
        if d in _DOMAIN_DEFAULTS:
            return d

    # Fall back to keyword scan over metric + notes + constraint text.
    haystack = " ".join(
        [
            extracted.objective_metric or "",
            extracted.objective_name or "",
            extracted.notes or "",
            *[c.description for c in extracted.constraints],
            *[c.name for c in extracted.constraints],
        ]
    ).lower()

    best_domain, best_hits = None, 0
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in haystack)
        if hits > best_hits:
            best_domain, best_hits = domain, hits

    if best_domain is None:
        raise IngestionError(
            "Could not determine optimization domain from the document. "
            "Expected one of: collateral, money_market, financing."
        )
    return best_domain


def _coerce_enum(value: str | None, enum_cls, default):
    if not value:
        return default
    try:
        return enum_cls(value.strip().lower())
    except ValueError:
        return default


def _map_constraint(ec: ExtractedConstraint) -> Constraint:
    return Constraint(
        name=ec.name,
        constraint_type=_coerce_enum(ec.constraint_type, ConstraintType, ConstraintType.CUSTOM),
        description=ec.description,
        parameters=ec.parameters,
        is_hard=ec.is_hard,
    )


def _map_scenario(es: ExtractedScenario) -> Scenario:
    return Scenario(
        name=es.name,
        scenario_type=_coerce_enum(es.scenario_type, ScenarioType, ScenarioType.STRESS),
        description=es.description,
        parameter_overrides=es.parameter_overrides,
    )


def to_optimization_request(
    extracted: ExtractedRequest,
    *,
    source: str = "pdf",
    seed: int | None = None,
) -> OptimizationRequest:
    """
    Reconcile a loose extraction into a fully-validated OptimizationRequest.

    Parameters
    ----------
    extracted:
        The best-effort parse of the source document.
    source:
        Provenance tag recorded in ``context['ingest_source']``.
    seed:
        Optional override for the simulated-data RNG seed.
    """
    domain = _infer_domain(extracted)
    defaults = _DOMAIN_DEFAULTS[domain]

    metric = extracted.objective_metric or defaults["objective_metric"]
    direction = _coerce_enum(
        extracted.objective_direction, ObjectiveDirection, defaults["direction"]
    )
    objective = Objective(
        name=extracted.objective_name or f"{direction.value}_{metric}",
        direction=direction,
        metric=metric,
    )

    constraints = [_map_constraint(c) for c in extracted.constraints]
    scenarios = [_map_scenario(s) for s in extracted.scenarios]

    exec_mode = _coerce_enum(
        extracted.execution_mode, ExecutionMode, ExecutionMode.RECOMMENDATION
    )

    context = dict(defaults["context"])
    if seed is not None:
        context["seed"] = seed
    context["ingest_source"] = source
    if extracted.notes:
        context["ingest_notes"] = extracted.notes

    return OptimizationRequest(
        domain=domain,
        portfolio_id=extracted.portfolio_id or "PORT_PDF",
        objective=objective,
        constraints=constraints,
        scenarios=scenarios,
        execution_mode=exec_mode,
        requestor=extracted.requestor or "pdf_ingest",
        context=context,
    )
