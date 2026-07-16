"""Deterministic explanation engine.

The optimizer-specific ``result.explanation`` string remains the concise
narrative. This module builds a structured report from the result so APIs,
exports, and UI surfaces can render consistent decision sections without
calling an LLM.
"""

from __future__ import annotations

from typing import Any

from decision_intelligence.contracts.results import ExplanationReport, OptimizationResult


def build_explanation_report(result: OptimizationResult) -> ExplanationReport:
    """Build a structured, deterministic explanation report for a result."""
    return ExplanationReport(
        summary=_summary(result),
        what_changed=_what_changed(result),
        rationale=_rationale(result),
        economic_impact=_economic_impact(result),
        binding_constraints=list(result.binding_constraints),
        risks=_risks(result),
        alternatives=_alternatives(result),
        sensitivities=_sensitivity_notes(result),
        scenarios=_scenario_notes(result),
        governance=_governance_note(result),
        source_explanation=result.explanation,
    )


def _summary(result: OptimizationResult) -> str:
    if result.explanation:
        return result.explanation.splitlines()[0]
    return (
        f"{_domain_label(result.domain)} optimization returned {result.status.value} "
        f"with {result.improvement_pct:.2f}% improvement."
    )


def _what_changed(result: OptimizationResult) -> list[str]:
    changes: list[str] = []
    if result.allocations:
        total_value = sum(item.allocated_value for item in result.allocations)
        changes.append(
            f"Allocated {len(result.allocations)} positions totaling {_money(total_value)}."
        )
        for item in result.allocations[:5]:
            changes.append(
                f"{item.label}: {_money(item.allocated_value)} "
                f"({_pct(item.allocated_fraction)})."
            )
    if result.improvement != 0:
        changes.append(
            f"Improved objective by {_signed_number(result.improvement)} "
            f"({result.improvement_pct:.2f}%)."
        )
    return changes or ["No allocation changes were produced."]


def _rationale(result: OptimizationResult) -> list[str]:
    rationale: list[str] = []
    top = result.allocations[:3]
    if top:
        rationale.append(
            "The recommendation prioritizes the highest-contributing feasible "
            "allocations while preserving portfolio constraints."
        )
    if result.binding_constraints:
        rationale.append(
            "Binding constraints shaped the final allocation: "
            + ", ".join(result.binding_constraints)
            + "."
        )
    if result.sensitivities:
        best = max(result.sensitivities, key=lambda item: abs(item.shadow_price))
        rationale.append(
            f"The largest sensitivity driver is {best.parameter} "
            f"with shadow price {best.shadow_price:.4f}."
        )
    if not result.validation.passed:
        rationale.append("Validation findings should be resolved before relying on the result.")
    return rationale or [
        "The result follows the deterministic optimizer objective and constraints."
    ]


def _economic_impact(result: OptimizationResult) -> dict[str, Any]:
    return {
        "objective_value": result.objective_value,
        "baseline_value": result.baseline_value,
        "improvement": result.improvement,
        "improvement_pct": result.improvement_pct,
        "direction": "favorable" if result.improvement >= 0 else "unfavorable",
    }


def _risks(result: OptimizationResult) -> list[str]:
    risks: list[str] = []
    if result.validation.violations:
        risks.extend(
            f"Validation violation: {violation}"
            for violation in result.validation.violations
        )
    if result.validation.warnings:
        risks.extend(f"Validation warning: {warning}" for warning in result.validation.warnings)
    concentrated = [
        item for item in result.allocations if item.allocated_fraction >= 0.45
    ]
    for item in concentrated[:3]:
        risks.append(
            f"Concentration review: {item.label} receives {_pct(item.allocated_fraction)}."
        )
    if result.binding_constraints:
        risks.append("Active binding constraints may limit flexibility if assumptions change.")
    if result.scenario_results:
        weaker = [
            name
            for name, scenario in result.scenario_results.items()
            if scenario.improvement < result.improvement
        ]
        if weaker:
            risks.append(
                "Scenario results are less favorable than base in: "
                + ", ".join(weaker)
                + "."
            )
    return risks or ["No deterministic validation risks were detected."]


def _alternatives(result: OptimizationResult) -> list[str]:
    alternatives: list[str] = []
    if result.sensitivities:
        ranked = sorted(result.sensitivities, key=lambda item: -abs(item.shadow_price))
        for item in ranked[:3]:
            if item.interpretation:
                alternatives.append(item.interpretation)
            else:
                alternatives.append(
                    f"Test relaxing {item.parameter}; shadow price is {item.shadow_price:.4f}."
                )
    if result.binding_constraints:
        alternatives.append(
            "Run a scenario with relaxed binding constraints to quantify the cost of policy limits."
        )
    if not alternatives:
        alternatives.append("Run downside and stress scenarios to compare robustness.")
    return alternatives


def _sensitivity_notes(result: OptimizationResult) -> list[str]:
    return [
        item.interpretation
        or f"{item.parameter}: shadow price {item.shadow_price:.4f}."
        for item in result.sensitivities
    ]


def _scenario_notes(result: OptimizationResult) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for name, scenario in result.scenario_results.items():
        notes.append(
            {
                "name": name,
                "status": scenario.status.value,
                "objective_value": scenario.objective_value,
                "improvement": scenario.improvement,
                "improvement_pct": scenario.improvement_pct,
                "delta_vs_base": scenario.objective_value - result.objective_value,
            }
        )
    return notes


def _governance_note(result: OptimizationResult) -> str | None:
    if result.governance is None:
        return None
    status = getattr(result.governance.status, "value", result.governance.status)
    execution_mode = getattr(
        result.governance.execution_mode,
        "value",
        result.governance.execution_mode,
    )
    return (
        f"Approval status is {status} for execution mode {execution_mode}."
    )


def _domain_label(domain: str) -> str:
    return domain.replace("_", " ").title()


def _money(value: float) -> str:
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _signed_number(value: float) -> str:
    prefix = "+" if value >= 0 else ""
    return f"{prefix}{value:.4f}"
