import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .constraints import Constraint
from .objectives import Objective
from .scenarios import Scenario


class ExecutionMode(StrEnum):
    EXPLAIN = "explain"                    # tier 0 — no changes
    SCENARIO_ANALYSIS = "scenario_analysis"  # tier 1
    RECOMMENDATION = "recommendation"      # tier 2
    STAGE = "stage"                        # tier 3
    EXECUTE = "execute"                    # tier 4
    CHANGE_CONSTRAINTS = "change_constraints"  # tier 5 — production policy change


class OptimizationRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: str
    portfolio_id: str
    objective: Objective
    constraints: list[Constraint] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.RECOMMENDATION
    requestor: str = "system"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}
