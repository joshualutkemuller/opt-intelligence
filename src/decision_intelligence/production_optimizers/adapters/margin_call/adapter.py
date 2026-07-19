"""Production adapter scaffold for margin-call workflow optimization."""

from __future__ import annotations

from typing import Any

from decision_intelligence.contracts import OptimizationRequest

from ...adapter import ProductionOptimizerAdapter
from ...contracts import (
    NormalizedOptimizerResult,
    PreflightReport,
    ProductionOptimizerEvidence,
)
from .._utils import data_snapshot_id, reproducibility_fingerprint, to_jsonable
from .config import margin_call_workflow_optimizer_config


class MarginCallWorkflowProductionAdapter(ProductionOptimizerAdapter):
    """Production-facing adapter for margin-call operations prioritization."""

    optimizer_id = "production.margin_call.workflow"
    domain = "margin_operations"
    model_config = margin_call_workflow_optimizer_config()

    def __init__(self) -> None:
        self._last_preflight: PreflightReport | None = None

    def validate_inputs(self, request: OptimizationRequest) -> PreflightReport:
        queue = _margin_call_queue(request.context)
        capacity = float(request.context.get("team_capacity_minutes", 420))
        blocking_issues: list[str] = []
        warnings: list[str] = []

        if request.domain != self.domain:
            blocking_issues.append(f"Expected domain '{self.domain}', got '{request.domain}'.")
        if not queue:
            blocking_issues.append("At least one margin call is required.")
        if capacity <= 0:
            blocking_issues.append("Team capacity must be positive.")

        for call in queue:
            call_id = call.get("call_id")
            if float(call.get("amount", 0.0)) < 0:
                blocking_issues.append(f"Call {call_id} has negative amount.")
            if float(call.get("ops_minutes", 0.0)) <= 0:
                blocking_issues.append(f"Call {call_id} must have positive ops minutes.")
            dispute_probability = float(call.get("dispute_probability", 0.0))
            if not 0 <= dispute_probability <= 1:
                blocking_issues.append(f"Call {call_id} dispute probability must be 0 to 1.")
            if float(call.get("due_in_hours", 0.0)) < 0:
                warnings.append(f"Call {call_id} is already past due.")

        snapshot_id = data_snapshot_id(self.domain, request.portfolio_id, request.context)
        fingerprint = reproducibility_fingerprint(
            model_config=self.model_config,
            request_payload=request.model_dump(mode="json"),
            snapshot_id=snapshot_id,
        )
        report = PreflightReport(
            passed=not blocking_issues,
            data_snapshot_id=snapshot_id,
            reproducibility_fingerprint=fingerprint,
            warnings=warnings,
            blocking_issues=blocking_issues,
            checked_datasets={
                "margin_call_queue": len(queue),
                "ops_capacity": 1,
            },
            checked_limits={
                "team_capacity_minutes": capacity,
                "materiality_threshold": request.context.get("materiality_threshold", 25_000_000),
                "dispute_stress_multiplier": request.context.get(
                    "dispute_stress_multiplier",
                    1.0,
                ),
            },
        )
        self._last_preflight = report
        return report

    def build_problem(self, request: OptimizationRequest) -> dict[str, Any]:
        return {
            "portfolio_id": request.portfolio_id,
            "margin_call_queue": _margin_call_queue(request.context),
            "team_capacity_minutes": float(request.context.get("team_capacity_minutes", 420)),
            "materiality_threshold": float(
                request.context.get("materiality_threshold", 25_000_000)
            ),
            "sla_escalation_hours": float(request.context.get("sla_escalation_hours", 2)),
            "dispute_stress_multiplier": float(
                request.context.get("dispute_stress_multiplier", 1.0)
            ),
            "production_model_config": self.model_config,
        }

    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        capacity_remaining = float(problem["team_capacity_minutes"])
        scored_calls = [
            {
                **call,
                "sla_escalation_hours": float(problem["sla_escalation_hours"]),
                "priority_score": _priority_score(
                    call,
                    float(problem["materiality_threshold"]),
                    float(problem["dispute_stress_multiplier"]),
                ),
            }
            for call in problem["margin_call_queue"]
        ]
        scored_calls.sort(key=lambda row: row["priority_score"], reverse=True)

        assigned: list[dict[str, Any]] = []
        deferred: list[dict[str, Any]] = []
        for call in scored_calls:
            ops_minutes = float(call["ops_minutes"])
            action = _recommended_action(call, float(problem["materiality_threshold"]))
            if ops_minutes <= capacity_remaining:
                assigned.append(
                    {
                        **call,
                        "assigned_order": len(assigned) + 1,
                        "recommended_action": action,
                        "capacity_minutes": ops_minutes,
                    }
                )
                capacity_remaining -= ops_minutes
            else:
                deferred.append(
                    {
                        **call,
                        "defer_reason": "capacity_limit",
                        "recommended_action": (
                            "escalate_capacity" if call["priority_score"] > 0.5 else "defer"
                        ),
                    }
                )

        total_risk = sum(float(call["priority_score"]) for call in scored_calls)
        assigned_risk = sum(float(call["priority_score"]) for call in assigned)
        residual_risk = max(0.0, total_risk - assigned_risk)
        return {
            "status": "optimal",
            "objective_value": residual_risk,
            "baseline_value": total_risk,
            "assigned": assigned,
            "deferred": deferred,
            "capacity_used": float(problem["team_capacity_minutes"]) - capacity_remaining,
            "capacity_remaining": capacity_remaining,
            "binding_constraints": ["team_capacity"] if deferred else ["priority_order"],
            "metadata": {"solver_method": "exposure_sla_dispute_weighted_score"},
        }

    def explain_outputs(
        self,
        request: OptimizationRequest,
        problem: dict[str, Any],
        native_solution: dict[str, Any],
    ) -> NormalizedOptimizerResult:
        total_amount = sum(float(row.get("amount", 0.0)) for row in problem["margin_call_queue"])
        allocations = [
            {
                "asset_id": str(row["call_id"]),
                "label": f"{row['counterparty']} margin call",
                "allocated_value": float(row["amount"]),
                "allocated_fraction": float(row["amount"]) / total_amount if total_amount else 0.0,
                "metadata": row,
            }
            for row in native_solution["assigned"]
        ]
        assigned_amount = sum(float(row["amount"]) for row in native_solution["assigned"])
        return NormalizedOptimizerResult(
            optimizer_id=self.optimizer_id,
            domain=self.domain,
            status=native_solution["status"],
            objective_value=float(native_solution["objective_value"]),
            baseline_value=float(native_solution["baseline_value"]),
            allocations=allocations,
            binding_constraints=list(native_solution["binding_constraints"]),
            diagnostics={
                "solver_metadata": native_solution["metadata"],
                "explanation": (
                    f"Prioritized ${assigned_amount:,.0f} of margin calls within "
                    f"{problem['team_capacity_minutes']:.0f} minutes of operational capacity."
                ),
            },
            domain_attachments={
                "assigned_calls": to_jsonable(native_solution["assigned"]),
                "deferred_calls": to_jsonable(native_solution["deferred"]),
                "capacity_used": native_solution["capacity_used"],
                "capacity_remaining": native_solution["capacity_remaining"],
                "total_queue_amount": total_amount,
                "assigned_amount": assigned_amount,
            },
        )

    def serialize_evidence(
        self,
        request: OptimizationRequest,
        problem: dict[str, Any],
        native_solution: dict[str, Any],
        normalized_result: NormalizedOptimizerResult,
    ) -> ProductionOptimizerEvidence:
        preflight = self._last_preflight or self.validate_inputs(request)
        return ProductionOptimizerEvidence(
            optimizer_id=self.optimizer_id,
            model_version=self.model_config.lineage.model_version,
            config_version=self.model_config.lineage.config_version,
            data_snapshot_id=preflight.data_snapshot_id,
            solver_version=str(native_solution["metadata"]["solver_method"]),
            reproducibility_fingerprint=preflight.reproducibility_fingerprint,
            artifacts={
                "request": request.model_dump(mode="json"),
                "preflight": preflight.model_dump(mode="json"),
                "model_config": self.model_config.model_dump(mode="json"),
                "native_solution": to_jsonable(native_solution),
                "normalized_result": normalized_result.model_dump(
                    mode="json",
                    exclude={"evidence"},
                ),
            },
        )


