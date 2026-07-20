"""Production adapter for the current collateral optimizer."""

from __future__ import annotations

from typing import Any

from decision_intelligence.contracts import OptimizationRequest
from decision_intelligence.data import load_collateral
from decision_intelligence.optimizers.collateral import CollateralOptimizer
from decision_intelligence.production_optimizers.data import build_data_preflight_report

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
from .config import collateral_optimizer_config


class CollateralProductionAdapter(ProductionOptimizerAdapter):
    """Production-facing wrapper around the phase 1 collateral optimizer."""

    optimizer_id = "production.collateral.allocation"
    domain = "collateral"
    model_config = collateral_optimizer_config()

    def __init__(self, native_optimizer: CollateralOptimizer | None = None) -> None:
        self.native_optimizer = native_optimizer or CollateralOptimizer()
        self._last_preflight: PreflightReport | None = None

    def validate_inputs(self, request: OptimizationRequest) -> PreflightReport:
        blocking_issues = self.native_optimizer.validate_request(request)
        checked_datasets: dict[str, int] = {}
        warnings: list[str] = []
        data_preflight = build_data_preflight_report(request, self.model_config)
        blocking_issues.extend(data_preflight.blocking_issues)
        warnings.extend(data_preflight.warnings)
        checked_datasets.update(data_preflight.checked_datasets)
        snapshot_id = (
            request.context.get("data_snapshot_id")
            or data_preflight.snapshot_id
            or data_snapshot_id(
                self.domain,
                request.portfolio_id,
                request.context,
            )
        )

        try:
            assets, obligations = load_collateral(request)
            eligible_assets = [asset for asset in assets if asset.eligible]
            checked_datasets["collateral_inventory"] = len(assets)
            checked_datasets["eligible_collateral_inventory"] = len(eligible_assets)
            checked_datasets["margin_obligations"] = len(obligations)
            if not eligible_assets:
                blocking_issues.append("No eligible collateral assets are available.")
            if not obligations:
                blocking_issues.append("No collateral obligations are available.")
            for obligation in obligations:
                if obligation.required_value <= 0:
                    blocking_issues.append(
                        f"Obligation {obligation.obligation_id} must have positive required_value."
                    )
                if not obligation.eligible_asset_classes:
                    blocking_issues.append(
                        f"Obligation {obligation.obligation_id} has no eligible asset classes."
                    )
        except Exception as exc:  # noqa: BLE001 - preflight must turn data errors into blocks.
            blocking_issues.append(f"Collateral data preflight failed: {exc}")

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
                "concentration_limit": request.context.get("concentration_limit", 0.60),
                "solver_backend": request.context.get("solver_backend", "scipy"),
                "problem_type": request.context.get("problem_type", "lp"),
            },
            data_sources=[
                report.model_dump(mode="json") for report in data_preflight.reports
            ],
            data_quality={
                "passed": data_preflight.passed,
                "warning_count": len(data_preflight.warnings),
                "blocking_issue_count": len(data_preflight.blocking_issues),
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
        allocations = allocation_dicts(native_solution.get("allocations", []))
        binding_constraints = list(native_solution.get("binding_constraints", []))
        obligations = problem.get("obligations", [])
        venue_counts: dict[str, int] = {}
        for obligation in obligations:
            venue = str(getattr(obligation, "venue_type", "bilateral"))
            venue_counts[venue] = venue_counts.get(venue, 0) + 1
        domain_attachments: dict[str, Any] = {
            "asset_count": len(problem.get("assets", [])),
            "obligation_count": len(obligations),
            "obligation_venue_counts": venue_counts,
            "obligation_counterparties": [
                {
                    "obligation_id": getattr(obligation, "obligation_id", ""),
                    "counterparty": getattr(obligation, "counterparty", ""),
                    "venue_type": getattr(obligation, "venue_type", "bilateral"),
                    "agreement_type": getattr(obligation, "agreement_type", "CSA"),
                    "required_value": getattr(obligation, "required_value", 0.0),
                }
                for obligation in obligations
            ],
            "concentration_limit": problem.get("conc_limit"),
        }

        if status == "optimal":
            violations = self.native_optimizer.validate_solution(problem, native_solution)
            sensitivities = self.native_optimizer.run_sensitivity(problem, native_solution)
            diagnostics["validation_violations"] = violations
            diagnostics["explanation"] = self.native_optimizer.explain(problem, native_solution)
            domain_attachments["sensitivities"] = to_jsonable(sensitivities)
            domain_attachments["lending_opportunities"] = to_jsonable(
                native_solution.get("lending_opportunities", [])
            )
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
        metadata = native_solution.get("metadata", {})
        return ProductionOptimizerEvidence(
            optimizer_id=self.optimizer_id,
            model_version=self.model_config.lineage.model_version,
            config_version=self.model_config.lineage.config_version,
            data_snapshot_id=preflight.data_snapshot_id,
            solver_version=str(
                metadata.get("solver_method", metadata.get("solver_backend", "unknown"))
            ),
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
                    "obligation_count": len(problem.get("obligations", [])),
                    "obligation_venue_counts": to_jsonable(
                        normalized_result.domain_attachments.get(
                            "obligation_venue_counts",
                            {},
                        )
                    ),
                    "concentration_limit": problem.get("conc_limit"),
                    "solver_spec": to_jsonable(problem.get("solver_spec")),
                },
            },
        )
