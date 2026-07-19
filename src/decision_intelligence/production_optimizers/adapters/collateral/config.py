"""Production model config for the collateral optimizer."""

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


def collateral_optimizer_config() -> ModelConfigSpec:
    """Return the production-facing model factsheet for collateral allocation."""

    return ModelConfigSpec(
        optimizer_id="production.collateral.allocation",
        domain="collateral",
        lineage=ModelLineageSpec(
            model_name="Collateral Allocation Optimizer",
            model_version="0.1.0",
            config_version="2026.07.18",
            owner="secured-financing-quant",
            approved_for=["explain", "scenario_analysis", "recommendation"],
        ),
        objectives=[
            ObjectiveTermSpec(
                name="funding_cost",
                direction="minimize",
                weight=1.0,
                units="annual_usd",
                description="Funding cost in basis points times allocated market value.",
            ),
            ObjectiveTermSpec(
                name="haircut_cost",
                direction="minimize",
                weight=1.0,
                units="annual_usd_proxy",
                description="Alternative objective that proxies cost through collateral haircuts.",
            ),
        ],
        constraints=[
            ConstraintFamilySpec(
                name="inventory",
                constraint_type="budget",
                hard=True,
                tolerance=1e-6,
                limit_source="collateral_inventory",
                description="No asset can be allocated beyond available inventory.",
            ),
            ConstraintFamilySpec(
                name="coverage",
                constraint_type="regulatory",
                hard=True,
                tolerance=1e-4,
                limit_source="margin_obligations",
                description="Haircut-adjusted collateral value must cover each obligation.",
            ),
            ConstraintFamilySpec(
                name="eligibility",
                constraint_type="regulatory",
                hard=True,
                tolerance=0.0,
                limit_source="eligibility_rules",
                description="Assets may only be posted where eligible.",
            ),
            ConstraintFamilySpec(
                name="concentration",
                constraint_type="custom",
                hard=True,
                tolerance=1e-6,
                limit_source="collateral_policy",
                description="Asset-class concentration is capped per obligation.",
            ),
        ],
        limit_sources=[
            LimitSourceSpec(
                name="collateral_inventory",
                source_type="market_data",
                owner="collateral-ops",
                refresh_frequency="intraday",
            ),
            LimitSourceSpec(
                name="margin_obligations",
                source_type="market_data",
                owner="margin-ops",
                refresh_frequency="intraday",
            ),
            LimitSourceSpec(
                name="eligibility_rules",
                source_type="regulatory",
                owner="legal-and-ops",
                refresh_frequency="daily",
            ),
            LimitSourceSpec(
                name="collateral_policy",
                source_type="policy",
                owner="treasury-risk",
                refresh_frequency="on policy change",
            ),
        ],
        scenario_knobs=[
            ScenarioKnobSpec(
                name="concentration_limit",
                value_type="percent",
                default=0.60,
                description="Maximum obligation exposure from one collateral asset class.",
            ),
            ScenarioKnobSpec(
                name="inventory_scale",
                value_type="number",
                default=1.0,
                description="Scenario multiplier for available collateral inventory.",
            ),
            ScenarioKnobSpec(
                name="obligation_scale",
                value_type="number",
                default=1.0,
                description="Scenario multiplier for required collateral obligations.",
            ),
        ],
        data_contract=DataContractSpec(
            required_datasets=["collateral_inventory", "margin_obligations"],
            optional_datasets=["eligibility_overrides", "haircut_policy"],
            primary_keys={
                "collateral_inventory": ["asset_id"],
                "margin_obligations": ["obligation_id"],
            },
            required_columns={
                "collateral_inventory": [
                    "asset_id",
                    "asset_class",
                    "market_value",
                    "haircut",
                    "funding_cost_bps",
                    "eligible",
                ],
                "margin_obligations": [
                    "obligation_id",
                    "counterparty",
                    "required_value",
                    "eligible_asset_classes",
                    "venue_type",
                    "agreement_type",
                ],
            },
            quality_checks=[
                "market values are nonnegative",
                "haircuts are between 0 and 1",
                "each obligation has at least one eligible asset class",
                "at least one eligible asset exists",
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
            "native_optimizer": "decision_intelligence.optimizers.CollateralOptimizer",
            "objective_formula": (
                "sum(funding_cost_bps * market_value * allocation_fraction) / 10000"
            ),
        },
    )
