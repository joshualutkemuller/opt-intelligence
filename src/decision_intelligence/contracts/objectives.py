from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ObjectiveDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class Objective(BaseModel):
    name: str
    direction: ObjectiveDirection
    metric: str
    weight: float = Field(default=1.0, ge=0.0)
    parameters: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}
