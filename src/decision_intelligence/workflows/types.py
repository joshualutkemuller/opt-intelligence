"""Typed contracts for deterministic multi-optimizer workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from decision_intelligence.contracts import OptimizationRequest, OptimizationResult

WorkflowStatus = Literal["complete", "partial", "error"]
DependencyRuleType = Literal[
    "funding_pressure_liquidity_buffer",
    "collateral_pressure_liquidity_buffer",
]


class WorkflowDependencyRule(BaseModel):
    """Declarative rule that lets one completed step alter a downstream request."""

    source_step_id: str
    rule_type: DependencyRuleType
    target_context_keys: list[str]
    description: str = ""

    model_config = {"frozen": True}


class DependencyEffect(BaseModel):
    """Audit record for a cross-step context mutation."""

    rule_type: DependencyRuleType
    source_step_id: str
    target_step_id: str
    target_context_key: str
    previous_value: float
    new_value: float
    delta: float
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowStep(BaseModel):
    """One optimizer invocation inside a workflow plan."""

    step_id: str
    domain: str
    name: str
    description: str = ""
    request: OptimizationRequest
    depends_on: list[str] = Field(default_factory=list)
    dependency_rules: list[WorkflowDependencyRule] = Field(default_factory=list)

    model_config = {"frozen": True}


class WorkflowPlan(BaseModel):
    """Deterministic ordered plan for a multi-optimizer workflow."""

    workflow_id: str
    name: str
    description: str = ""
    steps: list[WorkflowStep]
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class WorkflowTraceEvent(BaseModel):
    event: str
    message: str
    step_id: str | None = None
    domain: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkflowStepResult(BaseModel):
    step_id: str
    domain: str
    name: str
    status: str
    request: OptimizationRequest
    result: OptimizationResult
    inputs_from: list[str] = Field(default_factory=list)
    dependency_effects: list[DependencyEffect] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class WorkflowExplanationReport(BaseModel):
    summary: str
    overall_recommendation: str
    key_drivers: list[str] = Field(default_factory=list)
    dependency_changes: list[str] = Field(default_factory=list)
    economic_impact: dict[str, Any] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    step_summaries: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowResult(BaseModel):
    workflow_id: str
    name: str
    status: WorkflowStatus
    step_results: list[WorkflowStepResult] = Field(default_factory=list)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    dependency_summary: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    explanation_report: WorkflowExplanationReport | None = None
    trace: list[WorkflowTraceEvent] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
