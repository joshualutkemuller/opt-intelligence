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
    workflow_plan: dict[str, Any] | None = None
    workflow_result: dict[str, Any] | None = None


class LLMChatRequest(BaseModel):
    message: str
    system: str | None = None
    provider: str = "openai"
    model: str | None = None
    base_url: str | None = None
    max_tokens: int = Field(default=512, ge=1, le=4096)


class LLMChatResponse(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    response: str


class PolicyIngestionRequest(BaseModel):
    workflow_id: str
    text: str | None = None
    pdf_base64: str | None = None
    filename: str | None = None


class PolicyIngestionResponse(BaseModel):
    workflow_id: str
    source_type: str
    input_values: dict[str, str] = Field(default_factory=dict)
    context_patch: dict[str, Any] = Field(default_factory=dict)
    extracted_fields: list[dict[str, Any]] = Field(default_factory=list)
    review_summary: dict[str, Any] = Field(default_factory=dict)


class DirectOptimizationRequest(BaseModel):
    domain: Literal["asset_allocation", "collateral", "money_market", "financing"]
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
    type: Literal[
        "string",
        "integer",
        "number",
        "currency",
        "fraction",
        "percent",
        "boolean",
        "select",
    ]
    default: Any = None
    required: bool = True
    options: list[str] = Field(default_factory=list)


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


class DemoPresetCatalogItem(BaseModel):
    preset_id: str
    version: int
    name: str
    description: str
    audience: str
    workflow_id: str
    portfolio_id: str
    seed: int
    duration_minutes: int
    context: dict[str, Any] = Field(default_factory=dict)
    talking_points: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class DemoPresetCatalogResponse(BaseModel):
    presets: list[DemoPresetCatalogItem]


class DemoDataPacketCatalogItem(BaseModel):
    packet_id: str
    version: int
    name: str
    description: str
    audience: str
    workflow_id: str
    preset_id: str
    source_type: str
    domains: list[str]
    files: dict[str, str]
    talking_points: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class DemoDataPacketCatalogResponse(BaseModel):
    packets: list[DemoDataPacketCatalogItem]


class WorkflowRunRequest(BaseModel):
    workflow: str = "liquidity_stress_funding_workflow"
    portfolio_id: str = "PORT_001"
    seed: int = 42
    execution_mode: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunResponse(BaseModel):
    plan: dict[str, Any]
    result: dict[str, Any]


class WorkflowScenarioCompareRequest(BaseModel):
    runs: list[dict[str, Any]]
    labels: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)


class WorkflowScenarioCompareResponse(BaseModel):
    comparison: dict[str, Any]


class ApprovalDecisionRequest(BaseModel):
    approval_id: str
    approver: str
    reason: str = ""
    granted: bool = True


class ApprovalDecisionResponse(BaseModel):
    approval_id: str
    fingerprint: str
    status: Literal["approved", "rejected"]
    approver: str
    reason: str = ""


class PendingApprovalsResponse(BaseModel):
    approvals: list[dict[str, Any]]


class WorkflowExportPackageRequest(BaseModel):
    response: dict[str, Any]
    payload: dict[str, Any] = Field(default_factory=dict)
    preset: dict[str, Any] = Field(default_factory=dict)
    workflow: dict[str, Any] = Field(default_factory=dict)


class WorkflowExportPackageResponse(BaseModel):
    filename: str
    content_type: str = "text/html"
    html: str


class WorkflowEvidenceExportRequest(BaseModel):
    response: dict[str, Any]
    payload: dict[str, Any] = Field(default_factory=dict)
    preset: dict[str, Any] = Field(default_factory=dict)
    workflow: dict[str, Any] = Field(default_factory=dict)


class WorkflowEvidenceExportResponse(BaseModel):
    json_filename: str
    json_content_type: str = "application/json"
    json_payload: dict[str, Any]
    pdf_filename: str
    pdf_content_type: str = "application/pdf"
    pdf_base64: str
