"""Local FastAPI app for the browser-based Decision Intelligence demo."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from decision_intelligence.chat import ChatSession
from decision_intelligence.chat.workflows import SCENARIO_PRESETS, WORKFLOWS
from decision_intelligence.contracts import Objective, OptimizationRequest, Scenario
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.contracts.scenarios import ScenarioType
from decision_intelligence.governance import (
    ApprovalPolicy,
    ApprovalStore,
    GovernanceController,
)
from decision_intelligence.governance.audit import AuditLog
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)
from decision_intelligence.workflows import (
    DEFAULT_WORKFLOW_REGISTRY,
    SequentialWorkflowRunner,
)

from .schemas import (
    ChatMessageRequest,
    ChatSessionResponse,
    CreateChatSessionRequest,
    DirectOptimizationRequest,
    OptimizationResponse,
    WorkflowCatalogResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
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
            "Tell me which workflow you want: collateral, money market, or financing."
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

    if reply.request is not None:
        request = _json(reply.request)
        result = _json(_run_request(reply.request))

    state = session.snapshot()
    trace = state.get("trace", [])
    if result is not None:
        result["agent_trace"] = trace

    return ChatSessionResponse(
        session_id=session_id,
        assistant_message=reply.message,
        state=state,
        trace=trace,
        result=result,
        request=request,
    )


@app.post("/api/optimizations/run", response_model=OptimizationResponse)
def run_optimization(payload: DirectOptimizationRequest) -> OptimizationResponse:
    request = _build_direct_request(payload)
    result = _run_request(request)
    return OptimizationResponse(result=_json(result), request=_json(request))


@app.get("/api/workflows", response_model=WorkflowCatalogResponse)
def list_workflows() -> WorkflowCatalogResponse:
    return WorkflowCatalogResponse(workflows=DEFAULT_WORKFLOW_REGISTRY.list_catalog())


@app.post("/api/workflows/run", response_model=WorkflowRunResponse)
def run_workflow(payload: WorkflowRunRequest) -> WorkflowRunResponse:
    try:
        plan = DEFAULT_WORKFLOW_REGISTRY.build(
            payload.workflow,
            portfolio_id=payload.portfolio_id,
            seed=payload.seed,
            context=payload.context,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    orchestrator, _audit = _build_orchestrator()
    result = SequentialWorkflowRunner(orchestrator).run(plan)
    return WorkflowRunResponse(plan=_json(plan), result=_json(result))


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
    audit = AuditLog()
    registry = OptimizerRegistry()
    registry.register(CollateralOptimizer())
    registry.register(MoneyMarketOptimizer())
    registry.register(FinancingOptimizer())
    governance = GovernanceController(ApprovalPolicy(), ApprovalStore(), audit)
    return OptimizationOrchestrator(registry, audit, governance), audit


def _json(value: Any) -> dict[str, Any]:
    return jsonable_encoder(value)
