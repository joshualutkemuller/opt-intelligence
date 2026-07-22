"""Tests for the production optimizer adapter scaffold."""

from typing import Any

import pytest

from decision_intelligence.contracts import (
    ExecutionMode,
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
)
from decision_intelligence.production_optimizers import (
    AssetAllocationMVOProductionAdapter,
    CashMovementProductionAdapter,
    CollateralProductionAdapter,
    ConstraintFamilySpec,
    DataContractSpec,
    ExecutionIsolationSpec,
    FinancingProductionAdapter,
    MarginCallWorkflowProductionAdapter,
    ModelConfigSpec,
    ModelLineageSpec,
    MoneyMarketProductionAdapter,
    NormalizedOptimizerResult,
    ObjectiveTermSpec,
    PreflightReport,
    ProductionOptimizerAdapter,
    ProductionOptimizerEvidence,
    ProductionOptimizerRegistry,
    SolverBackendSpec,
    build_default_production_registry,
)


def make_model_config() -> ModelConfigSpec:
    return ModelConfigSpec(
        optimizer_id="prod.asset_allocation.demo",
        domain="asset_allocation",
        lineage=ModelLineageSpec(
            model_name="Production Demo MVO",
            model_version="1.0.0",
            config_version="2026.07.18",
            owner="quant-research",
            approved_for=["recommendation"],
        ),
        objectives=[
            ObjectiveTermSpec(
                name="expected_return",
                direction="maximize",
                weight=1.0,
                units="annual_return",
            )
        ],
        constraints=[
            ConstraintFamilySpec(
                name="max_single_asset_weight",
                constraint_type="bounds",
                hard=True,
                tolerance=0.0,
                limit_source="ips",
            )
        ],
        data_contract=DataContractSpec(
            required_datasets=["holdings", "risk_model"],
            primary_keys={"holdings": ["portfolio_id", "asset_id"]},
            required_columns={"holdings": ["market_value", "current_weight"]},
            quality_checks=["nonnegative_market_value"],
        ),
        solver=SolverBackendSpec(
            backend="scipy",
            problem_family="qp",
            vendor="scipy",
            version="1.x",
        ),
        execution=ExecutionIsolationSpec(mode="in_process", timeout_seconds=30),
    )


def make_request() -> OptimizationRequest:
    return OptimizationRequest(
        domain="asset_allocation",
        portfolio_id="PORT_PROD_001",
        objective=Objective(
            name="rebalance",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="risk_adjusted_return",
        ),
        context={"data_snapshot_id": "SNAP_001"},
    )


class DemoProductionAdapter(ProductionOptimizerAdapter):
    optimizer_id = "prod.asset_allocation.demo"
    domain = "asset_allocation"
    model_config = make_model_config()

    def validate_inputs(self, request: OptimizationRequest) -> PreflightReport:
        if "data_snapshot_id" not in request.context:
            return PreflightReport(
                passed=False,
                blocking_issues=["Missing required context: data_snapshot_id"],
            )
        return PreflightReport(
            passed=True,
            data_snapshot_id=str(request.context["data_snapshot_id"]),
            reproducibility_fingerprint="fp-demo",
            checked_datasets={"holdings": 3, "risk_model": 1},
        )

    def build_problem(self, request: OptimizationRequest) -> dict[str, Any]:
        return {
            "portfolio_id": request.portfolio_id,
            "weights": {"Global Equity": 0.55, "Core Fixed Income": 0.35, "Cash": 0.10},
        }

    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "optimal",
            "objective_value": 0.071,
            "weights": problem["weights"],
            "active_constraints": ["max_single_asset_weight"],
        }

    def explain_outputs(
        self,
        request: OptimizationRequest,
        problem: dict[str, Any],
        native_solution: dict[str, Any],
    ) -> NormalizedOptimizerResult:
        return NormalizedOptimizerResult(
            optimizer_id=self.optimizer_id,
            domain=self.domain,
            status="optimal",
            objective_value=float(native_solution["objective_value"]),
            baseline_value=0.064,
            allocations=[
                {"name": name, "weight": weight}
                for name, weight in native_solution["weights"].items()
            ],
            binding_constraints=list(native_solution["active_constraints"]),
            diagnostics={"portfolio_id": request.portfolio_id, "problem_keys": sorted(problem)},
        )

    def serialize_evidence(
        self,
        request: OptimizationRequest,
        problem: dict[str, Any],
        native_solution: dict[str, Any],
        normalized_result: NormalizedOptimizerResult,
    ) -> ProductionOptimizerEvidence:
        return ProductionOptimizerEvidence(
            optimizer_id=self.optimizer_id,
            model_version=self.model_config.lineage.model_version,
            config_version=self.model_config.lineage.config_version,
            data_snapshot_id=str(request.context["data_snapshot_id"]),
            solver_version=self.model_config.solver.version,
            reproducibility_fingerprint="fp-demo",
            artifacts={
                "native_solution": native_solution,
                "normalized_status": normalized_result.status,
            },
        )


