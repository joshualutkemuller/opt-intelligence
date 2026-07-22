"""LLM-assisted parsing of collateral schedules from PDF documents.

This is the LLM path for extension point #11 / known-limitation #1 in the
handoff: structured PDFs with embedded tables that the text-heuristic
``parse_pdf_text`` handles poorly are read by a language model instead.

Provider-agnostic by design: the caller passes an *already-constructed* provider
object (dependency injection), so this module — and therefore the whole
``collateral_schedule`` library — keeps **zero imports from
``decision_intelligence``**. Any object implementing the small duck-typed
protocol below works: Anthropic (native PDF), an OpenAI-compatible endpoint
(OpenAI / Azure / local **Ollama** / vLLM), or a custom in-house model.

Required provider surface (matches ``decision_intelligence.llm.LLMProvider``)::

    provider.supports_native_pdf: bool
    provider.extract(schema, *, instruction, system=None,
                     pdf_path=Path|None, text=str|None) -> schema instance

The provider returns a validated :class:`LLMCollateralSchedule`; we then map its
free-text fields onto the same canonical entry dicts produced by the CSV/XLSX
path (via :func:`normalize_asset_class` / :func:`normalize_eligible`), so
downstream ``CollateralDatabase.insert_entries`` is unchanged.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from .models import normalize_asset_class, normalize_eligible
from .parser import _parse_float


# --------------------------------------------------------------------------- #
# Provider protocol (duck-typed — no import of decision_intelligence)
# --------------------------------------------------------------------------- #
@runtime_checkable
class _ExtractionProvider(Protocol):
    supports_native_pdf: bool

    def extract(
        self,
        schema: type[BaseModel],
        *,
        instruction: str,
        system: str | None = ...,
        pdf_path: Path | None = ...,
        text: str | None = ...,
    ) -> BaseModel: ...


# --------------------------------------------------------------------------- #
# Extraction schema (what the model must return)
# --------------------------------------------------------------------------- #
class LLMCollateralEntry(BaseModel):
    """One row of an eligible-collateral schedule, as read by the model."""

    asset_class: str = Field(
        description=(
            "Raw asset / collateral class label exactly as written, e.g. "
            "'US Treasury securities', 'Investment grade corporate bonds', "
            "'Cash in USD', 'Agency MBS'."
        )
    )
    isin: str | None = Field(
        default=None, description="ISIN or CUSIP identifier if a specific security is named."
    )
    currency: str | None = Field(default=None, description="Currency / denomination, e.g. 'USD'.")
    rating_floor: str | None = Field(
        default=None, description="Minimum acceptable credit rating, e.g. 'A-', 'BBB', 'Aa3'."
    )
    max_maturity_years: float | None = Field(
        default=None, description="Maximum remaining maturity in YEARS as a plain number."
    )
    haircut_pct: float | None = Field(
        default=None,
        description="Haircut / valuation margin as a percentage NUMBER only (e.g. 2.5 for 2.5%). No '%' sign.",
    )
    concentration_limit_pct: float | None = Field(
        default=None, description="Concentration limit as a percentage number, or null if none."
    )
    eligible: bool = Field(
        default=True,
        description="True if this collateral is eligible/accepted, False if explicitly excluded.",
    )
    notes: str | None = Field(
        default=None, description="Any qualifying conditions, tiers, or remarks."
    )


class LLMCollateralSchedule(BaseModel):
    """The full eligible-collateral schedule extracted from a document."""

    entries: list[LLMCollateralEntry] = Field(
        default_factory=list, description="Every eligible-collateral row found in the document."
    )
    # Optional context — best-effort, never invented.
    base_currency: str | None = Field(
        default=None, description="Base / reporting currency of the schedule if stated."
    )
    detected_margin_type: str | None = Field(
        default=None,
        description="One of IM, VM, REPO, SBL, CCP_IM, HOUSE, OTHER if inferable, else null.",
    )
    source_description: str | None = Field(
        default=None, description="Short description of the document / issuer if stated."
    )


_SYSTEM_PROMPT = (
    "You are a collateral-management analyst. You read a document describing an "
    "eligible-collateral or haircut schedule and extract every eligible-collateral "
    "line item into a structured schema. Percentages are numbers without a '%' sign. "
    "Maturities are in years. If a value is not stated, leave it null rather than "
    "guessing. Include rows that are marked ineligible/excluded with eligible=false."
)

_INSTRUCTION = (
    "Extract the eligible-collateral schedule from this document into the structured "
    "schema. Return one entry per distinct asset class / haircut tier."
)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def parse_pdf_with_llm(
    pdf: bytes | str | Path,
    provider: _ExtractionProvider,
    *,
    max_text_chars: int = 24_000,
    return_schedule: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], LLMCollateralSchedule]:
    """Extract collateral entries from a PDF using an LLM *provider*.

    Args:
        pdf: PDF as raw bytes, or a path to a ``.pdf`` file.
        provider: An object implementing :class:`_ExtractionProvider`
            (e.g. ``decision_intelligence.llm`` providers). Injected by the
            caller so this library imports nothing from the parent project.
        max_text_chars: For non-native-PDF providers (OpenAI-compatible / Ollama),
            the PDF text is extracted locally and truncated to this many
            characters before being sent — keeps local models tractable on large
            documents. Ignored by native-PDF providers (Anthropic).
        return_schedule: If True, also return the raw validated
            :class:`LLMCollateralSchedule` (for reporting metadata).

    Returns:
        A list of canonical entry dicts (same shape as :func:`parse_schedule`),
        or ``(entries, schedule)`` when *return_schedule* is True.
    """
    if provider is None:  # defensive — caller must inject a provider
        raise ValueError(
            "parse_pdf_with_llm requires a provider object. Construct one via the "
            "consumer's LLM layer (e.g. decision_intelligence.llm.resolve_provider) "
            "and pass it in."
        )

    pdf_bytes = _coerce_pdf_bytes(pdf)

    if getattr(provider, "supports_native_pdf", False):
        # Native path: hand the raw PDF to the provider via a temp file.
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp.flush()
            schedule = provider.extract(
                LLMCollateralSchedule,
                instruction=_INSTRUCTION,
                system=_SYSTEM_PROMPT,
                pdf_path=Path(tmp.name),
            )
    else:
        # Text path: extract + truncate locally so we control token volume.
        text = _pdf_bytes_to_text(pdf_bytes)
        if max_text_chars and len(text) > max_text_chars:
            text = text[:max_text_chars]
        schedule = provider.extract(
            LLMCollateralSchedule,
            instruction=_INSTRUCTION,
            system=_SYSTEM_PROMPT,
            text=text,
        )

    if not isinstance(schedule, LLMCollateralSchedule):  # provider contract guard
        schedule = LLMCollateralSchedule.model_validate(schedule)

    entries = _entries_from_schedule(schedule)
    if return_schedule:
        return entries, schedule
    return entries


def _entries_from_schedule(schedule: LLMCollateralSchedule) -> list[dict[str, Any]]:
    """Map validated LLM output onto canonical entry dicts (same as CSV path)."""
    entries: list[dict[str, Any]] = []
    for i, row in enumerate(schedule.entries):
        entry: dict[str, Any] = {
            "asset_class": normalize_asset_class(row.asset_class or "OTHER"),
            "eligible": normalize_eligible(row.eligible),
            "source_row": i + 1,
        }
        if row.isin:
            entry["isin"] = row.isin.strip()
        if row.currency:
            entry["currency"] = row.currency.strip()
        if row.rating_floor:
            entry["rating_floor"] = row.rating_floor.strip()
        if row.notes:
            entry["notes"] = row.notes.strip()
        # Numeric fields: coerce defensively in case a model returned "2.5%".
        for field in ("haircut_pct", "max_maturity_years", "concentration_limit_pct"):
            val = _parse_float(getattr(row, field))
            if val is not None:
                entry[field] = val
        entries.append(entry)
    return entries


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _coerce_pdf_bytes(pdf: bytes | str | Path) -> bytes:
    if isinstance(pdf, bytes):
        return pdf
    return Path(pdf).read_bytes()


def _pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Extracting PDF text for a non-native-PDF provider needs 'pypdf' "
            "(pip install pypdf)."
        ) from exc
    import io

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
