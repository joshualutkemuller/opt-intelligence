"""Production model config for treasury cash-movement optimization."""

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


def cash_movement_optimizer_config() -> ModelConfigSpec:
    """Return the production-facing model factsheet for cash movement."""

    return ModelConfigSpec(
        optimizer_id="production.treasury.cash_movement",
        domain="treasury_operations",
        lineage=ModelLineageSpec(
            model_name="Treasury Cash Movement Optimizer",
            model_version="0.1.0",
            config_version="2026.07.19",
            owner="treasury-operations-quant",
            approved_for=["explain", "scenario_analysis", "recommendation"],
        ),
        objectives=[
            ObjectiveTermSpec(
                name="transfer_cost",
                direction="minimize",
                weight=1.0,
                units="currency",
                description=(
                    "Minimize movement cost across payment rails while satisfying "
                    "entity funding needs before cutoff."
                ),
            ),
            ObjectiveTermSpec(
                name="cutoff_risk",
                direction="minimize",
                weight=0.35,
                units="risk_score",
                description="Prefer rails and routes with lower cutoff and settlement risk.",
            ),
        ],
        constraints=[
            ConstraintFamilySpec(
                name="funding_requirements",
                constraint_type="budget",
                hard=True,
                limit_source="funding_needs",
                description=(
                    "Each target account must receive enough cash to cover required funding."
                ),
            ),
            ConstraintFamilySpec(
                name="source_liquidity_buffer",
                constraint_type="liquidity",
                hard=True,
                tolerance=1e-6,
                limit_source="cash_balances",
                description="Source accounts must retain minimum operating liquidity buffers.",
            ),
            ConstraintFamilySpec(
                name="payment_cutoff",
                constraint_type="custom",
                hard=True,
                limit_source="payment_rail_calendar",
                description=(
                    "Only payment rails available before the target cutoff may be selected."
                ),
            ),
            ConstraintFamilySpec(
                name="rail_capacity",
                constraint_type="bounds",
                hard=True,
                limit_source="payment_rail_limits",
                description=(
                    "Payment rail daily limits and per-transfer maximums must be respected."
                ),
            ),
        ],
        limit_sources=[
            LimitSourceSpec(
                name="cash_balances",
                source_type="market_data",
                owner="treasury-ops",
                refresh_frequency="intraday",
            ),
            LimitSourceSpec(
                name="funding_needs",
                source_type="manual",
                owner="cash-management",
                refresh_frequency="intraday",
            ),
            LimitSourceSpec(
                name="payment_rail_calendar",
                source_type="policy",
                owner="payment-operations",
                refresh_frequency="daily",
            ),
            LimitSourceSpec(
                name="payment_rail_limits",
                source_type="policy",
                owner="treasury-controls",
                refresh_frequency="on policy change",
            ),
        ],
        scenario_knobs=[
            ScenarioKnobSpec(
                name="cutoff_hour",
                value_type="number",
                default=15,
                description="Latest local settlement cutoff hour for same-day movement.",
            ),
            ScenarioKnobSpec(
                name="liquidity_buffer_pct",
                value_type="percent",
                default=0.05,
                description="Minimum source-account liquidity buffer after transfers.",
            ),
            ScenarioKnobSpec(
                name="stress_multiplier",
                value_type="number",
                default=1.0,
                description="Multiplier applied to target funding needs for stress scenarios.",
            ),
        ],
        data_contract=DataContractSpec(
            required_datasets=["cash_balances", "funding_requirements", "payment_rails"],
            optional_datasets=["holiday_calendar", "entity_transfer_limits"],
            primary_keys={
                "cash_balances": ["account_id"],
                "funding_requirements": ["requirement_id"],
                "payment_rails": ["rail_id"],
            },
            required_columns={
                "cash_balances": [
                    "account_id",
                    "entity",
                    "currency",
                    "available_cash",
                    "minimum_buffer",
                ],
                "funding_requirements": [
                    "requirement_id",
                    "target_account_id",
                    "currency",
                    "required_cash",
                    "cutoff_hour",
                ],
                "payment_rails": [
                    "rail_id",
                    "currency",
                    "fee_bps",
                    "fixed_fee",
                    "cutoff_hour",
                    "max_transfer",
                ],
            },
            quality_checks=[
                "cash balances are nonnegative",
                "funding requirements are positive",
                "source buffers do not exceed available cash",
                "at least one open rail exists for each currency",
            ],
            snapshot_required=True,
        ),
        solver=SolverBackendSpec(
            backend="adapter_native",
            problem_family="custom",
            vendor="internal",
            version="demo-routing-v0",
            parameters={"allocation_rule": "least_cost_cutoff_feasible"},
        ),
        execution=ExecutionIsolationSpec(mode="in_process", timeout_seconds=45),
        metadata={
            "native_optimizer": "cash_movement_route_selector",
            "objective_formula": "sum(amount * fee_bps / 10000 + fixed_fee + cutoff_penalty)",
        },
    )
