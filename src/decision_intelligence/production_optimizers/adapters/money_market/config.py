"""Production model config for the money-market optimizer."""

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


def money_market_optimizer_config() -> ModelConfigSpec:
    """Return the production-facing model factsheet for money-market allocation."""

    return ModelConfigSpec(
        optimizer_id="production.money_market.allocation",
        domain="money_market",
        lineage=ModelLineageSpec(
            model_name="Money Market Allocation Optimizer",
            model_version="0.1.0",
            config_version="2026.07.18",
            owner="treasury-liquidity-quant",
            approved_for=["explain", "scenario_analysis", "recommendation"],
        ),
        objectives=[
            ObjectiveTermSpec(
                name="net_yield",
                direction="maximize",
                weight=1.0,
                units="annual_percent",
                description="Weighted 7-day yield across eligible money-market funds.",
            )
        ],
        constraints=[
            ConstraintFamilySpec(
                name="cash_budget",
                constraint_type="budget",
                hard=True,
                tolerance=1e-6,
                limit_source="cash_position",
                description="Portfolio weights must sum to the available cash balance.",
            ),
            ConstraintFamilySpec(
                name="daily_liquidity",
                constraint_type="liquidity",
                hard=True,
                tolerance=1e-4,
                limit_source="liquidity_policy",
                description="Weighted daily liquidity must meet or exceed the policy floor.",
            ),
            ConstraintFamilySpec(
                name="weekly_liquidity",
                constraint_type="liquidity",
                hard=True,
                tolerance=1e-4,
                limit_source="liquidity_policy",
                description="Weighted weekly liquidity must meet or exceed the policy floor.",
            ),
            ConstraintFamilySpec(
                name="prime_concentration",
                constraint_type="regulatory",
                hard=True,
                tolerance=1e-6,
                limit_source="liquidity_policy",
                description="Prime fund exposure is capped by mandate.",
            ),
            ConstraintFamilySpec(
                name="wam_limit",
                constraint_type="risk",
                hard=True,
                tolerance=1e-6,
                limit_source="liquidity_policy",
                description="Weighted-average maturity must remain below the policy cap.",
            ),
            ConstraintFamilySpec(
                name="single_fund_limit",
                constraint_type="bounds",
                hard=True,
                tolerance=1e-6,
                limit_source="liquidity_policy",
                description="No single fund may exceed the concentration limit.",
            ),
        ],
        limit_sources=[
            LimitSourceSpec(
                name="fund_universe",
                source_type="market_data",
                owner="investment-ops",
                refresh_frequency="daily",
            ),
            LimitSourceSpec(
                name="cash_position",
                source_type="market_data",
                owner="treasury-ops",
                refresh_frequency="intraday",
            ),
            LimitSourceSpec(
                name="liquidity_policy",
                source_type="policy",
                owner="treasury-risk",
                refresh_frequency="on policy change",
            ),
        ],
        scenario_knobs=[
            ScenarioKnobSpec(
                name="total_cash",
                value_type="currency",
                default=500_000_000,
                description="Cash notional to allocate across eligible funds.",
            ),
            ScenarioKnobSpec(
                name="daily_liquidity_req",
                value_type="percent",
                default=0.30,
                description="Minimum weighted daily liquidity floor.",
            ),
            ScenarioKnobSpec(
                name="weekly_liquidity_req",
                value_type="percent",
                default=0.60,
                description="Minimum weighted weekly liquidity floor.",
            ),
            ScenarioKnobSpec(
                name="max_prime_fraction",
                value_type="percent",
                default=0.40,
                description="Maximum allocation to prime funds.",
            ),
            ScenarioKnobSpec(
                name="max_wam_days",
                value_type="number",
                default=60,
                description="Portfolio WAM cap in days.",
            ),
            ScenarioKnobSpec(
                name="max_funds",
                value_type="number",
                default=4,
                description="Optional MILP fund-count limit.",
            ),
        ],
        data_contract=DataContractSpec(
            required_datasets=["money_market_fund_universe", "cash_position"],
            optional_datasets=["fund_eligibility_overrides", "liquidity_policy_limits"],
            primary_keys={
                "money_market_fund_universe": ["fund_id"],
                "cash_position": ["portfolio_id"],
            },
            required_columns={
                "money_market_fund_universe": [
                    "fund_id",
                    "label",
                    "yield_7day",
                    "daily_liquidity_pct",
                    "weekly_liquidity_pct",
                    "wam_days",
                    "credit_quality",
                    "min_investment",
                ],
                "cash_position": [
                    "portfolio_id",
                    "total_cash",
                    "daily_liquidity_requirement",
                    "weekly_liquidity_requirement",
                ],
            },
            quality_checks=[
                "fund yields are finite",
                "liquidity percentages are between 0 and 1",
                "WAM values are nonnegative",
                "cash balance is positive",
                "at least one eligible fund is available",
            ],
            snapshot_required=True,
        ),
        solver=SolverBackendSpec(
            backend="scipy",
            problem_family="lp",
            vendor="scipy",
            version="HiGHS",
            parameters={"method": "highs", "supports_milp": True},
        ),
        execution=ExecutionIsolationSpec(mode="in_process", timeout_seconds=60),
        metadata={
            "native_optimizer": "decision_intelligence.optimizers.MoneyMarketOptimizer",
            "objective_formula": "sum(yield_7day_i * allocation_weight_i)",
        },
    )
