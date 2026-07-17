"""Pydantic schemas for the browser-facing API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateChatSessionRequest(BaseModel):
    seed: int = 42
    default_portfolio: str = "PORT_001"


class ChatMessageRequest(BaseModel):
    message: str


class ChatSessionResponse(BaseModel):
    session_id: str
    assistant_message: str
    state: dict[str, Any]
    trace: list[dict[str, Any]] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    request: dict[str, Any] | None = None


class DirectOptimizationRequest(BaseModel):
    domain: Literal["collateral", "money_market", "financing"]
    portfolio_id: str = "PORT_001"
    objective_metric: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[str] = Field(default_factory=list)
    execution_mode: str = "recommendation"


class OptimizationResponse(BaseModel):
    result: dict[str, Any]
    request: dict[str, Any]


class WorkflowCatalogInput(BaseModel):
    key: str
    label: str
    type: Literal["string", "integer", "number", "currency", "fraction", "percent"]
    default: Any = None
    required: bool = True


class WorkflowCatalogItem(BaseModel):
    workflow_id: str
    version: int
    name: str
    description: str
    domains: list[str]
    tags: list[str] = Field(default_factory=list)
    default_context: dict[str, Any] = Field(default_factory=dict)
    inputs: list[WorkflowCatalogInput] = Field(default_factory=list)


class WorkflowCatalogResponse(BaseModel):
    workflows: list[WorkflowCatalogItem]


class WorkflowRunRequest(BaseModel):
    workflow: str = "liquidity_stress_funding_workflow"
    portfolio_id: str = "PORT_001"
    seed: int = 42
    context: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunResponse(BaseModel):
    plan: dict[str, Any]
    result: dict[str, Any]
