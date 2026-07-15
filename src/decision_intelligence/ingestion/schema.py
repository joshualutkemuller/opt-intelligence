"""
Intermediate extraction schema for PDF ingestion.

This is the *natural-language contract* — a loose, LLM-friendly shape that a
document (PDF, memo, mandate) is parsed into before it is mapped onto the
strict :class:`OptimizationRequest`. Keeping the two separate means the
extraction step can be lossy / best-effort while the optimizer still receives a
fully-validated request.

All fields are optional so that a partial extraction still parses; the mapper
(:mod:`decision_intelligence.ingestion.mapper`) is responsible for filling
defaults and validating that the essentials are present.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractedConstraint(BaseModel):
    """A single constraint as described in prose."""

    name: str = Field(description="Short snake_case identifier, e.g. 'max_prime_fraction'.")
    constraint_type: str = Field(
        default="custom",
        description=(
            "One of: eligibility, concentration, liquidity, credit_quality, "
            "maturity, currency, inventory, balance_sheet, regulatory, "
            "counterparty, mandate, custom."
        ),
    )
    description: str = Field(default="", description="Verbatim or paraphrased constraint text.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Numeric knobs, e.g. {'limit': 0.4} or {'min_days': 0.3}.",
    )
    is_hard: bool = Field(default=True, description="True = must satisfy; False = soft/penalty.")


class ExtractedScenario(BaseModel):
    """A stress / what-if scenario described in the document."""

    name: str = Field(description="Short snake_case name, e.g. 'liquidity_stress'.")
    scenario_type: str = Field(
        default="stress",
        description="One of: base, upside, downside, stress, custom.",
    )
    description: str = Field(default="")
    parameter_overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameter shifts applied under this scenario.",
    )


class ExtractedRequest(BaseModel):
    """
    The full best-effort extraction of an optimization scenario from a document.

    Every field is optional; the mapper enforces what is actually required.
    """

    domain: str | None = Field(
        default=None,
        description=(
            "Which optimizer this maps to: 'collateral', 'money_market', or "
            "'financing'. Infer from the subject matter if not stated."
        ),
    )
    portfolio_id: str | None = Field(
        default=None,
        description="Portfolio / account identifier if mentioned (e.g. 'PORT_204').",
    )
    objective_metric: str | None = Field(
        default=None,
        description=(
            "The quantity to optimize, e.g. 'funding_cost', 'yield', "
            "'funding_spread'."
        ),
    )
    objective_direction: str | None = Field(
        default=None,
        description="'minimize' or 'maximize'.",
    )
    objective_name: str | None = Field(
        default=None, description="Human label for the objective."
    )
    constraints: list[ExtractedConstraint] = Field(default_factory=list)
    scenarios: list[ExtractedScenario] = Field(default_factory=list)
    execution_mode: str | None = Field(
        default=None,
        description=(
            "Requested tier: explain, scenario_analysis, recommendation, "
            "stage, execute."
        ),
    )
    requestor: str | None = Field(
        default=None, description="Who authored / requested the analysis."
    )
    notes: str = Field(
        default="",
        description="Any additional free-text context worth preserving.",
    )
