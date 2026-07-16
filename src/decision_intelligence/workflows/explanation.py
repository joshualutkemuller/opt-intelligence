"""Workflow-level explanation engine."""

from __future__ import annotations

from typing import Any

from .types import (
    WorkflowExplanationReport,
    WorkflowPlan,
    WorkflowStatus,
    WorkflowStepResult,
)


def build_workflow_explanation_report(
    *,
    plan: WorkflowPlan,
    step_results: list[WorkflowStepResult],
    status: WorkflowStatus,
    validation_summary: dict[str, Any],
    dependency_summary: dict[str, Any],
) -> WorkflowExplanationReport:
    """Build a deterministic explanation across all workflow steps."""

    completed_steps = len(step_results)
    planned_steps = len(plan.steps)
    dependency_count = int(dependency_summary.get("total_effects", 0))
    validation_passed = bool(validation_summary.get("passed", False))

    summary = (
        f"{plan.name} finished with status {status}; "
        f"{completed_steps} of {planned_steps} steps completed, "
        f"{dependency_count} dependency changes applied, and aggregate validation "
        f"{'passed' if validation_passed else 'requires review'}."
    )

    return WorkflowExplanationReport(
        summary=summary,
        overall_recommendation=_overall_recommendation(status, validation_passed),
        key_drivers=_key_drivers(step_results),
        dependency_changes=_dependency_changes(dependency_summary),
        economic_impact=_economic_impact(step_results, dependency_summary),
        risks=_risks(step_results, validation_summary, dependency_summary),
        next_actions=_next_actions(status, validation_passed, dependency_count),
        step_summaries=_step_summaries(step_results),
    )


def _overall_recommendation(status: WorkflowStatus, validation_passed: bool) -> str:
    if status == "complete" and validation_passed:
        return "Ready for review as a recommendation; no blocking validation issues were detected."
    if status == "partial":
        return (
            "Review required before use; the workflow stopped before every planned "
            "step completed."
        )
    return "Do not use without investigation; the workflow has errors or validation issues."


def _key_drivers(step_results: list[WorkflowStepResult]) -> list[str]:
    drivers: list[str] = []
    for step in step_results:
        if step.result.binding_constraints:
            constraints = ", ".join(step.result.binding_constraints[:3])
            drivers.append(
                f"{step.name} was shaped by binding constraints: {constraints}."
            )
        elif step.result.explanation_report and step.result.explanation_report.rationale:
            drivers.append(step.result.explanation_report.rationale[0])

    if not drivers:
        drivers.append("The workflow completed without prominent binding constraints.")
    return drivers[:6]


def _dependency_changes(dependency_summary: dict[str, Any]) -> list[str]:
    changes = []
    for change in dependency_summary.get("context_changes", []):
        key = str(change.get("target_context_key", "context")).replace("_", " ")
        previous = _format_fraction(change.get("previous_value"))
        new = _format_fraction(change.get("new_value"))
        source = str(change.get("source_step_id", "upstream step")).replace("_", " ")
        changes.append(f"{source} changed {key} from {previous} to {new}.")
    if not changes:
        changes.append("No cross-step dependency changes were applied.")
    return changes


def _economic_impact(
    step_results: list[WorkflowStepResult],
    dependency_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "steps": [
            {
                "step_id": step.step_id,
                "domain": step.domain,
                "objective_value": step.result.objective_value,
                "baseline_value": step.result.baseline_value,
                "improvement": step.result.improvement,
                "improvement_pct": step.result.improvement_pct,
            }
            for step in step_results
        ],
        "favorable_steps": sum(1 for step in step_results if step.result.improvement >= 0),
        "dependency_effect_count": dependency_summary.get("total_effects", 0),
    }


def _risks(
    step_results: list[WorkflowStepResult],
    validation_summary: dict[str, Any],
    dependency_summary: dict[str, Any],
) -> list[str]:
    risks: list[str] = []
    risks.extend(validation_summary.get("violations", []))
    risks.extend(validation_summary.get("warnings", []))

    for step in step_results:
        report = step.result.explanation_report
        if report:
            risks.extend(report.risks[:2])

    if dependency_summary.get("total_effects", 0):
        risks.append(
            "Downstream recommendations depend on deterministic stress-linkage rules; "
            "review rule assumptions before staging."
        )

    if not risks:
        risks.append("No deterministic workflow-level risks were detected.")
    return risks[:8]


def _next_actions(
    status: WorkflowStatus,
    validation_passed: bool,
    dependency_count: int,
) -> list[str]:
    if status != "complete" or not validation_passed:
        return [
            "Review failed or incomplete workflow steps.",
            "Resolve validation issues before presenting the recommendation.",
        ]

    actions = [
        "Review the final money-market allocation and binding constraints.",
        "Compare dependency-adjusted liquidity requirements against policy limits.",
    ]
    if dependency_count:
        actions.append("Validate cross-step dependency assumptions with the desk owner.")
    actions.append("Run a downside or alternate stress workflow before staging any action.")
    return actions


def _step_summaries(step_results: list[WorkflowStepResult]) -> list[dict[str, Any]]:
    return [
        {
            "step_id": step.step_id,
            "domain": step.domain,
            "name": step.name,
            "status": step.status,
            "objective_value": step.result.objective_value,
            "improvement_pct": step.result.improvement_pct,
            "allocation_count": len(step.result.allocations),
            "dependency_effect_count": len(step.dependency_effects),
        }
        for step in step_results
    ]


def _format_fraction(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.2%}"
