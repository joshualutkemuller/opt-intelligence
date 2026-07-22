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
from collateral_schedule import CollateralDatabase, parse_pdf_with_llm, parse_schedule
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
    CollateralEntryResponse,
    CollateralEntryUpdateRequest,
    CollateralScheduleIngestRequest,
    CollateralScheduleIngestResponse,
    CollateralScheduleResponse,
    CounterpartyCreateRequest,
    CounterpartyResponse,
    CounterpartyListResponse,
    MarginAgreementCreateRequest,
    MarginAgreementResponse,
    MarginAgreementListResponse,
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

import pathlib as _pathlib

_COLLATERAL_DB = CollateralDatabase()
_CHAT_SESSIONS: dict[str, ChatSession] = {}
_APPROVAL_STORE = ApprovalStore()
_APPROVAL_AUDIT = AuditLog()

# Approver registry: maps approver_id → {name, role, max_tier}.
# max_tier is the highest governance tier this approver is authorized to approve.
_APPROVER_REGISTRY: dict[str, dict[str, Any]] = {
    "analyst.risk": {
        "id": "analyst.risk",
        "name": "Alex Chen",
        "role": "Risk Analyst",
        "max_tier": 3,
    },
    "head.domain": {
        "id": "head.domain",
        "name": "Morgan Davis",
        "role": "Domain Head",
        "max_tier": 3,
    },
    "md.funding": {
        "id": "md.funding",
        "name": "Jordan Lee",
        "role": "Senior Funding MD",
        "max_tier": 4,
    },
    "cro": {
        "id": "cro",
        "name": "Sam Rivera",
        "role": "Chief Risk Officer",
        "max_tier": 5,
    },
    "cco": {
        "id": "cco",
        "name": "Taylor Kim",
        "role": "Chief Compliance Officer",
        "max_tier": 5,
    },
}

# approval_id → governance tier, populated when an approval is registered
# so that submit_approval_decision can validate tier authority.
_APPROVAL_TIER_MAP: dict[str, int] = {}
_DRIFT_MONITOR = DriftMonitor()
_GOVERNANCE_ORCHESTRATOR = GovernanceOrchestrator(
    store=_APPROVAL_STORE,
    audit=_APPROVAL_AUDIT,
)

# Narrative store — in-memory with disk backing so exports survive API restarts.
_NARRATIVE_DIR = _pathlib.Path.home() / ".decision_intelligence" / "narratives"
_NARRATIVE_DIR.mkdir(parents=True, exist_ok=True)


def _load_narrative_store() -> dict[str, dict[str, Any]]:
    store: dict[str, dict[str, Any]] = {}
    for path in _NARRATIVE_DIR.glob("*.json"):
        try:
            store[path.stem] = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            pass
    return store


_NARRATIVE_STORE: dict[str, dict[str, Any]] = _load_narrative_store()


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
        _persist_narrative(
            workflow_id=patched_plan.workflow_id,
            response={"plan": _json(patched_plan), "result": workflow_result},
        )
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



def _to_entry_response(r: dict) -> CollateralEntryResponse:
    return CollateralEntryResponse(
        id=r["id"],
        agreement_id=r["agreement_id"],
        asset_class=r["asset_class"],
        isin=r.get("isin"),
        isin_invalid=r.get("isin_invalid"),
        currency=r.get("currency"),
        rating_floor=r.get("rating_floor"),
        max_maturity_years=r.get("max_maturity_years"),
        haircut_pct=r["haircut_pct"],
        concentration_limit_pct=r.get("concentration_limit_pct"),
        eligible=bool(r["eligible"]),
        notes=r.get("notes"),
        source_row=r.get("source_row"),
        created_at=r["created_at"],
        schedule_version=r.get("schedule_version", 1),
    )


# ── Collateral schedule management ───────────────────────────────────────────

@app.post("/api/collateral/counterparties", response_model=CounterpartyResponse)
def create_counterparty(payload: CounterpartyCreateRequest) -> CounterpartyResponse:
    """Register a new counterparty."""
    rec = _COLLATERAL_DB.upsert_counterparty(
        name=payload.name,
        lei=payload.lei,
        jurisdiction=payload.jurisdiction,
        counterparty_id=payload.counterparty_id,
    )
    return CounterpartyResponse(**rec)


@app.get("/api/collateral/counterparties", response_model=CounterpartyListResponse)
def list_counterparties() -> CounterpartyListResponse:
    rows = _COLLATERAL_DB.list_counterparties()
    return CounterpartyListResponse(counterparties=[CounterpartyResponse(**r) for r in rows])


