"""Deterministic intent agent."""

from __future__ import annotations

from decision_intelligence.chat.parser import detect_domain, detect_scenarios
from decision_intelligence.workflows.library import (
    COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID,
    FUNDING_CAPACITY_SHOCK_WORKFLOW_ID,
    LIQUIDITY_STRESS_WORKFLOW_ID,
    PORTFOLIO_REBALANCE_MVO_WORKFLOW_ID,
)

from .types import AgentAction, AgentIntent


class IntentAgent:
    """Infer a structured optimization intent from plain language."""

    def analyze(self, text: str) -> AgentIntent:
        normalized = text.strip().lower()
        domain = detect_domain(text)
        scenarios = detect_scenarios(text)
        workflow_id = _detect_workflow_id(normalized)
        action, action_signal = _detect_action(normalized, scenarios, workflow_id)
        signals = []
        if workflow_id:
            signals.append(f"workflow:{workflow_id}")
        if domain:
            signals.append(f"domain:{domain}")
        if action_signal:
            signals.append(action_signal)
        signals.extend(f"scenario:{name}" for name in scenarios)
        missing = [] if domain or workflow_id else ["domain"]
        confidence = _confidence(domain, action, scenarios, workflow_id)
        return AgentIntent(
            raw_text=text,
            action=action,
            domain=domain,
            workflow_id=workflow_id,
            confidence=confidence,
            scenarios=scenarios,
            missing_inputs=missing,
            signals=signals,
        )


def _detect_action(
    text: str,
    scenarios: list[str],
    workflow_id: str | None,
) -> tuple[AgentAction, str | None]:
    if workflow_id:
        return "multi_domain_workflow", "action:multi_domain_workflow"
    if any(token in text for token in ("pdf", "ingest", "parse", "document")):
        return "ingest", "action:ingest"
    if any(token in text for token in ("why", "explain", "rationale")):
        return "explain", "action:explain"
    if scenarios or any(token in text for token in ("scenario", "stress", "downside")):
        return "scenario_analysis", "action:scenario_analysis"
    if any(token in text for token in ("optimize", "allocate", "solve", "run", "recommend")):
        return "optimize", "action:optimize"
    return "optimize", "action:default_optimize"


def _detect_workflow_id(text: str) -> str | None:
    workflow_signal = any(
        token in text
        for token in (
            "workflow",
            "chain",
            "multi domain",
            "multi-domain",
            "end to end",
            "end-to-end",
            "full",
            "sequential",
        )
    )
    if "liquidity stress" in text or (
        workflow_signal and "liquidity" in text and "fund" in text
    ):
        return LIQUIDITY_STRESS_WORKFLOW_ID
    if "funding capacity" in text or "capacity shock" in text:
        return FUNDING_CAPACITY_SHOCK_WORKFLOW_ID
    if "collateral liquidity" in text or (
        workflow_signal and "collateral" in text and "liquidity" in text
    ):
        return COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID
    if "rebalance" in text and ("mvo" in text or "asset allocation" in text):
        return PORTFOLIO_REBALANCE_MVO_WORKFLOW_ID
    return None


def _confidence(
    domain: str | None,
    action: AgentAction,
    scenarios: list[str],
    workflow_id: str | None,
) -> float:
    score = 0.25
    if workflow_id:
        score += 0.55
    if domain:
        score += 0.45
    if action != "unknown":
        score += 0.15
    if scenarios:
        score += 0.10
    return min(round(score, 2), 0.95)
