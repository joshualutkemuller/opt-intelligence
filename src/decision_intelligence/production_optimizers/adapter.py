"""Formal adapter interface for production optimizer integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from decision_intelligence.contracts import OptimizationRequest

from .contracts import (
    ModelConfigSpec,
    NormalizedOptimizerResult,
    PreflightReport,
    ProductionOptimizerEvidence,
)
from .governance import evaluate_model_governance


class ProductionOptimizerAdapter(ABC):
    """Stable lifecycle every production optimizer adapter must implement."""

    optimizer_id: str
    domain: str
    model_config: ModelConfigSpec

    @abstractmethod
    def validate_inputs(self, request: OptimizationRequest) -> PreflightReport:
        """Validate request, model config, data availability, and policy readiness."""

    @abstractmethod
    def build_problem(self, request: OptimizationRequest) -> dict[str, Any]:
        """Translate platform inputs into the native optimizer problem payload."""

    @abstractmethod
    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        """Execute the native optimizer through the configured isolation mode."""

    @abstractmethod
    def explain_outputs(
        self,
        request: OptimizationRequest,
        problem: dict[str, Any],
        native_solution: dict[str, Any],
    ) -> NormalizedOptimizerResult:
        """Normalize dense native output into platform result sections."""

    @abstractmethod
    def serialize_evidence(
        self,
        request: OptimizationRequest,
        problem: dict[str, Any],
        native_solution: dict[str, Any],
        normalized_result: NormalizedOptimizerResult,
    ) -> ProductionOptimizerEvidence:
        """Create reproducible audit evidence for exports, approval, and review."""

    def run(self, request: OptimizationRequest) -> NormalizedOptimizerResult:
        """Canonical adapter lifecycle used by future production orchestrators."""

        model_governance = evaluate_model_governance(request, self.model_config)
        if model_governance.blocking_issues:
            return NormalizedOptimizerResult(
                optimizer_id=self.optimizer_id,
                domain=self.domain,
                status="blocked",
                objective_value=0.0,
                baseline_value=0.0,
                allocations=[],
                diagnostics={
                    "model_governance": model_governance.model_dump(mode="json"),
                    "preflight": {
                        "blocking_issues": model_governance.blocking_issues,
                        "warnings": model_governance.warnings,
                    },
                },
                evidence=ProductionOptimizerEvidence(
                    optimizer_id=self.optimizer_id,
                    model_version=self.model_config.lineage.model_version,
                    config_version=self.model_config.lineage.config_version,
                    data_snapshot_id=None,
                    approvals=[model_governance.record.model_dump(mode="json")],
                    artifacts={
                        "model_governance": model_governance.model_dump(mode="json"),
                    },
                ),
            )

        preflight = self.validate_inputs(request)
        if preflight.blocking_issues:
            return NormalizedOptimizerResult(
                optimizer_id=self.optimizer_id,
                domain=self.domain,
                status="blocked",
                objective_value=0.0,
                baseline_value=0.0,
                allocations=[],
                diagnostics={"preflight": preflight.model_dump(mode="json")},
                evidence=ProductionOptimizerEvidence(
                    optimizer_id=self.optimizer_id,
                    model_version=self.model_config.lineage.model_version,
                    config_version=self.model_config.lineage.config_version,
                    data_snapshot_id=preflight.data_snapshot_id,
                    reproducibility_fingerprint=preflight.reproducibility_fingerprint,
                    approvals=[model_governance.record.model_dump(mode="json")],
                    artifacts={},
                ),
            )

        problem = self.build_problem(request)
        native_solution = self.solve(problem)
        normalized = self.explain_outputs(request, problem, native_solution)
        evidence = self.serialize_evidence(request, problem, native_solution, normalized)
        evidence = evidence.model_copy(
            update={
                "approvals": [
                    *evidence.approvals,
                    model_governance.record.model_dump(mode="json"),
                ],
                "artifacts": {
                    **evidence.artifacts,
                    "model_governance": model_governance.model_dump(mode="json"),
                },
            }
        )
        return normalized.model_copy(update={"evidence": evidence})
