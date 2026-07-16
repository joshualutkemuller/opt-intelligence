"""Deterministic intent agent."""

from __future__ import annotations

from decision_intelligence.chat.parser import detect_domain, detect_scenarios

from .types import AgentAction, AgentIntent


class IntentAgent:
    """Infer a structured optimization intent from plain language."""

    def analyze(self, text: str) -> AgentIntent:
        normalized = text.strip().lower()
        domain = detect_domain(text)
        scenarios = detect_scenarios(text)
        action, action_signal = _detect_action(normalized, scenarios)
        signals = []
        if domain:
            signals.append(f"domain:{domain}")
        if action_signal:
            signals.append(action_signal)
        signals.extend(f"scenario:{name}" for name in scenarios)
        missing = [] if domain else ["domain"]
        confidence = _confidence(domain, action, scenarios)
        return AgentIntent(
            raw_text=text,
            action=action,
            domain=domain,
            confidence=confidence,
            scenarios=scenarios,
            missing_inputs=missing,
            signals=signals,
        )


def _detect_action(text: str, scenarios: list[str]) -> tuple[AgentAction, str | None]:
    if any(token in text for token in ("pdf", "ingest", "parse", "document")):
        return "ingest", "action:ingest"
    if any(token in text for token in ("why", "explain", "rationale")):
        return "explain", "action:explain"
    if scenarios or any(token in text for token in ("scenario", "stress", "downside")):
        return "scenario_analysis", "action:scenario_analysis"
    if any(token in text for token in ("optimize", "allocate", "solve", "run", "recommend")):
        return "optimize", "action:optimize"
    return "optimize", "action:default_optimize"


def _confidence(domain: str | None, action: AgentAction, scenarios: list[str]) -> float:
    score = 0.25
    if domain:
        score += 0.45
    if action != "unknown":
        score += 0.15
    if scenarios:
        score += 0.10
    return min(round(score, 2), 0.95)
