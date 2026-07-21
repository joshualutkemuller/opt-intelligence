"""Local FastAPI app for the browser-based Decision Intelligence demo."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
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
    DriftMonitor,
    GovernanceController,
    GovernanceOrchestrator,
    build_workflow_audit_narrative,
    polish_narrative,
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
from decision_intelligence.production_optimizers import build_default_production_registry
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
    ConstraintApprovalRequest,
    ConstraintApprovalResponse,
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
    ProductionOptimizerCatalogResponse,
    WorkflowCatalogResponse,
    WorkflowEvidenceExportRequest,
    WorkflowEvidenceExportResponse,
    WorkflowExportPackageRequest,
    WorkflowExportPackageResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
    WorkflowScenarioCompareRequest,
    WorkflowScenarioCompareResponse,
    SubstituteReoptimizeRequest,
    SubstituteReoptimizeResponse,
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
_NARRATIVE_STORE: dict[str, dict[str, Any]] = {}  # workflow_id → AuditNarrative dict
_DRIFT_MONITOR = DriftMonitor()
_GOVERNANCE_ORCHESTRATOR = GovernanceOrchestrator(
    store=_APPROVAL_STORE,
    audit=_APPROVAL_AUDIT,
)


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
        # Apply production optimizer settings from the request payload
        patched_steps = []
        for step in reply.workflow_plan.steps:
            ctx = dict(step.request.context)
            if payload.optimizer_runtime != "phase1":
                ctx["optimizer_runtime"] = payload.optimizer_runtime
            if payload.production_optimizer_id:
                ctx["production_optimizer_id"] = payload.production_optimizer_id
            patched_request = step.request.model_copy(update={"context": ctx})
            patched_steps.append(step.model_copy(update={"request": patched_request}))
        patched_plan = reply.workflow_plan.model_copy(update={"steps": patched_steps})
        orchestrator, _audit = _build_orchestrator()
        workflow_run = SequentialWorkflowRunner(orchestrator).run(patched_plan)
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


@app.get("/api/production-optimizers", response_model=ProductionOptimizerCatalogResponse)
def list_production_optimizers() -> ProductionOptimizerCatalogResponse:
    registry = build_default_production_registry()
    optimizers = []
    for optimizer_id in registry.list_ids():
        adapter = registry.get(optimizer_id)
        config = adapter.model_config
        optimizers.append(
            {
                "optimizer_id": optimizer_id,
                "domain": config.domain,
                "model_name": config.lineage.model_name,
                "model_version": config.lineage.model_version,
                "config_version": config.lineage.config_version,
                "objectives": [
                    objective.model_dump(mode="json")
                    for objective in config.objectives
                ],
                "constraints": [
                    constraint.model_dump(mode="json")
                    for constraint in config.constraints
                ],
                "data_contract": config.data_contract.model_dump(mode="json"),
                "solver": config.solver.model_dump(mode="json"),
                "execution": config.execution.model_dump(mode="json"),
            }
        )
    return ProductionOptimizerCatalogResponse(optimizers=optimizers)


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
    if payload.optimizer_runtime != "phase1":
        context["optimizer_runtime"] = payload.optimizer_runtime
    if payload.production_optimizer_id:
        context["production_optimizer_id"] = payload.production_optimizer_id
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
    _persist_narrative(
        workflow_id=plan.workflow_id,
        response={"plan": _json(plan), "result": _json(result)},
        payload=_json(payload),
    )
    return WorkflowRunResponse(plan=_json(plan), result=_json(result))


@app.post("/api/workflows/run-stream")
def run_workflow_stream(payload: WorkflowRunRequest) -> StreamingResponse:
    context = dict(payload.context)
    if payload.execution_mode:
        context["execution_mode"] = payload.execution_mode
    if payload.optimizer_runtime != "phase1":
        context["optimizer_runtime"] = payload.optimizer_runtime
    if payload.production_optimizer_id:
        context["production_optimizer_id"] = payload.production_optimizer_id
    try:
        plan = DEFAULT_WORKFLOW_REGISTRY.build(
            payload.workflow,
            portfolio_id=payload.portfolio_id,
            seed=payload.seed,
            context=context,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    orchestrator, _audit = _build_orchestrator()

    def generate():
        for event in SequentialWorkflowRunner(orchestrator).run_streaming(plan):
            if event.get("event") == "workflow_completed":
                result_dict = event.get("result") or {}
                _persist_narrative(
                    workflow_id=plan.workflow_id,
                    response={"plan": _json(plan), "result": result_dict},
                    payload=_json(payload),
                )
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


@app.post("/api/collateral/reoptimize-with-substitutes", response_model=SubstituteReoptimizeResponse)
def reoptimize_with_substitutes(payload: SubstituteReoptimizeRequest) -> SubstituteReoptimizeResponse:
    """Re-run the collateral optimizer with flagged high-lending assets excluded.

    The excluded assets are removed from the eligible inventory so the LP must
    find cheaper substitute collateral to cover the same obligations.  Returns
    the original and substitute objective values, the lending-opportunity diff,
    and the full substitute result for the frontend to display.
    """
    from decision_intelligence.contracts.objectives import ObjectiveDirection
    from decision_intelligence.optimizers.collateral import CollateralOptimizer

    optimizer = CollateralOptimizer()

    def _build_request(extra_context: dict) -> OptimizationRequest:
        ctx = dict(payload.context)
        ctx.update(extra_context)
        if payload.optimizer_runtime != "phase1":
            ctx["optimizer_runtime"] = payload.optimizer_runtime
        if payload.production_optimizer_id:
            ctx["production_optimizer_id"] = payload.production_optimizer_id
        return OptimizationRequest(
            domain="collateral",
            portfolio_id=payload.portfolio_id,
            objective=Objective(
                name="minimize_funding_cost",
                direction=ObjectiveDirection.MINIMIZE,
                metric="funding_cost",
            ),
            context=ctx,
            seed=payload.seed,
        )

    orig_request = _build_request({})
    orig_problem = optimizer.prepare_problem(orig_request)
    orig_solution = optimizer.solve(orig_problem)
    orig_obj = float(orig_solution.get("objective_value", 0.0))
    orig_opps = orig_solution.get("lending_opportunities", [])

    sub_request = _build_request({"excluded_asset_ids": payload.excluded_asset_ids})
    sub_problem = optimizer.prepare_problem(sub_request)
    sub_solution = optimizer.solve(sub_problem)

    if sub_solution.get("status") != "optimal":
        raise HTTPException(
            status_code=422,
            detail=(
                "Substitute re-optimization did not find a feasible solution. "
                "The excluded assets may be required to cover obligations — "
                "consider excluding fewer assets. "
                f"Solver message: {sub_solution.get('message', 'unknown')}"
            ),
        )

    sub_obj = float(sub_solution.get("objective_value", 0.0))
    remaining_opps = sub_solution.get("lending_opportunities", [])
    delta = sub_obj - orig_obj
    excluded_count = len(payload.excluded_asset_ids)
    freed_count = len(orig_opps) - len(remaining_opps)

    if delta <= 0:
        cost_note = f"funding cost improved by ${abs(delta):,.2f} after substitution"
    else:
        cost_note = f"funding cost increased by ${delta:,.2f} after substitution (substitute assets carry higher cost)"

    summary = (
        f"Re-optimized with {excluded_count} asset(s) excluded from collateral pool. "
        f"{freed_count} of {len(orig_opps)} lending opportunity conflict(s) resolved. "
        f"{len(remaining_opps)} conflict(s) remain. "
        f"Original objective: ${orig_obj:,.2f}; substitute objective: ${sub_obj:,.2f} — {cost_note}."
    )

    from decision_intelligence.production_optimizers.adapters._utils import to_jsonable

    return SubstituteReoptimizeResponse(
        original_objective=orig_obj,
        substitute_objective=sub_obj,
        objective_delta=round(delta, 4),
        original_lending_opportunities=to_jsonable(orig_opps),
        remaining_lending_opportunities=to_jsonable(remaining_opps),
        substitute_result=to_jsonable({k: v for k, v in sub_solution.items() if k != "x"}),
        summary=summary,
    )


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
    wf_id = (
        payload.response.get("result", {}).get("workflow_id")
        or payload.workflow.get("workflow_id")
        or payload.payload.get("workflow")
    )
    audit_narrative = _NARRATIVE_STORE.get(wf_id) if wf_id else None
    packet = build_workflow_evidence_packet(
        response=payload.response,
        payload=payload.payload,
        preset=payload.preset,
        workflow=payload.workflow,
        comparison=payload.comparison,
        audit_narrative=audit_narrative,
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
    if payload.llm_polish:
        try:
            provider = resolve_provider(
                payload.provider,
                model=payload.model,
                base_url=payload.base_url,
                api_key=payload.api_key,
            )
        except LLMConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if provider is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "llm_polish requires a configured LLM provider. "
                    "Pass provider='openai' with base_url for Ollama, "
                    "or provider='anthropic' with an API key."
                ),
            )
        narrative = polish_narrative(narrative, provider)
    wf_id = (
        payload.response.get("result", {}).get("workflow_id")
        or payload.workflow.get("workflow_id") if payload.workflow else None
        or payload.payload.get("workflow") if payload.payload else None
    )
    if wf_id:
        _NARRATIVE_STORE[str(wf_id)] = _json(narrative)
    return AuditNarrativeResponse(narrative=_json(narrative))


@app.get("/api/audit/narrative/{workflow_id}", response_model=AuditNarrativeResponse)
def get_audit_narrative(workflow_id: str) -> AuditNarrativeResponse:
    narrative = _NARRATIVE_STORE.get(workflow_id)
    if narrative is None:
        raise HTTPException(
            status_code=404,
            detail=f"No narrative persisted for workflow_id '{workflow_id}'.",
        )
    return AuditNarrativeResponse(narrative=narrative)


@app.post("/api/governance/route")
def route_governance(payload: dict[str, Any]) -> dict[str, Any]:
    """Auto-route a workflow result or request to the correct approval tier."""
    from decision_intelligence.governance.orchestrator import _synthetic_request_from_workflow
    request = _synthetic_request_from_workflow(payload, payload.get("context") or {})
    decision = _GOVERNANCE_ORCHESTRATOR.route(request)
    return decision.as_dict()


@app.post("/api/governance/advance")
def advance_governance(payload: dict[str, Any]) -> dict[str, Any]:
    """Submit an approve/reject decision for a pending governance gate."""
    approval_id = str(payload.get("approval_id") or "")
    approver = str(payload.get("approver") or "").strip()
    granted = bool(payload.get("granted", False))
    reason = str(payload.get("reason") or "")
    if not approval_id:
        raise HTTPException(status_code=400, detail="approval_id is required.")
    if not approver:
        raise HTTPException(status_code=400, detail="approver is required.")
    try:
        result = _GOVERNANCE_ORCHESTRATOR.advance(
            approval_id,
            approver=approver,
            granted=granted,
            reason=reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "approval_id": result.approval_id,
        "fingerprint": result.fingerprint,
        "status": result.status,
        "approver": result.approver,
        "reason": result.reason,
        "tier": result.tier,
        "action_performed": result.action_performed,
        "decided_at": result.decided_at,
    }


@app.get("/api/governance/pending")
def list_governance_pending() -> dict[str, Any]:
    """Return all pending (undecided) governance gates across all requests."""
    return {"pending": _GOVERNANCE_ORCHESTRATOR.pending()}


@app.post("/api/drift/snapshot")
def drift_snapshot(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Store the given workflow result as the drift baseline."""
    workflow_result = payload.get("workflow_result") or payload
    _DRIFT_MONITOR.snapshot(workflow_result)
    return {"status": "ok", "baseline_time": _DRIFT_MONITOR.baseline_time()}


