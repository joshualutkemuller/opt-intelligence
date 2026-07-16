"""Deterministic planning agent."""

from __future__ import annotations

from typing import Any

from decision_intelligence.chat.workflows import WORKFLOWS

from .scenarios import ScenarioAgent
from .types import AgentIntent, ExecutionPlan, PlanStep


class PlanningAgent:
    """Convert intent and collected fields into an executable workflow plan."""

    def __init__(self, scenario_agent: ScenarioAgent | None = None) -> None:
        self.scenario_agent = scenario_agent or ScenarioAgent()

    def build_plan(
        self,
        intent: AgentIntent,
        *,
        collected: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
        collected_fields = dict(collected or {})
        if intent.domain not in WORKFLOWS:
            return ExecutionPlan(
                domain=intent.domain,
                action=intent.action,
                summary="I need the optimization domain before I can build a plan.",
                missing_fields=["domain"],
                steps=[
                    PlanStep(
                        name="interpret_intent",
                        description="Identify the requested optimization domain.",
                        status="blocked",
                    )
                ],
            )

        spec = WORKFLOWS[intent.domain]
        scenario_names = _scenario_names(intent, collected_fields)
        missing_fields = [
            field.key for field in spec.fields if field.key not in collected_fields
        ]
        execution_mode = "scenario_analysis" if scenario_names else "recommendation"
        required_fields = [
            {
                "key": field.key,
                "label": field.display_label,
                "target": field.target,
                "default": field.default,
            }
            for field in spec.fields
        ]
        ready_to_run = not missing_fields
        steps = [
            PlanStep(
                name="interpret_intent",
                description=f"Route request to {spec.title}.",
                status="complete",
            ),
            PlanStep(
                name="collect_inputs",
                description="Collect portfolio, constraints, solver, and scenario inputs.",
                status="complete" if ready_to_run else "pending",
            ),
            PlanStep(
                name="compile_request",
                description="Build a structured OptimizationRequest.",
                status="complete" if ready_to_run else "pending",
            ),
            PlanStep(
                name="run_optimizer",
                description="Run deterministic optimizer, validation, and explanation.",
                status="pending",
            ),
        ]
        return ExecutionPlan(
            domain=spec.domain,
            title=spec.title,
            action=intent.action,
            objective_metric=spec.objective_metric,
            execution_mode=execution_mode,
            summary=_summary(spec.title, missing_fields, scenario_names),
            collected_fields=collected_fields,
            missing_fields=missing_fields,
            required_fields=required_fields,
            scenario_names=scenario_names,
            scenario_suggestions=self.scenario_suggestions(intent),
            solver_options={
                "supported_backends": ["scipy", "cvxpy"],
                "supported_problem_types": ["lp", "milp", "qp", "conic"],
            },
            steps=steps,
            ready_to_run=ready_to_run,
        )

    def scenario_suggestions(self, intent: AgentIntent) -> list[dict[str, Any]]:
        return [
            item.model_dump()
            for item in self.scenario_agent.suggest(
                domain=intent.domain,
                text=intent.raw_text,
                selected=intent.scenarios,
            )
        ]


def _scenario_names(intent: AgentIntent, collected: dict[str, Any]) -> list[str]:
    if "scenario_names" in collected:
        return list(collected["scenario_names"] or [])
    return list(intent.scenarios)


def _summary(title: str, missing_fields: list[str], scenario_names: list[str]) -> str:
    scenario_text = (
        f" with {', '.join(scenario_names)} scenario analysis"
        if scenario_names
        else ""
    )
    if missing_fields:
        return (
            f"Plan {title}{scenario_text}: collect {len(missing_fields)} remaining "
            "inputs, compile a governed request, run validation, then explain the result."
        )
    return (
        f"Plan {title}{scenario_text}: ready to compile the governed request, "
        "run validation, and explain the result."
    )
