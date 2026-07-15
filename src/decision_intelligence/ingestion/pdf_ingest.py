"""
PDF ingestion — turn a document describing an optimization scenario into a
validated :class:`OptimizationRequest`.

Two extraction backends are provided:

* **llm** (default when ``ANTHROPIC_API_KEY`` is set and the ``anthropic`` SDK
  is installed): Claude reads the PDF natively via a base64 document block and
  returns a structured :class:`ExtractedRequest` using the Messages ``parse``
  helper (schema-validated structured output).

* **heuristic** (offline fallback): the PDF text is extracted with ``pypdf`` and
  parsed with regexes / keyword rules. No network, no API key — this keeps the
  POC fully runnable and testable, and mirrors the same intermediate schema the
  LLM produces.

The public entry point is :func:`ingest_pdf`, which auto-selects a backend and
returns an ``(OptimizationRequest, ExtractedRequest)`` pair.
"""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Literal

from decision_intelligence.contracts import OptimizationRequest

from .mapper import IngestionError, to_optimization_request
from .schema import ExtractedConstraint, ExtractedRequest, ExtractedScenario

Backend = Literal["auto", "llm", "heuristic"]

_MODEL = "claude-opus-4-8"

_SYSTEM_PROMPT = (
    "You are the intake agent for a financial optimization platform. You read a "
    "document (a mandate, desk memo, or optimization brief) and extract a "
    "structured optimization request. The platform supports exactly three "
    "domains:\n"
    "  - collateral   : minimize funding cost across collateral assets\n"
    "  - money_market : maximize net yield across money market funds\n"
    "  - financing    : minimize financing spread across counterparties\n"
    "Choose the single best-fitting domain. Extract the objective (metric + "
    "direction), every constraint with its numeric parameters, and any stress / "
    "what-if scenarios. Use snake_case identifiers. If a value is not stated, "
    "leave it null rather than inventing it."
)


# --------------------------------------------------------------------------- #
# Backend availability
# --------------------------------------------------------------------------- #
def llm_available() -> bool:
    """True when the Anthropic path can be used."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


# --------------------------------------------------------------------------- #
# LLM backend
# --------------------------------------------------------------------------- #
def extract_with_llm(pdf_path: Path, *, model: str = _MODEL) -> ExtractedRequest:
    """Extract via Claude reading the PDF natively (schema-validated output)."""
    import anthropic

    data = base64.standard_b64encode(pdf_path.read_bytes()).decode("ascii")
    client = anthropic.Anthropic()

    message = client.messages.parse(
        model=model,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract the optimization request described in this "
                            "document into the structured schema."
                        ),
                    },
                ],
            }
        ],
        output_format=ExtractedRequest,
    )
    parsed = message.parsed_output
    if parsed is None:
        raise IngestionError("LLM returned no structured extraction.")
    return parsed


# --------------------------------------------------------------------------- #
# Heuristic (offline) backend
# --------------------------------------------------------------------------- #
def extract_text(pdf_path: Path) -> str:
    """Extract raw text from a PDF using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise IngestionError(
            "Offline PDF parsing needs 'pypdf' (pip install pypdf), "
            "or set ANTHROPIC_API_KEY to use the LLM backend."
        ) from exc

    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


_DOMAIN_KEYWORDS = {
    "collateral": ("collateral", "haircut", "pledge", "eligibility"),
    "money_market": ("money market", "mmf", "wam", "prime fund"),
    "financing": ("financing", "repo", "funding spread", "counterparty", "tenor"),
}

# (regex, constraint name, type, param key, transform) for heuristic constraint mining.
# Common "upper bound" trigger words shared by several concentration rules.
_MAX = r"(?:no more than|not exceed|exceed|max(?:imum)?|below|under|at most|cap(?:ped at)?)"

_CONSTRAINT_RULES: list[tuple[str, str, str, str, str]] = [
    (rf"prime[^.\n]*?{_MAX}\s*([\d.]+)\s*%",
     "max_prime_fraction", "concentration", "limit", "pct"),
    (r"daily liquidity[^.\n]*?(?:at least|min(?:imum)?|>=?)\s*([\d.]+)\s*%",
     "daily_liquidity_req", "liquidity", "min_fraction", "pct"),
    (r"weekly liquidity[^.\n]*?(?:at least|min(?:imum)?|>=?)\s*([\d.]+)\s*%",
     "weekly_liquidity_req", "liquidity", "min_fraction", "pct"),
    (r"(?:wam|weighted average maturity)[^.\n]*?(?:below|under|max(?:imum)?|<=?)\s*(\d+)\s*days",
     "max_wam_days", "maturity", "max_days", "int"),
    (rf"single[- ]fund[^.\n]*?{_MAX}\s*([\d.]+)\s*%",
     "single_fund_limit", "concentration", "limit", "pct"),
    (rf"(?:per[- ]?counterparty|counterparty)[^.\n]*?{_MAX}\s*([\d.]+)\s*%",
     "counterparty_limit", "counterparty", "limit", "pct"),
    (r"capital (?:budget|usage)[^.\n]*?(?:below|under|max(?:imum)?|<=?)\s*\$?\s*([\d,]+)",
     "capital_budget", "balance_sheet", "limit", "money"),
]

