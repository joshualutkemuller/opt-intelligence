"""Production adapter for the current financing optimizer."""

from __future__ import annotations

from typing import Any

import numpy as np

from decision_intelligence.contracts import OptimizationRequest
from decision_intelligence.data import load_financing
from decision_intelligence.optimizers.financing import FinancingOptimizer

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
from .config import financing_optimizer_config


class FinancingProductionAdapter(ProductionOptimizerAdapter):
    """Production-facing wrapper around the phase 1 financing optimizer."""

    optimizer_id = "production.financing.allocation"
    domain = "financing"
    model_config = financing_optimizer_config()

    def __init__(self, native_optimizer: FinancingOptimizer | None = None) -> None:
        self.native_optimizer = native_optimizer or FinancingOptimizer()
        self._last_preflight: PreflightReport | None = None

    def validate_inputs(self, request: OptimizationRequest) -> PreflightReport:
        blocking_issues = self.native_optimizer.validate_request(request)
        warnings: list[str] = []
        checked_datasets: dict[str, int] = {}
        checked_limits: dict[str, Any] = {}
        snapshot_id = data_snapshot_id(self.domain, request.portfolio_id, request.context)

        try:
            counterparties, needs = load_financing(request)
            checked_datasets["financing_counterparties"] = len(counterparties)
            checked_datasets["funding_needs"] = len(needs)
            total_need = sum(need.notional for need in needs)
            total_capacity = sum(cp.capacity for cp in counterparties)
            checked_limits = {
                "total_funding_need": total_need,
                "total_counterparty_capacity": total_capacity,
                "max_cp_concentration": request.context.get("max_cp_concentration", 0.40),
                "capital_budget_pct": request.context.get("capital_budget_pct", 5.0),
                "solver_backend": request.context.get("solver_backend", "scipy"),
                "problem_type": request.context.get("problem_type", "lp"),
            }
            if not counterparties:
                blocking_issues.append("No financing counterparties are available.")
            if not needs:
                blocking_issues.append("No funding needs are available.")
            if total_need <= 0:
                blocking_issues.append("Total funding need must be positive.")
            if total_capacity <= 0:
                blocking_issues.append("Total counterparty capacity must be positive.")
            if total_capacity < total_need:
                warnings.append(
                    "Total counterparty capacity is below total funding need before "
                    "tenor and concentration constraints."
                )

            for cp in counterparties:
                if cp.capacity < 0:
                    blocking_issues.append(
                        f"Counterparty {cp.counterparty_id} has negative capacity."
                    )
                if not np.isfinite(cp.spread_bps):
                    blocking_issues.append(
                        f"Counterparty {cp.counterparty_id} has a non-finite spread."
                    )
                if not np.isfinite(cp.capital_usage_pct):
                    blocking_issues.append(
                        f"Counterparty {cp.counterparty_id} has non-finite capital usage."
                    )
                if cp.min_tenor_days > cp.max_tenor_days:
                    blocking_issues.append(
                        f"Counterparty {cp.counterparty_id} has invalid tenor bounds."
                    )

            for need in needs:
                if need.notional <= 0:
                    blocking_issues.append(f"Funding need {need.position_id} must be positive.")
                compatible_capacity = sum(
                    cp.capacity
                    for cp in counterparties
                    if cp.min_tenor_days <= need.required_tenor_days <= cp.max_tenor_days
                )
                if compatible_capacity <= 0:
                    blocking_issues.append(
                        f"Funding need {need.position_id} has no tenor-compatible counterparties."
                    )
        except Exception as exc:  # noqa: BLE001 - preflight must turn data errors into blocks.
            blocking_issues.append(f"Financing data preflight failed: {exc}")

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
            checked_limits=checked_limits,
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
        x = native_solution.get("x")
        domain_attachments: dict[str, Any] = {
            "counterparty_count": len(problem.get("counterparties", [])),
            "funding_need_count": len(problem.get("needs", [])),
            "total_funding": problem.get("total_funding"),
            "capital_budget": problem.get("cap_budget"),
            "max_cp_concentration": problem.get("max_cp_conc"),
        }
        if x is not None:
            cps = problem.get("counterparties", [])
            n = problem.get("n", 0)
            m = problem.get("m", 0)
            source_totals: dict[str, float] = {}
            instrument_mix: dict[str, float] = {}
            capital_usage = 0.0
            for i, cp in enumerate(cps):
                used = float(sum(x[i + j * n] for j in range(m)))
                if used > 1.0:
                    source_totals[cp.counterparty_id] = used
                    instrument_mix[cp.instrument] = instrument_mix.get(cp.instrument, 0.0) + used
                    capital_usage += used * cp.capital_usage_pct / 100
            domain_attachments.update(
                {
                    "counterparty_source_totals": source_totals,
                    "instrument_mix": instrument_mix,
                    "capital_usage": capital_usage,
                    "counterparties_used": len(source_totals),
                }
            )

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
                    "counterparty_count": len(problem.get("counterparties", [])),
                    "funding_need_count": len(problem.get("needs", [])),
                    "total_funding": problem.get("total_funding"),
                    "capital_budget": problem.get("cap_budget"),
                    "max_cp_concentration": problem.get("max_cp_conc"),
                    "solver_spec": to_jsonable(problem.get("solver_spec")),
                },
            },
        )
