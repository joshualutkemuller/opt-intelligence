"""Tests for the production optimizer adapter scaffold."""

from typing import Any

import pytest

from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.production_optimizers import (
    ConstraintFamilySpec,
    DataContractSpec,
    ExecutionIsolationSpec,
    ModelConfigSpec,
    ModelLineageSpec,
    NormalizedOptimizerResult,
    ObjectiveTermSpec,
    PreflightReport,
    ProductionOptimizerAdapter,
    ProductionOptimizerEvidence,
    ProductionOptimizerRegistry,
    SolverBackendSpec,
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