def test_production_adapter_run_attaches_normalized_evidence() -> None:
    result = DemoProductionAdapter().run(make_request())

    assert result.status == "optimal"
    assert result.objective_value == pytest.approx(0.071)
    assert result.baseline_value == pytest.approx(0.064)
    assert result.binding_constraints == ["max_single_asset_weight"]
    assert result.evidence is not None
    assert result.evidence.model_version == "1.0.0"
    assert result.evidence.data_snapshot_id == "SNAP_001"
    assert result.evidence.reproducibility_fingerprint == "fp-demo"


def test_production_adapter_blocks_before_solve_when_preflight_fails() -> None:
    request = make_request().model_copy(update={"context": {}})

    result = DemoProductionAdapter().run(request)

    assert result.status == "blocked"
    assert result.diagnostics["preflight"]["blocking_issues"] == [
        "Missing required context: data_snapshot_id"
    ]
    assert result.evidence is not None
    assert result.evidence.model_version == "1.0.0"


def test_production_optimizer_registry_lists_and_fetches_adapters() -> None:
    registry = ProductionOptimizerRegistry()
    adapter = DemoProductionAdapter()

    registry.register(adapter)

    assert registry.list_ids() == ["prod.asset_allocation.demo"]
    assert "prod.asset_allocation.demo" in registry
    assert registry.get("prod.asset_allocation.demo") is adapter


def test_production_optimizer_registry_rejects_duplicates() -> None:
    registry = ProductionOptimizerRegistry()
    registry.register(DemoProductionAdapter())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(DemoProductionAdapter())


def test_asset_allocation_mvo_production_adapter_runs_native_optimizer() -> None:
    request = OptimizationRequest(
        domain="asset_allocation",
        portfolio_id="PORT_MVO_PROD",
        objective=Objective(
            name="mvo_rebalance",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="risk_adjusted_return",
        ),
        context={
            "seed": 42,
            "portfolio_notional": 250_000_000,
            "target_return": 0.05,
            "risk_aversion": 3.0,
            "max_single_asset_weight": 0.45,
            "min_cash_weight": 0.02,
            "data_snapshot_id": "SNAP_MVO_001",
        },
    )

    result = AssetAllocationMVOProductionAdapter().run(request)

    assert result.optimizer_id == "production.asset_allocation.mvo"
    assert result.status == "optimal"
    assert result.allocations
    assert result.domain_attachments["expected_return"] >= 0.05
    assert result.evidence is not None
    assert result.evidence.data_snapshot_id == "SNAP_MVO_001"
    assert result.evidence.artifacts["model_config"]["optimizer_id"] == (
        "production.asset_allocation.mvo"
    )
    assert result.evidence.approvals[0]["status"] == "approved"
    assert result.evidence.artifacts["model_governance"]["passed"] is True


def test_production_adapter_blocks_unapproved_execution_mode_before_solve() -> None:
    request = OptimizationRequest(
        domain="asset_allocation",
        portfolio_id="PORT_MVO_EXECUTE_BLOCK",
        objective=Objective(
            name="mvo_rebalance",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="risk_adjusted_return",
        ),
        execution_mode=ExecutionMode.EXECUTE,
        context={
            "seed": 42,
            "portfolio_notional": 250_000_000,
            "target_return": 0.05,
        },
    )

    result = AssetAllocationMVOProductionAdapter().run(request)

    assert result.status == "blocked"
    assert result.evidence is not None
    assert result.evidence.artifacts["model_governance"]["passed"] is False
    assert "not approved for execution mode 'execute'" in (
        result.diagnostics["model_governance"]["blocking_issues"][0]
    )


