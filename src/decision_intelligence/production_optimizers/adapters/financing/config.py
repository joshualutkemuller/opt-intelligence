"""Production model config for the financing optimizer."""

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


def financing_optimizer_config() -> ModelConfigSpec:
    """Return the production-facing model factsheet for financing allocation."""

    return ModelConfigSpec(
        optimizer_id="production.financing.allocation",
        domain="financing",
        lineage=ModelLineageSpec(
            model_name="Financing Source Optimizer",
            model_version="0.1.0",
            config_version="2026.07.19",
            owner="secured-financing-quant",
            approved_for=["explain", "scenario_analysis", "recommendation"],
        ),
        objectives=[
            ObjectiveTermSpec(
                name="funding_spread_cost",
                direction="minimize",
                weight=1.0,
                units="usd_annualized_cost",
                description=(
                    "Minimize spread cost across eligible financing counterparties "
                    "for each funding need."
                ),
            ),
            ObjectiveTermSpec(
                name="capital_usage",
                direction="minimize",
                weight=0.0,
                units="rwa_percent_of_notional",
                description=(
                    "Optional objective mode that minimizes capital usage instead "
                    "of funding spread."
                ),
            ),
        ],
        constraints=[
            ConstraintFamilySpec(
                name="funding_need_coverage",
                constraint_type="budget",
                hard=True,
                tolerance=1e-4,
                limit_source="funding_needs",
                description="Each position funding need must be fully sourced.",
            ),
            ConstraintFamilySpec(
                name="counterparty_capacity",
                constraint_type="bounds",
                hard=True,
                tolerance=1e-4,
                limit_source="counterparty_limits",
                description="Counterparty allocations cannot exceed available capacity.",
            ),
            ConstraintFamilySpec(
                name="tenor_compatibility",
                constraint_type="custom",
                hard=True,
                tolerance=0.0,
                limit_source="counterparty_terms",
                description="Funding source tenor windows must support required tenor.",
            ),
            ConstraintFamilySpec(
                name="single_counterparty_concentration",
                constraint_type="risk",
                hard=True,
                tolerance=1e-4,
                limit_source="treasury_policy",
                description="No counterparty may exceed the configured share of total funding.",
            ),
            ConstraintFamilySpec(
                name="capital_budget",
                constraint_type="regulatory",
                hard=True,
                tolerance=1e-4,
                limit_source="capital_policy",
                description="Total capital usage must remain inside the configured budget.",
            ),
        ],
        limit_sources=[
            LimitSourceSpec(
                name="counterparty_limits",
                source_type="policy",
                owner="secured-financing-ops",
                refresh_frequency="intraday",
            ),
            LimitSourceSpec(
                name="counterparty_terms",
                source_type="market_data",
                owner="secured-financing-ops",
                refresh_frequency="daily",
            ),
            LimitSourceSpec(
                name="funding_needs",
                source_type="market_data",
                owner="treasury-desk",
                refresh_frequency="intraday",
            ),
            LimitSourceSpec(
                name="treasury_policy",
                source_type="policy",
                owner="treasury-risk",
                refresh_frequency="on policy change",
            ),
            LimitSourceSpec(
                name="capital_policy",
                source_type="regulatory",
                owner="finance-capital-management",
                refresh_frequency="monthly",
            ),
        ],
        scenario_knobs=[
            ScenarioKnobSpec(
                name="total_funding_need",
                value_type="currency",
                default=300_000_000,
                description="Aggregate notional requiring financing.",
            ),
            ScenarioKnobSpec(
                name="capacity_scale",
                value_type="number",
                default=1.0,
                description="Stress multiplier applied to available counterparty capacity.",
            ),
            ScenarioKnobSpec(
                name="spread_shift",
                value_type="number",
                default=1.0,
                description="Stress multiplier applied to financing spreads.",
            ),
            ScenarioKnobSpec(
                name="max_cp_concentration",
                value_type="percent",
                default=0.40,
                description="Maximum share of total funding from a single counterparty.",
            ),
            ScenarioKnobSpec(
                name="capital_budget_pct",
                value_type="percent",
                default=5.0,
                description="Capital usage budget as a percent of total funding.",
            ),
        ],
        data_contract=DataContractSpec(
            required_datasets=["financing_counterparties", "funding_needs"],
            optional_datasets=["counterparty_eligibility", "capital_policy_limits"],
            primary_keys={
                "financing_counterparties": ["counterparty_id"],
                "funding_needs": ["position_id"],
            },
            required_columns={
                "financing_counterparties": [
                    "counterparty_id",
                    "name",
                    "instrument",
                    "spread_bps",
                    "capacity",
                    "min_tenor_days",
                    "max_tenor_days",
                    "capital_usage_pct",
                ],
                "funding_needs": [
                    "position_id",
                    "instrument_type",
                    "notional",
                    "required_tenor_days",
                    "preferred_instrument",
                ],
            },
            quality_checks=[
                "funding notionals are positive",
                "counterparty capacities are nonnegative",
                "spread and capital usage values are finite",
                "tenor minimum is less than or equal to tenor maximum",
                "each funding need has at least one tenor-compatible counterparty",
            ],
            snapshot_required=True,
        ),
        solver=SolverBackendSpec(
            backend="scipy",
            problem_family="lp",
            vendor="scipy",
            version="HiGHS",
            parameters={"method": "highs"},
        ),
        execution=ExecutionIsolationSpec(mode="in_process", timeout_seconds=60),
        metadata={
            "native_optimizer": "decision_intelligence.optimizers.FinancingOptimizer",
            "objective_formula": "sum(spread_bps_i * funding_amount_ij / 10000)",
        },
    )
