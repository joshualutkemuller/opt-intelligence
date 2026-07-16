"""Deterministic cross-domain validation engine."""

from __future__ import annotations

from decision_intelligence.contracts.results import (
    OptimizationResult,
    SolveStatus,
    ValidationCheck,
    ValidationReport,
)


def apply_validation_report(result: OptimizationResult) -> OptimizationResult:
    """Attach a structured validation report and mirror it into ValidationResult."""
    report = build_validation_report(result)
    validation = result.validation.model_copy(
        update={
            "passed": report.passed,
            "checks": [check.model_dump() for check in report.checks],
            "violations": _dedupe([*result.validation.violations, *report.violations]),
            "warnings": _dedupe([*result.validation.warnings, *report.warnings]),
        }
    )
    return result.model_copy(
        update={"validation": validation, "validation_report": report}
    )


def build_validation_report(result: OptimizationResult) -> ValidationReport:
    """Build deterministic validation checks that apply across optimizer domains."""
    checks = [
        _solver_status_check(result),
        _optimizer_validation_check(result),
        _allocation_presence_check(result),
        _allocation_value_check(result),
        _allocation_fraction_check(result),
        _objective_quality_check(result),
        _scenario_check(result),
        _governance_check(result),
        _explanation_check(result),
    ]
    violations = [check.message for check in checks if check.status == "fail"]
    warnings = [check.message for check in checks if check.status == "warning"]
    risk_score = _risk_score(checks)
    return ValidationReport(
        passed=not violations,
        recommendation=_recommendation(violations, warnings),
        risk_score=risk_score,
        checks=checks,
        violations=violations,
        warnings=warnings,
        data_quality={
            "allocation_count": len(result.allocations),
            "has_sensitivities": bool(result.sensitivities),
            "has_scenarios": bool(result.scenario_results),
            "has_explanation": bool(result.explanation),
        },
        policy_status=_policy_status(result),
    )


def _solver_status_check(result: OptimizationResult) -> ValidationCheck:
    if result.status == SolveStatus.OPTIMAL:
        return _check("solver_status", "pass", "info", "Solver returned an optimal result.")
    return _check(
        "solver_status",
        "fail",
        "error",
        f"Solver status is {result.status.value}.",
    )


def _optimizer_validation_check(result: OptimizationResult) -> ValidationCheck:
    if result.validation.violations:
        return _check(
            "optimizer_validation",
            "fail",
            "error",
            "Optimizer validation reported violations.",
            {"violations": result.validation.violations},
        )
    if result.validation.warnings:
        return _check(
            "optimizer_validation",
            "warning",
            "warning",
            "Optimizer validation reported warnings.",
            {"warnings": result.validation.warnings},
        )
    return _check("optimizer_validation", "pass", "info", "Optimizer validation passed.")


def _allocation_presence_check(result: OptimizationResult) -> ValidationCheck:
    if result.status == SolveStatus.OPTIMAL and not result.allocations:
        return _check(
            "allocation_presence",
            "fail",
            "error",
            "Optimal result did not include allocations.",
        )
    return _check(
        "allocation_presence",
        "pass",
        "info",
        f"Result includes {len(result.allocations)} allocation rows.",
    )


def _allocation_value_check(result: OptimizationResult) -> ValidationCheck:
    negative = [
        item.label
        for item in result.allocations
        if item.allocated_value < -1e-6 or item.allocated_fraction < -1e-6
    ]
    if negative:
        return _check(
            "allocation_values",
            "fail",
            "error",
            "Allocations contain negative values.",
            {"allocations": negative},
        )
    return _check("allocation_values", "pass", "info", "Allocation values are non-negative.")


