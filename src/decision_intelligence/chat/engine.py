"""Stateful deterministic chat workflow engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from decision_intelligence.contracts import Objective, OptimizationRequest, Scenario
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.contracts.scenarios import ScenarioType

from .parser import detect_domain, detect_scenarios, is_no, is_yes
from .workflows import SCENARIO_PRESETS, WORKFLOWS, FieldSpec, WorkflowSpec


@dataclass(frozen=True)
class ChatResponse:
    message: str
    request: OptimizationRequest | None = None
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

    @property
    def active(self) -> bool:
        return self._state is not None

    def reply(self, text: str) -> ChatResponse:
        prompt = text.strip()
        low = prompt.lower()

        if low in {"exit", "quit", "q", "bye"}:
            self._state = None
            return ChatResponse("Leaving guided workflow.", should_exit=True)

        if self._state is None:
            domain = detect_domain(prompt)
            if domain is None:
                return ChatResponse(
                    "Tell me which workflow you want: collateral, money market, or financing."
                )
            return self._start(domain, prompt)

        if self._state.awaiting_confirmation:
            return self._handle_confirmation(prompt)

        return self._handle_answer(prompt)

    def _start(self, domain: str, prompt: str) -> ChatResponse:
        spec = WORKFLOWS[domain]
        self._state = _WorkflowState(spec=spec, seed=self.seed)

        scenarios = detect_scenarios(prompt)
        if scenarios:
            self._state.values["scenario_names"] = scenarios

        return ChatResponse(f"{spec.intro}\n\n{self._next_question()}")

    def _handle_answer(self, prompt: str) -> ChatResponse:
        state = self._require_state()
        field_spec = self._current_field()
        if field_spec is None:
            state.awaiting_confirmation = True
            return ChatResponse(self._confirmation_message())

        try:
            value = self._parse_field(field_spec, prompt)
        except ValueError as exc:
            return ChatResponse(f"{exc}\n\n{self._format_question(field_spec)}")

        state.values[field_spec.key] = value
        state.current_index += 1

        next_question = self._next_question()
        if next_question:
            return ChatResponse(next_question)

        state.awaiting_confirmation = True
        return ChatResponse(self._confirmation_message())

    def _handle_confirmation(self, prompt: str) -> ChatResponse:
        if is_yes(prompt):
            request = self._build_request()
            self._state = None
            return ChatResponse("Confirmed. Running optimization...", request=request)
        if is_no(prompt):
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

    def _advance_to_missing_field(self) -> FieldSpec | None:
        state = self._require_state()
        while state.current_index < len(state.spec.fields):
            field_spec = state.spec.fields[state.current_index]
            if field_spec.key not in state.values:
                return field_spec
            state.current_index += 1
        return None

    def _current_field(self) -> FieldSpec | None:
        state = self._require_state()
        if state.current_index >= len(state.spec.fields):
            return None
        return state.spec.fields[state.current_index]

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


def _format_value(value: Any, field_spec: FieldSpec) -> str:
    if field_spec.target == "scenarios":
        return ", ".join(value) if value else "none"
    if isinstance(value, int | float):
        if field_spec.key.endswith("_cash") or field_spec.key.endswith("_need"):
            return f"${value / 1_000_000:,.0f}M"
    if isinstance(value, float):
        if 0 <= value <= 1:
            return f"{value:.0%}"
        return f"{value:g}%"
    return str(value)
