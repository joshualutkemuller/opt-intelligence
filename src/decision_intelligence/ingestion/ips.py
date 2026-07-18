"""IPS / policy-document ingestion for workflow-ready constraints.

This module accepts pasted policy text or a PDF payload, extracts known
constraint fields, and returns a reviewable context patch that can be applied to
a registered workflow before execution.

The default backend is deterministic. An LLM-assisted backend can be enabled for
messier policy language, but its output still passes through the same
deterministic validator before it reaches the workflow context patch.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Iterable
from io import BytesIO
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from .mapper import IngestionError

if TYPE_CHECKING:
    from decision_intelligence.llm import LLMProvider

Backend = Literal["auto", "deterministic", "llm"]


_LLM_SYSTEM_PROMPT = (
    "You are an IPS ingestion agent for a financial optimization platform. "
    "Extract only workflow input fields that are explicitly supported for the "
    "requested workflow. Do not invent values. Use decimals for fractions "
    "where possible, for example 5.25% may be returned as 0.0525 or '5.25%'. "
    "Preserve short evidence snippets from the source document."
)

_LLM_INSTRUCTION = (
    "Extract supported Investment Policy Statement fields into the provided "
    "schema. Return only fields that are present or strongly implied in the "
    "document. Unsupported or uncertain fields should be omitted."
)


class PolicyFieldExtraction(BaseModel):
    """One workflow input inferred from an IPS or policy document."""

    key: str
    label: str
    value: str | int | float | bool
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""
    applied: bool = True


class PolicyIngestionResult(BaseModel):
    """Reviewable output from policy extraction."""

    workflow_id: str
    source_type: str
    input_values: dict[str, str] = Field(default_factory=dict)
    context_patch: dict[str, Any] = Field(default_factory=dict)
    extracted_fields: list[PolicyFieldExtraction] = Field(default_factory=list)
    review_summary: dict[str, Any] = Field(default_factory=dict)


class LLMPolicyFieldExtraction(BaseModel):
    """One field proposed by an LLM before deterministic validation."""

    key: str
    label: str = ""
    value: str | int | float | bool
    confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    evidence: str = ""


class LLMPolicyExtractionResult(BaseModel):
    """LLM extraction envelope for IPS ingestion."""

    fields: list[LLMPolicyFieldExtraction] = Field(default_factory=list)
    notes: str = ""


class _FieldRule(BaseModel):
    key: str
    label: str
    patterns: list[str]
    value_type: str
    confidence: float = 0.86

    model_config = {"frozen": True}


_MONEY = r"\$?\s*([\d,.]+)\s*(billion|bn|million|mm|m)?"
_PCT = r"([\d.]+)\s*%"
_MAX = r"(?:no more than|not exceed|exceed|max(?:imum)?|below|under|at most|cap(?:ped at)?)"
_MIN = r"(?:at least|min(?:imum)?|>=?)"

_RULES: dict[str, list[_FieldRule]]


def ingest_policy_document(
    *,
    workflow_id: str,
    text: str | None = None,
    pdf_base64: str | None = None,
    filename: str | None = None,
    backend: Backend = "deterministic",
    provider: LLMProvider | None = None,
    model: str | None = None,
    llm_provider: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> PolicyIngestionResult:
    """Extract workflow inputs from pasted policy text or a base64 PDF."""

    if workflow_id not in _RULES:
        available = ", ".join(sorted(_RULES))
        raise IngestionError(
            f"Policy ingestion does not support workflow '{workflow_id}'. {available}"
        )

    source_type = "text"
    document_text = text or ""
    if pdf_base64:
        source_type = "pdf"
        document_text = _extract_pdf_text(pdf_base64)

    document_text = document_text.strip()
    if not document_text:
        raise IngestionError("Policy ingestion requires either text or pdf_base64.")

    chosen_backend = _choose_backend(backend, provider)
    if chosen_backend == "llm":
        extracted, llm_notes = _extract_fields_with_llm(
            workflow_id,
            document_text,
            provider=provider,
            model=model,
            llm_provider=llm_provider,
            base_url=base_url,
            api_key=api_key,
        )
    else:
        extracted = _extract_fields(document_text, _RULES[workflow_id])
        llm_notes = ""

    input_values = {field.key: _stringify(field.value) for field in extracted if field.applied}
    context_patch: dict[str, Any] = {}
    for field in extracted:
        if field.applied:
            _set_nested(context_patch, field.key, field.value)

    required_missing = _required_missing(workflow_id, input_values)
    warnings = _review_warnings(extracted, required_missing)
    if filename:
        context_patch.setdefault("policy_ingestion", {})["filename"] = filename
    context_patch.setdefault("policy_ingestion", {})["source_type"] = source_type
    context_patch["policy_ingestion"]["backend"] = chosen_backend
    context_patch["policy_ingestion"]["field_count"] = len(extracted)

    return PolicyIngestionResult(
        workflow_id=workflow_id,
        source_type=source_type,
        input_values=input_values,
        context_patch=context_patch,
        extracted_fields=extracted,
        review_summary={
            "ready": not required_missing,
            "applied_count": sum(1 for field in extracted if field.applied),
            "extracted_count": len(extracted),
            "missing_required": required_missing,
            "warnings": warnings,
            "backend": chosen_backend,
            "llm_notes": llm_notes,
        },
    )


def supported_policy_workflows() -> list[str]:
    """Return workflow IDs with deterministic policy extraction rules."""

    return sorted(_RULES)


def _money_market_rules() -> list[_FieldRule]:
    return [
        _FieldRule(
            key="money_market.daily_liquidity_req",
            label="Daily liquidity",
            value_type="fraction",
            patterns=[rf"daily liquidity[^.\n]*?{_MIN}\s*{_PCT}"],
        ),
        _FieldRule(
            key="money_market.weekly_liquidity_req",
            label="Weekly liquidity",
            value_type="fraction",
            patterns=[rf"weekly liquidity[^.\n]*?{_MIN}\s*{_PCT}"],
        ),
        _FieldRule(
            key="money_market.max_prime_fraction",
            label="Prime fund limit",
            value_type="fraction",
            patterns=[rf"prime[^.\n]*?{_MAX}\s*{_PCT}"],
        ),
        _FieldRule(
            key="money_market.max_wam_days",
            label="Max WAM",
            value_type="integer",
            patterns=[
                r"(?:wam|weighted average maturity)[^.\n]*?(?:below|under|max(?:imum)?|<=?)"
                r"\s*(\d+)\s*days"
            ],
        ),
        _FieldRule(
            key="money_market.max_single_fund",
            label="Single fund limit",
            value_type="fraction",
            patterns=[rf"single[- ]fund[^.\n]*?{_MAX}\s*{_PCT}"],
        ),
    ]


def _governance_rules() -> list[_FieldRule]:
    return [
        _FieldRule(
            key="governance.materiality_notional",
            label="Materiality notional",
            value_type="currency",
            patterns=[
                rf"(?:materiality notional|approval notional|notional exposure)[^.\n]*?{_MONEY}"
            ],
            confidence=0.82,
        ),
        _FieldRule(
            key="governance.estimated_pnl_impact",
            label="Estimated PnL impact",
            value_type="currency",
            patterns=[rf"(?:pnl impact|p&l impact|estimated pnl)[^.\n]*?{_MONEY}"],
            confidence=0.82,
        ),
        _FieldRule(
            key="governance.production_constraint_change",
            label="Production constraint change",
            value_type="boolean",
            patterns=[
                r"(production constraint change|change production constraints|policy override)"
            ],
            confidence=0.78,
        ),
    ]


def _build_rules() -> dict[str, list[_FieldRule]]:
    portfolio_id = _FieldRule(
        key="portfolio_id",
        label="Portfolio ID",
        value_type="string",
        patterns=[
            r"\b(?:portfolio|account)[ _#:]+([A-Z]{2,}[_A-Z0-9-]*\d+)\b",
            r"\b(PORT[_A-Z0-9-]*\d+)\b",
        ],
        confidence=0.90,
    )

    return {
        "liquidity_stress_funding_workflow": [
            portfolio_id,
            _FieldRule(
                key="money_market.total_cash",
                label="Money-market cash",
                value_type="currency",
                patterns=[
                    rf"(?:money[- ]market cash|cash balance|total cash)[^.\n]*?{_MONEY}",
                    rf"{_MONEY}[^.\n]*?(?:money[- ]market cash|cash balance|total cash)",
                ],
            ),
            *_money_market_rules(),
            *_governance_rules(),
        ],
        "funding_capacity_shock": [
            portfolio_id,
            _FieldRule(
                key="financing.total_funding_need",
                label="Funding need",
                value_type="currency",
                patterns=[
                    rf"(?:funding need|financing need|repo need)[^.\n]*?{_MONEY}",
                    rf"{_MONEY}[^.\n]*?(?:funding need|financing need|repo need)",
                ],
            ),
            _FieldRule(
                key="financing.capacity_scale",
                label="Capacity scale",
                value_type="fraction",
                patterns=[
                    rf"(?:capacity scale|available capacity)[^.\n]*?{_PCT}",
                    r"(?:capacity scale|available capacity)[^.\n]*?([\d.]+)\b",
                ],
            ),
            *_governance_rules(),
        ],
        "collateral_liquidity_review": [
            portfolio_id,
            _FieldRule(
                key="collateral.obligation_scale",
                label="Obligation scale",
                value_type="fraction",
                patterns=[
                    rf"(?:obligation scale|obligations scaled|margin call scale)[^.\n]*?{_PCT}",
                    (
                        r"(?:obligation scale|obligations scaled|margin call scale)"
                        r"[^.\n]*?([\d.]+)\b"
                    ),
                ],
            ),
            _FieldRule(
                key="money_market.total_cash",
                label="Money-market cash",
                value_type="currency",
                patterns=[
                    rf"(?:money[- ]market cash|cash balance|total cash)[^.\n]*?{_MONEY}"
                ],
            ),
            *_money_market_rules(),
            *_governance_rules(),
        ],
        "portfolio_rebalance_mvo": [
            portfolio_id,
            _FieldRule(
                key="asset_allocation.portfolio_notional",
                label="Portfolio notional",
                value_type="currency",
                patterns=[
                    (
                        rf"(?:portfolio notional|portfolio value|aum|assets under management)"
                        rf"[^.\n]*?{_MONEY}"
                    ),
                    rf"{_MONEY}[^.\n]*?(?:portfolio notional|portfolio value|aum)",
                ],
            ),
            _FieldRule(
                key="asset_allocation.target_return",
                label="Target annual return",
                value_type="fraction",
                patterns=[
                    rf"(?:target annual return|target return|return target)[^.\n]*?{_PCT}"
                ],
            ),
            _FieldRule(
                key="asset_allocation.risk_aversion",
                label="Risk aversion lambda",
                value_type="number",
                patterns=[r"(?:risk aversion|lambda)[^.\n]*?([\d.]+)\b"],
            ),
            _FieldRule(
                key="asset_allocation.max_single_asset_weight",
                label="Max single asset weight",
                value_type="fraction",
                patterns=[rf"(?:single asset|issuer|asset class)[^.\n]*?{_MAX}\s*{_PCT}"],
            ),
            _FieldRule(
                key="asset_allocation.min_cash_weight",
                label="Minimum cash weight",
                value_type="fraction",
                patterns=[
                    rf"(?:cash weight|cash allocation|cash floor)[^.\n]*?{_MIN}\s*{_PCT}"
                ],
            ),
            *_governance_rules(),
        ],
    }


_RULES = _build_rules()


def _extract_fields(text: str, rules: Iterable[_FieldRule]) -> list[PolicyFieldExtraction]:
    fields: list[PolicyFieldExtraction] = []
    for rule in rules:
        match = _first_match(text, rule.patterns)
        if match is None:
            continue
        value = _coerce_value(match, rule.value_type)
        fields.append(
            PolicyFieldExtraction(
                key=rule.key,
                label=rule.label,
                value=value,
                confidence=rule.confidence,
                evidence=_evidence(text, match),
            )
        )
    return fields


def _choose_backend(
    backend: Backend,
    provider: LLMProvider | None,
) -> Literal["deterministic", "llm"]:
    if backend == "deterministic":
        return "deterministic"
    if backend == "llm":
        return "llm"
    if backend == "auto":
        if provider is not None:
            return "llm"
        from decision_intelligence.llm import provider_available

        return "llm" if provider_available() else "deterministic"
    raise IngestionError(f"Unknown policy ingestion backend '{backend}'.")


def _extract_fields_with_llm(
    workflow_id: str,
    text: str,
    *,
    provider: LLMProvider | None = None,
    model: str | None = None,
    llm_provider: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> tuple[list[PolicyFieldExtraction], str]:
    from decision_intelligence.llm import LLMConfigError, LLMError, resolve_provider

    resolved = provider
    if resolved is None:
        try:
            resolved = resolve_provider(
                llm_provider,
                model=model,
                base_url=base_url,
                api_key=api_key,
            )
        except LLMConfigError as exc:
            raise IngestionError(str(exc)) from exc
    if resolved is None:
        raise IngestionError(
            "No LLM provider is configured for policy ingestion. For local Ollama, "
            "use provider 'openai' with base_url 'http://localhost:11434/v1'."
        )

    rules = _rules_by_key(workflow_id)
    allowed_fields = [
        {
            "key": rule.key,
            "label": rule.label,
            "value_type": rule.value_type,
        }
        for rule in rules.values()
    ]
    required = _required_missing(workflow_id, {})
    instruction = (
        f"{_LLM_INSTRUCTION}\n\n"
        f"Workflow ID: {workflow_id}\n"
        f"Required keys: {required}\n"
        f"Allowed fields: {allowed_fields}\n"
        "Return evidence snippets short enough for a reviewer table."
    )

    try:
        llm_result = resolved.extract(
            LLMPolicyExtractionResult,
            instruction=instruction,
            system=_LLM_SYSTEM_PROMPT,
            text=text,
        )
    except LLMError as exc:
        raise IngestionError(str(exc)) from exc

    return _validate_llm_fields(workflow_id, llm_result.fields), llm_result.notes


def _validate_llm_fields(
    workflow_id: str,
    fields: Iterable[LLMPolicyFieldExtraction],
) -> list[PolicyFieldExtraction]:
    rules = _rules_by_key(workflow_id)
    validated: list[PolicyFieldExtraction] = []
    seen: set[str] = set()

    for field in fields:
        key = field.key.strip()
        if key in seen:
            validated.append(
                _unapplied_field(
                    key=key,
                    label=field.label or key,
                    value=field.value,
                    confidence=field.confidence,
                    evidence=field.evidence,
                    reason="duplicate_field",
                )
            )
            continue
        seen.add(key)
        rule = rules.get(key)
        if rule is None:
            validated.append(
                _unapplied_field(
                    key=key,
                    label=field.label or key,
                    value=field.value,
                    confidence=field.confidence,
                    evidence=field.evidence,
                    reason="unsupported_field",
                )
            )
            continue
        try:
            value = _coerce_llm_value(field.value, rule.value_type)
        except (TypeError, ValueError) as exc:
            validated.append(
                _unapplied_field(
                    key=key,
                    label=field.label or rule.label,
                    value=field.value,
                    confidence=field.confidence,
                    evidence=field.evidence,
                    reason=f"invalid_{rule.value_type}: {exc}",
                )
            )
            continue
        if issue := _value_issue(value, rule.value_type):
            validated.append(
                _unapplied_field(
                    key=key,
                    label=field.label or rule.label,
                    value=value,
                    confidence=field.confidence,
                    evidence=field.evidence,
                    reason=issue,
                )
            )
            continue
        validated.append(
            PolicyFieldExtraction(
                key=key,
                label=field.label or rule.label,
                value=value,
                confidence=field.confidence,
                evidence=field.evidence,
                applied=True,
            )
        )

    return validated


def _unapplied_field(
    *,
    key: str,
    label: str,
    value: str | int | float | bool,
    confidence: float,
    evidence: str,
    reason: str,
) -> PolicyFieldExtraction:
    suffix = f"validator rejected: {reason}"
    full_evidence = f"{evidence} ({suffix})" if evidence else suffix
    return PolicyFieldExtraction(
        key=key,
        label=label,
        value=value,
        confidence=confidence,
        evidence=full_evidence,
        applied=False,
    )


def _rules_by_key(workflow_id: str) -> dict[str, _FieldRule]:
    return {rule.key: rule for rule in _RULES[workflow_id]}


def _coerce_llm_value(value: str | int | float | bool, value_type: str) -> str | int | float | bool:
    if value_type == "boolean":
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"true", "yes", "y", "1", "required", "change"}:
            return True
        if normalized in {"false", "no", "n", "0", "not required", "none"}:
            return False
        raise ValueError(f"expected boolean, got {value!r}")
    if value_type == "string":
        return str(value).strip().upper().replace("-", "_")

    raw = str(value).strip().lower().replace(",", "")
    percent = raw.endswith("%")
    raw = raw.replace("$", "").replace("%", "").strip()
    multiplier = 1.0
    for suffix, scale in (
        ("billion", 1_000_000_000.0),
        ("bn", 1_000_000_000.0),
        ("million", 1_000_000.0),
        ("mm", 1_000_000.0),
        ("m", 1_000_000.0),
    ):
        if raw.endswith(suffix):
            multiplier = scale
            raw = raw[: -len(suffix)].strip()
            break
    number = float(raw) * multiplier

    if value_type == "currency":
        return number
    if value_type == "fraction":
        return round(number / 100.0, 6) if percent or number > 1.0 else number
    if value_type == "integer":
        return int(number)
    return number


def _value_issue(value: str | int | float | bool, value_type: str) -> str | None:
    if value_type == "fraction":
        if not isinstance(value, int | float) or not 0.0 <= float(value) <= 1.0:
            return "fraction_out_of_range"
    if value_type == "currency":
        if not isinstance(value, int | float) or float(value) < 0:
            return "currency_out_of_range"
    if value_type in {"integer", "number"}:
        if not isinstance(value, int | float) or float(value) < 0:
            return "number_out_of_range"
    return None


def _first_match(text: str, patterns: Iterable[str]) -> re.Match[str] | None:
    for pattern in patterns:
        if match := re.search(pattern, text, re.IGNORECASE):
            return match
    return None


def _coerce_value(match: re.Match[str], value_type: str) -> str | int | float | bool:
    if value_type == "boolean":
        return True
    if value_type == "string":
        return match.group(1).upper().replace("-", "_")
    raw = match.group(1).replace(",", "")
    if value_type == "currency":
        multiplier = _money_multiplier(match.group(2) if len(match.groups()) >= 2 else None)
        return float(raw) * multiplier
    number = float(raw)
    if value_type == "fraction":
        return round(number / 100.0, 6) if number > 1.0 else number
    if value_type == "integer":
        return int(number)
    return number


def _money_multiplier(unit: str | None) -> float:
    if not unit:
        return 1.0
    normalized = unit.lower()
    if normalized in {"billion", "bn"}:
        return 1_000_000_000.0
    if normalized in {"million", "mm", "m"}:
        return 1_000_000.0
    return 1.0


def _evidence(text: str, match: re.Match[str]) -> str:
    start = max(0, match.start() - 48)
    end = min(len(text), match.end() + 48)
    return " ".join(text[start:end].split())


def _set_nested(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor = target
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = value


def _required_missing(workflow_id: str, input_values: dict[str, str]) -> list[str]:
    required = {
        "liquidity_stress_funding_workflow": ["portfolio_id", "money_market.total_cash"],
        "funding_capacity_shock": ["portfolio_id", "financing.total_funding_need"],
        "collateral_liquidity_review": ["portfolio_id", "money_market.total_cash"],
        "portfolio_rebalance_mvo": [
            "portfolio_id",
            "asset_allocation.portfolio_notional",
            "asset_allocation.target_return",
        ],
    }
    return [key for key in required[workflow_id] if key not in input_values]


def _review_warnings(
    fields: list[PolicyFieldExtraction],
    required_missing: list[str],
) -> list[str]:
    warnings = [
        f"Missing required field: {key}."
        for key in required_missing
    ]
    if fields and min(field.confidence for field in fields) < 0.80:
        warnings.append("One or more extracted fields should be reviewed before applying.")
    rejected = [field.key for field in fields if not field.applied]
    if rejected:
        warnings.append(f"Rejected unsupported or invalid fields: {', '.join(rejected)}.")
    if not fields:
        warnings.append("No supported workflow inputs were extracted from the document.")
    return warnings


def _stringify(value: str | int | float | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _extract_pdf_text(pdf_base64: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise IngestionError(
            "PDF policy ingestion requires the optional 'pypdf' dependency."
        ) from exc

    try:
        pdf_bytes = base64.b64decode(pdf_base64, validate=True)
    except ValueError as exc:
        raise IngestionError("pdf_base64 is not valid base64.") from exc
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
