"""Typed production optimizer adapter contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ObjectiveTermSpec(BaseModel):
    name: str
    direction: Literal["minimize", "maximize"]
    weight: float = 1.0
    units: str = ""
    description: str = ""


class ConstraintFamilySpec(BaseModel):
    name: str
    constraint_type: Literal[
        "budget",
        "bounds",
        "liquidity",
        "risk",
        "turnover",
        "regulatory",
        "custom",
    ]
    hard: bool = True
    tolerance: float = 0.0
    limit_source: str | None = None
    description: str = ""


class LimitSourceSpec(BaseModel):
    name: str
    source_type: Literal["policy", "regulatory", "market_data", "risk_model", "manual"]
    owner: str = ""
    refresh_frequency: str = ""
    evidence_required: bool = True


class ScenarioKnobSpec(BaseModel):
    name: str
    value_type: Literal["number", "percent", "currency", "boolean", "string"]
    default: Any = None
    allowed_values: list[Any] = Field(default_factory=list)
    description: str = ""


class DataContractSpec(BaseModel):
    required_datasets: list[str] = Field(default_factory=list)
    optional_datasets: list[str] = Field(default_factory=list)
    primary_keys: dict[str, list[str]] = Field(default_factory=dict)
    required_columns: dict[str, list[str]] = Field(default_factory=dict)
    quality_checks: list[str] = Field(default_factory=list)
    snapshot_required: bool = True


class SolverBackendSpec(BaseModel):
    backend: str
    problem_family: Literal["lp", "milp", "qp", "nlp", "conic", "simulation", "custom"]
    vendor: str = ""
    version: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class ExecutionIsolationSpec(BaseModel):
    mode: Literal["in_process", "subprocess", "rest", "grpc", "batch", "container"]
    timeout_seconds: int = 300
    retry_count: int = 0
    resource_profile: str = "standard"
    endpoint: str | None = None
    command: list[str] = Field(default_factory=list)
    container_image: str | None = None


class ModelLineageSpec(BaseModel):
    model_name: str
    model_version: str
    config_version: str
    owner: str = ""
    approved_for: list[str] = Field(default_factory=list)
    change_ticket: str | None = None


class ModelConfigSpec(BaseModel):
    optimizer_id: str
    domain: str
    lineage: ModelLineageSpec
    objectives: list[ObjectiveTermSpec]
    constraints: list[ConstraintFamilySpec] = Field(default_factory=list)
    limit_sources: list[LimitSourceSpec] = Field(default_factory=list)
    scenario_knobs: list[ScenarioKnobSpec] = Field(default_factory=list)
    data_contract: DataContractSpec
    solver: SolverBackendSpec
    execution: ExecutionIsolationSpec
    metadata: dict[str, Any] = Field(default_factory=dict)


class PreflightReport(BaseModel):
    passed: bool
    data_snapshot_id: str | None = None
    reproducibility_fingerprint: str | None = None
    warnings: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    checked_datasets: dict[str, int] = Field(default_factory=dict)
    checked_limits: dict[str, Any] = Field(default_factory=dict)


class ProductionOptimizerEvidence(BaseModel):
    optimizer_id: str
    model_version: str
    config_version: str
    data_snapshot_id: str | None = None
    solver_version: str | None = None
    reproducibility_fingerprint: str | None = None
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)


class NormalizedOptimizerResult(BaseModel):
    optimizer_id: str
    domain: str
    status: Literal["optimal", "feasible", "infeasible", "error", "blocked"]
    objective_value: float
    baseline_value: float
    allocations: list[dict[str, Any]] = Field(default_factory=list)
    binding_constraints: list[str] = Field(default_factory=list)
    duals: dict[str, float] = Field(default_factory=dict)
    shadow_prices: dict[str, float] = Field(default_factory=dict)
    infeasibility_diagnostics: dict[str, Any] = Field(default_factory=dict)
    frontier_points: list[dict[str, Any]] = Field(default_factory=list)
    scenario_grid: list[dict[str, Any]] = Field(default_factory=list)
    turnover: dict[str, Any] = Field(default_factory=dict)
    transaction_costs: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    domain_attachments: dict[str, Any] = Field(default_factory=dict)
    evidence: ProductionOptimizerEvidence | None = None
