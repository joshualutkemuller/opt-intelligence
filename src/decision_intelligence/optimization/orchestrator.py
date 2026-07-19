"""
Deterministic orchestrator — routes OptimizationRequests to the correct
optimizer and returns a structured OptimizationResult.

No LLM in this layer: it is a pure router and lifecycle coordinator.
The agent layer (future) sits above this and translates natural language
into OptimizationRequest objects.
"""

import logging
import time
from typing import Any

from decision_intelligence.contracts import (
    AllocationItem,
    OptimizationRequest,
    OptimizationResult,
)
from decision_intelligence.contracts.results import SolveStatus, ValidationResult
from decision_intelligence.explanation import build_explanation_report
from decision_intelligence.governance.approvals import ApprovalDecision, GovernanceController
from decision_intelligence.governance.audit import AuditLog
from decision_intelligence.production_optimizers import (
    NormalizedOptimizerResult,
    ProductionOptimizerRegistry,
)
from decision_intelligence.production_optimizers.registry import build_default_production_registry
from decision_intelligence.validation import apply_validation_report

from .registry import OptimizerRegistry

logger = logging.getLogger(__name__)


class OptimizationOrchestrator:
    """
    Accepts an OptimizationRequest, selects the optimizer, executes the full
    lifecycle (including scenario analysis if requested), and returns a result.
    """

    def __init__(
        self,
        registry: OptimizerRegistry,
        audit: AuditLog | None = None,
        governance: GovernanceController | None = None,
        production_registry: ProductionOptimizerRegistry | None = None,
    ) -> None:
        self.registry = registry
        self.audit = audit or AuditLog()
        # When set, execution-mode approval is enforced and recorded on results.
        self.governance = governance
        self.production_registry = production_registry or build_default_production_registry()

    def run(
        self,
        request: OptimizationRequest,
        approval: ApprovalDecision | None = None,
    ) -> OptimizationResult:
        logger.info(
            "Orchestrator received request %s domain=%s mode=%s",
            request.request_id,
            request.domain,
            request.execution_mode,
        )
        self.audit.record("request_received", request.request_id, {"domain": request.domain})

        optimizer_runtime = str(request.context.get("optimizer_runtime", "phase1"))
        if optimizer_runtime not in {"phase1", "production"}:
            msg = "context['optimizer_runtime'] must be 'phase1' or 'production'."
            logger.error(msg)
            return OptimizationResult(
                request_id=request.request_id,
                domain=request.domain,
                status=SolveStatus.ERROR,
                objective_value=0.0,
                baseline_value=0.0,
                improvement=0.0,
                improvement_pct=0.0,
                validation=ValidationResult(passed=False, violations=[msg]),
                explanation=msg,
            )

        if optimizer_runtime == "production":
            result = self._run_production(request)
            return self._finalize_result(request, result, approval)

        if request.domain not in self.registry:
            msg = (
                f"Domain '{request.domain}' not registered. "
                f"Available: {self.registry.list_domains()}"
            )
            logger.error(msg)
            return OptimizationResult(
                request_id=request.request_id,
                domain=request.domain,
                status=SolveStatus.ERROR,
                objective_value=0.0,
                baseline_value=0.0,
                improvement=0.0,
                improvement_pct=0.0,
                validation=ValidationResult(passed=False, violations=[msg]),
                explanation=msg,
            )

        optimizer = self.registry.get(request.domain)

        t0 = time.perf_counter()
        result = optimizer.run(request)
        elapsed = time.perf_counter() - t0

        self.audit.record(
            "optimization_complete",
            request.request_id,
            {
                "status": result.status,
                "objective_value": result.objective_value,
                "improvement_pct": result.improvement_pct,
                "elapsed_s": round(elapsed, 4),
            },
        )

        if request.scenarios and result.status == SolveStatus.OPTIMAL:
            result = self._run_scenarios(request, result, optimizer)

        return self._finalize_result(request, result, approval)

    def _finalize_result(
        self,
        request: OptimizationRequest,
        result: OptimizationResult,
        approval: ApprovalDecision | None,
    ) -> OptimizationResult:
        # Execution-mode governance: gate state-changing tiers behind approval.
        if self.governance is not None and result.status == SolveStatus.OPTIMAL:
            record = self.governance.evaluate(request, approval)
            result = result.model_copy(update={"governance": record})

        result = apply_validation_report(result)
        result = result.model_copy(
            update={"explanation_report": build_explanation_report(result)}
        )

        logger.info(
            "Request %s complete: status=%s improvement=%.2f%%",
            request.request_id,
            result.status,
            result.improvement_pct,
        )
        return result

    def _run_production(self, request: OptimizationRequest) -> OptimizationResult:
        adapter_id = _production_adapter_id(request)
        if adapter_id not in self.production_registry:
            msg = (
                f"Production optimizer '{adapter_id}' not registered. "
                f"Available: {self.production_registry.list_ids()}"
            )
            logger.error(msg)
            return OptimizationResult(
                request_id=request.request_id,
                domain=request.domain,
                status=SolveStatus.ERROR,
                objective_value=0.0,
                baseline_value=0.0,
                improvement=0.0,
                improvement_pct=0.0,
                validation=ValidationResult(passed=False, violations=[msg]),
                explanation=msg,
            )

        adapter = self.production_registry.get(adapter_id)
        t0 = time.perf_counter()
        normalized = adapter.run(request)
        elapsed = time.perf_counter() - t0
        result = _normalized_to_optimization_result(request, normalized)

        self.audit.record(
            "production_optimization_complete",
            request.request_id,
            {
                "optimizer_id": adapter_id,
                "status": result.status,
                "objective_value": result.objective_value,
                "improvement_pct": result.improvement_pct,
                "elapsed_s": round(elapsed, 4),
                "fingerprint": (
                    normalized.evidence.reproducibility_fingerprint
                    if normalized.evidence
                    else None
                ),
            },
        )

        if request.scenarios and result.status == SolveStatus.OPTIMAL:
            result = self._run_production_scenarios(request, result)
        return result

    def _run_production_scenarios(
        self,
        base_request: OptimizationRequest,
        base_result: OptimizationResult,
    ) -> OptimizationResult:
        scenario_results: dict[str, OptimizationResult] = {}

        for scenario in base_request.scenarios:
            logger.info("Running production scenario: %s", scenario.name)
            merged_context = {**base_request.context, **scenario.parameter_overrides}
            scenario_request = base_request.model_copy(
                update={
                    "context": merged_context,
                    "scenarios": [],
                }
            )
            scenario_results[scenario.name] = self._run_production(scenario_request)

        return base_result.model_copy(update={"scenario_results": scenario_results})

    def _run_scenarios(
        self,
        base_request: OptimizationRequest,
        base_result: OptimizationResult,
        optimizer: Any,
    ) -> OptimizationResult:
        scenario_results: dict[str, OptimizationResult] = {}

        for scenario in base_request.scenarios:
            logger.info("Running scenario: %s", scenario.name)
            # Merge scenario overrides into a new request context
            merged_context = {**base_request.context, **scenario.parameter_overrides}
            scenario_request = base_request.model_copy(
                update={
                    "context": merged_context,
                    "scenarios": [],  # avoid infinite recursion
                }
            )
            scenario_result = optimizer.run(scenario_request)
            scenario_results[scenario.name] = scenario_result

        return base_result.model_copy(update={"scenario_results": scenario_results})


