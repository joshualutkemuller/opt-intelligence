"""Deterministic cross-step dependency rules for workflow execution."""

from __future__ import annotations

from typing import Any

from decision_intelligence.contracts import OptimizationRequest

from .types import DependencyEffect, WorkflowDependencyRule, WorkflowStep, WorkflowStepResult


class CrossStepDependencyEngine:
    """Apply declarative upstream-to-downstream context transformations."""

    def apply(
        self,
        step: WorkflowStep,
        completed: dict[str, WorkflowStepResult],
    ) -> tuple[OptimizationRequest, list[DependencyEffect]]:
        context = dict(step.request.context)
        effects: list[DependencyEffect] = []

        for rule in step.dependency_rules:
            source = completed.get(rule.source_step_id)
            if source is None:
                continue

            if rule.rule_type == "funding_pressure_liquidity_buffer":
                effects.extend(self._apply_funding_pressure(rule, step, source, context))
            elif rule.rule_type == "collateral_pressure_liquidity_buffer":
                effects.extend(self._apply_collateral_pressure(rule, step, source, context))

        if not effects:
            return step.request, effects

        context["workflow_dependency_effects"] = [
            effect.model_dump(mode="json") for effect in effects
        ]
        return step.request.model_copy(update={"context": context}), effects

    def _apply_funding_pressure(
        self,
        rule: WorkflowDependencyRule,
        step: WorkflowStep,
        source: WorkflowStepResult,
        context: dict[str, Any],
    ) -> list[DependencyEffect]:
        capacity_bindings = sum(
            1 for item in source.result.binding_constraints if item.startswith("capacity:")
        )
        cost_ratio = _safe_ratio(source.result.objective_value, source.result.baseline_value)
        pressure = min(1.0, (capacity_bindings / 4 * 0.65) + (cost_ratio * 0.35))
        deltas = {
            "daily_liquidity_req": round(0.0100 + pressure * 0.0200, 4),
            "weekly_liquidity_req": round(0.0050 + pressure * 0.0150, 4),
        }
        details = {
            "capacity_bindings": capacity_bindings,
            "funding_cost_ratio": round(cost_ratio, 4),
            "pressure_score": round(pressure, 4),
        }
        reason = (
            "Funding pressure increased the required liquidity reserve because "
            f"{capacity_bindings} counterparty capacity constraints were binding."
        )
        return self._apply_liquidity_deltas(rule, step, context, deltas, reason, details)

    def _apply_collateral_pressure(
        self,
        rule: WorkflowDependencyRule,
        step: WorkflowStep,
        source: WorkflowStepResult,
        context: dict[str, Any],
    ) -> list[DependencyEffect]:
        pressure_bindings = sum(
            1
            for item in source.result.binding_constraints
            if item.startswith("coverage:") or item.startswith("inventory:")
        )
        cost_ratio = _safe_ratio(source.result.objective_value, source.result.baseline_value)
        pressure = min(1.0, (pressure_bindings / 5 * 0.75) + (cost_ratio * 0.25))
        deltas = {
            "daily_liquidity_req": round(0.0050 + pressure * 0.0150, 4),
            "weekly_liquidity_req": round(0.0050 + pressure * 0.0200, 4),
        }
        details = {
            "collateral_pressure_bindings": pressure_bindings,
            "collateral_cost_ratio": round(cost_ratio, 4),
            "pressure_score": round(pressure, 4),
        }
        reason = (
            "Collateral pressure increased the liquidity reserve because "
            f"{pressure_bindings} inventory or coverage constraints were binding."
        )
        return self._apply_liquidity_deltas(rule, step, context, deltas, reason, details)

    def _apply_liquidity_deltas(
        self,
        rule: WorkflowDependencyRule,
        step: WorkflowStep,
        context: dict[str, Any],
        deltas: dict[str, float],
        reason: str,
        details: dict[str, Any],
    ) -> list[DependencyEffect]:
        effects: list[DependencyEffect] = []

        for key in rule.target_context_keys:
            if key not in deltas:
                continue
            previous = float(context.get(key, 0.0))
            new_value = min(0.95, round(previous + deltas[key], 4))
            delta = round(new_value - previous, 4)
            if delta <= 0:
                continue

            context[key] = new_value
            effects.append(
                DependencyEffect(
                    rule_type=rule.rule_type,
                    source_step_id=rule.source_step_id,
                    target_step_id=step.step_id,
                    target_context_key=key,
                    previous_value=previous,
                    new_value=new_value,
                    delta=delta,
                    reason=reason,
                    details=details,
                )
            )

        return effects


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return max(0.0, numerator / abs(denominator))