def _priority_score(
    call: dict[str, Any],
    materiality_threshold: float,
    dispute_stress_multiplier: float,
) -> float:
    amount_score = min(1.0, float(call.get("amount", 0.0)) / materiality_threshold)
    due_in_hours = float(call.get("due_in_hours", 24.0))
    sla_score = 1.0 if due_in_hours <= 0 else min(1.0, 8.0 / due_in_hours)
    dispute_score = min(
        1.0,
        float(call.get("dispute_probability", 0.0)) * dispute_stress_multiplier,
    )
    tier_score = {"low": 0.15, "medium": 0.35, "high": 0.70, "critical": 1.0}.get(
        str(call.get("risk_tier", "medium")).lower(),
        0.35,
    )
    return round(
        0.40 * amount_score
        + 0.30 * sla_score
        + 0.15 * dispute_score
        + 0.15 * tier_score,
        6,
    )


def _recommended_action(call: dict[str, Any], materiality_threshold: float) -> str:
    if float(call.get("amount", 0.0)) >= materiality_threshold:
        return "supervisor_review"
    if float(call.get("dispute_probability", 0.0)) >= 0.45:
        return "dispute_review"
    if float(call.get("due_in_hours", 24.0)) <= float(call.get("sla_escalation_hours", 2)):
        return "same_day_escalation"
    return "process"


def _margin_call_queue(context: dict[str, Any]) -> list[dict[str, Any]]:
    return list(
        context.get(
            "margin_call_queue",
            [
                {
                    "call_id": "MC_001",
                    "counterparty": "Dealer A",
                    "amount": 45_000_000,
                    "due_in_hours": 2,
                    "dispute_probability": 0.20,
                    "ops_minutes": 90,
                    "risk_tier": "high",
                },
                {
                    "call_id": "MC_002",
                    "counterparty": "CCP SwapClear",
                    "amount": 82_000_000,
                    "due_in_hours": 1,
                    "dispute_probability": 0.05,
                    "ops_minutes": 75,
                    "risk_tier": "critical",
                },
                {
                    "call_id": "MC_003",
                    "counterparty": "Dealer B",
                    "amount": 18_000_000,
                    "due_in_hours": 6,
                    "dispute_probability": 0.55,
                    "ops_minutes": 120,
                    "risk_tier": "medium",
                },
            ],
        )
    )
