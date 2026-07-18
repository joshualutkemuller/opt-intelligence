"""Scenario comparison utilities for completed workflow runs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .types import WorkflowResult


class WorkflowScenarioComparisonRun(BaseModel):
    """Comparable metrics for one completed or restored workflow run."""

    run_id: str
    label: str
    workflow_id: str
    status: str
    timestamp: str | None = None
    step_count: int
    final_domain: str | None = None
    final_objective_value: float = 0.0
    final_improvement_pct: float = 0.0
    average_improvement_pct: float = 0.0
    total_dependency_effects: int = 0
    warning_count: int = 0
    violation_count: int = 0
    validation_passed: bool = False
    expected_return: float | None = None
    volatility: float | None = None
    sharpe: float | None = None
    deltas: dict[str, float] = Field(default_factory=dict)


class WorkflowScenarioComparison(BaseModel):
    """Side-by-side comparison across saved or replayed workflow runs."""

    baseline_run_id: str | None = None
    best_run_id: str | None = None
    run_count: int = 0
    comparison_ready: bool = False
    runs: list[WorkflowScenarioComparisonRun] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)


def build_workflow_scenario_comparison(
    runs: list[WorkflowResult | dict[str, Any]],
    *,
    labels: list[str] | None = None,
    run_ids: list[str] | None = None,
) -> WorkflowScenarioComparison:
    """Build a deterministic comparison across completed workflow runs."""

    normalized = [_as_dict(run) for run in runs]
    comparable = [run for run in normalized if run.get("step_results")]
    if not comparable:
        return WorkflowScenarioComparison(insights=["No completed workflow runs to compare."])

    baseline = _comparison_row(
        comparable[0],
        label=_label_for(comparable[0], labels, 0),
        run_id=_run_id_for(comparable[0], run_ids, 0),
    )
    rows = [baseline]
    for index, run in enumerate(comparable[1:], start=1):
        row = _comparison_row(
            run,
            label=_label_for(run, labels, index),
            run_id=_run_id_for(run, run_ids, index),
        )
        row.deltas.update(
            {
                "final_objective_value": (
                    row.final_objective_value - baseline.final_objective_value
                ),
                "final_improvement_pct": (
                    row.final_improvement_pct - baseline.final_improvement_pct
                ),
                "average_improvement_pct": (
                    row.average_improvement_pct - baseline.average_improvement_pct
                ),
                "total_dependency_effects": float(
                    row.total_dependency_effects - baseline.total_dependency_effects
                ),
                "warning_count": float(row.warning_count - baseline.warning_count),
                "violation_count": float(row.violation_count - baseline.violation_count),
            }
        )
        if row.expected_return is not None and baseline.expected_return is not None:
            row.deltas["expected_return"] = row.expected_return - baseline.expected_return
        if row.volatility is not None and baseline.volatility is not None:
            row.deltas["volatility"] = row.volatility - baseline.volatility
        rows.append(row)

    best = max(rows, key=lambda row: row.final_improvement_pct, default=None)
    return WorkflowScenarioComparison(
        baseline_run_id=baseline.run_id,
        best_run_id=best.run_id if best else None,
        run_count=len(rows),
        comparison_ready=len(rows) >= 2,
        runs=rows,
        insights=_comparison_insights(rows, baseline, best),
    )


def _comparison_row(
    run: dict[str, Any],
    *,
    label: str,
    run_id: str,
) -> WorkflowScenarioComparisonRun:
    steps = _list(run.get("step_results"))
    final_step = steps[-1] if steps else {}
    final_result = _dict(final_step.get("result"))
    final_metadata = _dict(final_result.get("solver_metadata"))
    visual = _dict(run.get("visual_summary"))
    validation = _dict(run.get("validation_summary"))
    return WorkflowScenarioComparisonRun(
        run_id=run_id,
        label=label,
        workflow_id=str(run.get("workflow_id") or "workflow"),
        status=str(run.get("status") or "unknown"),
        timestamp=str(run.get("timestamp")) if run.get("timestamp") else None,
        step_count=len(steps),
        final_domain=str(final_step.get("domain")) if final_step.get("domain") else None,
        final_objective_value=_float(final_result.get("objective_value")),
        final_improvement_pct=_float(final_result.get("improvement_pct")),
        average_improvement_pct=_float(visual.get("average_improvement_pct")),
        total_dependency_effects=int(visual.get("total_dependency_effects") or 0),
        warning_count=int(validation.get("warning_count") or visual.get("total_warnings") or 0),
        violation_count=int(
            validation.get("violation_count") or visual.get("total_violations") or 0
        ),
        validation_passed=bool(validation.get("passed")),
        expected_return=_optional_float(final_metadata.get("expected_return")),
        volatility=_optional_float(final_metadata.get("volatility")),
        sharpe=_optional_float(final_metadata.get("sharpe")),
    )


def _comparison_insights(
    rows: list[WorkflowScenarioComparisonRun],
    baseline: WorkflowScenarioComparisonRun,
    best: WorkflowScenarioComparisonRun | None,
) -> list[str]:
    if len(rows) < 2:
        return ["Add or replay a second workflow run to unlock side-by-side comparison."]

    insights = []
    if best and best.run_id != baseline.run_id:
        delta = best.final_improvement_pct - baseline.final_improvement_pct
        insights.append(
            f"{best.label} has the strongest final-step improvement "
            f"({delta:+.2f} percentage points vs baseline)."
        )
    else:
        insights.append(f"{baseline.label} remains the strongest final-step improvement case.")

    riskiest = max(rows, key=lambda row: row.warning_count + row.violation_count)
    if riskiest.warning_count or riskiest.violation_count:
        insights.append(
            f"{riskiest.label} carries the highest review load "
            f"({riskiest.warning_count} warnings, {riskiest.violation_count} violations)."
        )

    dependency_leader = max(rows, key=lambda row: row.total_dependency_effects)
    if dependency_leader.total_dependency_effects:
        insights.append(
            f"{dependency_leader.label} applied the most cross-step dependency effects "
            f"({dependency_leader.total_dependency_effects})."
        )
    return insights


def _label_for(run: dict[str, Any], labels: list[str] | None, index: int) -> str:
    if labels and index < len(labels) and labels[index]:
        return labels[index]
    return str(run.get("name") or f"Scenario {index + 1}")


def _run_id_for(run: dict[str, Any], run_ids: list[str] | None, index: int) -> str:
    if run_ids and index < len(run_ids) and run_ids[index]:
        return run_ids[index]
    return str(run.get("timestamp") or f"run_{index + 1}")


def _as_dict(run: WorkflowResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(run, WorkflowResult):
        return run.model_dump(mode="json")
    return run


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