_DOMAIN_DEFAULT_PRODUCTION_ADAPTERS = {
    "asset_allocation": "production.asset_allocation.mvo",
    "collateral": "production.collateral.allocation",
}


def _production_adapter_id(request: OptimizationRequest) -> str:
    configured = request.context.get("production_optimizer_id")
    if configured:
        return str(configured)
    return _DOMAIN_DEFAULT_PRODUCTION_ADAPTERS.get(
        request.domain,
        f"production.{request.domain}",
    )


def _normalized_to_optimization_result(
    request: OptimizationRequest,
    normalized: NormalizedOptimizerResult,
) -> OptimizationResult:
    status = _solve_status(normalized.status)
    improvement = _calculate_improvement(request, normalized)
    improvement_pct = (
        improvement / abs(normalized.baseline_value) * 100
        if normalized.baseline_value
        else 0.0
    )
    evidence = normalized.evidence.model_dump(mode="json") if normalized.evidence else None
    validation_violations = list(
        normalized.diagnostics.get("validation_violations", [])
    )
    preflight = normalized.diagnostics.get("preflight", {})
    if normalized.status == "blocked":
        validation_violations.extend(preflight.get("blocking_issues", []))

    solver_metadata = {
        **normalized.diagnostics.get("solver_metadata", {}),
        "optimizer_runtime": "production",
        "production_optimizer_id": normalized.optimizer_id,
        "production_domain": normalized.domain,
        "production_evidence": evidence,
        "domain_attachments": normalized.domain_attachments,
    }

    return OptimizationResult(
        request_id=request.request_id,
        domain=request.domain,
        status=status,
        objective_value=normalized.objective_value,
        baseline_value=normalized.baseline_value,
        improvement=improvement,
        improvement_pct=improvement_pct,
        allocations=[
            AllocationItem(**allocation)
            for allocation in normalized.allocations
            if _is_allocation_item_payload(allocation)
        ],
        binding_constraints=normalized.binding_constraints,
        validation=ValidationResult(
            passed=normalized.status not in {"blocked", "error"} and not validation_violations,
            violations=validation_violations,
            warnings=list(preflight.get("warnings", [])),
        ),
        explanation=normalized.diagnostics.get(
            "explanation",
            normalized.diagnostics.get("message", ""),
        ),
        solver_metadata=solver_metadata,
    )


def _solve_status(status: str) -> SolveStatus:
    if status == "optimal":
        return SolveStatus.OPTIMAL
    if status == "infeasible":
        return SolveStatus.INFEASIBLE
    return SolveStatus.ERROR


def _calculate_improvement(
    request: OptimizationRequest,
    normalized: NormalizedOptimizerResult,
) -> float:
    if request.objective.direction.value == "minimize":
        return normalized.baseline_value - normalized.objective_value
    return normalized.objective_value - normalized.baseline_value


def _is_allocation_item_payload(allocation: dict[str, Any]) -> bool:
    required = {"asset_id", "label", "allocated_value", "allocated_fraction"}
    return required.issubset(allocation)
