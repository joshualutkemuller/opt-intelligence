"""Production model config for margin-call workflow optimization."""

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


def margin_call_workflow_optimizer_config() -> ModelConfigSpec:
    """Return the production-facing model factsheet for margin-call operations."""

    return ModelConfigSpec(
        optimizer_id="production.margin_call.workflow",
        domain="margin_operations",
        lineage=ModelLineageSpec(
            model_name="Margin Call Workflow Optimizer",
            model_version="0.1.0",
            config_version="2026.07.19",
            owner="margin-operations-quant",
            approved_for=["explain", "scenario_analysis", "recommendation"],
        ),
        objectives=[
            ObjectiveTermSpec(
                name="sla_breach_risk",
                direction="minimize",
                weight=1.0,
                units="risk_score",
                description=(
                    "Minimize residual SLA and exposure risk by prioritizing the "
                    "highest-impact margin calls within operational capacity."
                ),
            ),
            ObjectiveTermSpec(
                name="manual_effort",
                direction="minimize",
                weight=0.20,
                units="minutes",
                description="Prefer action plans that fit available reviewer capacity.",
            ),
        ],
        constraints=[
            ConstraintFamilySpec(
                name="team_capacity",
                constraint_type="budget",
                hard=True,
                limit_source="ops_capacity",
                description="Assigned calls must fit available analyst capacity.",
            ),
            ConstraintFamilySpec(
                name="sla_cutoff",
                constraint_type="custom",
                hard=True,
                tolerance=0.0,
                limit_source="margin_sla_policy",
                description="Calls close to SLA breach receive priority and escalation.",
            ),
            ConstraintFamilySpec(
                name="counterparty_escalation",
                constraint_type="risk",
                hard=False,
                tolerance=0.05,
                limit_source="counterparty_risk_policy",
                description=(
                    "High-risk counterparties and disputed calls require escalation evidence."
                ),
            ),
            ConstraintFamilySpec(
                name="approval_required",
                constraint_type="regulatory",
                hard=True,
                limit_source="margin_governance_policy",
                description="Material calls above threshold require supervisor review.",
            ),
        ],
        limit_sources=[
            LimitSourceSpec(
                name="margin_call_queue",
                source_type="manual",
                owner="margin-operations",
                refresh_frequency="intraday",
            ),
            LimitSourceSpec(
                name="ops_capacity",
                source_type="manual",
                owner="operations-management",
                refresh_frequency="daily",
            ),
            LimitSourceSpec(
                name="margin_sla_policy",
                source_type="policy",
                owner="operations-risk",
                refresh_frequency="on policy change",
            ),
            LimitSourceSpec(
                name="counterparty_risk_policy",
                source_type="risk_model",
                owner="counterparty-risk",
                refresh_frequency="daily",
            ),
        ],
        scenario_knobs=[
            ScenarioKnobSpec(
                name="team_capacity_minutes",
                value_type="number",
                default=420,
                description="Available analyst minutes for the prioritization window.",
            ),
            ScenarioKnobSpec(
                name="materiality_threshold",
                value_type="currency",
                default=25_000_000,
                description="Call size that triggers supervisor review.",
            ),
            ScenarioKnobSpec(
                name="dispute_stress_multiplier",
                value_type="number",
                default=1.0,
                description="Multiplier applied to dispute probability under stress.",
            ),
        ],
        data_contract=DataContractSpec(
            required_datasets=["margin_call_queue", "ops_capacity"],
            optional_datasets=["counterparty_risk_scores", "holiday_calendar"],
            primary_keys={
                "margin_call_queue": ["call_id"],
                "ops_capacity": ["desk_id"],
            },
            required_columns={
                "margin_call_queue": [
                    "call_id",
                    "counterparty",
                    "amount",
                    "due_in_hours",
                    "dispute_probability",
                    "ops_minutes",
                    "risk_tier",
                ],
                "ops_capacity": ["desk_id", "available_minutes"],
            },
            quality_checks=[
                "call amounts are nonnegative",
                "due-in hours are finite",
                "dispute probabilities are between 0 and 1",
                "operations minutes are positive",
                "team capacity is positive",
            ],
            snapshot_required=True,
        ),
        solver=SolverBackendSpec(
            backend="adapter_native",
            problem_family="custom",
            vendor="internal",
            version="demo-priority-v0",
            parameters={"priority_rule": "exposure_sla_dispute_weighted_score"},
        ),
        execution=ExecutionIsolationSpec(mode="in_process", timeout_seconds=45),
        metadata={
            "native_optimizer": "margin_call_priority_selector",
            "objective_formula": "residual_risk = total_queue_risk - assigned_risk_reduction",
        },
    )
