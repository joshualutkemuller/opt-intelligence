"""Production model config for Asset Allocation MVO."""

from decision_intelligence.production_optimizers.contracts import (
    ConstraintFamilySpec,
    DataContractSpec,
    ExecutionIsolationSpec,
    LimitSourceSpec,
    ModelConfigSpec,
    ModelLineageSpec,
    ObjectiveTermSpec,
    ScenarioKnobSpec,
    SolverBackendSpec,
)


def asset_allocation_mvo_config() -> ModelConfigSpec:
    """Return the production-facing model factsheet for Asset Allocation MVO."""

    return ModelConfigSpec(
        optimizer_id="production.asset_allocation.mvo",
        domain="asset_allocation",
        lineage=ModelLineageSpec(
            model_name="Asset Allocation MVO",
            model_version="0.1.0",
            config_version="2026.07.18",
            owner="quant-research",
            approved_for=["explain", "scenario_analysis", "recommendation"],
        ),
        objectives=[
            ObjectiveTermSpec(
                name="expected_return",
                direction="maximize",
                weight=1.0,
                units="annual_return",
                description="Annualized expected return from asset-class assumptions.",
            ),
            ObjectiveTermSpec(
                name="portfolio_variance",
                direction="minimize",
                weight=3.0,
                units="annual_variance",
                description="Risk penalty scaled by the risk_aversion context parameter.",
            ),
        ],
        constraints=[
            ConstraintFamilySpec(
                name="fully_invested",
                constraint_type="budget",
                hard=True,
                tolerance=1e-5,
                description="Portfolio weights must sum to 100%.",
            ),
            ConstraintFamilySpec(
                name="asset_bounds",
                constraint_type="bounds",
                hard=True,
                tolerance=1e-5,
                limit_source="asset_policy_limits",
                description="Each asset class observes configured min/max weights.",
            ),
            ConstraintFamilySpec(
                name="target_return",
                constraint_type="risk",
                hard=True,
                tolerance=1e-5,
                limit_source="portfolio_policy",
                description="Optional annual target return floor.",
            ),
            ConstraintFamilySpec(
                name="cash_floor",
                constraint_type="liquidity",
                hard=True,
                tolerance=1e-5,
                limit_source="portfolio_policy",
                description="Minimum allocation to cash or cash-like liquidity.",
            ),
        ],
        limit_sources=[
            LimitSourceSpec(
                name="asset_policy_limits",
                source_type="policy",
                owner="investment-policy",
                refresh_frequency="on policy change",
            ),
            LimitSourceSpec(
                name="portfolio_policy",
                source_type="policy",
                owner="cio-office",
                refresh_frequency="on mandate change",
            ),
        ],
        scenario_knobs=[
            ScenarioKnobSpec(
                name="risk_aversion",
                value_type="number",
                default=3.0,
                description="Variance penalty multiplier in the MVO utility objective.",
            ),
            ScenarioKnobSpec(
                name="target_return",
                value_type="percent",
                default=None,
                description="Optional minimum annual expected return.",
            ),
            ScenarioKnobSpec(
                name="max_single_asset_weight",
                value_type="percent",
                default=0.45,
                description="Cap applied to each asset-class allocation.",
            ),
            ScenarioKnobSpec(
                name="min_cash_weight",
                value_type="percent",
                default=0.02,
                description="Minimum allocation to cash.",
            ),
        ],
        data_contract=DataContractSpec(
            required_datasets=["asset_universe", "covariance_matrix"],
            optional_datasets=["current_portfolio"],
            primary_keys={"asset_universe": ["asset_id"]},
            required_columns={
                "asset_universe": [
                    "asset_id",
                    "expected_return",
                    "volatility",
                    "current_weight",
                    "min_weight",
                    "max_weight",
                ],
                "covariance_matrix": ["asset_id", "covariances"],
            },
            quality_checks=[
                "asset weights are nonnegative",
                "current weights sum to a positive number",
                "covariance matrix is square",
                "covariance matrix dimension matches asset universe",
            ],
            snapshot_required=True,
        ),
        solver=SolverBackendSpec(
            backend="scipy",
            problem_family="qp",
            vendor="scipy",
            version="SLSQP",
            parameters={"ftol": 1e-10, "maxiter": 500},
        ),
        execution=ExecutionIsolationSpec(mode="in_process", timeout_seconds=60),
        metadata={
            "native_optimizer": "decision_intelligence.optimizers.AssetAllocationMVOOptimizer",
            "objective_formula": "expected_return - risk_aversion * variance",
        },
    )
