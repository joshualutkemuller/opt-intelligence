"""Constraint negotiation / inversion agent."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from decision_intelligence.contracts.results import OptimizationResult


class ConstraintRelaxationProposal(BaseModel):
    parameter: str
    proposed_change: str
    estimated_impact: float = 0.0
    estimated_impact_units: str = "objective"
    governance_tier: int
    governance_reason: str
    rationale: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.75)


class ConstraintNegotiationResult(BaseModel):
    domain: str
    target_improvement: float = 0.0
    target_units: str = "bps"
    proposals: list[ConstraintRelaxationProposal] = Field(default_factory=list)
    recommendation: str
    blockers: list[str] = Field(default_factory=list)


def negotiate_constraints(
    result: OptimizationResult | dict[str, Any],
    *,
    target_improvement: float = 0.0,
    target_units: str = "bps",
    max_proposals: int = 5,
) -> ConstraintNegotiationResult:
    """Return ranked constraint-relaxation proposals for an optimization result."""

    record = _as_dict(result)
    domain = str(record.get("domain") or "workflow")
    sensitivities = _list(record.get("sensitivities"))
    binding_constraints = [str(item) for item in _list(record.get("binding_constraints"))]
    proposals = [
        _proposal_from_sensitivity(domain, item)
        for item in sensitivities
        if isinstance(item, dict)
    ]
    proposed_parameters = {proposal.parameter for proposal in proposals}
    proposals.extend(
        _proposal_from_binding(domain, constraint)
        for constraint in binding_constraints
        if _canonical_parameter(constraint) not in proposed_parameters
    )
    ranked = sorted(
        proposals,
        key=lambda proposal: (
            -proposal.estimated_impact,
            proposal.governance_tier,
            proposal.parameter,
        ),
    )[:max_proposals]
    blockers = _blockers(ranked, target_improvement, target_units)
    return ConstraintNegotiationResult(
        domain=domain,
        target_improvement=target_improvement,
        target_units=target_units,
        proposals=ranked,
        recommendation=_recommendation(ranked, target_improvement, target_units),
        blockers=blockers,
    )


def _proposal_from_sensitivity(
    domain: str,
    sensitivity: dict[str, Any],
) -> ConstraintRelaxationProposal:
    parameter = str(sensitivity.get("parameter") or "constraint")
    rule = _rule_for(parameter, domain)
    estimated_impact = _estimated_impact(parameter, sensitivity)
    return ConstraintRelaxationProposal(
        parameter=parameter,
        proposed_change=rule["change"],
        estimated_impact=estimated_impact,
        estimated_impact_units=rule["units"],
        governance_tier=int(rule["tier"]),
        governance_reason=str(rule["governance"]),
        rationale=str(sensitivity.get("interpretation") or rule["rationale"]),
        source="sensitivity",
        confidence=0.86 if estimated_impact else 0.72,
    )


def _proposal_from_binding(domain: str, constraint: str) -> ConstraintRelaxationProposal:
    parameter = _canonical_parameter(constraint)
    rule = _rule_for(parameter, domain)
    return ConstraintRelaxationProposal(
        parameter=parameter,
        proposed_change=rule["change"],
        estimated_impact=0.0,
        estimated_impact_units=rule["units"],
        governance_tier=int(rule["tier"]),
        governance_reason=str(rule["governance"]),
        rationale=(
            f"{constraint} is binding; run a relaxed scenario to quantify the exact "
            "economic tradeoff."
        ),
        source="binding_constraint",
        confidence=0.68,
    )


def _rule_for(parameter: str, domain: str) -> dict[str, Any]:
    if parameter.startswith("capacity:"):
        return _rule(
            "Increase approved counterparty capacity by 25%.",
            4,
            "Counterparty capacity changes require senior funding approval.",
            "cost_savings",
            "Capacity is scarce in the financing optimization.",
        )
    if parameter.startswith("required_value:"):
        return _rule(
            "Reduce or substitute the covered obligation requirement by 10%.",
            4,
            "Collateral coverage changes require risk approval.",
            "cost_savings",
            "Collateral requirement is expensive to satisfy.",
        )
    rules: dict[str, dict[str, Any]] = {
        "daily_liquidity_req": _rule(
            "Reduce the daily liquidity floor by 5 percentage points.",
            5,
            "Liquidity-policy relaxation changes a production constraint.",
            "bps",
            "Daily liquidity is constraining higher-yielding allocations.",
        ),
        "weekly_liquidity_req": _rule(
            "Reduce the weekly liquidity floor by 5 percentage points.",
            5,
            "Liquidity-policy relaxation changes a production constraint.",
            "bps",
            "Weekly liquidity is constraining higher-yielding allocations.",
        ),
        "max_prime_fraction": _rule(
            "Increase the prime fund concentration cap by 10 percentage points.",
            5,
            "Prime exposure cap changes a production concentration limit.",
            "bps",
            "Prime concentration limits restrict higher-yielding funds.",
        ),
        "prime_concentration": _rule(
            "Increase the prime fund concentration cap by 10 percentage points.",
            5,
            "Prime exposure cap changes a production concentration limit.",
            "bps",
            "Prime concentration is binding.",
        ),
        "wam_limit": _rule(
            "Increase the WAM cap by 5 days.",
            5,
            "Maturity-limit relaxation changes a production risk constraint.",
            "bps",
            "WAM is limiting access to longer-duration yield.",
        ),
        "single_fund_limit": _rule(
            "Increase the single-fund cap by 5 percentage points.",
            5,
            "Single-name concentration changes a production concentration limit.",
            "bps",
            "Single-fund caps limit concentration in preferred funds.",
        ),
        "max_single_asset_weight": _rule(
            "Increase the max single-asset weight by 5 percentage points.",
            5,
            "Asset concentration changes a production portfolio constraint.",
            "utility",
            "Concentration limits are shaping the MVO frontier.",
        ),
        "target_return": _rule(
            "Lower the target annual return by 25 basis points.",
            4,
            "Changing target return affects the investment mandate.",
            "utility",
            "Target return can be traded for lower risk.",
        ),
        "risk_aversion": _rule(
            "Run a scenario with risk aversion 25% lower.",
            2,
            "Risk-preference scenarios are recommendation-tier analysis.",
            "utility",
            "Risk aversion changes the return/variance tradeoff.",
        ),
    }
    return rules.get(
        parameter,
        _rule(
            f"Relax or reparameterize {parameter}.",
            4 if domain != "asset_allocation" else 3,
            "Constraint change requires domain-owner review.",
            "objective",
            "The optimizer identified this as a decision driver.",
        ),
    )


def _rule(
    change: str,
    tier: int,
    governance: str,
    units: str,
    rationale: str,
) -> dict[str, Any]:
    return {
        "change": change,
        "tier": tier,
        "governance": governance,
        "units": units,
        "rationale": rationale,
    }


def _estimated_impact(parameter: str, sensitivity: dict[str, Any]) -> float:
    shadow = abs(_float(sensitivity.get("shadow_price")))
    if parameter in {"daily_liquidity_req", "weekly_liquidity_req"}:
        return round(shadow * 0.05, 4)
    if parameter == "max_prime_fraction":
        return round(shadow * 0.10, 4)
    if parameter.startswith("capacity:") or parameter.startswith("required_value:"):
        return round(shadow, 4)
    return round(shadow, 6)


def _canonical_parameter(constraint: str) -> str:
    if constraint.startswith("single_fund_limit:"):
        return "single_fund_limit"
    mapping = {
        "daily_liquidity": "daily_liquidity_req",
        "weekly_liquidity": "weekly_liquidity_req",
        "prime_concentration": "max_prime_fraction",
        "wam_limit": "wam_limit",
        "target_return": "target_return",
        "max_single_asset_weight": "max_single_asset_weight",
    }
    return mapping.get(constraint, constraint)


def _blockers(
    proposals: list[ConstraintRelaxationProposal],
    target_improvement: float,
    target_units: str,
) -> list[str]:
    if not proposals:
        return ["No sensitivities or binding constraints were available to invert."]
    if not target_improvement:
        return []
    total = sum(max(0.0, proposal.estimated_impact) for proposal in proposals)
    if total < target_improvement:
        return [
            f"Top proposals estimate {total:.2f} {target_units}, below the target "
            f"{target_improvement:.2f} {target_units}."
        ]
    return []


def _recommendation(
    proposals: list[ConstraintRelaxationProposal],
    target_improvement: float,
    target_units: str,
) -> str:
    if not proposals:
        return "No constraint negotiation proposal is available for this result."
    top = proposals[0]
    target_text = (
        f" against the {target_improvement:.2f} {target_units} target"
        if target_improvement
        else ""
    )
    return (
        f"Start with {top.parameter}: {top.proposed_change} Estimated impact "
        f"{top.estimated_impact:.2f} {top.estimated_impact_units}{target_text}; "
        f"governance tier {top.governance_tier}."
    )


def _as_dict(result: OptimizationResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, OptimizationResult):
        return result.model_dump(mode="json")
    return result


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
