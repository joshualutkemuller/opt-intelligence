"""Shared contracts for the agent layer."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentAction = Literal[
    "optimize",
    "multi_domain_workflow",
    "explain",
    "scenario_analysis",
    "ingest",
    "unknown",
]


class AgentIntent(BaseModel):
    raw_text: str
    action: AgentAction = "unknown"
    domain: str | None = None
    workflow_id: str | None = None
    confidence: float = 0.0
    scenarios: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    name: str
    description: str
    status: Literal["complete", "pending", "blocked"] = "pending"


class AgentTraceEvent(BaseModel):
    event: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    domain: str | None = None
    title: str = "Optimization workflow"
    action: AgentAction = "unknown"
    objective_metric: str | None = None
    execution_mode: str = "recommendation"
    summary: str
    collected_fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    required_fields: list[dict[str, Any]] = Field(default_factory=list)
    scenario_names: list[str] = Field(default_factory=list)
    scenario_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    solver_options: dict[str, Any] = Field(default_factory=dict)
    steps: list[PlanStep] = Field(default_factory=list)
    ready_to_run: bool = False


class ScenarioSuggestion(BaseModel):
    name: str
    reason: str
    selected: bool = False
