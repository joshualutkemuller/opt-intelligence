"""Compliance-readable audit narratives for workflow runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from decision_intelligence.llm.base import LLMProvider


class AuditNarrative(BaseModel):
    """Human-readable audit narrative plus structured source sections."""

    title: str
    generated_at: str
    decision_summary: str
    constraint_context: list[str] = Field(default_factory=list)
    approval_chain: list[str] = Field(default_factory=list)
    outcome: str
    risk_flags: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)
    markdown: str
    json_payload: dict[str, Any] = Field(default_factory=dict)
    llm_polished: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None


def build_workflow_audit_narrative(
    *,
    response: dict[str, Any],
    payload: dict[str, Any] | None = None,
    preset: dict[str, Any] | None = None,
    workflow: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> AuditNarrative:
    """Build a deterministic narrative from a completed workflow API response."""

    result = _record(response.get("result"))
    plan = _record(response.get("plan"))
    payload = _record(payload)
    preset = _record(preset)
    workflow = _record(workflow)
    steps = [_record(step) for step in result.get("step_results", []) or []]
    final_step = steps[-1] if steps else {}
    final_result = _record(final_step.get("result"))
    validation = _record(result.get("validation_summary"))
    dependency = _record(result.get("dependency_summary"))
    explanation = _record(result.get("explanation_report"))
    workflow_name = str(
        result.get("name")
        or workflow.get("name")
        or plan.get("name")
        or payload.get("workflow")
        or "Workflow run"
    )
    generated = generated_at or datetime.now(UTC).isoformat()

    narrative = AuditNarrative(
        title=f"Audit Narrative - {workflow_name}",
        generated_at=generated,
        decision_summary=_decision_summary(
            workflow_name=workflow_name,
            payload=payload,
            result=result,
            validation=validation,
            dependency=dependency,
            final_step=final_step,
            final_result=final_result,
        ),
        constraint_context=_constraint_context(steps, payload, explanation),
        approval_chain=_approval_chain(steps),
        outcome=_outcome(explanation, result, final_result),
        risk_flags=[],
        timeline=_timeline(result, steps),
        markdown="",
        json_payload={
            "workflow_id": result.get("workflow_id") or payload.get("workflow"),
            "preset_id": preset.get("preset_id"),
            "portfolio_id": payload.get("portfolio_id")
            or _dig(final_step, "request", "portfolio_id"),
            "status": result.get("status"),
            "validation": validation,
            "dependency_summary": dependency,
        },
    )
    risk_flags = _risk_flags(validation, steps, narrative.approval_chain)
    narrative = narrative.model_copy(update={"risk_flags": risk_flags})
    return narrative.model_copy(update={"markdown": _markdown(narrative)})


def _decision_summary(
    *,
    workflow_name: str,
    payload: dict[str, Any],
    result: dict[str, Any],
    validation: dict[str, Any],
    dependency: dict[str, Any],
    final_step: dict[str, Any],
    final_result: dict[str, Any],
) -> str:
    portfolio_id = payload.get("portfolio_id") or _dig(final_step, "request", "portfolio_id")
    final_domain = final_result.get("domain") or final_step.get("domain") or "final optimizer"
    final_status = final_result.get("status") or final_step.get("status") or "unknown"
    improvement = _fmt_number(final_result.get("improvement_pct"))
    return (
        f"{workflow_name} ran for portfolio {portfolio_id or 'unknown'} with workflow "
        f"status {result.get('status', 'unknown')}. The final {final_domain} step "
        f"finished {final_status} with improvement {improvement}%. Aggregate validation "
        f"{'passed' if validation.get('passed') else 'requires review'} and "
        f"{dependency.get('total_effects', 0)} cross-step dependency effects were recorded."
    )


def _constraint_context(
    steps: list[dict[str, Any]],
    payload: dict[str, Any],
    explanation: dict[str, Any],
) -> list[str]:
    lines = []
    context = _record(payload.get("context"))
    if context:
        lines.append(f"Workflow context included top-level keys: {', '.join(sorted(context))}.")
    visible_keys = {
        "total_cash",
        "daily_liquidity_req",
        "weekly_liquidity_req",
        "max_prime_fraction",
        "max_wam_days",
        "portfolio_notional",
        "target_return",
        "risk_aversion",
        "total_funding_need",
        "capacity_scale",
        "obligation_scale",
    }
    for step in steps:
        request_context = _record(_dig(step, "request", "context"))
        visible = {key: value for key, value in request_context.items() if key in visible_keys}
        if visible:
            lines.append(
                f"{step.get('name') or step.get('step_id')} used constraints: "
                f"{_kv_pairs(visible)}."
            )
    for driver in _list(explanation.get("key_drivers"))[:3]:
        lines.append(str(driver))
    return lines or ["No explicit constraint context was recorded in the workflow payload."]


def _approval_chain(steps: list[dict[str, Any]]) -> list[str]:
    chain = []
    for step in steps:
        governance = _record(_dig(step, "result", "governance"))
        if not governance:
            continue
        mode = governance.get("execution_mode")
        status = governance.get("status")
        tier = governance.get("tier")
        approval_id = governance.get("approval_id")
        reason = governance.get("escalation_reason") or governance.get("required_role")
        line = (
            f"{step.get('name') or step.get('step_id')}: mode={mode}, tier={tier}, "
            f"status={status}"
        )
        if approval_id:
            line += f", approval_id={approval_id}"
        if reason:
            line += f", reason={reason}"
        chain.append(line)
    return chain or ["No material approval gate was required for this recommendation."]


def _risk_flags(
    validation: dict[str, Any],
    steps: list[dict[str, Any]],
    approval_chain: list[str],
) -> list[str]:
    flags = []
    flags.extend(str(item) for item in _list(validation.get("warnings"))[:5])
    flags.extend(str(item) for item in _list(validation.get("violations"))[:5])
    for step in steps:
        report = _record(_dig(step, "result", "validation_report"))
        recommendation = report.get("recommendation")
        if recommendation and recommendation not in {"ready", "passed"}:
            flags.append(f"{step.get('name')}: validation recommendation is {recommendation}.")
    if any("pending" in item for item in approval_chain):
        flags.append("One or more governance approvals remain pending.")
    return flags or ["No deterministic risk flags were recorded."]


def _timeline(result: dict[str, Any], steps: list[dict[str, Any]]) -> list[str]:
    events = [
        str(event.get("message"))
        for event in _list(result.get("trace"))
        if event.get("message")
    ]
    if events:
        return events
    return [
        f"{step.get('name') or step.get('step_id')} completed with status {step.get('status')}."
        for step in steps
    ]


def _outcome(
    explanation: dict[str, Any],
    result: dict[str, Any],
    final_result: dict[str, Any],
) -> str:
    recommendation = explanation.get("overall_recommendation")
    if recommendation:
        return str(recommendation)
    return (
        f"Workflow completed with status {result.get('status', 'unknown')}; final objective "
        f"value was {_fmt_number(final_result.get('objective_value'))}."
    )


def _markdown(narrative: AuditNarrative) -> str:
    sections = [
        f"# {narrative.title}",
        f"Generated: {narrative.generated_at}",
        "## Decision Summary",
        narrative.decision_summary,
        "## Constraint Context",
        _bullets(narrative.constraint_context),
        "## Approval Chain",
        _bullets(narrative.approval_chain),
        "## Risk Flags",
        _bullets(narrative.risk_flags),
        "## Timeline",
        _bullets(narrative.timeline),
        "## Outcome",
        narrative.outcome,
    ]
    return "\n\n".join(sections)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _kv_pairs(values: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(values.items()))


def _fmt_number(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def polish_narrative(narrative: AuditNarrative, provider: LLMProvider) -> AuditNarrative:
    """Rewrite ``narrative.markdown`` as compliance-grade prose via ``provider``.

    The structured fields (decision_summary, constraint_context, etc.) are kept
    verbatim as source-of-truth; only the ``markdown`` output and
    ``decision_summary`` / ``outcome`` prose fields are overwritten with the
    LLM-polished versions.  ``llm_polished``, ``llm_provider``, and
    ``llm_model`` are set on the returned narrative.
    """
    system = (
        "You are a compliance documentation specialist. "
        "Rewrite the provided draft audit narrative as polished, professional prose "
        "suitable for regulatory review. "
        "Preserve all factual content, section headings, and bullet lists. "
        "Return only the finished markdown — no preamble or commentary."
    )
    prompt = (
        f"Rewrite the following draft audit narrative as polished compliance prose.\n\n"
        f"{narrative.markdown}"
    )
    try:
        polished_md = provider.generate(prompt, system=system, max_tokens=2048)
    except Exception:  # noqa: BLE001 — fall back to deterministic on any LLM failure
        return narrative

    # Extract an updated decision_summary from the first non-heading paragraph.
    lines = [ln.strip() for ln in polished_md.splitlines() if ln.strip()]
    new_summary = narrative.decision_summary
    for line in lines:
        if not line.startswith("#") and not line.startswith("-") and len(line) > 40:
            new_summary = line
            break

    return narrative.model_copy(
        update={
            "markdown": polished_md,
            "decision_summary": new_summary,
            "llm_polished": True,
            "llm_provider": provider.name,
            "llm_model": provider.model,
        }
    )


def _dig(source: dict[str, Any], *keys: str) -> Any:
    current: Any = source
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
