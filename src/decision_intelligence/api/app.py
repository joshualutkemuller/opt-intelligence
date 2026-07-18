"""Local FastAPI app for the browser-based Decision Intelligence demo."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from decision_intelligence.agents import negotiate_constraints
from decision_intelligence.chat import ChatSession
from decision_intelligence.chat.workflows import SCENARIO_PRESETS, WORKFLOWS
from decision_intelligence.contracts import Objective, OptimizationRequest, Scenario
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.contracts.scenarios import ScenarioType
from decision_intelligence.data.demo_packets import load_demo_data_packets
from decision_intelligence.export import (
    build_workflow_evidence_packet,
    encode_pdf_base64,
    generate_workflow_demo_package,
    generate_workflow_evidence_csvs,
    generate_workflow_evidence_pdf,
    generate_workflow_evidence_xlsx,
)
from decision_intelligence.governance import (
    ApprovalDecision,
    ApprovalPolicy,
    ApprovalStore,
    ApprovalThreshold,
    GovernanceController,
    build_workflow_audit_narrative,
)
from decision_intelligence.governance.audit import AuditLog
from decision_intelligence.ingestion import IngestionError, ingest_policy_document
from decision_intelligence.llm import LLMConfigError, LLMError, resolve_provider
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    AssetAllocationMVOOptimizer,
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)
from decision_intelligence.workflows import (
    DEFAULT_DEMO_PRESET_DIR,
    DEFAULT_WORKFLOW_REGISTRY,
    SequentialWorkflowRunner,
    build_workflow_scenario_comparison,
    load_demo_presets,
)

from .schemas import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    AuditNarrativeRequest,
    AuditNarrativeResponse,
    ChatMessageRequest,
    ChatSessionResponse,
    ConstraintNegotiationRequest,
    ConstraintNegotiationResponse,
    CreateChatSessionRequest,
    DemoDataPacketCatalogResponse,
    DemoPresetCatalogResponse,
    DirectOptimizationRequest,
    LLMChatRequest,
    LLMChatResponse,
    OptimizationResponse,
    PendingApprovalsResponse,
    PolicyIngestionRequest,
    PolicyIngestionResponse,
    WorkflowCatalogResponse,
    WorkflowEvidenceExportRequest,
    WorkflowEvidenceExportResponse,
    WorkflowExportPackageRequest,
    WorkflowExportPackageResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
    WorkflowScenarioCompareRequest,
    WorkflowScenarioCompareResponse,
)

app = FastAPI(
    title="Decision Intelligence Demo API",
    version="0.1.0",
    description="Local API wrapper for guided chat optimization demos.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CHAT_SESSIONS: dict[str, ChatSession] = {}
_APPROVAL_STORE = ApprovalStore()
_APPROVAL_AUDIT = AuditLog()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat/sessions", response_model=ChatSessionResponse)
def create_chat_session(payload: CreateChatSessionRequest) -> ChatSessionResponse:
    session_id = str(uuid.uuid4())
    session = ChatSession(seed=payload.seed, default_portfolio=payload.default_portfolio)
    _CHAT_SESSIONS[session_id] = session
    return ChatSessionResponse(
        session_id=session_id,
        assistant_message=(
            "Tell me which workflow you want: asset allocation, collateral, "
            "money market, financing, or a full sequential workflow."
        ),
        state=session.snapshot(),
        trace=session.snapshot().get("trace", []),
    )


@app.post("/api/chat/sessions/{session_id}/messages", response_model=ChatSessionResponse)
def send_chat_message(
    session_id: str,
    payload: ChatMessageRequest,
) -> ChatSessionResponse:
    session = _CHAT_SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown chat session.")

    reply = session.reply(payload.message)
    result = None
    request = None
    workflow_plan = None
    workflow_result = None
    assistant_message = reply.message

    if reply.request is not None:
        request = _json(reply.request)
        result = _json(_run_request(reply.request))

    if reply.workflow_plan is not None:
        workflow_plan = _json(reply.workflow_plan)
        orchestrator, _audit = _build_orchestrator()
        workflow_run = SequentialWorkflowRunner(orchestrator).run(reply.workflow_plan)
        workflow_result = _json(workflow_run)
        final_step = workflow_run.step_results[-1] if workflow_run.step_results else None
        if final_step is not None:
            result = _json(final_step.result)
        assistant_message = (
            f"Sequential workflow complete. {len(workflow_run.step_results)} "
            f"optimizer steps ran with aggregate validation "
            f"{'passing' if workflow_run.validation_summary.get('passed') else 'requiring review'}."
        )

    state = session.snapshot()
    trace = state.get("trace", [])
    if result is not None:
        result["agent_trace"] = trace
    if workflow_result is not None:
        workflow_result["agent_trace"] = trace

    return ChatSessionResponse(
        session_id=session_id,
        assistant_message=assistant_message,
        state=state,
        trace=trace,
        result=result,
        request=request,
        workflow_plan=workflow_plan,
        workflow_result=workflow_result,
    )


@app.post("/api/policy/ingest", response_model=PolicyIngestionResponse)
def ingest_policy(payload: PolicyIngestionRequest) -> PolicyIngestionResponse:
    try:
        result = ingest_policy_document(
            workflow_id=payload.workflow_id,
            text=payload.text,
            pdf_base64=payload.pdf_base64,
            filename=payload.filename,
            backend=payload.backend,
            llm_provider=payload.provider,
            model=payload.model,
            base_url=payload.base_url,
            api_key=payload.api_key,
        )
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PolicyIngestionResponse(**_json(result))


@app.post("/api/llm/chat", response_model=LLMChatResponse)
def send_llm_chat_message(payload: LLMChatRequest) -> LLMChatResponse:
    try:
        provider = resolve_provider(
            payload.provider,
            model=payload.model,
            base_url=payload.base_url,
        )
    except LLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if provider is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "No LLM provider is configured. For local Ollama, use provider "
                "'openai' with base_url 'http://localhost:11434/v1'."
            ),
        )

    try:
        response = provider.generate(
            payload.message,
            system=payload.system,
            max_tokens=payload.max_tokens,
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface local model connection failures
        raise HTTPException(status_code=502, detail=f"LLM chat failed: {exc}") from exc

    return LLMChatResponse(
        provider=provider.name,
        model=provider.model,
        base_url=payload.base_url,
        response=response,
    )


@app.post("/api/optimizations/run", response_model=OptimizationResponse)
def run_optimization(payload: DirectOptimizationRequest) -> OptimizationResponse:
    request = _build_direct_request(payload)
    result = _run_request(request)
    return OptimizationResponse(result=_json(result), request=_json(request))


@app.get("/api/workflows", response_model=WorkflowCatalogResponse)
def list_workflows() -> WorkflowCatalogResponse:
    return WorkflowCatalogResponse(workflows=DEFAULT_WORKFLOW_REGISTRY.list_catalog())


@app.get("/api/demo-presets", response_model=DemoPresetCatalogResponse)
def list_demo_presets() -> DemoPresetCatalogResponse:
    presets = load_demo_presets(
        DEFAULT_DEMO_PRESET_DIR,
        known_workflow_ids=set(DEFAULT_WORKFLOW_REGISTRY.list_ids()),
    )
    return DemoPresetCatalogResponse(
        presets=[preset.catalog_item() for preset in presets]
    )


@app.get("/api/demo-data-packets", response_model=DemoDataPacketCatalogResponse)
def list_demo_data_packets() -> DemoDataPacketCatalogResponse:
    packets = load_demo_data_packets()
    return DemoDataPacketCatalogResponse(
        packets=[packet.catalog_item() for packet in packets]
    )


@app.post("/api/workflows/run", response_model=WorkflowRunResponse)
def run_workflow(payload: WorkflowRunRequest) -> WorkflowRunResponse:
    context = dict(payload.context)
    if payload.execution_mode:
        context["execution_mode"] = payload.execution_mode
    try:
        plan = DEFAULT_WORKFLOW_REGISTRY.build(
            payload.workflow,
            portfolio_id=payload.portfolio_id,
            seed=payload.seed,
            context=context,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    orchestrator, _audit = _build_orchestrator()
    result = SequentialWorkflowRunner(orchestrator).run(plan)
    return WorkflowRunResponse(plan=_json(plan), result=_json(result))


@app.post("/api/workflows/compare", response_model=WorkflowScenarioCompareResponse)
def compare_workflow_runs(
    payload: WorkflowScenarioCompareRequest,
) -> WorkflowScenarioCompareResponse:
    comparison = build_workflow_scenario_comparison(
        payload.runs,
        labels=payload.labels,
        run_ids=payload.run_ids,
    )
    return WorkflowScenarioCompareResponse(comparison=_json(comparison))


@app.get("/api/approvals/pending", response_model=PendingApprovalsResponse)
def list_pending_approvals() -> PendingApprovalsResponse:
    return PendingApprovalsResponse(approvals=_pending_approval_items())


@app.post("/api/approvals/decisions", response_model=ApprovalDecisionResponse)
def submit_approval_decision(
    payload: ApprovalDecisionRequest,
) -> ApprovalDecisionResponse:
    if not payload.approver.strip():
        raise HTTPException(status_code=400, detail="Approver is required.")

    decision = ApprovalDecision(
        approver=payload.approver.strip(),
        granted=payload.granted,
        reason=payload.reason,
    )
    fingerprint = _APPROVAL_STORE.submit_for_approval_id(payload.approval_id, decision)
    if fingerprint is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown approval_id: {payload.approval_id}",
        )

    _APPROVAL_AUDIT.record(
        "approval_decision_submitted",
        payload.approval_id,
        {
            "fingerprint": fingerprint,
            "approver": decision.approver,
            "granted": decision.granted,
            "reason": decision.reason,
        },
    )
    return ApprovalDecisionResponse(
        approval_id=payload.approval_id,
        fingerprint=fingerprint,
        status="approved" if decision.granted else "rejected",
        approver=decision.approver,
        reason=decision.reason,
    )


@app.post("/api/workflows/export-package", response_model=WorkflowExportPackageResponse)
def export_workflow_package(
    payload: WorkflowExportPackageRequest,
) -> WorkflowExportPackageResponse:
    html = generate_workflow_demo_package(
        response=payload.response,
        payload=payload.payload,
        preset=payload.preset,
        workflow=payload.workflow,
        comparison=payload.comparison,
    )
    workflow_id = (
        payload.response.get("result", {}).get("workflow_id")
        or payload.workflow.get("workflow_id")
        or payload.payload.get("workflow")
        or "workflow-demo"
    )
    return WorkflowExportPackageResponse(
        filename=f"{_safe_filename(str(workflow_id))}-demo-package.html",
        html=html,
    )


@app.post("/api/workflows/export-evidence", response_model=WorkflowEvidenceExportResponse)
def export_workflow_evidence(
    payload: WorkflowEvidenceExportRequest,
) -> WorkflowEvidenceExportResponse:
    packet = build_workflow_evidence_packet(
        response=payload.response,
        payload=payload.payload,
        preset=payload.preset,
        workflow=payload.workflow,
        comparison=payload.comparison,
    )
    pdf = generate_workflow_evidence_pdf(packet)
    csv_files = generate_workflow_evidence_csvs(packet)
    xlsx = generate_workflow_evidence_xlsx(packet)
    workflow_id = (
        payload.response.get("result", {}).get("workflow_id")
        or payload.workflow.get("workflow_id")
        or payload.payload.get("workflow")
        or "workflow-demo"
    )
    filename = _safe_filename(str(workflow_id))
    return WorkflowEvidenceExportResponse(
        json_filename=f"{filename}-evidence.json",
        json_payload=packet,
        pdf_filename=f"{filename}-evidence.pdf",
        pdf_base64=encode_pdf_base64(pdf),
        csv_files=csv_files,
        xlsx_filename=f"{filename}-evidence.xlsx",
        xlsx_base64=encode_pdf_base64(xlsx),
    )


@app.post("/api/audit/narrative", response_model=AuditNarrativeResponse)
def generate_audit_narrative(payload: AuditNarrativeRequest) -> AuditNarrativeResponse:
    narrative = build_workflow_audit_narrative(
        response=payload.response,
        payload=payload.payload,
        preset=payload.preset,
        workflow=payload.workflow,
    )
    return AuditNarrativeResponse(narrative=_json(narrative))


@app.post("/api/constraints/negotiate", response_model=ConstraintNegotiationResponse)
def negotiate_result_constraints(
    payload: ConstraintNegotiationRequest,
) -> ConstraintNegotiationResponse:
    negotiation = negotiate_constraints(
        payload.result,
        target_improvement=payload.target_improvement,
        target_units=payload.target_units,
        max_proposals=payload.max_proposals,
    )
    return ConstraintNegotiationResponse(negotiation=_json(negotiation))


def _build_direct_request(payload: DirectOptimizationRequest) -> OptimizationRequest:
    spec = WORKFLOWS[payload.domain]
    context = {**spec.base_context, **payload.context}
    objective_metric = payload.objective_metric or spec.objective_metric
    scenarios = [
        Scenario(
            name=name,
            scenario_type=ScenarioType.STRESS if "stress" in name else ScenarioType.DOWNSIDE,
            parameter_overrides=SCENARIO_PRESETS.get(name, {}).get(payload.domain, {}),
        )
        for name in payload.scenarios
    ]

    try:
        execution_mode = ExecutionMode(payload.execution_mode)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown execution mode: {payload.execution_mode}",
        ) from exc

    return OptimizationRequest(
        domain=payload.domain,
        portfolio_id=payload.portfolio_id,
        objective=Objective(
            name=f"{spec.direction.value}_{objective_metric}",
            direction=spec.direction,
            metric=objective_metric,
        ),
        scenarios=scenarios,
        execution_mode=execution_mode,
        context=context,
        requestor="api",
    )


def _run_request(request: OptimizationRequest):
    orchestrator, _audit = _build_orchestrator()
    return orchestrator.run(request)


def _build_orchestrator() -> tuple[OptimizationOrchestrator, AuditLog]:
    audit = _APPROVAL_AUDIT
    registry = OptimizerRegistry()
    registry.register(AssetAllocationMVOOptimizer())
    registry.register(CollateralOptimizer())
    registry.register(MoneyMarketOptimizer())
    registry.register(FinancingOptimizer())
    governance = GovernanceController(_demo_approval_policy(), _APPROVAL_STORE, audit)
    return OptimizationOrchestrator(registry, audit, governance), audit


def _demo_approval_policy() -> ApprovalPolicy:
    return ApprovalPolicy(
        thresholds=[
            ApprovalThreshold(
                name="large_notional",
                context_keys=(
                    "governance.materiality_notional",
                    "materiality_notional",
                    "notional",
                    "total_funding_need",
                    "portfolio_notional",
                ),
                threshold=1_000_000_000,
                tier=4,
                description="notional exposure exceeds $1B",
            ),
            ApprovalThreshold(
                name="pnl_impact",
                context_keys=(
                    "governance.estimated_pnl_impact",
                    "estimated_pnl_impact",
                    "pnl_impact",
                    "pnl_at_risk",
                ),
                threshold=5_000_000,
                tier=4,
                description="estimated PnL impact exceeds $5M",
            ),
        ]
    )


def _json(value: Any) -> dict[str, Any]:
    return jsonable_encoder(value)


def _pending_approval_items() -> list[dict[str, Any]]:
    items = []
    for item in _APPROVAL_STORE.list_approvals():
        decision = item["decision"]
        items.append(
            {
                "approval_id": item["approval_id"],
                "fingerprint": item["fingerprint"],
                "status": (
                    "pending"
                    if decision is None
                    else "approved" if decision.granted else "rejected"
                ),
                "approver": decision.approver if decision else None,
                "reason": decision.reason if decision else "",
                "decided_at": decision.decided_at.isoformat() if decision else None,
            }
        )
    return items


def _safe_filename(value: str) -> str:
    safe = "".join(
        character.lower() if character.isalnum() else "-"
        for character in value.strip()
    ).strip("-")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe or "workflow-demo"