def _allocation_fraction_check(result: OptimizationResult) -> ValidationCheck:
    if not result.allocations:
        return _check(
            "allocation_fractions",
            "pass",
            "info",
            "No allocation fractions to validate.",
        )
    out_of_bounds = [
        item.label
        for item in result.allocations
        if item.allocated_fraction < -1e-6 or item.allocated_fraction > 1 + 1e-6
    ]
    if out_of_bounds:
        return _check(
            "allocation_fractions",
            "fail",
            "error",
            "Allocation fractions must stay between 0% and 100%.",
            {"allocations": out_of_bounds},
        )
    total_fraction = sum(item.allocated_fraction for item in result.allocations)
    if result.domain == "money_market" and abs(total_fraction - 1.0) > 1e-4:
        return _check(
            "allocation_fractions",
            "fail",
            "error",
            "Money market allocation fractions must sum to 100%.",
            {"total_fraction": total_fraction},
        )
    return _check(
        "allocation_fractions",
        "pass",
        "info",
        "Allocation fractions are within expected bounds.",
        {"total_fraction": total_fraction},
    )


def _objective_quality_check(result: OptimizationResult) -> ValidationCheck:
    if result.status != SolveStatus.OPTIMAL:
        return _check(
            "objective_quality",
            "fail",
            "error",
            "Objective quality cannot be assessed without an optimal solution.",
        )
    if result.improvement < -1e-9:
        return _check(
            "objective_quality",
            "warning",
            "warning",
            "Optimization result is worse than the baseline.",
            {"improvement": result.improvement, "improvement_pct": result.improvement_pct},
        )
    return _check(
        "objective_quality",
        "pass",
        "info",
        "Optimization result is at least as good as the baseline.",
        {"improvement": result.improvement, "improvement_pct": result.improvement_pct},
    )


def _scenario_check(result: OptimizationResult) -> ValidationCheck:
    if not result.scenario_results:
        return _check("scenario_results", "pass", "info", "No scenario results requested.")
    failed = [
        name
        for name, scenario in result.scenario_results.items()
        if scenario.status != SolveStatus.OPTIMAL
    ]
    if failed:
        return _check(
            "scenario_results",
            "fail",
            "error",
            "One or more scenario optimizations failed.",
            {"scenarios": failed},
        )
    weaker = [
        name
        for name, scenario in result.scenario_results.items()
        if scenario.improvement < result.improvement
    ]
    if weaker:
        return _check(
            "scenario_results",
            "warning",
            "warning",
            "Some scenarios are less favorable than the base result.",
            {"scenarios": weaker},
        )
    return _check("scenario_results", "pass", "info", "Scenario results are optimal.")


def _governance_check(result: OptimizationResult) -> ValidationCheck:
    if result.governance is None:
        return _check("governance", "pass", "info", "No governance gate was configured.")
    status = getattr(result.governance.status, "value", result.governance.status)
    if status == "rejected":
        return _check(
            "governance",
            "fail",
            "error",
            "Governance rejected the requested action.",
            {"status": status},
        )
    if status == "pending":
        return _check(
            "governance",
            "warning",
            "warning",
            "Governance approval is pending; action is withheld.",
            {"status": status},
        )
    return _check(
        "governance",
        "pass",
        "info",
        f"Governance status is {status}.",
        {"status": status},
    )


def _explanation_check(result: OptimizationResult) -> ValidationCheck:
    if result.explanation:
        return _check("explanation", "pass", "info", "Optimizer produced an explanation.")
    return _check(
        "explanation",
        "warning",
        "warning",
        "Optimizer did not produce a narrative explanation.",
    )


def _check(
    name: str,
    status: str,
    severity: str,
    message: str,
    details: dict | None = None,
) -> ValidationCheck:
    return ValidationCheck(
        name=name,
        status=status,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        message=message,
        details=details or {},
    )


def _risk_score(checks: list[ValidationCheck]) -> float:
    score = 0.0
    for check in checks:
        if check.status == "fail":
            score += 1.0
        elif check.status == "warning":
            score += 0.35
    return round(min(score, 5.0), 2)


def _recommendation(violations: list[str], warnings: list[str]) -> str:
    if violations:
        return "blocked"
    if warnings:
        return "review"
    return "ready"


def _policy_status(result: OptimizationResult) -> str | None:
    if result.governance is None:
        return None
    return str(getattr(result.governance.status, "value", result.governance.status))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped
