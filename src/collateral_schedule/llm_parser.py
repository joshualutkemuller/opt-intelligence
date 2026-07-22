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

Accuracy design (see handoff §5.1 / limitation #1):

* ``asset_class`` is **enum-constrained** in the schema — capable providers
  enforce it at decode time; a lenient before-validator coerces anything else
  through :func:`normalize_asset_class` so validation never hard-fails.
* Maturity-banded haircuts are modelled as explicit ``tiers`` and expanded to
  one canonical entry per tier (GSD/DTC-style schedules).
* Ratings are normalised to the S&P scale via :func:`normalize_rating`.
* For non-native-PDF providers, input is pre-extracted **table-aware** with
  ``pdfplumber`` (falling back to flat ``pypdf`` text), and long documents are
  **chunked** across multiple extract calls instead of truncated.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from .models import AssetClass, normalize_asset_class, normalize_eligible, normalize_rating
from .parser import _parse_float


def _lenient_number(v: Any) -> Any:
    """Coerce model-emitted strings like '7%' or '2,500' to floats (else None)."""
    if v is None or isinstance(v, (int, float)):
        return v
    return _parse_float(v)


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
class MaturityTier(BaseModel):
    """One maturity band of a tiered haircut (e.g. '1–2 years: 3.0%')."""

    min_maturity_years: float | None = Field(
        default=None, description="Lower bound of the maturity band in years (null if open)."
    )
    max_maturity_years: float | None = Field(
        default=None, description="Upper bound of the maturity band in years (null if open)."
    )
    haircut_pct: float | None = Field(
        default=None, description="Haircut for this band as a percentage number (no '%')."
    )

    @field_validator("min_maturity_years", "max_maturity_years", "haircut_pct", mode="before")
    @classmethod
    def _lenient_float(cls, v: Any) -> Any:
        return _lenient_number(v)


class LLMCollateralEntry(BaseModel):
    """One row of an eligible-collateral schedule, as read by the model."""

    asset_class: AssetClass = Field(
        description=(
            "Canonical asset class. CASH=cash/deposits; GOVT=sovereign debt "
            "(UST/T-bills/TIPS/gilts/bunds); AGENCY=agency/GSE debentures/supras; "
            "CORP=investment-grade corporate incl. commercial paper; HY_CORP=high-yield "
            "corporate; EQUITY=listed equities; ABS=asset-backed; MBS=mortgage-backed "
            "(GNMA/FNMA/FHLMC/UMBS pools); MUNI=municipal; MMF=money-market funds; "
            "COVERED=covered bonds; OTHER=anything else (gold, letters of credit, loans)."
        )
    )
    asset_class_label: str | None = Field(
        default=None,
        description="The asset/collateral label exactly as written in the document.",
    )
    isin: str | None = Field(
        default=None, description="ISIN or CUSIP identifier if a specific security is named."
    )
    currency: str | None = Field(default=None, description="Currency / denomination, e.g. 'USD'.")
    rating_floor: str | None = Field(
        default=None,
        description=(
            "Minimum acceptable credit rating as printed (e.g. 'A-', 'Baa3', 'P-1'). "
            "Only if the document states one — never infer."
        ),
    )
    max_maturity_years: float | None = Field(
        default=None, description="Maximum remaining maturity in YEARS as a plain number."
    )
    haircut_pct: float | None = Field(
        default=None,
        description=(
            "Haircut / valuation margin as a percentage NUMBER only (e.g. 2.5 for 2.5%). "
            "No '%' sign. If the haircut varies by maturity band, use 'tiers' instead."
        ),
    )
    tiers: list[MaturityTier] = Field(
        default_factory=list,
        description=(
            "For maturity-banded haircuts ('0-1y: 2%, 1-5y: 3%…'): one tier per band. "
            "Leave empty when a single haircut applies."
        ),
    )
    concentration_limit_pct: float | None = Field(
        default=None, description="Concentration limit as a percentage number, or null if none."
    )
    eligible: bool = Field(
        default=True,
        description=(
            "True unless the document EXPLICITLY marks this collateral as "
            "ineligible/excluded/not accepted."
        ),
    )
    notes: str | None = Field(
        default=None, description="Any qualifying conditions or remarks (brief)."
    )

    @field_validator(
        "max_maturity_years", "haircut_pct", "concentration_limit_pct", mode="before"
    )
    @classmethod
    def _lenient_float(cls, v: Any) -> Any:
        return _lenient_number(v)

    @field_validator("asset_class", mode="before")
    @classmethod
    def _coerce_asset_class(cls, v: Any) -> Any:
        """Never hard-fail on a free-text class from a weak model — normalise it."""
        if isinstance(v, AssetClass):
            return v
        if v is None:
            return AssetClass.OTHER
        s = str(v).strip()
        try:
            return AssetClass(s.upper())
        except ValueError:
            return normalize_asset_class(s)


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
    "guessing — never infer ratings or limits. When a haircut varies by maturity "
    "band, fill the 'tiers' list with one tier per band instead of a single "
    "haircut_pct. Mark eligible=false ONLY for rows the document explicitly "
    "excludes; everything listed as acceptable collateral is eligible=true."
)