_SCENARIO_RULES: list[tuple[str, str, dict]] = [
    (r"liquidity stress|liquidity shock", "liquidity_stress",
     {"daily_liquidity_req": 0.40, "weekly_liquidity_req": 0.70}),
    (r"credit stress|credit shock|downgrade", "credit_stress",
     {"obligation_scale": 1.3}),
    (r"spread widen|widening spread|funding shock", "spread_stress",
     {"spread_shift": 1.5, "capacity_scale": 0.6}),
    (r"inventory (?:reduction|shortfall|shortage)", "inventory_shock",
     {"inventory_scale": 0.7}),
]


def _num(raw: str, kind: str) -> float | int:
    raw = raw.replace(",", "")
    val = float(raw)
    if kind == "pct":
        return round(val / 100.0, 6)
    if kind == "int":
        return int(val)
    return val  # money / raw


def extract_heuristic(pdf_path: Path) -> ExtractedRequest:
    """Regex/keyword extraction from PDF text — offline, deterministic."""
    text = extract_text(pdf_path)
    low = text.lower()

    # Domain by keyword vote.
    domain, best = None, 0
    for dom, kws in _DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in low)
        if hits > best:
            domain, best = dom, hits

    # Objective direction from language.
    direction = None
    if re.search(r"\b(minim(?:ize|ise)|reduce|lower)\b", low):
        direction = "minimize"
    if re.search(r"\b(maxim(?:ize|ise)|increase|boost)\b.*\byield\b", low):
        direction = "maximize"

    # Objective metric.
    metric = None
    for m in ("funding cost", "funding spread", "net yield", "yield"):
        if m in low:
            metric = m.replace(" ", "_")
            break

    portfolio_id = None
    if pm := re.search(r"\b(?:portfolio|account|port)[ _#:]*([A-Z]{2,}[_-]?\d+)", text, re.I):
        portfolio_id = pm.group(1).upper()

    requestor = None
    _req_pat = r"(?:prepared by|requested by|author|desk)[:\s]+([A-Z][\w .&/-]{2,40})"
    if rm := re.search(_req_pat, text, re.I):
        requestor = rm.group(1).strip()

    constraints: list[ExtractedConstraint] = []
    for pattern, name, ctype, pkey, kind in _CONSTRAINT_RULES:
        m = re.search(pattern, low)
        if m:
            constraints.append(
                ExtractedConstraint(
                    name=name,
                    constraint_type=ctype,
                    description=m.group(0).strip(),
                    parameters={pkey: _num(m.group(1), kind)},
                )
            )

    scenarios: list[ExtractedScenario] = []
    for pattern, name, overrides in _SCENARIO_RULES:
        if re.search(pattern, low):
            stype = "downside" if "inventory" in name else "stress"
            scenarios.append(
                ExtractedScenario(
                    name=name,
                    scenario_type=stype,
                    description=f"Detected '{name}' scenario in document.",
                    parameter_overrides=overrides,
                )
            )

    exec_mode = None
    if "recommend" in low:
        exec_mode = "recommendation"
    elif "scenario" in low or "stress" in low:
        exec_mode = "scenario_analysis"
    elif "explain" in low:
        exec_mode = "explain"

    return ExtractedRequest(
        domain=domain,
        portfolio_id=portfolio_id,
        objective_metric=metric,
        objective_direction=direction,
        constraints=constraints,
        scenarios=scenarios,
        execution_mode=exec_mode,
        requestor=requestor,
        notes=(text[:600].strip() if text else ""),
    )


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def ingest_pdf(
    pdf_path: str | Path,
    *,
    backend: Backend = "auto",
    seed: int | None = None,
    model: str = _MODEL,
) -> tuple[OptimizationRequest, ExtractedRequest]:
    """
    Ingest a PDF into a validated OptimizationRequest.

    Returns ``(request, extracted)`` so callers can inspect the intermediate
    extraction (useful for showing "what the intake agent understood").
    """
    path = Path(pdf_path)
    if not path.exists():
        raise IngestionError(f"PDF not found: {path}")

    chosen = backend
    if chosen == "auto":
        chosen = "llm" if llm_available() else "heuristic"

    if chosen == "llm":
        extracted = extract_with_llm(path, model=model)
    elif chosen == "heuristic":
        extracted = extract_heuristic(path)
    else:  # pragma: no cover
        raise IngestionError(f"Unknown backend '{backend}'.")

    request = to_optimization_request(extracted, source=f"pdf:{path.name}", seed=seed)
    return request, extracted
