from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ScenarioType(StrEnum):
    BASE = "base"
    UPSIDE = "upside"
    DOWNSIDE = "downside"
    STRESS = "stress"
    CUSTOM = "custom"


class Scenario(BaseModel):
    name: str
    scenario_type: ScenarioType
    description: str = ""
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}
