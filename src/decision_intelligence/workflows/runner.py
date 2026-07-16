"""Sequential workflow runner for deterministic optimizer chains."""

from __future__ import annotations

from typing import Any

from decision_intelligence.contracts import OptimizationRequest, OptimizationResult
from decision_intelligence.contracts.results import SolveStatus
from decision_intelligence.optimization import OptimizationOrchestrator

from .types import (
    WorkflowPlan,
    WorkflowResult,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepResult,
    WorkflowTraceEvent,
)


class SequentialWorkflowRunner:
    """Run a WorkflowPlan one step at a time through the optimization orchestrator."""

    def __init__(self, orchestrator: OptimizationOrchestrator) -> None:
        self.orchestrator = orchestrator

    def run(self, plan: WorkflowPlan) -> WorkflowResult:
        trace: list[WorkflowTraceEvent] = [
            WorkflowTraceEvent(
                event="workflow_started",
                message=f"Started workflow '{plan.name}'.",
                details={"workflow_id": plan.workflow_id, "steps": len(plan.steps)},
            )
        ]
        completed: dict[str, WorkflowStepResult] = {}
        step_results: list[WorkflowStepResult] = []

        for step in plan.steps:
            missing = [dep for dep in step.depends_on if dep not in completed]
            if missing:
                trace.append(
                    WorkflowTraceEvent(
                        event="step_blocked",
                        message=f"Blocked step '{step.name}' because dependencies are missing.",
                        step_id=step.step_id,
                        domain=step.domain,
                        details={"missing_dependencies": missing},
                    )
                )
                break

            request = self._apply_prior_outputs(step, completed)
            trace.append(
                WorkflowTraceEvent(
                    event="step_started",
                    message=f"Running {step.domain} optimizer.",
                    step_id=step.step_id,
                    domain=step.domain,
                    details={"request_id": request.request_id},
                )
            )

            result = self.orchestrator.run(request)
            step_result = WorkflowStepResult(
                step_id=step.step_id,
                domain=step.domain,
                name=step.name,
                status=result.status.value,
                request=request,
                result=result,
                inputs_from=list(step.depends_on),
                summary=self._summarize_result(result),
            )
            completed[step.step_id] = step_result
            step_results.append(step_result)

            trace.append(
                WorkflowTraceEvent(
                    event="step_completed",
                    message=f"Completed {step.domain} optimizer with status {result.status.value}.",
                    step_id=step.step_id,
                    domain=step.domain,
                    details=step_result.summary,
                )
            )

            if result.status != SolveStatus.OPTIMAL:
                trace.append(
                    WorkflowTraceEvent(
                        event="workflow_stopped",
                        message=f"Stopped workflow after non-optimal step '{step.name}'.",
                        step_id=step.step_id,
                        domain=step.domain,
                    )
                )
                break

        status = self._workflow_status(plan, step_results)
        trace.append(
            WorkflowTraceEvent(
                event="workflow_completed",
                message=f"Workflow finished with status {status}.",
                details={"completed_steps": len(step_results), "planned_steps": len(plan.steps)},
            )
        )

        return WorkflowResult(
            workflow_id=plan.workflow_id,
            name=plan.name,
            status=status,
            step_results=step_results,
            validation_summary=self._aggregate_validation(step_results),
            explanation=self._build_explanation(plan, step_results, status),
            trace=trace,
        )

    def _apply_prior_outputs(
        self,
        step: WorkflowStep,
        completed: dict[str, WorkflowStepResult],
    ) -> OptimizationRequest:
        if not step.depends_on:
            return step.request

        upstream = {
            dep: completed[dep].summary
            for dep in step.depends_on
            if dep in completed
        }
        context = {
            **step.request.context,
            "workflow_inputs": upstream,
        }
        return step.request.model_copy(update={"context": context})

    def _summarize_result(self, result: OptimizationResult) -> dict[str, Any]:
        validation = result.validation_report
        return {
            "status": result.status.value,
            "objective_value": result.objective_value,
            "baseline_value": result.baseline_value,
            "improvement": result.improvement,
            "improvement_pct": result.improvement_pct,
            "allocation_count": len(result.allocations),
            "validation_recommendation": validation.recommendation if validation else None,
            "validation_passed": validation.passed if validation else result.validation.passed,
            "warning_count": (
                len(validation.warnings) if validation else len(result.validation.warnings)
            ),
            "violation_count": (
                len(validation.violations) if validation else len(result.validation.violations)
            ),
        }

    def _workflow_status(
        self,
        plan: WorkflowPlan,
        step_results: list[WorkflowStepResult],
    ) -> WorkflowStatus:
        if not step_results:
            return "error"
        if any(step.status == SolveStatus.ERROR.value for step in step_results):
            return "error"
        if len(step_results) != len(plan.steps):
            return "partial"
        if all(step.status == SolveStatus.OPTIMAL.value for step in step_results):
            return "complete"
        return "partial"

    def _aggregate_validation(
        self,
        step_results: list[WorkflowStepResult],
    ) -> dict[str, Any]:
        warnings: list[str] = []
        violations: list[str] = []
        recommendations: dict[str, str] = {}
        passed = True
        total_checks = 0

        for step in step_results:
            report = step.result.validation_report
            if report is None:
                passed = passed and step.result.validation.passed
                warnings.extend(step.result.validation.warnings)
                violations.extend(step.result.validation.violations)
                total_checks += len(step.result.validation.checks)
                continue

            passed = passed and report.passed
            warnings.extend(f"{step.step_id}: {message}" for message in report.warnings)
            violations.extend(f"{step.step_id}: {message}" for message in report.violations)
            recommendations[step.step_id] = report.recommendation
            total_checks += len(report.checks)

        return {
            "passed": passed,
            "total_steps": len(step_results),
            "total_checks": total_checks,
            "warning_count": len(warnings),
            "violation_count": len(violations),
            "warnings": warnings,
            "violations": violations,
            "recommendations": recommendations,
        }

    def _build_explanation(
        self,
        plan: WorkflowPlan,
        step_results: list[WorkflowStepResult],
        status: WorkflowStatus,
    ) -> str:
        pieces = [f"{plan.name} finished with status {status}."]
        for step in step_results:
            pieces.append(
                f"{step.name}: {step.status}, objective {step.result.objective_value:,.4f}, "
                f"improvement {step.result.improvement_pct:,.2f}%."
            )
        return " ".join(pieces)
