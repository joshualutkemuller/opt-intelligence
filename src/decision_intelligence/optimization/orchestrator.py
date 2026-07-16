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

from decision_intelligence.contracts import OptimizationRequest, OptimizationResult
from decision_intelligence.contracts.results import SolveStatus, ValidationResult
from decision_intelligence.explanation import build_explanation_report
from decision_intelligence.governance.approvals import ApprovalDecision, GovernanceController
from decision_intelligence.governance.audit import AuditLog
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
    ) -> None:
        self.registry = registry
        self.audit = audit or AuditLog()
        # When set, execution-mode approval is enforced and recorded on results.
        self.governance = governance

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