@app.post("/api/collateral/agreements", response_model=MarginAgreementResponse)
def create_margin_agreement(payload: MarginAgreementCreateRequest) -> MarginAgreementResponse:
    """Create a margin agreement (counterparty × margin type)."""
    if not _COLLATERAL_DB.get_counterparty(payload.counterparty_id):
        raise HTTPException(
            status_code=404,
            detail=f"Counterparty '{payload.counterparty_id}' not found. Create it first.",
        )
    rec = _COLLATERAL_DB.create_agreement(
        counterparty_id=payload.counterparty_id,
        margin_type=payload.margin_type,
        agreement_ref=payload.agreement_ref,
        base_currency=payload.base_currency,
        threshold_amount=payload.threshold_amount,
        mta_amount=payload.mta_amount,
        rounding_amount=payload.rounding_amount,
        governing_law=payload.governing_law,
        effective_date=payload.effective_date,
    )
    return MarginAgreementResponse(**rec)


@app.get("/api/collateral/agreements", response_model=MarginAgreementListResponse)
def list_margin_agreements(
    counterparty_id: str | None = None,
    margin_type: str | None = None,
) -> MarginAgreementListResponse:
    rows = _COLLATERAL_DB.list_agreements(
        counterparty_id=counterparty_id,
        margin_type=margin_type,
    )
    return MarginAgreementListResponse(agreements=[MarginAgreementResponse(**r) for r in rows])


@app.get("/api/collateral/agreements/{agreement_id}", response_model=MarginAgreementResponse)
def get_margin_agreement(agreement_id: str) -> MarginAgreementResponse:
    rec = _COLLATERAL_DB.get_agreement(agreement_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found.")
    return MarginAgreementResponse(**rec)


@app.post(
    "/api/collateral/agreements/{agreement_id}/ingest",
    response_model=CollateralScheduleIngestResponse,
)
def ingest_collateral_schedule(
    agreement_id: str,
    payload: CollateralScheduleIngestRequest,
) -> CollateralScheduleIngestResponse:
    """Parse and store a collateral schedule for the given margin agreement."""
    if not _COLLATERAL_DB.get_agreement(agreement_id):
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found.")

    if payload.csv_content:
        entries = parse_schedule(payload.csv_content, filename=payload.filename)
    elif payload.xlsx_base64:
        import base64 as _b64
        xlsx_bytes = _b64.b64decode(payload.xlsx_base64)
        entries = parse_schedule(xlsx_bytes, filename=payload.filename or "schedule.xlsx")
    elif payload.pdf_base64:
        import base64 as _b64
        pdf_bytes = _b64.b64decode(payload.pdf_base64)
        if payload.use_llm:
            try:
                provider = resolve_provider()
            except LLMConfigError as exc:
                raise HTTPException(status_code=502, detail=f"LLM provider error: {exc}") from exc
            if provider is None:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "No LLM provider is configured. Set provider and api_key in "
                        "config/llm.yaml, or set DI_LLM_API_KEY / ANTHROPIC_API_KEY / "
                        "OPENAI_API_KEY. Pass use_llm=false to fall back to text-heuristic "
                        "parsing (CSV/XLSX-style PDFs only)."
                    ),
                )
            try:
                entries = parse_pdf_with_llm(pdf_bytes, provider)
            except LLMError as exc:
                raise HTTPException(status_code=502, detail=f"LLM extraction failed: {exc}") from exc
        else:
            entries = parse_schedule(pdf_bytes, filename=payload.filename or "schedule.pdf")
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide one of: csv_content, xlsx_base64, or pdf_base64.",
        )

    if not entries:
        hint = (
            "No collateral entries could be parsed from the provided file. "
            + (
                "The LLM returned no structured entries — check that the PDF contains "
                "a collateral eligibility or haircut schedule table."
                if payload.pdf_base64 and payload.use_llm
                else "Ensure headers include: asset_class, haircut_pct (or synonyms). "
                "See GET /api/collateral/schema for accepted column names."
            )
        )
        raise HTTPException(status_code=422, detail=hint)

    isin_warnings = [
        {"source_row": e.get("source_row"), "isin": e["isin"], "reason": e["isin_invalid"]}
        for e in entries
        if e.get("isin_invalid")
    ]

    count = _COLLATERAL_DB.insert_entries(
        agreement_id=agreement_id,
        entries=entries,
        replace=payload.replace,
    )
    summary = _COLLATERAL_DB.summary(agreement_id)
    return CollateralScheduleIngestResponse(
        agreement_id=agreement_id,
        entries_inserted=count,
        replaced=payload.replace,
        summary=summary,
        isin_warnings=isin_warnings,
    )


