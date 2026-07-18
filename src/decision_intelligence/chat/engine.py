"""Stateful deterministic chat workflow engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from decision_intelligence.agents import (
    AgentIntent,
    AgentTraceEvent,
    ExecutionPlan,
    IntentAgent,
    PlanningAgent,
    PlanStep,
)
from decision_intelligence.contracts import (
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
    Scenario,
)
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.contracts.scenarios import ScenarioType
from decision_intelligence.workflows import DEFAULT_WORKFLOW_REGISTRY, WorkflowPlan
from decision_intelligence.workflows.config_loader import WorkflowInputConfig

from .parser import (
    detect_domain,
    detect_scenarios,
    is_no,
    is_yes,
    parse_amount,
    parse_float,
    parse_fraction,
    parse_int,
)
from .workflows import SCENARIO_PRESETS, WORKFLOWS, FieldSpec, WorkflowSpec


@dataclass(frozen=True)
class ChatResponse:
    message: str
    request: OptimizationRequest | None = None
    workflow_plan: WorkflowPlan | None = None
    should_exit: bool = False


@dataclass
class _WorkflowState:
    spec: WorkflowSpec
    seed: int
    values: dict[str, Any] = field(default_factory=dict)
    current_index: int = 0
    awaiting_confirmation: bool = False


class ChatSession:
    """Collect optimization request fields one turn at a time."""

    def __init__(self, *, seed: int = 42, default_portfolio: str = "PORT_001") -> None:
        self.seed = seed
        self.default_portfolio = default_portfolio
        self._state: _WorkflowState | None = None
        self._intent_agent = IntentAgent()
        self._planning_agent = PlanningAgent()
        self._last_intent: AgentIntent | None = None
        self._last_plan: ExecutionPlan | None = None
        self._trace: list[AgentTraceEvent] = []

    @property
    def active(self) -> bool:
        return self._state is not None

    def snapshot(self) -> dict[str, Any]:
        """Return browser-friendly workflow state for the current chat session."""
        if self._state is None:
            return {
                "domain": None,
                "title": None,
                "collected": {},
                "next_field": None,
                "awaiting_confirmation": False,
                "intent": _dump_model(self._last_intent),
                "plan": _dump_model(self._last_plan),
                "trace": _dump_models(self._trace),
            }

        state = self._state
        plan = self._build_plan()
        next_field = (
            plan.missing_fields[0]
            if not state.awaiting_confirmation and plan.missing_fields
            else None
        )
        if not state.awaiting_confirmation:
            self._sync_index_to_plan(plan)

        return {
            "domain": state.spec.domain,
            "title": state.spec.title,
            "collected": dict(state.values),
            "next_field": next_field,
            "awaiting_confirmation": state.awaiting_confirmation,
            "intent": _dump_model(self._last_intent),
            "plan": _dump_model(plan),
            "trace": _dump_models(self._trace),
        }

    def reply(self, text: str) -> ChatResponse:
        prompt = text.strip()
        low = prompt.lower()

        if low in {"exit", "quit", "q", "bye"}:
            self._record_trace("session_exit", "User exited the guided workflow.")
            self._state = None
            return ChatResponse("Leaving guided workflow.", should_exit=True)

        if self._state is None:
            intent = self._intent_agent.analyze(prompt)
            self._last_intent = intent
            self._record_trace(
                "intent_detected",
                "Detected user intent from the opening message.",
                intent=intent.model_dump(),
            )
            if intent.action == "multi_domain_workflow" and intent.workflow_id:
                return self._start_multi_domain_workflow(prompt, intent)
            domain = intent.domain or detect_domain(prompt)
            if domain is None:
                return ChatResponse(
                    "Tell me which workflow you want: asset allocation, collateral, "
                    "money market, financing, or a full sequential workflow."
                )
            return self._start(domain, prompt, intent)

        if self._state.awaiting_confirmation:
            return self._handle_confirmation(prompt)

        return self._handle_answer(prompt)

    def _start(
        self,
        domain: str,
        prompt: str,
        intent: AgentIntent | None = None,
    ) -> ChatResponse:
        spec = WORKFLOWS[domain]
        self._state = _WorkflowState(spec=spec, seed=self.seed)

        intent = intent or self._intent_agent.analyze(prompt)
        self._last_intent = intent.model_copy(update={"domain": domain})
        scenarios = intent.scenarios or detect_scenarios(prompt)
        if scenarios:
            self._state.values["scenario_names"] = scenarios

        plan = self._build_plan()
        self._record_trace(
            "plan_built",
            "Built an execution plan from detected intent.",
            plan=plan.model_dump(),
        )
        return ChatResponse(f"{spec.intro}\n\n{plan.summary}\n\n{self._next_question()}")

    def _start_multi_domain_workflow(
        self,
        prompt: str,
        intent: AgentIntent,
    ) -> ChatResponse:
        workflow_id = intent.workflow_id
        if workflow_id is None:
            return ChatResponse(
                "Tell me which sequential workflow you want: liquidity stress funding, "
                "funding capacity shock, collateral liquidity review, or MVO rebalance."
            )

        template = DEFAULT_WORKFLOW_REGISTRY.get(workflow_id)
        if template.inputs and _should_collect_registered_inputs(prompt):
            spec = _workflow_spec_from_template(template)
            portfolio_id = _detect_portfolio_id(prompt)
            self._state = _WorkflowState(spec=spec, seed=self.seed)
            if portfolio_id:
                self._state.values["portfolio_id"] = portfolio_id
            self._last_plan = self._build_registered_execution_plan(self._state)
            self._record_trace(
                "registered_workflow_collection_started",
                "Started field-by-field collection from workflow registry metadata.",
                workflow_id=workflow_id,
                input_count=len(template.inputs),
                plan=self._last_plan.model_dump(),
            )
            return ChatResponse(
                f"I will guide {template.name} using its registered workflow inputs.\n\n"
                f"{self._last_plan.summary}\n\n{self._next_question()}"
            )

        portfolio_id = _detect_portfolio_id(prompt) or self.default_portfolio
        context = _workflow_context_from_intent(intent)
        plan = DEFAULT_WORKFLOW_REGISTRY.build(
            workflow_id,
            portfolio_id=portfolio_id,
            seed=self.seed,
            context=context,
        )
        self._last_plan = _execution_plan_from_workflow(intent, plan)
        self._record_trace(
            "workflow_plan_built",
            "Built a registered multi-domain workflow plan from detected intent.",
            workflow_id=plan.workflow_id,
            plan=self._last_plan.model_dump(),
        )
        self._record_trace(
            "workflow_request_compiled",
            "Compiled WorkflowPlan for sequential optimizer execution.",
            workflow_id=plan.workflow_id,
            step_count=len(plan.steps),
        )
        return ChatResponse(
            (
                f"Running {plan.name} as a sequential workflow with "
                f"{len(plan.steps)} optimizer steps..."
            ),
            workflow_plan=plan,
        )

    def _handle_answer(self, prompt: str) -> ChatResponse:
        state = self._require_state()
        plan = self._build_plan()
        field_spec = self._current_field(plan)
        if field_spec is None:
            state.awaiting_confirmation = True
            self._record_trace(
                "plan_ready",
                "All plan-required inputs have been collected.",
                plan=plan.model_dump(),
            )
            return ChatResponse(self._confirmation_message())

        try:
            value = self._parse_field(field_spec, prompt)
        except ValueError as exc:
            return ChatResponse(f"{exc}\n\n{self._format_question(field_spec)}")

        state.values[field_spec.key] = value
        self._record_trace(
            "field_collected",
            f"Collected {field_spec.display_label}.",
            field=field_spec.key,
            value=value,
        )
        self._sync_index_to_plan()

        next_question = self._next_question()
        if next_question:
            return ChatResponse(next_question)

        state.awaiting_confirmation = True
        self._record_trace(
            "plan_ready",
            "All plan-required inputs have been collected.",
            plan=self._build_plan().model_dump(),
        )
        return ChatResponse(self._confirmation_message())

    def _handle_confirmation(self, prompt: str) -> ChatResponse:
        if is_yes(prompt):
            if self._is_registered_workflow_state():
                workflow_plan = self._build_registered_workflow_plan()
                self._record_trace(
                    "workflow_request_compiled",
                    "Compiled registered WorkflowPlan from the confirmed plan.",
                    workflow_id=workflow_plan.workflow_id,
                    step_count=len(workflow_plan.steps),
                )
                self._state = None
                return ChatResponse(
                    "Confirmed. Running sequential workflow...",
                    workflow_plan=workflow_plan,
                )
            request = self._build_request()
            self._record_trace(
                "request_compiled",
                "Compiled OptimizationRequest from the confirmed plan.",
                request_id=request.request_id,
                domain=request.domain,
                execution_mode=request.execution_mode.value,
            )
            self._state = None
            return ChatResponse("Confirmed. Running optimization...", request=request)
        if is_no(prompt):
            self._record_trace("plan_cancelled", "User cancelled the execution plan.")
            self._state = None
            return ChatResponse("Cancelled this workflow. Start another request when ready.")
        return ChatResponse("Please confirm with yes or no.\n\n" + self._confirmation_message())

    def _parse_field(self, field_spec: FieldSpec, prompt: str) -> Any:
        if prompt.strip().lower() in {"", "default", "use default", "skip"}:
            if field_spec.key == "portfolio_id":
                return self.default_portfolio
            return field_spec.default
        return field_spec.parser(prompt)

    def _next_question(self) -> str:
        field_spec = self._advance_to_missing_field()
        if field_spec is None:
            return ""
        return self._format_question(field_spec)

    def _advance_to_missing_field(self, plan: ExecutionPlan | None = None) -> FieldSpec | None:
        state = self._require_state()
        plan = plan or self._build_plan()
        if not plan.missing_fields:
            state.current_index = len(state.spec.fields)
            return None
        next_key = plan.missing_fields[0]
        for index, field_spec in enumerate(state.spec.fields):
            if field_spec.key == next_key:
                state.current_index = index
                return field_spec
        return None

    def _current_field(self, plan: ExecutionPlan | None = None) -> FieldSpec | None:
        state = self._require_state()
        plan = plan or self._build_plan()
        if not plan.missing_fields:
            return None
        next_key = plan.missing_fields[0]
        return next((field for field in state.spec.fields if field.key == next_key), None)

    def _format_question(self, field_spec: FieldSpec) -> str:
        value = self.default_portfolio if field_spec.key == "portfolio_id" else field_spec.default
        default = _format_value(value, field_spec)
        return f"{field_spec.prompt} [default: {default}]"

    def _confirmation_message(self) -> str:
        state = self._require_state()
        lines = [
            "I have enough to run the optimizer. Confirm?",
            "",
            f"- Domain: {state.spec.domain}",
            f"- Objective: {state.spec.direction.value} {state.spec.objective_metric}",
        ]
        for field_spec in state.spec.fields:
            value = state.values.get(field_spec.key, field_spec.default)
            lines.append(f"- {field_spec.display_label}: {_format_value(value, field_spec)}")
        lines.append("")
        lines.append("Type yes to run, or no to cancel.")
        return "\n".join(lines)

    def _build_request(self) -> OptimizationRequest:
        state = self._require_state()
        spec = state.spec
        context = {**spec.base_context, "seed": state.seed}
        portfolio_id = self.default_portfolio
        scenario_names: list[str] = []

        for field_spec in spec.fields:
            value = state.values.get(field_spec.key, field_spec.default)
            if field_spec.target == "portfolio":
                portfolio_id = value
            elif field_spec.target == "scenarios":
                scenario_names = list(value)
            else:
                context[field_spec.key] = value

        scenarios = [
            Scenario(
                name=name,
                scenario_type=ScenarioType.STRESS if "stress" in name else ScenarioType.DOWNSIDE,
                parameter_overrides=SCENARIO_PRESETS.get(name, {}).get(spec.domain, {}),
            )
            for name in scenario_names
        ]

        return OptimizationRequest(
            domain=spec.domain,
            portfolio_id=portfolio_id,
            objective=Objective(
                name=f"{spec.direction.value}_{spec.objective_metric}",
                direction=spec.direction,
                metric=spec.objective_metric,
            ),
            scenarios=scenarios,
            execution_mode=ExecutionMode.SCENARIO_ANALYSIS
            if scenarios
            else ExecutionMode.RECOMMENDATION,
            context=context,
            requestor="guided_cli",
        )

    def _require_state(self) -> _WorkflowState:
        if self._state is None:
            raise RuntimeError("No active workflow.")
        return self._state

    def _build_plan(self) -> ExecutionPlan:
        state = self._require_state()
        if self._registered_workflow_id(state.spec) is not None:
            self._last_plan = self._build_registered_execution_plan(state)
            return self._last_plan
        intent = self._last_intent or AgentIntent(raw_text="", domain=state.spec.domain)
        self._last_plan = self._planning_agent.build_plan(intent, collected=state.values)
        return self._last_plan

    def _sync_index_to_plan(self, plan: ExecutionPlan | None = None) -> None:
        self._advance_to_missing_field(plan)

    def _record_trace(self, event: str, message: str, **details: Any) -> None:
        self._trace.append(AgentTraceEvent(event=event, message=message, details=details))

    def _is_registered_workflow_state(self) -> bool:
        state = self._state
        return state is not None and self._registered_workflow_id(state.spec) is not None

    @staticmethod
    def _registered_workflow_id(spec: WorkflowSpec) -> str | None:
        prefix = "workflow:"
        if not spec.domain.startswith(prefix):
            return None
        return spec.domain[len(prefix):]

    def _build_registered_execution_plan(self, state: _WorkflowState) -> ExecutionPlan:
        workflow_id = self._registered_workflow_id(state.spec)
        missing_fields = [
            field.key for field in state.spec.fields if field.key not in state.values
        ]
        ready_to_run = not missing_fields
        summary = (
            f"Plan {state.spec.title}: collect {len(missing_fields)} remaining "
            "registered workflow inputs, compile a WorkflowPlan, run each optimizer "
            "step, then validate and explain the chain."
            if missing_fields
            else f"Plan {state.spec.title}: ready to compile the registered WorkflowPlan."
        )
        return ExecutionPlan(
            domain="multi_domain",
            title=state.spec.title,
            action="multi_domain_workflow",
            objective_metric="workflow",
            execution_mode=str(state.values.get("execution_mode", "recommendation")),
            summary=summary,
            collected_fields=dict(state.values),
            missing_fields=missing_fields,
            required_fields=[
                {
                    "key": field.key,
                    "label": field.display_label,
                    "target": field.target,
                    "default": field.default,
                }
                for field in state.spec.fields
            ],
            scenario_names=[],
            scenario_suggestions=[],
            solver_options={
                "supported_backends": ["scipy", "cvxpy"],
                "supported_problem_types": ["lp", "milp", "qp", "conic"],
            },
            steps=[
                PlanStep(
                    name="collect_registered_inputs",
                    description=f"Collect configured inputs for {workflow_id}.",
                    status="complete" if ready_to_run else "pending",
                ),
                PlanStep(
                    name="compile_workflow_plan",
                    description="Build the deterministic WorkflowPlan from registry metadata.",
                    status="complete" if ready_to_run else "pending",
                ),
                PlanStep(
                    name="run_sequential_workflow",
                    description=(
                        "Run optimizer steps with dependencies, validation, "
                        "and governance."
                    ),
                    status="pending",
                ),
            ],
            ready_to_run=ready_to_run,
        )

    def _build_registered_workflow_plan(self) -> WorkflowPlan:
        state = self._require_state()
        workflow_id = self._registered_workflow_id(state.spec)
        if workflow_id is None:
            raise RuntimeError("Active chat state is not a registered workflow.")
        context = dict(state.spec.base_context)
        portfolio_id = self.default_portfolio
        seed = state.seed
        for field_spec in state.spec.fields:
            value = state.values.get(field_spec.key, field_spec.default)
            if field_spec.key == "portfolio_id":
                portfolio_id = str(value)
            elif field_spec.key == "seed":
                seed = int(value)
            elif field_spec.key == "execution_mode":
                context["execution_mode"] = str(value)
            else:
                _set_nested_context_value(context, field_spec.key, value)
        return DEFAULT_WORKFLOW_REGISTRY.build(
            workflow_id,
            portfolio_id=portfolio_id,
            seed=seed,
            context=context,
        )


def _should_collect_registered_inputs(text: str) -> bool:
    normalized = text.lower()
    return any(
        token in normalized
        for token in (
            "guide",
            "walk me through",
            "line by line",
            "step by step",
            "collect",
            "ask me",
        )
    )


def _workflow_spec_from_template(template: Any) -> WorkflowSpec:
    return WorkflowSpec(
        domain=f"workflow:{template.workflow_id}",
        title=template.name,
        intro=f"I will guide {template.name} using the workflow registry.",
        objective_metric="workflow",
        direction=ObjectiveDirection.MAXIMIZE,
        fields=tuple(_field_spec_from_input(item) for item in template.inputs),
        base_context=dict(template.default_context),
    )


def _field_spec_from_input(item: WorkflowInputConfig) -> FieldSpec:
    return FieldSpec(
        key=item.key,
        prompt=f"{item.label}?",
        parser=_parser_for_input(item),
        default=item.default,
        target="portfolio" if item.key == "portfolio_id" else "context",
        label=item.label,
    )


def _parser_for_input(item: WorkflowInputConfig) -> Any:
    if item.type == "integer":
        return parse_int
    if item.type == "currency":
        return parse_amount
    if item.type in {"fraction", "percent"}:
        return parse_fraction
    if item.type == "number":
        return parse_float
    if item.type == "boolean":
        return _parse_boolean
    if item.type == "select":
        options = tuple(item.options)
        return lambda text: _parse_select(text, options)
    return _parse_text


def _parse_text(text: str) -> str:
    value = text.strip()
    if not value:
        raise ValueError("Enter a value.")
    return value


def _parse_boolean(text: str) -> bool:
    normalized = text.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError("Enter yes or no.")


def _parse_select(text: str, options: tuple[str, ...]) -> str:
    value = text.strip().lower().replace(" ", "_")
    if value in options:
        return value
    readable = ", ".join(option.replace("_", " ") for option in options)
    raise ValueError(f"Enter one of: {readable}.")


def _set_nested_context_value(
    context: dict[str, Any],
    path: str,
    value: Any,
) -> None:
    parts = path.split(".")
    cursor = context
    for part in parts[:-1]:
        existing = cursor.get(part)
        if not isinstance(existing, dict):
            existing = {}
            cursor[part] = existing
        cursor = existing
    cursor[parts[-1]] = value


def _format_value(value: Any, field_spec: FieldSpec) -> str:
    if field_spec.target == "scenarios":
        return ", ".join(value) if value else "none"
    if isinstance(value, int | float):
        if (
            field_spec.key.endswith("_cash")
            or field_spec.key.endswith("_need")
            or field_spec.key.endswith("_notional")
        ):
            return f"${value / 1_000_000:,.0f}M"
        if field_spec.key == "risk_aversion":
            return f"{value:g}"
    if isinstance(value, float):
        if 0 <= value <= 1:
            return f"{value:.0%}"
        return f"{value:g}%"
    return str(value)


def _workflow_context_from_intent(intent: AgentIntent) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if intent.scenarios:
        context["scenario"] = intent.scenarios[0]
    return context


def _execution_plan_from_workflow(
    intent: AgentIntent,
    workflow: WorkflowPlan,
) -> ExecutionPlan:
    return ExecutionPlan(
        domain="multi_domain",
        title=workflow.name,
        action="multi_domain_workflow",
        objective_metric="workflow",
        execution_mode="recommendation",
        summary=(
            f"Plan {workflow.name}: run {len(workflow.steps)} optimizer steps in "
            "sequence, apply cross-step dependencies, validate aggregate results, "
            "then explain the workflow."
        ),
        collected_fields={
            "workflow_id": workflow.workflow_id,
            "portfolio_id": workflow.context.get("portfolio_id"),
            "seed": workflow.context.get("seed"),
        },
        missing_fields=[],
        required_fields=[],
        scenario_names=list(intent.scenarios),
        scenario_suggestions=[],
        solver_options={
            "supported_backends": ["scipy", "cvxpy"],
            "supported_problem_types": ["lp", "milp", "qp", "conic"],
        },
        steps=[
            PlanStep(
                name=step.step_id,
                description=step.description or step.name,
                status="pending",
            )
            for step in workflow.steps
        ],
        ready_to_run=True,
    )


def _detect_portfolio_id(text: str) -> str | None:
    match = re.search(r"\bPORT[A-Z0-9_-]*\b", text, flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _dump_model(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return value.model_dump()


def _dump_models(values: list[Any]) -> list[dict[str, Any]]:
    return [value.model_dump() for value in values]