def test_asset_allocation_mvo_adapter_reports_local_csv_data_sources() -> None:
    request = OptimizationRequest(
        domain="asset_allocation",
        portfolio_id="PORT_MVO_CSV",
        objective=Objective(
            name="mvo_rebalance",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="risk_adjusted_return",
        ),
        context={
            "portfolio_notional": 250_000_000,
            "target_return": 0.05,
            "risk_aversion": 3.0,
            "max_single_asset_weight": 0.45,
            "min_cash_weight": 0.02,
            "data_source": {
                "type": "csv",
                "assets": "examples/data/asset_allocation_assets.csv",
                "covariance": "examples/data/asset_allocation_covariance.csv",
            },
        },
    )

    result = AssetAllocationMVOProductionAdapter().run(request)

    assert result.status == "optimal"
    assert result.evidence is not None
    preflight = result.evidence.artifacts["preflight"]
    assert result.evidence.data_snapshot_id.startswith("DATA-ASSET_ALLOCATION-")
    assert preflight["checked_datasets"]["asset_universe"] == 6
    assert preflight["checked_datasets"]["covariance_matrix"] == 6
    assert {item["dataset"] for item in preflight["data_sources"]} == {
        "asset_universe",
        "covariance_matrix",
    }


def test_collateral_production_adapter_runs_native_optimizer() -> None:
    request = OptimizationRequest(
        domain="collateral",
        portfolio_id="PORT_COLLAT_PROD",
        objective=Objective(
            name="minimize_funding_cost",
            direction=ObjectiveDirection.MINIMIZE,
            metric="funding_cost",
        ),
        context={
            "seed": 42,
            "concentration_limit": 0.60,
            "solver_backend": "scipy",
            "problem_type": "lp",
            "data_snapshot_id": "SNAP_COLLATERAL_001",
        },
    )

    result = CollateralProductionAdapter().run(request)

    assert result.optimizer_id == "production.collateral.allocation"
    assert result.status == "optimal"
    assert result.allocations
    assert result.baseline_value > result.objective_value
    assert result.evidence is not None
    assert result.evidence.data_snapshot_id == "SNAP_COLLATERAL_001"
    assert result.evidence.artifacts["model_config"]["optimizer_id"] == (
        "production.collateral.allocation"
    )


def test_collateral_adapter_blocks_missing_declared_production_source() -> None:
    request = OptimizationRequest(
        domain="collateral",
        portfolio_id="PORT_COLLATERAL_SOURCE_BLOCK",
        objective=Objective(
            name="minimize_funding_cost",
            direction=ObjectiveDirection.MINIMIZE,
            metric="funding_cost",
        ),
        context={
            "production_data_sources": {
                "collateral_inventory": {
                    "type": "csv",
                    "path": "examples/data/collateral_assets.csv",
                }
            }
        },
    )

    result = CollateralProductionAdapter().run(request)

    assert result.status == "blocked"
    assert result.evidence is not None
    preflight = result.diagnostics["preflight"]
    assert preflight["data_quality"]["passed"] is False
    assert any(
        "margin_obligations source is missing" in item
        for item in preflight["blocking_issues"]
    )


def test_money_market_production_adapter_runs_native_optimizer() -> None:
    request = OptimizationRequest(
        domain="money_market",
        portfolio_id="PORT_MM_PROD",
        objective=Objective(
            name="maximize_yield",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="yield",
        ),
        context={
            "seed": 42,
            "total_cash": 500_000_000,
            "daily_liquidity_req": 0.30,
            "weekly_liquidity_req": 0.60,
            "max_prime_fraction": 0.40,
            "max_wam_days": 60,
            "max_single_fund": 0.50,
            "solver_backend": "scipy",
            "problem_type": "lp",
            "data_snapshot_id": "SNAP_MM_001",
        },
    )

    result = MoneyMarketProductionAdapter().run(request)

    assert result.optimizer_id == "production.money_market.allocation"
    assert result.status == "optimal"
    assert result.allocations
    assert result.domain_attachments["daily_liquidity"] >= 0.30
    assert result.evidence is not None
    assert result.evidence.data_snapshot_id == "SNAP_MM_001"
    assert result.evidence.artifacts["model_config"]["optimizer_id"] == (
        "production.money_market.allocation"
    )