@app.get(
    "/api/collateral/agreements/{agreement_id}/schedule",
    response_model=CollateralScheduleResponse,
)
def get_collateral_schedule(
    agreement_id: str,
    asset_class: str | None = None,
    eligible_only: bool = False,
) -> CollateralScheduleResponse:
    if not _COLLATERAL_DB.get_agreement(agreement_id):
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found.")

    rows = _COLLATERAL_DB.list_entries(
        agreement_id=agreement_id,
        asset_class=asset_class,
        eligible_only=eligible_only,
    )
    summary = _COLLATERAL_DB.summary(agreement_id)

    return CollateralScheduleResponse(
        agreement_id=agreement_id,
        entries=[_to_entry_response(r) for r in rows],
        summary=summary,
    )


@app.delete("/api/collateral/agreements/{agreement_id}/schedule")
def clear_collateral_schedule(agreement_id: str) -> dict:
    if not _COLLATERAL_DB.get_agreement(agreement_id):
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found.")
    deleted = _COLLATERAL_DB.delete_entries(agreement_id)
    return {"agreement_id": agreement_id, "entries_deleted": deleted}


@app.get("/api/collateral/agreements/{agreement_id}/history")
def get_collateral_schedule_history(agreement_id: str) -> dict:
    """Return a version-by-version audit trail of schedule ingestions."""
    if not _COLLATERAL_DB.get_agreement(agreement_id):
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found.")
    versions = _COLLATERAL_DB.list_schedule_history(agreement_id)
    return {"agreement_id": agreement_id, "versions": versions}


@app.patch(
    "/api/collateral/entries/{entry_id}",
    response_model=CollateralEntryResponse,
)
def update_collateral_entry(
    entry_id: str,
    payload: CollateralEntryUpdateRequest,
) -> CollateralEntryResponse:
    """Update editable fields on a single live collateral entry."""
    existing = _COLLATERAL_DB.get_entry(entry_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Entry '{entry_id}' not found.")
    if existing.get("superseded_at"):
        raise HTTPException(status_code=409, detail="Cannot edit a superseded (historical) entry.")
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = _COLLATERAL_DB.update_entry(entry_id, fields)
    return _to_entry_response(updated)


@app.delete("/api/collateral/entries/{entry_id}")
def delete_collateral_entry(entry_id: str) -> dict:
    """Hard-delete a single live collateral entry."""
    existing = _COLLATERAL_DB.get_entry(entry_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Entry '{entry_id}' not found.")
    if existing.get("superseded_at"):
        raise HTTPException(status_code=409, detail="Cannot delete a superseded (historical) entry.")
    deleted = _COLLATERAL_DB.delete_entry(entry_id)
    return {"entry_id": entry_id, "deleted": deleted}


@app.get("/api/collateral/schema")
def get_collateral_schema() -> dict:
    """Return the accepted column name aliases for schedule ingestion."""
    from decision_intelligence.collateral.models import COLUMN_ALIASES, ASSET_CLASS_ALIASES
    return {
        "column_aliases": COLUMN_ALIASES,
        "asset_class_aliases": {k: v.value for k, v in ASSET_CLASS_ALIASES.items()},
        "margin_types": ["IM", "VM", "REPO", "SBL", "CCP_IM", "HOUSE", "OTHER"],
    }


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


@app.get("/api/approvers")
def list_approvers() -> dict[str, Any]:
    """Return the registered approver roster with their tier authority."""
    return {"approvers": list(_APPROVER_REGISTRY.values())}


@app.get("/api/approvals/pending", response_model=PendingApprovalsResponse)
def list_pending_approvals() -> PendingApprovalsResponse:
    return PendingApprovalsResponse(approvals=_pending_approval_items())


@app.post("/api/approvals/decisions", response_model=ApprovalDecisionResponse)
def submit_approval_decision(
    payload: ApprovalDecisionRequest,
) -> ApprovalDecisionResponse:
    approver_id = payload.approver.strip()
    if not approver_id:
        raise HTTPException(status_code=400, detail="Approver is required.")

    approver_rec = _APPROVER_REGISTRY.get(approver_id)
    if approver_rec is None:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Approver '{approver_id}' is not in the registered approver list. "
                "Use GET /api/approvers to see valid approver IDs."
            ),
        )

    # Validate tier authority when granting (rejections are always allowed).
    if payload.granted:
        required_tier = _APPROVAL_TIER_MAP.get(payload.approval_id, 0)
        if required_tier > approver_rec["max_tier"]:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Approver '{approver_id}' ({approver_rec['role']}) is authorized "
                    f"up to tier {approver_rec['max_tier']}, but this approval requires "
                    f"tier {required_tier}. "
                    f"Required role: {_TIER_APPROVER_ROLES.get(required_tier, f'Tier {required_tier} approver')}."
                ),
            )

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
    if audit_narrative is None:
        # Generate on-the-fly so a cold export still produces a complete PDF.
        _persist_narrative(
            workflow_id=wf_id or "export",
            response=payload.response,
            payload=payload.payload,
        )
        audit_narrative = _NARRATIVE_STORE.get(wf_id or "export")
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
        _persist_narrative(
            workflow_id=str(wf_id),
            response=payload.response,
            payload=payload.payload,
        )
        # Use the (possibly LLM-polished) narrative rather than re-generating.
        _NARRATIVE_STORE[str(wf_id)] = _json(narrative)
        (_NARRATIVE_DIR / f"{wf_id}.json").write_text(json.dumps(_json(narrative), indent=2))
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
    if decision.approval_id:
        _APPROVAL_TIER_MAP[decision.approval_id] = decision.tier
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

    approver_rec = _APPROVER_REGISTRY.get(approver)
    if approver_rec is None:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Approver '{approver}' is not in the registered approver list. "
                "Use GET /api/approvers to see valid approver IDs."
            ),
        )
    if granted:
        required_tier = _APPROVAL_TIER_MAP.get(approval_id, 0)
        if required_tier > approver_rec["max_tier"]:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Approver '{approver}' ({approver_rec['role']}) is authorized "
                    f"up to tier {approver_rec['max_tier']}, but this approval requires "
                    f"tier {required_tier}. "
                    f"Required role: {_TIER_APPROVER_ROLES.get(required_tier, f'Tier {required_tier} approver')}."
                ),
            )

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


