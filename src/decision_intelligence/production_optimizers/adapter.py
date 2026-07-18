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
                    artifacts={},
                ),
            )

        problem = self.build_problem(request)
        native_solution = self.solve(problem)
        normalized = self.explain_outputs(request, problem, native_solution)
        evidence = self.serialize_evidence(request, problem, native_solution, normalized)
        return normalized.model_copy(update={"evidence": evidence})