def test_money_market_adapter_reports_explicit_production_data_sources() -> None:
    request = OptimizationRequest(
        domain="money_market",
        portfolio_id="PORT_MM_SOURCES",
        objective=Objective(
            name="maximize_yield",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="yield",
        ),
        context={
            "total_cash": 500_000_000,
            "daily_liquidity_req": 0.30,
            "weekly_liquidity_req": 0.60,
            "max_prime_fraction": 0.40,
            "max_wam_days": 60,
            "max_single_fund": 0.50,
            "solver_backend": "scipy",
            "problem_type": "lp",
            "data_source": {
                "type": "csv",
                "funds": "examples/data/mmf_universe.csv",
                "position": "examples/data/money_market_cash_position_production.csv",
            },
            "production_data_sources": {
                "money_market_fund_universe": {
                    "type": "csv",
                    "path": "examples/data/mmf_universe.csv",
                    "freshness_sla_hours": 1_000_000,
                },
                "cash_position": {
                    "type": "csv",
                    "path": "examples/data/money_market_cash_position_production.csv",
                    "freshness_sla_hours": 1_000_000,
                },
            },
        },
    )

    result = MoneyMarketProductionAdapter().run(request)

    assert result.status == "optimal"
    assert result.evidence is not None
    preflight = result.evidence.artifacts["preflight"]
    reports = {item["dataset"]: item for item in preflight["data_sources"]}
    assert reports["money_market_fund_universe"]["row_count"] == 8
    assert reports["money_market_fund_universe"]["content_hash"]
    assert reports["cash_position"]["row_count"] == 1
    assert preflight["data_quality"]["passed"] is True


def test_financing_production_adapter_runs_native_optimizer() -> None:
    request = OptimizationRequest(
        domain="financing",
        portfolio_id="PORT_FIN_PROD",
        objective=Objective(
            name="minimize_funding_spread",
            direction=ObjectiveDirection.MINIMIZE,
            metric="funding_spread",
        ),
        context={
            "seed": 42,
            "total_funding_need": 300_000_000,
            "max_cp_concentration": 0.40,
            "capital_budget_pct": 5.0,
            "solver_backend": "scipy",
            "problem_type": "lp",
            "data_snapshot_id": "SNAP_FIN_001",
        },
    )

    result = FinancingProductionAdapter().run(request)

    assert result.optimizer_id == "production.financing.allocation"
    assert result.status == "optimal"
    assert result.allocations
    assert result.baseline_value > result.objective_value
    assert result.domain_attachments["total_funding"] == pytest.approx(300_000_000)
    assert result.domain_attachments["counterparties_used"] > 0
    assert result.evidence is not None
    assert result.evidence.data_snapshot_id == "SNAP_FIN_001"
    assert result.evidence.artifacts["model_config"]["optimizer_id"] == (
        "production.financing.allocation"
    )


def test_financing_adapter_reports_local_csv_data_sources() -> None:
    request = OptimizationRequest(
        domain="financing",
        portfolio_id="PORT_FIN_SOURCES",
        objective=Objective(
            name="minimize_funding_spread",
            direction=ObjectiveDirection.MINIMIZE,
            metric="funding_spread",
        ),
        context={
            "max_cp_concentration": 0.40,
            "capital_budget_pct": 5.0,
            "solver_backend": "scipy",
            "problem_type": "lp",
            "data_source": {
                "type": "csv",
                "counterparties": "examples/data/financing_counterparties.csv",
                "needs": "examples/data/financing_needs.csv",
            },
        },
    )

    result = FinancingProductionAdapter().run(request)

    assert result.status == "optimal"
    assert result.evidence is not None
    preflight = result.evidence.artifacts["preflight"]
    reports = {item["dataset"]: item for item in preflight["data_sources"]}
    assert result.evidence.data_snapshot_id.startswith("DATA-FINANCING-")
    assert reports["financing_counterparties"]["row_count"] == 10
    assert reports["funding_needs"]["row_count"] == 3
    assert reports["financing_counterparties"]["content_hash"]


def test_cash_movement_production_adapter_routes_operational_cash() -> None:
    request = OptimizationRequest(
        domain="treasury_operations",
        portfolio_id="PORT_TREASURY_OPS",
        objective=Objective(
            name="minimize_cash_movement_cost",
            direction=ObjectiveDirection.MINIMIZE,
            metric="transfer_cost",
        ),
        context={
            "data_snapshot_id": "SNAP_CASHMOVE_001",
            "cutoff_hour": 15,
            "cash_balances": [
                {
                    "account_id": "SRC_1",
                    "entity": "Broker Dealer",
                    "currency": "USD",
                    "available_cash": 150_000_000,
                    "minimum_buffer": 20_000_000,
                },
                {
                    "account_id": "SRC_2",
                    "entity": "Bank Entity",
                    "currency": "USD",
                    "available_cash": 80_000_000,
                    "minimum_buffer": 15_000_000,
                },
            ],
            "funding_requirements": [
                {
                    "requirement_id": "PAY_A",
                    "target_account_id": "CLEARING_A",
                    "currency": "USD",
                    "required_cash": 90_000_000,
                    "cutoff_hour": 15,
                },
                {
                    "requirement_id": "PAY_B",
                    "target_account_id": "SETTLEMENT_B",
                    "currency": "USD",
                    "required_cash": 65_000_000,
                    "cutoff_hour": 16,
                },
            ],
            "payment_rails": [
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
            ],
        },
    )

    result = CashMovementProductionAdapter().run(request)

    assert result.optimizer_id == "production.treasury.cash_movement"
    assert result.status == "optimal"
    assert result.allocations
    assert result.baseline_value > result.objective_value
    assert result.domain_attachments["total_moved_cash"] == pytest.approx(155_000_000)
    assert result.evidence is not None
    assert result.evidence.data_snapshot_id == "SNAP_CASHMOVE_001"


