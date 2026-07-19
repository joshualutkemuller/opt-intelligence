"""Production adapter for the current money-market optimizer."""

from __future__ import annotations

from typing import Any

import numpy as np

from decision_intelligence.contracts import OptimizationRequest
from decision_intelligence.data import load_money_market
from decision_intelligence.optimizers.money_market import MoneyMarketOptimizer

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
from .config import money_market_optimizer_config


class MoneyMarketProductionAdapter(ProductionOptimizerAdapter):
    """Production-facing wrapper around the phase 1 money-market optimizer."""

    optimizer_id = "production.money_market.allocation"
    domain = "money_market"
    model_config = money_market_optimizer_config()

    def __init__(self, native_optimizer: MoneyMarketOptimizer | None = None) -> None:
        self.native_optimizer = native_optimizer or MoneyMarketOptimizer()
        self._last_preflight: PreflightReport | None = None

    def validate_inputs(self, request: OptimizationRequest) -> PreflightReport:
        blocking_issues = self.native_optimizer.validate_request(request)
        warnings: list[str] = []
        checked_datasets: dict[str, int] = {}
        snapshot_id = data_snapshot_id(self.domain, request.portfolio_id, request.context)

        try:
            funds, position = load_money_market(request)
            eligible_funds = [
                fund
                for fund in funds
                if fund.min_investment <= request.context.get("min_investment_threshold", 250_000)
                or position.total_cash * 0.01 >= fund.min_investment
            ]
            checked_datasets["money_market_fund_universe"] = len(funds)
            checked_datasets["eligible_money_market_funds"] = len(eligible_funds)
            checked_datasets["cash_position"] = 1
            if position.total_cash <= 0:
                blocking_issues.append("Money-market cash position must be positive.")
            if not eligible_funds:
                blocking_issues.append("No eligible money-market funds are available.")
            for fund in funds:
                if not np.isfinite(fund.yield_7day):
                    blocking_issues.append(f"Fund {fund.fund_id} has a non-finite yield.")
                if not 0 <= fund.daily_liquidity_pct <= 1:
                    blocking_issues.append(
                        f"Fund {fund.fund_id} daily liquidity must be between 0 and 1."
                    )
                if not 0 <= fund.weekly_liquidity_pct <= 1:
                    blocking_issues.append(
                        f"Fund {fund.fund_id} weekly liquidity must be between 0 and 1."
                    )
                if fund.wam_days < 0:
                    blocking_issues.append(f"Fund {fund.fund_id} has negative WAM.")
        except Exception as exc:  # noqa: BLE001 - preflight must turn data errors into blocks.
            blocking_issues.append(f"Money-market data preflight failed: {exc}")

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
                "daily_liquidity_req": request.context.get("daily_liquidity_req"),
                "weekly_liquidity_req": request.context.get("weekly_liquidity_req"),
                "max_prime_fraction": request.context.get("max_prime_fraction", 0.40),
                "max_wam_days": request.context.get("max_wam_days", 60),
                "max_single_fund": request.context.get("max_single_fund", 0.50),
                "max_funds": request.context.get("max_funds"),
                "problem_type": request.context.get("problem_type", "lp"),
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
        weights = native_solution.get("w")
        domain_attachments: dict[str, Any] = {
            "fund_count": len(problem.get("funds", [])),
            "total_cash": problem.get("total_cash"),
            "daily_liquidity_req": problem.get("daily_req"),
            "weekly_liquidity_req": problem.get("weekly_req"),
            "max_prime_fraction": problem.get("max_prime"),
            "max_wam_days": problem.get("max_wam"),
            "max_single_fund": problem.get("max_single"),
        }
        if weights is not None:
            w = np.asarray(weights, dtype=float)
            domain_attachments.update(
                {
                    "daily_liquidity": float(problem["daily_liq"] @ w),
                    "weekly_liquidity": float(problem["weekly_liq"] @ w),
                    "portfolio_wam": float(problem["wam"] @ w),
                    "prime_fraction": float(problem["is_prime"] @ w),
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
                    "fund_count": len(problem.get("funds", [])),
                    "total_cash": problem.get("total_cash"),
                    "daily_liquidity_req": problem.get("daily_req"),
                    "weekly_liquidity_req": problem.get("weekly_req"),
                    "max_prime_fraction": problem.get("max_prime"),
                    "max_wam_days": problem.get("max_wam"),
                    "solver_spec": to_jsonable(problem.get("solver_spec")),
                },
            },
        )
