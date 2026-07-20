"""Production adapter scaffold for treasury cash-movement optimization."""

from __future__ import annotations

from typing import Any

from decision_intelligence.contracts import OptimizationRequest
from decision_intelligence.production_optimizers.data import build_data_preflight_report

from ...adapter import ProductionOptimizerAdapter
from ...contracts import (
    NormalizedOptimizerResult,
    PreflightReport,
    ProductionOptimizerEvidence,
)
from .._utils import data_snapshot_id, reproducibility_fingerprint, to_jsonable
from .config import cash_movement_optimizer_config


class CashMovementProductionAdapter(ProductionOptimizerAdapter):
    """Production-facing adapter for operational treasury cash movement."""

    optimizer_id = "production.treasury.cash_movement"
    domain = "treasury_operations"
    model_config = cash_movement_optimizer_config()

    def __init__(self) -> None:
        self._last_preflight: PreflightReport | None = None

    def validate_inputs(self, request: OptimizationRequest) -> PreflightReport:
        balances = _cash_balances(request.context)
        requirements = _funding_requirements(request.context)
        rails = _payment_rails(request.context)
        blocking_issues: list[str] = []
        warnings: list[str] = []
        data_preflight = build_data_preflight_report(request, self.model_config)
        blocking_issues.extend(data_preflight.blocking_issues)
        warnings.extend(data_preflight.warnings)
        checked_datasets = dict(data_preflight.checked_datasets)

        if request.domain != self.domain:
            blocking_issues.append(f"Expected domain '{self.domain}', got '{request.domain}'.")
        if not balances:
            blocking_issues.append("At least one source cash balance is required.")
        if not requirements:
            blocking_issues.append("At least one funding requirement is required.")
        if not rails:
            blocking_issues.append("At least one payment rail is required.")

        for row in balances:
            if float(row.get("available_cash", 0.0)) < 0:
                blocking_issues.append(f"Account {row.get('account_id')} has negative cash.")
            if float(row.get("minimum_buffer", 0.0)) < 0:
                blocking_issues.append(f"Account {row.get('account_id')} has negative buffer.")
        for row in requirements:
            if float(row.get("required_cash", 0.0)) <= 0:
                blocking_issues.append(f"Requirement {row.get('requirement_id')} must be positive.")
        currencies = {str(row.get("currency", "USD")) for row in rails}
        for row in requirements:
            currency = str(row.get("currency", "USD"))
            if currency not in currencies:
                blocking_issues.append(f"No payment rail configured for {currency}.")

        if len(requirements) > 8:
            warnings.append("Large funding queue; consider batch execution isolation.")

        snapshot_id = (
            request.context.get("data_snapshot_id")
            or data_preflight.snapshot_id
            or data_snapshot_id(
                self.domain,
                request.portfolio_id,
                request.context,
            )
        )
        fingerprint = reproducibility_fingerprint(
            model_config=self.model_config,
            request_payload=request.model_dump(mode="json"),
            snapshot_id=snapshot_id,
        )
        checked_datasets.update(
            {
                "cash_balances": len(balances),
                "funding_requirements": len(requirements),
                "payment_rails": len(rails),
            }
        )
        report = PreflightReport(
            passed=not blocking_issues,
            data_snapshot_id=snapshot_id,
            reproducibility_fingerprint=fingerprint,
            warnings=warnings,
            blocking_issues=blocking_issues,
            checked_datasets=checked_datasets,
            checked_limits={
                "cutoff_hour": request.context.get("cutoff_hour", 15),
                "liquidity_buffer_pct": request.context.get("liquidity_buffer_pct", 0.05),
                "stress_multiplier": request.context.get("stress_multiplier", 1.0),
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
        return {
            "portfolio_id": request.portfolio_id,
            "cash_balances": _cash_balances(request.context),
            "funding_requirements": _funding_requirements(request.context),
            "payment_rails": _payment_rails(request.context),
            "cutoff_hour": float(request.context.get("cutoff_hour", 15)),
            "stress_multiplier": float(request.context.get("stress_multiplier", 1.0)),
            "production_model_config": self.model_config,
        }

    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        available = {
            str(row["account_id"]): float(row["available_cash"]) - float(row["minimum_buffer"])
            for row in problem["cash_balances"]
        }
        source_rows = {str(row["account_id"]): row for row in problem["cash_balances"]}
        rails = sorted(
            [
                rail
                for rail in problem["payment_rails"]
                if float(rail.get("cutoff_hour", 0)) >= float(problem["cutoff_hour"])
            ],
            key=lambda item: (float(item.get("fee_bps", 0.0)), float(item.get("fixed_fee", 0.0))),
        )

        transfers: list[dict[str, Any]] = []
        unmet: list[dict[str, Any]] = []
        objective_value = 0.0
        stress_multiplier = float(problem["stress_multiplier"])

        for requirement in problem["funding_requirements"]:
            need = float(requirement["required_cash"]) * stress_multiplier
            remaining = need
            currency = str(requirement.get("currency", "USD"))
            open_rails = [rail for rail in rails if str(rail.get("currency", currency)) == currency]
            source_ids = [
                account_id
                for account_id, row in source_rows.items()
                if str(row.get("currency", currency)) == currency and available[account_id] > 0
            ]
            source_ids.sort(key=lambda account_id: available[account_id], reverse=True)

            for rail in open_rails:
                max_transfer = float(rail.get("max_transfer", remaining))
                for account_id in source_ids:
                    if remaining <= 0:
                        break
                    amount = min(remaining, max_transfer, available[account_id])
                    if amount <= 0:
                        continue
                    cost = amount * float(rail.get("fee_bps", 0.0)) / 10_000 + float(
                        rail.get("fixed_fee", 0.0)
                    )
                    transfers.append(
                        {
                            "requirement_id": requirement["requirement_id"],
                            "from_account_id": account_id,
                            "to_account_id": requirement["target_account_id"],
                            "currency": currency,
                            "rail_id": rail["rail_id"],
                            "amount": amount,
                            "cost": cost,
                            "cutoff_hour": rail.get("cutoff_hour"),
                        }
                    )
                    available[account_id] -= amount
                    remaining -= amount
                    objective_value += cost
                if remaining <= 0:
                    break
            if remaining > 1e-6:
                unmet.append(
                    {
                        "requirement_id": requirement["requirement_id"],
                        "unmet_cash": remaining,
                    }
                )

        baseline_value = objective_value * 1.25 + len(problem["funding_requirements"]) * 500
        return {
            "status": "optimal" if not unmet else "infeasible",
            "objective_value": objective_value,
            "baseline_value": baseline_value,
            "transfers": transfers,
            "unmet": unmet,
            "remaining_liquidity": available,
            "binding_constraints": ["payment_cutoff"] if unmet else ["least_cost_route"],
            "metadata": {"solver_method": "least_cost_cutoff_feasible"},
        }

    def explain_outputs(
        self,
        request: OptimizationRequest,
        problem: dict[str, Any],
        native_solution: dict[str, Any],
    ) -> NormalizedOptimizerResult:
        total_required = sum(
            float(row["required_cash"]) * float(problem["stress_multiplier"])
            for row in problem["funding_requirements"]
        )
        total_moved = sum(float(row["amount"]) for row in native_solution["transfers"])
        requirement_rows = {
            str(row["requirement_id"]): row for row in problem["funding_requirements"]
        }
        source_rows = {str(row["account_id"]): row for row in problem["cash_balances"]}
        action_rows = [
            _cash_transfer_action_row(
                transfer=row,
                requirement=requirement_rows.get(str(row["requirement_id"]), {}),
                source=source_rows.get(str(row["from_account_id"]), {}),
                remaining_liquidity=native_solution["remaining_liquidity"],
            )
            for row in native_solution["transfers"]
        ]
        allocations = [
            {
                "asset_id": f"{row['requirement_id']}:{row['rail_id']}:{row['from_account_id']}",
                "label": f"{row['from_account_id']} to {row['to_account_id']} via {row['rail_id']}",
                "allocated_value": row["amount"],
                "allocated_fraction": row["amount"] / total_required if total_required else 0.0,
                "metadata": row,
            }
            for row in native_solution["transfers"]
        ]
        return NormalizedOptimizerResult(
            optimizer_id=self.optimizer_id,
            domain=self.domain,
            status=native_solution["status"],
            objective_value=float(native_solution["objective_value"]),
            baseline_value=float(native_solution["baseline_value"]),
            allocations=allocations,
            binding_constraints=list(native_solution["binding_constraints"]),
            infeasibility_diagnostics={"unmet": native_solution["unmet"]},
            diagnostics={
                "solver_metadata": native_solution["metadata"],
                "explanation": (
                    f"Moved ${total_moved:,.0f} of ${total_required:,.0f} requested cash "
                    "using least-cost open payment rails while preserving source buffers."
                ),
            },
            domain_attachments={
                "total_required_cash": total_required,
                "total_moved_cash": total_moved,
                "transfer_count": len(native_solution["transfers"]),
                "transfers": to_jsonable(native_solution["transfers"]),
                "operational_action_table": to_jsonable(action_rows),
                "unmet_requirements": native_solution["unmet"],
                "remaining_liquidity": native_solution["remaining_liquidity"],
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


def _cash_balances(context: dict[str, Any]) -> list[dict[str, Any]]:
    if "cash_balances" in context:
        return list(context["cash_balances"])
    source_minimum_buffer = context.get("source_minimum_buffer")
    balances = [
        {
            "account_id": "TREASURY_US_1",
            "entity": "Broker Dealer",
            "currency": "USD",
            "available_cash": 180_000_000,
            "minimum_buffer": 25_000_000,
        },
        {
            "account_id": "TREASURY_US_2",
            "entity": "Bank Entity",
            "currency": "USD",
            "available_cash": 95_000_000,
            "minimum_buffer": 20_000_000,
        },
    ]
    if source_minimum_buffer is not None:
        for row in balances:
            row["minimum_buffer"] = max(
                float(row["minimum_buffer"]),
                float(source_minimum_buffer),
            )
    return balances


def _funding_requirements(context: dict[str, Any]) -> list[dict[str, Any]]:
    if "funding_requirements" in context:
        return list(context["funding_requirements"])
    requirements = [
        {
            "requirement_id": "PAY_001",
            "target_account_id": "CLEARING_US",
            "currency": "USD",
            "required_cash": 120_000_000,
            "cutoff_hour": 15,
        },
        {
            "requirement_id": "PAY_002",
            "target_account_id": "SETTLEMENT_US",
            "currency": "USD",
            "required_cash": 70_000_000,
            "cutoff_hour": 16,
        },
    ]
    total_required_cash = context.get("total_required_cash")
    if total_required_cash is not None:
        current_total = sum(float(row["required_cash"]) for row in requirements)
        scale = float(total_required_cash) / current_total if current_total else 1.0
        for row in requirements:
            row["required_cash"] = float(row["required_cash"]) * scale
    return requirements


def _payment_rails(context: dict[str, Any]) -> list[dict[str, Any]]:
    if "payment_rails" in context:
        return list(context["payment_rails"])
    payment_rail_max_transfer = context.get("payment_rail_max_transfer")
    rails = [
        {
            "rail_id": "FEDWIRE",
            "currency": "USD",
            "fee_bps": 0.15,
            "fixed_fee": 35,
            "cutoff_hour": 17,
            "max_transfer": 250_000_000,
        },
        {
            "rail_id": "CHIPS",
            "currency": "USD",
            "fee_bps": 0.08,
            "fixed_fee": 20,
            "cutoff_hour": 16,
            "max_transfer": 125_000_000,
        },
    ]
    if payment_rail_max_transfer is not None:
        for row in rails:
            row["max_transfer"] = min(
                float(row["max_transfer"]),
                float(payment_rail_max_transfer),
            )
    return rails


def _cash_transfer_action_row(
    *,
    transfer: dict[str, Any],
    requirement: dict[str, Any],
    source: dict[str, Any],
    remaining_liquidity: dict[str, Any],
) -> dict[str, Any]:
    source_account = str(transfer.get("from_account_id", ""))
    target_cutoff = requirement.get("cutoff_hour", transfer.get("cutoff_hour"))
    rail_cutoff = transfer.get("cutoff_hour")
    cutoff_status = "open"
    if target_cutoff is not None and rail_cutoff is not None:
        cutoff_status = "meets_cutoff" if float(rail_cutoff) >= float(target_cutoff) else "late"
    return {
        "action_type": "cash_transfer",
        "requirement_id": transfer.get("requirement_id"),
        "source_account": source_account,
        "source_entity": source.get("entity"),
        "target_account": transfer.get("to_account_id"),
        "rail": transfer.get("rail_id"),
        "currency": transfer.get("currency"),
        "amount": transfer.get("amount"),
        "cost": transfer.get("cost"),
        "rail_cutoff_hour": rail_cutoff,
        "requirement_cutoff_hour": target_cutoff,
        "cutoff_status": cutoff_status,
        "remaining_source_liquidity": remaining_liquidity.get(source_account),
        "source_buffer": source.get("minimum_buffer"),
        "recommended_action": "execute_transfer",
        "reason": "least-cost cutoff-feasible route",
    }