def test_cash_movement_adapter_blocks_missing_declared_production_source() -> None:
    request = OptimizationRequest(
        domain="treasury_operations",
        portfolio_id="PORT_CASH_SOURCE_BLOCK",
        objective=Objective(
            name="minimize_transfer_cost",
            direction=ObjectiveDirection.MINIMIZE,
            metric="transfer_cost",
        ),
        context={
            "production_data_sources": {
                "cash_balances": {
                    "type": "csv",
                    "path": "examples/data/cash_position.csv",
                }
            }
        },
    )

    result = CashMovementProductionAdapter().run(request)

    assert result.status == "blocked"
    assert result.evidence is not None
    preflight = result.diagnostics["preflight"]
    assert preflight["data_quality"]["passed"] is False
    assert any(
        "funding_requirements source is missing" in item
        for item in preflight["blocking_issues"]
    )


def test_margin_call_workflow_adapter_prioritizes_queue_within_capacity() -> None:
    request = OptimizationRequest(
        domain="margin_operations",
        portfolio_id="PORT_MARGIN_OPS",
        objective=Objective(
            name="minimize_sla_breach_risk",
            direction=ObjectiveDirection.MINIMIZE,
            metric="residual_risk",
        ),
        context={
            "data_snapshot_id": "SNAP_MARGIN_001",
            "team_capacity_minutes": 150,
            "materiality_threshold": 25_000_000,
            "margin_call_queue": [
                {
                    "call_id": "MC_A",
                    "counterparty": "Dealer A",
                    "amount": 40_000_000,
                    "due_in_hours": 2,
                    "dispute_probability": 0.20,
                    "ops_minutes": 80,
                    "risk_tier": "high",
                },
                {
                    "call_id": "MC_B",
                    "counterparty": "CCP B",
                    "amount": 70_000_000,
                    "due_in_hours": 1,
                    "dispute_probability": 0.05,
                    "ops_minutes": 70,
                    "risk_tier": "critical",
                },
                {
                    "call_id": "MC_C",
                    "counterparty": "Dealer C",
                    "amount": 15_000_000,
                    "due_in_hours": 8,
                    "dispute_probability": 0.60,
                    "ops_minutes": 90,
                    "risk_tier": "medium",
                },
            ],
        },
    )

    result = MarginCallWorkflowProductionAdapter().run(request)

    assert result.optimizer_id == "production.margin_call.workflow"
    assert result.status == "optimal"
    assert [row["metadata"]["call_id"] for row in result.allocations] == ["MC_B", "MC_A"]
    assert result.binding_constraints == ["team_capacity"]
    assert result.domain_attachments["capacity_used"] == pytest.approx(150)
    assert result.evidence is not None
    assert result.evidence.data_snapshot_id == "SNAP_MARGIN_001"


def test_margin_call_adapter_blocks_missing_declared_production_source() -> None:
    request = OptimizationRequest(
        domain="margin_operations",
        portfolio_id="PORT_MARGIN_SOURCE_BLOCK",
        objective=Objective(
            name="prioritize_margin_calls",
            direction=ObjectiveDirection.MINIMIZE,
            metric="residual_queue_risk",
        ),
        context={
            "production_data_sources": {
                "margin_call_queue": {
                    "type": "csv",
                    "path": "examples/data/financing_needs.csv",
                }
            }
        },
    )

    result = MarginCallWorkflowProductionAdapter().run(request)

    assert result.status == "blocked"
    assert result.evidence is not None
    preflight = result.diagnostics["preflight"]
    assert preflight["data_quality"]["passed"] is False
    assert any("ops_capacity source is missing" in item for item in preflight["blocking_issues"])


def test_default_production_registry_contains_current_adapters() -> None:
    registry = build_default_production_registry()

    assert registry.list_ids() == [
        "production.asset_allocation.mvo",
        "production.collateral.allocation",
        "production.financing.allocation",
        "production.margin_call.workflow",
        "production.money_market.allocation",
        "production.treasury.cash_movement",
    ]