_INSTRUCTION = (
    "Extract the eligible-collateral schedule from this document into the structured "
    "schema. Return one entry per distinct asset class (use 'tiers' for "
    "maturity-banded haircuts). Copy the document's own label into "
    "asset_class_label."
)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def parse_pdf_with_llm(
    pdf: bytes | str | Path,
    provider: _ExtractionProvider,
    *,
    max_text_chars: int = 24_000,
    max_chunks: int = 6,
    return_schedule: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], LLMCollateralSchedule]:
    """Extract collateral entries from a PDF (or plain text) using an LLM *provider*.

    Args:
        pdf: PDF as raw bytes, or a path to a ``.pdf``/text file. Non-PDF bytes
            are treated as plain text (e.g. triparty eligibility profiles).
        provider: An object implementing :class:`_ExtractionProvider`
            (e.g. ``decision_intelligence.llm`` providers). Injected by the
            caller so this library imports nothing from the parent project.
        max_text_chars: For non-native-PDF providers, the per-call input budget.
            Longer documents are split into up to *max_chunks* chunks and the
            extracted entries merged (never silently truncated to one chunk).
        max_chunks: Upper bound on per-document LLM calls for chunked input.
        return_schedule: If True, also return the merged validated
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

    raw = _coerce_bytes(pdf)
    is_pdf = raw[:5] == b"%PDF-"

    if is_pdf and getattr(provider, "supports_native_pdf", False):
        # Native path: hand the raw PDF to the provider via a temp file.
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(raw)
            tmp.flush()
            schedule = _validated(
                provider.extract(
                    LLMCollateralSchedule,
                    instruction=_INSTRUCTION,
                    system=_SYSTEM_PROMPT,
                    pdf_path=Path(tmp.name),
                )
            )
    else:
        # Text path: table-aware extraction, then chunked LLM calls.
        if is_pdf:
            text = _pdf_tables_to_text(raw) or _pdf_bytes_to_text(raw)
        else:
            text = raw.decode("utf-8", errors="replace")
        schedule = _extract_text_chunked(
            provider, text, max_text_chars=max_text_chars, max_chunks=max_chunks
        )

    entries = _entries_from_schedule(schedule)
    if return_schedule:
        return entries, schedule
    return entries


def _extract_text_chunked(
    provider: _ExtractionProvider,
    text: str,
    *,
    max_text_chars: int,
    max_chunks: int,
) -> LLMCollateralSchedule:
    """Run extraction over the document in chunks and merge the results.

    Chunks split on paragraph/table boundaries so rows stay intact. A failed
    chunk is skipped rather than failing the whole document (the caller's
    heuristic fallback still applies when *everything* fails and no entries
    are produced).
    """
    chunks = _split_chunks(text, max_text_chars, max_chunks)
    merged: LLMCollateralSchedule | None = None
    errors: list[Exception] = []
    for chunk in chunks:
        try:
            part = _validated(
                provider.extract(
                    LLMCollateralSchedule,
                    instruction=_INSTRUCTION,
                    system=_SYSTEM_PROMPT,
                    text=chunk,
                )
            )
        except Exception as exc:  # noqa: BLE001 - keep other chunks' results
            errors.append(exc)
            continue
        if merged is None:
            merged = part
        else:
            merged.entries.extend(part.entries)
            merged.base_currency = merged.base_currency or part.base_currency
            merged.detected_margin_type = (
                merged.detected_margin_type or part.detected_margin_type
            )
            merged.source_description = merged.source_description or part.source_description
    if merged is None:
        if errors:
            raise errors[0]
        return LLMCollateralSchedule()
    return merged


def _entries_from_schedule(schedule: LLMCollateralSchedule) -> list[dict[str, Any]]:
    """Map validated LLM output onto canonical entry dicts (same as CSV path).

    Tiered entries are expanded to one canonical entry per maturity band.
    """
    entries: list[dict[str, Any]] = []
    for row in schedule.entries:
        base: dict[str, Any] = {
            "asset_class": _canonical_class(row),
            "eligible": normalize_eligible(row.eligible),
        }
        if row.isin:
            base["isin"] = row.isin.strip()
        if row.currency:
            base["currency"] = row.currency.strip()
        rating = normalize_rating(row.rating_floor)
        if rating:
            base["rating_floor"] = rating
        notes = (row.notes or "").strip()
        # Preserve the document's own label when normalisation lost it.
        if row.asset_class_label and base["asset_class"] == AssetClass.OTHER.value:
            label = row.asset_class_label.strip()
            notes = f"{label}. {notes}".strip().rstrip(".") + "." if notes else label
        conc = _parse_float(row.concentration_limit_pct)
        if conc is not None:
            base["concentration_limit_pct"] = conc

        if row.tiers:
            for tier in row.tiers:
                entry = dict(base)
                hc = _parse_float(tier.haircut_pct)
                if hc is None:
                    hc = _parse_float(row.haircut_pct)
                if hc is not None:
                    entry["haircut_pct"] = hc
                max_mat = _parse_float(tier.max_maturity_years)
                if max_mat is None:
                    max_mat = _parse_float(row.max_maturity_years)
                if max_mat is not None:
                    entry["max_maturity_years"] = max_mat
                band = _band_label(tier)
                entry_notes = " ".join(x for x in (band, notes) if x)
                if entry_notes:
                    entry["notes"] = entry_notes
                entries.append(entry)
        else:
            entry = dict(base)
            hc = _parse_float(row.haircut_pct)
            if hc is not None:
                entry["haircut_pct"] = hc
            max_mat = _parse_float(row.max_maturity_years)
            if max_mat is not None:
                entry["max_maturity_years"] = max_mat
            if notes:
                entry["notes"] = notes
            entries.append(entry)

    deduped = _dedupe(entries)
    for i, entry in enumerate(deduped):
        entry["source_row"] = i + 1
    return deduped


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _validated(schedule: Any) -> LLMCollateralSchedule:
    if isinstance(schedule, LLMCollateralSchedule):
        return schedule
    return LLMCollateralSchedule.model_validate(schedule)


def _canonical_class(row: LLMCollateralEntry) -> str:
    """Prefer the enum value; re-normalise via the document label when OTHER."""
    value = row.asset_class.value if isinstance(row.asset_class, AssetClass) else str(row.asset_class)
    if value == AssetClass.OTHER.value and row.asset_class_label:
        return normalize_asset_class(row.asset_class_label)
    return value


def _band_label(tier: MaturityTier) -> str:
    lo, hi = tier.min_maturity_years, tier.max_maturity_years
    if lo is None and hi is None:
        return ""
    if lo is None:
        return f"maturity ≤{hi:g}y."
    if hi is None:
        return f"maturity >{lo:g}y."
    return f"maturity {lo:g}–{hi:g}y."


def _dedupe(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop exact duplicates (same class/haircut/maturity/rating/eligibility)."""
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for e in entries:
        key = (
            e.get("asset_class"),
            e.get("haircut_pct"),
            e.get("max_maturity_years"),
            e.get("rating_floor"),
            e.get("eligible"),
            e.get("isin"),
            e.get("notes"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _split_chunks(text: str, max_chars: int, max_chunks: int) -> list[str]:
    """Split on paragraph boundaries into ≤max_chunks pieces of ≤max_chars.

    If the document exceeds the total budget, later content is dropped —
    but the budget (max_chars × max_chunks) is ~6× the old truncation limit.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for para in paragraphs:
        # A single paragraph larger than the budget is hard-split.
        while len(para) > max_chars:
            if current:
                chunks.append("\n\n".join(current))
                current, size = [], 0
            chunks.append(para[:max_chars])
            para = para[max_chars:]
            if len(chunks) >= max_chunks:
                return chunks[:max_chunks]
        if size + len(para) + 2 > max_chars and current:
            chunks.append("\n\n".join(current))
            current, size = [], 0
            if len(chunks) >= max_chunks:
                return chunks[:max_chunks]
        current.append(para)
        size += len(para) + 2
    if current and len(chunks) < max_chunks:
        chunks.append("\n\n".join(current))
    return chunks[:max_chunks]


def _coerce_bytes(pdf: bytes | str | Path) -> bytes:
    if isinstance(pdf, bytes):
        return pdf
    return Path(pdf).read_bytes()


def _pdf_tables_to_text(pdf_bytes: bytes) -> str | None:
    """Table-aware text extraction via pdfplumber.

    Per page: ruled tables (detected from line graphics) are rendered as
    pipe-delimited rows; pages without ruled tables use layout-preserving text
    (``extract_text(layout=True)``), which keeps whitespace-aligned columns
    readable. Returns None when pdfplumber is unavailable or yields nothing, so
    the caller can fall back to flat ``pypdf`` text. Keeping rows/columns
    aligned is the single biggest input-quality lever for text-only providers
    on schedule-style documents.
    """
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except ImportError:
        return None
    import io

    parts: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as doc:
            for page_no, page in enumerate(doc.pages, start=1):
                tables = page.extract_tables() or []
                rendered: list[str] = []
                for t_no, table in enumerate(tables, start=1):
                    rows = [
                        " | ".join((cell or "").replace("\n", " ").strip() for cell in row)
                        for row in table
                        if any(cell for cell in row)
                    ]
                    if rows:
                        rendered.append(f"[page {page_no} table {t_no}]\n" + "\n".join(rows))
                if rendered:
                    parts.extend(rendered)
                else:
                    layout = (page.extract_text(layout=True) or "").rstrip()
                    if layout.strip():
                        parts.append(f"[page {page_no}]\n{layout}")
    except Exception:  # noqa: BLE001 - malformed PDFs fall back to flat text
        return None
    return "\n\n".join(parts) if parts else None


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