@app.post("/api/drift/reoptimize")
def drift_reoptimize(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Re-run the optimizer for a single domain flagged by a drift alert.

    Accepts ``domain``, ``workflow_id`` (optional), ``portfolio_id``, ``seed``,
    ``context``, ``optimizer_runtime``, and ``production_optimizer_id``.
    After the run the drift baseline is updated so the next check starts fresh.
    Returns the domain step result and updated objective value.
    """
    from decision_intelligence.contracts.objectives import ObjectiveDirection
    from decision_intelligence.workflows import DEFAULT_WORKFLOW_REGISTRY

    domain = str(payload.get("domain", ""))
    portfolio_id = str(payload.get("portfolio_id", "PORT_001"))
    seed = int(payload.get("seed", 42))
    context: dict[str, Any] = dict(payload.get("context") or {})
    optimizer_runtime = str(payload.get("optimizer_runtime", "phase1"))
    production_optimizer_id = payload.get("production_optimizer_id")
    workflow_id = str(payload.get("workflow_id", "")) or None

    _DOMAIN_OPTIMIZER_MAP: dict[str, Any] = {
        "asset_allocation": AssetAllocationMVOOptimizer,
        "collateral": CollateralOptimizer,
        "money_market": MoneyMarketOptimizer,
        "financing": FinancingOptimizer,
    }
    optimizer_cls = _DOMAIN_OPTIMIZER_MAP.get(domain)
    if optimizer_cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown domain for drift reoptimize: {domain!r}")

    _DOMAIN_OBJECTIVE: dict[str, tuple[str, str]] = {
        "asset_allocation": ("maximize_return", "portfolio_return"),
        "collateral": ("minimize_funding_cost", "funding_cost"),
        "money_market": ("maximize_yield", "yield"),
        "financing": ("minimize_financing_cost", "financing_cost"),
    }
    obj_name, obj_metric = _DOMAIN_OBJECTIVE.get(domain, ("optimize", "objective_value"))
    direction = (
        ObjectiveDirection.MAXIMIZE
        if obj_name.startswith("maximize")
        else ObjectiveDirection.MINIMIZE
    )

    if optimizer_runtime != "phase1":
        context["optimizer_runtime"] = optimizer_runtime
    if production_optimizer_id:
        context["production_optimizer_id"] = production_optimizer_id

    request = OptimizationRequest(
        domain=domain,
        portfolio_id=portfolio_id,
        objective=Objective(name=obj_name, direction=direction, metric=obj_metric),
        context=context,
        seed=seed,
    )

    optimizer = optimizer_cls()
    problem = optimizer.prepare_problem(request)
    solution = optimizer.solve(problem)

    # Update drift baseline with a synthetic per-domain result so the monitor
    # stops firing for this domain after the auto-reoptimize completes.
    synthetic_result: dict[str, Any] = {
        "step_results": [
            {
                "domain": domain,
                "result": solution,
                "objective_value": solution.get("objective_value"),
                "status": solution.get("status"),
            }
        ]
    }
    _DRIFT_MONITOR.snapshot(synthetic_result)

    return {
        "domain": domain,
        "status": solution.get("status", "unknown"),
        "objective_value": solution.get("objective_value"),
        "result": solution,
        "reoptimized_at": _DRIFT_MONITOR.baseline_time(),
    }


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
    _APPROVAL_TIER_MAP[approval_id] = tier

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
        narrative_dict = _json(narrative)
        _NARRATIVE_STORE[workflow_id] = narrative_dict
        (_NARRATIVE_DIR / f"{workflow_id}.json").write_text(
            json.dumps(narrative_dict, indent=2)
        )
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
