import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .constraints import Constraint
from .objectives import Objective
from .scenarios import Scenario


class ExecutionMode(str, Enum):
    EXPLAIN = "explain"                    # tier 0 — no changes
    SCENARIO_ANALYSIS = "scenario_analysis"  # tier 1
    RECOMMENDATION = "recommendation"      # tier 2
    STAGE = "stage"                        # tier 3
    EXECUTE = "execute"                    # tier 4


class OptimizationRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: str
    portfolio_id: str
    objective: Objective
    constraints: list[Constraint] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.RECOMMENDATION
    requestor: str = "system"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}
