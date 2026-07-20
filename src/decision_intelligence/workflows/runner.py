"""Sequential workflow runner for deterministic optimizer chains."""

from __future__ import annotations

from typing import Any, Iterator

from decision_intelligence.contracts import OptimizationRequest, OptimizationResult
from decision_intelligence.contracts.results import SolveStatus
from decision_intelligence.optimization import OptimizationOrchestrator

from .dependencies import CrossStepDependencyEngine
from .explanation import build_workflow_explanation_report
from .types import (
    DependencyEffect,
    WorkflowPlan,
    WorkflowResult,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepResult,
    WorkflowTraceEvent,
    WorkflowVisualPoint,
    WorkflowVisualSummary,
)


class SequentialWorkflowRunner:
    """Run a WorkflowPlan one step at a time through the optimization orchestrator."""

    def __init__(
        self,
        orchestrator: OptimizationOrchestrator,
        dependency_engine: CrossStepDependencyEngine | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.dependency_engine = dependency_engine or CrossStepDependencyEngine()

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

            request, dependency_effects = self._prepare_request(step, completed)
            if dependency_effects:
                trace.append(
                    WorkflowTraceEvent(
                        event="dependencies_applied",
                        message=(
                            f"Applied {len(dependency_effects)} cross-step dependency "
                            f"effect{'s' if len(dependency_effects) != 1 else ''}."
                        ),
                        step_id=step.step_id,
                        domain=step.domain,
                        details={
                            "effects": [
                                effect.model_dump(mode="json")
                                for effect in dependency_effects
                            ]
                        },
                    )
                )
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
                dependency_effects=dependency_effects,
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

        validation_summary = self._aggregate_validation(step_results)
        dependency_summary = self._aggregate_dependencies(step_results)
        visual_summary = self._build_visual_summary(
            step_results,
            dependency_summary=dependency_summary,
        )
        explanation_report = build_workflow_explanation_report(
            plan=plan,
            step_results=step_results,
            status=status,
            validation_summary=validation_summary,
            dependency_summary=dependency_summary,
        )

        return WorkflowResult(
            workflow_id=plan.workflow_id,
            name=plan.name,
            status=status,
            step_results=step_results,
            validation_summary=validation_summary,
            dependency_summary=dependency_summary,
            visual_summary=visual_summary,
            explanation=explanation_report.summary,
            explanation_report=explanation_report,
            trace=trace,
        )

    def run_streaming(self, plan: WorkflowPlan) -> Iterator[dict[str, Any]]:
        """Yield SSE-ready progress dicts for each step, then the final WorkflowResult dict."""
        yield {
            "event": "workflow_started",
            "workflow_id": plan.workflow_id,
            "step_count": len(plan.steps),
        }

        trace: list[WorkflowTraceEvent] = [
            WorkflowTraceEvent(
                event="workflow_started",
                message=f"Started workflow '{plan.name}'.",
                details={"workflow_id": plan.workflow_id, "steps": len(plan.steps)},
            )
        ]
        completed: dict[str, WorkflowStepResult] = {}
        step_results: list[WorkflowStepResult] = []

        for i, step in enumerate(plan.steps):
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

            yield {
                "event": "step_started",
                "step_id": step.step_id,
                "domain": step.domain,
                "name": step.name,
                "step_index": i,
                "step_count": len(plan.steps),
            }

            request, dependency_effects = self._prepare_request(step, completed)
            if dependency_effects:
                trace.append(
                    WorkflowTraceEvent(
                        event="dependencies_applied",
                        message=(
                            f"Applied {len(dependency_effects)} cross-step dependency "
                            f"effect{'s' if len(dependency_effects) != 1 else ''}."
                        ),
                        step_id=step.step_id,
                        domain=step.domain,
                        details={
                            "effects": [
                                effect.model_dump(mode="json")
                                for effect in dependency_effects
                            ]
                        },
                    )
                )
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
                dependency_effects=dependency_effects,
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

            yield {
                "event": "step_completed",
                "step_id": step.step_id,
                "domain": step.domain,
                "status": result.status.value,
                "objective_value": result.objective_value,
                "improvement_pct": result.improvement_pct,
            }

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

        validation_summary = self._aggregate_validation(step_results)
        dependency_summary = self._aggregate_dependencies(step_results)
        visual_summary = self._build_visual_summary(
            step_results,
            dependency_summary=dependency_summary,
        )
        explanation_report = build_workflow_explanation_report(
            plan=plan,
            step_results=step_results,
            status=status,
            validation_summary=validation_summary,
            dependency_summary=dependency_summary,
        )

        workflow_result = WorkflowResult(
            workflow_id=plan.workflow_id,
            name=plan.name,
            status=status,
            step_results=step_results,
            validation_summary=validation_summary,
            dependency_summary=dependency_summary,
            visual_summary=visual_summary,
            explanation=explanation_report.summary,
            explanation_report=explanation_report,
            trace=trace,
        )

        yield {
            "event": "workflow_completed",
            "status": status,
            "result": workflow_result.model_dump(mode="json"),
        }

    def _prepare_request(
        self,
        step: WorkflowStep,
        completed: dict[str, WorkflowStepResult],
    ) -> tuple[OptimizationRequest, list[DependencyEffect]]:
        if not step.depends_on:
            return step.request, []

        upstream = {
            dep: completed[dep].summary
            for dep in step.depends_on
            if dep in completed
        }
        context = {
            **step.request.context,
            "workflow_inputs": upstream,
        }
        request = step.request.model_copy(update={"context": context})
        step_with_inputs = step.model_copy(update={"request": request})
        return self.dependency_engine.apply(step_with_inputs, completed)

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

    def _build_visual_summary(
        self,
        step_results: list[WorkflowStepResult],
        *,
        dependency_summary: dict[str, Any],
    ) -> WorkflowVisualSummary:
        points = [
            WorkflowVisualPoint(
                step_id=step.step_id,
                name=step.name,
                domain=step.domain,
                status=step.status,
                objective_value=step.result.objective_value,
                baseline_value=step.result.baseline_value,
                improvement=step.result.improvement,
                improvement_pct=step.result.improvement_pct,
                allocation_count=len(step.result.allocations),
                warning_count=int(step.summary.get("warning_count") or 0),
                violation_count=int(step.summary.get("violation_count") or 0),
                validation_recommendation=step.summary.get("validation_recommendation"),
                expected_return=self._optional_float(
                    step.result.solver_metadata.get("expected_return")
                ),
                volatility=self._optional_float(step.result.solver_metadata.get("volatility")),
                sharpe=self._optional_float(step.result.solver_metadata.get("sharpe")),
            )
            for step in step_results
        ]
        best = max(points, key=lambda point: point.improvement_pct, default=None)
        has_risk_return_points = any(
            point.expected_return is not None and point.volatility is not None
            for point in points
        )
        average_improvement_pct = (
            sum(point.improvement_pct for point in points) / len(points)
            if points
            else 0.0
        )

        return WorkflowVisualSummary(
            chart_kind="risk_return" if has_risk_return_points else "improvement_bar",
            points=points,
            best_step_id=best.step_id if best else None,
            average_improvement_pct=average_improvement_pct,
            total_dependency_effects=int(dependency_summary.get("total_effects") or 0),
            total_warnings=sum(point.warning_count for point in points),
            total_violations=sum(point.violation_count for point in points),
            has_risk_return_points=has_risk_return_points,
        )

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _aggregate_dependencies(
        self,
        step_results: list[WorkflowStepResult],
    ) -> dict[str, Any]:
        effects = [
            effect
            for step in step_results
            for effect in step.dependency_effects
        ]
        return {
            "total_effects": len(effects),
            "target_steps": sorted({effect.target_step_id for effect in effects}),
            "source_steps": sorted({effect.source_step_id for effect in effects}),
            "context_changes": [
                {
                    "source_step_id": effect.source_step_id,
                    "target_step_id": effect.target_step_id,
                    "target_context_key": effect.target_context_key,
                    "previous_value": effect.previous_value,
                    "new_value": effect.new_value,
                    "delta": effect.delta,
                    "reason": effect.reason,
                }
                for effect in effects
            ],
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
