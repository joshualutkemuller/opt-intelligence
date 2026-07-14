from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SolveStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    ERROR = "error"


class ValidationResult(BaseModel):
    passed: bool
    checks: list[dict[str, Any]] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AllocationItem(BaseModel):
    asset_id: str
    label: str
    allocated_value: float
    allocated_fraction: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SensitivityItem(BaseModel):
    parameter: str
    shadow_price: float
    range_lower: float
    range_upper: float
    interpretation: str = ""


class OptimizationResult(BaseModel):
    request_id: str
    domain: str
    status: SolveStatus
    objective_value: float
    baseline_value: float
    improvement: float
    improvement_pct: float
    allocations: list[AllocationItem] = Field(default_factory=list)
    binding_constraints: list[str] = Field(default_factory=list)
    sensitivities: list[SensitivityItem] = Field(default_factory=list)
    validation: ValidationResult = Field(
        default_factory=lambda: ValidationResult(passed=True)
    )
    explanation: str = ""
    scenario_results: dict[str, "OptimizationResult"] = Field(default_factory=dict)
    solver_metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
