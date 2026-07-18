"""Production adapter for the current Asset Allocation MVO optimizer."""

from __future__ import annotations

from typing import Any

import numpy as np

from decision_intelligence.contracts import OptimizationRequest
from decision_intelligence.data import load_asset_allocation
from decision_intelligence.optimizers.asset_allocation import AssetAllocationMVOOptimizer

from ...adapter import ProductionOptimizerAdapter
from ...contracts import (
    NormalizedOptimizerResult,
    PreflightReport,
    ProductionOptimizerEvidence,
)
from .._utils import (
    allocation_dicts,
    data_snapshot_id,
    normalize_status,
    reproducibility_fingerprint,
    to_jsonable,
)
from .config import asset_allocation_mvo_config


class AssetAllocationMVOProductionAdapter(ProductionOptimizerAdapter):
    """Production-facing wrapper around the phase 1 Asset Allocation MVO optimizer."""

    optimizer_id = "production.asset_allocation.mvo"
    domain = "asset_allocation"
    model_config = asset_allocation_mvo_config()

    def __init__(self, native_optimizer: AssetAllocationMVOOptimizer | None = None) -> None:
        self.native_optimizer = native_optimizer or AssetAllocationMVOOptimizer()
        self._last_preflight: PreflightReport | None = None

    def validate_inputs(self, request: OptimizationRequest) -> PreflightReport:
        blocking_issues = self.native_optimizer.validate_request(request)
        warnings: list[str] = []
        checked_datasets: dict[str, int] = {}
        snapshot_id = data_snapshot_id(self.domain, request.portfolio_id, request.context)

        try:
            assets, covariance = load_asset_allocation(request)
            checked_datasets["asset_universe"] = len(assets)
            checked_datasets["covariance_matrix_rows"] = int(np.asarray(covariance).shape[0])
            if not assets:
                blocking_issues.append("Asset universe is empty.")
            if np.asarray(covariance).shape != (len(assets), len(assets)):
                blocking_issues.append("Covariance matrix dimension does not match asset universe.")
            current_weight_sum = sum(asset.current_weight for asset in assets)
            if current_weight_sum <= 0:
                blocking_issues.append("Current asset weights must sum to a positive number.")
        except Exception as exc:  # noqa: BLE001 - preflight must turn data errors into blocks.
            blocking_issues.append(f"Asset allocation data preflight failed: {exc}")

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
            checked_datasets=checked_datasets,
            checked_limits={
                "risk_aversion": request.context.get("risk_aversion", 3.0),
                "target_return": request.context.get("target_return"),
                "max_single_asset_weight": request.context.get("max_single_asset_weight"),
                "min_cash_weight": request.context.get("min_cash_weight", 0.02),
            },
        )
        self._last_preflight = report
        return report

    def build_problem(self, request: OptimizationRequest) -> dict[str, Any]:
        problem = self.native_optimizer.prepare_problem(request)
        problem["production_request"] = request
        problem["production_model_config"] = self.model_config
        return problem

    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        return self.native_optimizer.solve(problem)

    def explain_outputs(
        self,
        request: OptimizationRequest,
        problem: dict[str, Any],
        native_solution: dict[str, Any],
    ) -> NormalizedOptimizerResult:
        status = normalize_status(native_solution.get("status"))
        diagnostics: dict[str, Any] = {
            "solver_metadata": to_jsonable(native_solution.get("metadata", {})),
        }
        domain_attachments: dict[str, Any] = {
            "expected_return": native_solution.get("expected_return"),
            "volatility": native_solution.get("volatility"),
            "variance": native_solution.get("variance"),
            "sharpe": native_solution.get("sharpe"),
            "risk_aversion": problem.get("risk_aversion"),
            "target_return": problem.get("target_return"),
        }
        allocations = allocation_dicts(native_solution.get("allocations", []))
        binding_constraints = list(native_solution.get("binding_constraints", []))

        if status == "optimal":
            violations = self.native_optimizer.validate_solution(problem, native_solution)
            sensitivities = self.native_optimizer.run_sensitivity(problem, native_solution)
            diagnostics["validation_violations"] = violations
            diagnostics["explanation"] = self.native_optimizer.explain(problem, native_solution)
            domain_attachments["sensitivities"] = to_jsonable(sensitivities)
        else:
            diagnostics["message"] = native_solution.get("message", "Optimizer did not solve.")

        return NormalizedOptimizerResult(
            optimizer_id=self.optimizer_id,
            domain=self.domain,
            status=status,
            objective_value=float(native_solution.get("objective_value", 0.0)),
            baseline_value=float(problem.get("baseline_value", 0.0)),
            allocations=allocations,
            binding_constraints=binding_constraints,
            diagnostics=diagnostics,
            domain_attachments=to_jsonable(domain_attachments),
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
            solver_version=str(native_solution.get("metadata", {}).get("solver_method", "SLSQP")),
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
                "problem_summary": {
                    "asset_count": len(problem.get("assets", [])),
                    "portfolio_notional": problem.get("portfolio_notional"),
                    "risk_aversion": problem.get("risk_aversion"),
                    "target_return": problem.get("target_return"),
                },
            },
        )
