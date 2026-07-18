from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ConstraintType(StrEnum):
    ELIGIBILITY = "eligibility"
    CONCENTRATION = "concentration"
    LIQUIDITY = "liquidity"
    CREDIT_QUALITY = "credit_quality"
    MATURITY = "maturity"
    CURRENCY = "currency"
    INVENTORY = "inventory"
    BALANCE_SHEET = "balance_sheet"
    REGULATORY = "regulatory"
    COUNTERPARTY = "counterparty"
    MANDATE = "mandate"
    CUSTOM = "custom"


class Constraint(BaseModel):
    name: str
    constraint_type: ConstraintType
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    is_hard: bool = True  # hard = must satisfy; soft = penalize violation

    model_config = {"frozen": True}