@app.post("/api/drift/check")
def drift_check(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Compare *workflow_result* against the stored baseline; return any drift alerts.

    If ``session_id`` is provided and a matching chat session exists, the alerts
    are also injected into that session so they surface on the next chat reply.
    """
    workflow_result = payload.get("workflow_result") or payload
    alerts = _DRIFT_MONITOR.check(workflow_result)
    if alerts and (session_id := payload.get("session_id")):
        session = _CHAT_SESSIONS.get(str(session_id))
        if session:
            session.inject_alerts(alerts)
    return {
        "alert_count": len(alerts),
        "alerts": [a.as_dict() for a in alerts],
        "has_baseline": _DRIFT_MONITOR.has_baseline(),
        "baseline_time": _DRIFT_MONITOR.baseline_time(),
    }


@app.get("/api/drift/thresholds")
def drift_list_thresholds() -> dict[str, Any]:
    return {"thresholds": _DRIFT_MONITOR.list_thresholds()}


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


_TIER_APPROVER_ROLES: dict[int, str] = {
    0: "No approval required",
    1: "No approval required",
    2: "No approval required (recommendation tier)",
    3: "Domain Head or Risk Analyst",
    4: "Senior Funding MD or equivalent",
    5: "CRO / CCO (production constraint change)",
}


@app.post("/api/constraints/negotiate/approve", response_model=ConstraintApprovalResponse)
def initiate_constraint_approval(
    payload: ConstraintApprovalRequest,
) -> ConstraintApprovalResponse:
    """Register a constraint relaxation proposal as a pending approval request."""
    import hashlib

    tier = payload.governance_tier
    required_role = _TIER_APPROVER_ROLES.get(tier, f"Tier {tier} approver")

    fingerprint_parts = "|".join([
        payload.domain,
        payload.portfolio_id,
        payload.parameter,
        payload.proposed_change,
        str(tier),
    ])
    fingerprint = hashlib.sha256(fingerprint_parts.encode()).hexdigest()[:16]
    approval_id = _APPROVAL_STORE.approval_id(fingerprint)

    _APPROVAL_AUDIT.record(
        "constraint_relaxation_approval_initiated",
        f"constraint-{fingerprint}",
        {
            "domain": payload.domain,
            "parameter": payload.parameter,
            "proposed_change": payload.proposed_change,
            "governance_tier": tier,
            "estimated_impact": payload.estimated_impact,
            "estimated_impact_units": payload.estimated_impact_units,
            "requestor": payload.requestor,
            "approval_id": approval_id,
        },
    )

    return ConstraintApprovalResponse(
        approval_id=approval_id,
        governance_tier=tier,
        required_approver_role=required_role,
        status="pending",
        message=(
            f"Approval request registered as {approval_id}. "
            f"This change requires {required_role} sign-off. "
            f"Submit a decision via POST /api/approvals/decisions with this approval_id."
        ),
    )


def _build_direct_request(payload: DirectOptimizationRequest) -> OptimizationRequest:
    spec = WORKFLOWS[payload.domain]
    context = {**spec.base_context, **payload.context}
    if payload.optimizer_runtime != "phase1":
        context["optimizer_runtime"] = payload.optimizer_runtime
    if payload.production_optimizer_id:
        context["production_optimizer_id"] = payload.production_optimizer_id
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


def _persist_narrative(
    workflow_id: str,
    response: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> None:
    try:
        narrative = build_workflow_audit_narrative(
            response=response,
            payload=payload,
        )
        _NARRATIVE_STORE[workflow_id] = _json(narrative)
    except Exception:  # noqa: BLE001 — narrative is best-effort; never block the run
        pass


def _safe_filename(value: str) -> str:
    safe = "".join(
        character.lower() if character.isalnum() else "-"
        for character in value.strip()
    ).strip("-")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe or "workflow-demo"
