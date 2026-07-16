"""Typed contracts for deterministic multi-optimizer workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from decision_intelligence.contracts import OptimizationRequest, OptimizationResult

WorkflowStatus = Literal["complete", "partial", "error"]


class WorkflowStep(BaseModel):
    """One optimizer invocation inside a workflow plan."""

    step_id: str
    domain: str
    name: str
    description: str = ""
    request: OptimizationRequest
    depends_on: list[str] = Field(default_factory=list)

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
    summary: dict[str, Any] = Field(default_factory=dict)


class WorkflowResult(BaseModel):
    workflow_id: str
    name: str
    status: WorkflowStatus
    step_results: list[WorkflowStepResult] = Field(default_factory=list)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    trace: list[WorkflowTraceEvent] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
