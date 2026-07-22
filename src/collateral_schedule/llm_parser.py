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

import re as _re
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
    supports_vision: bool

    def extract(
        self,
        schema: type[BaseModel],
        *,
        instruction: str,
        system: str | None = ...,
        pdf_path: Path | None = ...,
        text: str | None = ...,
    ) -> BaseModel: ...

    def extract_with_images(
        self,
        schema: type[BaseModel],
        *,
        instruction: str,
        system: str | None = ...,
        text: str | None = ...,
        images: list[bytes] | None = ...,
    ) -> BaseModel: ...


# --------------------------------------------------------------------------- #
# Extraction schema (what the model must return)
# --------------------------------------------------------------------------- #
class MaturityTier(BaseModel):
    """One cell of a maturity × rating haircut grid (e.g. '1–5 years / A-rated: 3.0%').

    Most schedules use only maturity bands (leave *rating_floor* null).  DTC-
    and Fed-style grids also vary by credit rating — capture that here so each
    grid cell becomes one canonical entry.
    """

    min_maturity_years: float | None = Field(
        default=None, description="Lower bound of the maturity band in years (null if open)."
    )
    max_maturity_years: float | None = Field(
        default=None, description="Upper bound of the maturity band in years (null if open)."
    )
    rating_floor: str | None = Field(
        default=None,
        description=(
            "Minimum credit rating for this tier cell, e.g. 'AAA', 'A-', 'BBB'. "
            "Only fill when the document shows different haircuts per rating band. "
            "Leave null when one haircut applies across all ratings for this asset class."
        ),
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
            "For maturity-banded or rating×maturity-grid haircuts: one tier per cell. "
            "Example — maturity only: [{max_maturity_years:1, haircut_pct:2}, ...]. "
            "Example — rating+maturity grid: [{rating_floor:'AAA', max_maturity_years:5, haircut_pct:2}, "
            "{rating_floor:'A-', max_maturity_years:5, haircut_pct:4}, ...]. "
            "Leave empty when a single haircut applies to all maturities and ratings."
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
    "line item into a structured schema.\n\n"
    "Rules:\n"
    "- Percentages are plain numbers without a '%' sign (2.5%, not '2.5%').\n"
    "- Maturities are in YEARS as plain numbers (1 year → 1.0, '1–5 years' → min=1, max=5).\n"
    "- If a value is not stated, leave it null — never infer or guess.\n"
    "- When a haircut varies by MATURITY BAND, fill the 'tiers' list with one tier per band "
    "instead of a single haircut_pct.\n"
    "- When a haircut varies by BOTH maturity and CREDIT RATING (a grid), create one tier "
    "per (rating, maturity-band) cell. Set tier.rating_floor to the minimum rating for that "
    "column (e.g. 'AAA', 'AA', 'A', 'BBB'). If the document shows a margin table with "
    "rating columns and duration columns, capture every cell.\n"
    "- Mark eligible=false ONLY for rows the document explicitly marks as ineligible or "
    "excluded; everything listed as acceptable collateral is eligible=true.\n"
    "- Margins expressed as '% of market value' (e.g. 99%) represent (100 − margin)% "
    "haircut, so a 99% margin = 1% haircut, 95% margin = 5% haircut. Convert accordingly."
)

_INSTRUCTION = (
    "Extract the eligible-collateral schedule from this document into the structured schema. "
    "Return one entry per distinct asset class / sub-type. "
    "Use 'tiers' for maturity-banded haircuts; use 'tiers' with rating_floor set for "
    "rating×maturity grids (one tier per grid cell). "
    "Copy the document's own label into asset_class_label."
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
        # Claude handles embedded images / scanned pages internally.
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
        # Text path: PyMuPDF table-aware extraction → chunked LLM calls.
        if is_pdf:
            text, image_pages = _pdf_to_text_mupdf(raw)
            if not text.strip():
                text = _pdf_bytes_to_text(raw)
                image_pages = []
        else:
            text = raw.decode("utf-8", errors="replace")
            image_pages = []

        # If image-heavy pages were found and the provider supports vision,
        # send text + rendered page images together in one call per chunk.
        if image_pages and getattr(provider, "supports_vision", False):
            schedule = _extract_with_vision(
                provider, text, image_pages,
                max_text_chars=max_text_chars, max_chunks=max_chunks,
            )
        else:
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
                # Tier-level rating overrides the row-level rating when set.
                tier_rating = normalize_rating(tier.rating_floor) if tier.rating_floor else None
                if tier_rating:
                    entry["rating_floor"] = tier_rating
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
    validated = _post_validate(deduped)
    for i, entry in enumerate(validated):
        entry["source_row"] = i + 1
    return validated


# --------------------------------------------------------------------------- #
# Post-extraction validation / auto-correction
# --------------------------------------------------------------------------- #
# Haircuts above this threshold on an eligible entry almost certainly mean the
# model emitted a "% of market value" margin figure instead of a haircut.
_MARGIN_TO_HAIRCUT_THRESHOLD = 50.0
# Maturities above this (years) are almost certainly model hallucinations.
_MAX_PLAUSIBLE_MATURITY = 100.0


def _post_validate(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply deterministic sanity checks and auto-corrections to LLM-extracted entries.

    Corrections applied (annotated in ``notes`` for transparency):

    1. **Margin % → haircut conversion**: ``haircut_pct > 50`` on an eligible
       entry almost always means the model emitted a "% of market value" figure
       (e.g. 99 for 99% margin = 1% haircut).  Converted as ``100 − value``.

    2. **Impossible maturity**: ``max_maturity_years > 100`` → cleared to None.
       Models occasionally emit a calendar year (e.g. 2030) instead of a
       remaining-maturity number.

    3. **OTHER asset class with a resolvable label**: when the model assigned
       ``OTHER`` but a note carries the original label, re-run
       :func:`normalize_asset_class` for a second-chance resolution.

    4. **Duplicate (asset_class, rating_floor, max_maturity_years) key**: when
       multiple entries share the same key, keep the one with the *lowest*
       haircut (most favourable rule) and drop the rest.  This handles models
       that emit the same row twice with slightly different haircuts.
    """
    out: list[dict[str, Any]] = []

    for entry in entries:
        e = dict(entry)

        # --- 1. Margin % → haircut -------------------------------------------
        hc = e.get("haircut_pct")
        if hc is not None and hc > _MARGIN_TO_HAIRCUT_THRESHOLD and e.get("eligible", True):
            corrected = round(100.0 - hc, 6)
            note_tag = f"[auto-corrected: margin {hc}% → haircut {corrected}%]"
            e["haircut_pct"] = corrected
            e["notes"] = (e.get("notes") or "") + (" " if e.get("notes") else "") + note_tag

        # --- 2. Impossible maturity ------------------------------------------
        mat = e.get("max_maturity_years")
        if mat is not None and mat > _MAX_PLAUSIBLE_MATURITY:
            note_tag = f"[auto-corrected: implausible max_maturity_years={mat} cleared]"
            e.pop("max_maturity_years", None)
            e["notes"] = (e.get("notes") or "") + (" " if e.get("notes") else "") + note_tag

        # --- 3. Second-chance asset class resolution -------------------------
        if e.get("asset_class") == AssetClass.OTHER.value:
            notes_text = e.get("notes", "")
            if notes_text:
                resolved = normalize_asset_class(notes_text.split(".")[0])
                if resolved != AssetClass.OTHER.value:
                    e["asset_class"] = resolved

        out.append(e)

    # --- 4. Duplicate key → keep lowest haircut ------------------------------
    seen: dict[tuple, int] = {}  # key → index in out
    final: list[dict[str, Any]] = []
    for e in out:
        key = (
            e.get("asset_class"),
            e.get("rating_floor"),
            e.get("max_maturity_years"),
            e.get("isin"),
        )
        if key in seen:
            existing = final[seen[key]]
            e_hc = e.get("haircut_pct") or float("inf")
            ex_hc = existing.get("haircut_pct") or float("inf")
            if e_hc < ex_hc:
                final[seen[key]] = e  # replace with lower haircut
        else:
            seen[key] = len(final)
            final.append(e)

    return final


#: Public alias — callers can run the same validation pass on CSV/XLSX entries.
validate_llm_entries = _post_validate


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
    parts: list[str] = []
    lo, hi = tier.min_maturity_years, tier.max_maturity_years
    if lo is not None or hi is not None:
        if lo is None:
            parts.append(f"maturity ≤{hi:g}y")
        elif hi is None:
            parts.append(f"maturity >{lo:g}y")
        else:
            parts.append(f"maturity {lo:g}–{hi:g}y")
    if tier.rating_floor:
        parts.append(f"min rating {tier.rating_floor}")
    return (", ".join(parts) + ".") if parts else ""


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


_TABLE_HEADER_RE = _re.compile(r"^\[page \d+ table \d+\]", _re.MULTILINE)


def _is_table_block(para: str) -> bool:
    return bool(_TABLE_HEADER_RE.match(para.lstrip()))


def _table_header_line(para: str) -> str:
    """Return the '[page N table M]' header line from a table paragraph."""
    m = _TABLE_HEADER_RE.search(para)
    return m.group(0) if m else ""


def _split_table_block(para: str, max_chars: int) -> list[str]:
    """Split an oversized table block on row boundaries.

    The first line is the '[page N table M]' header; the second line is
    treated as the column-header row. Both are repeated at the top of every
    sub-chunk so the model always knows what table and which columns it's
    reading.
    """
    lines = para.splitlines()
    # Identify header lines: the [page N table M] tag and the column header row.
    section_tag = lines[0] if lines and _TABLE_HEADER_RE.match(lines[0].strip()) else ""
    col_header = lines[1] if len(lines) > 1 and "|" in lines[1] else ""
    prefix_lines = [l for l in [section_tag, col_header] if l]
    prefix = "\n".join(prefix_lines) + "\n" if prefix_lines else ""

    data_lines = lines[len(prefix_lines):]
    sub_chunks: list[str] = []
    current_lines: list[str] = []
    current_size = len(prefix)

    for line in data_lines:
        line_len = len(line) + 1  # +1 for \n
        if current_size + line_len > max_chars and current_lines:
            sub_chunks.append(prefix + "\n".join(current_lines))
            current_lines = []
            current_size = len(prefix)
        # If a single row is itself longer than the budget, hard-split it.
        if line_len > max_chars:
            for i in range(0, len(line), max_chars - len(prefix)):
                sub_chunks.append(prefix + line[i : i + max_chars - len(prefix)])
            continue
        current_lines.append(line)
        current_size += line_len

    if current_lines:
        sub_chunks.append(prefix + "\n".join(current_lines))
    return sub_chunks or [para[:max_chars]]


def _split_chunks(text: str, max_chars: int, max_chunks: int) -> list[str]:
    """Split on paragraph boundaries into ≤max_chunks pieces of ≤max_chars.

    Table blocks (paragraphs starting with '[page N table M]') are split on
    row boundaries rather than mid-character, and the section header + column
    header row are repeated at the top of every continuation chunk so the
    model retains column context.

    Non-table paragraphs carry the most-recent section header as a one-line
    prefix when they start a new chunk mid-section, so the model knows which
    part of the document it is reading.

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
    last_section_tag: str = ""  # most recent [page N table M] or [page N] tag

    def _flush() -> bool:
        nonlocal current, size
        if current:
            chunks.append("\n\n".join(current))
            current, size = [], 0
            return len(chunks) >= max_chunks
        return False

    for para in paragraphs:
        # Track current section header for context carry-forward.
        m = _TABLE_HEADER_RE.search(para)
        if m:
            last_section_tag = m.group(0)
        elif para.lstrip().startswith("[page "):
            last_section_tag = para.lstrip().split("\n")[0]

        if _is_table_block(para) and len(para) > max_chars:
            # Flush whatever is pending before the table sub-chunks.
            if _flush():
                return chunks[:max_chunks]
            for sub in _split_table_block(para, max_chars):
                if len(chunks) >= max_chunks:
                    return chunks[:max_chunks]
                chunks.append(sub)
            continue

        # Hard-split non-table paragraphs that exceed the budget.
        # `was_hard_split` tracks whether we broke a paragraph mid-content so
        # the remainder also gets the section-context prefix.
        was_hard_split = False
        while len(para) > max_chars:
            if _flush():
                return chunks[:max_chunks]
            prefix = (last_section_tag + "\n") if last_section_tag else ""
            safe = max_chars - len(prefix)
            chunks.append(prefix + para[:safe])
            para = para[safe:]
            was_hard_split = True
            if len(chunks) >= max_chunks:
                return chunks[:max_chunks]

        if size + len(para) + 2 > max_chars:
            if _flush():
                return chunks[:max_chunks]
            # Carry section tag as first line of the new chunk.
            if last_section_tag and para and not _TABLE_HEADER_RE.match(para.lstrip()):
                current.append(last_section_tag)
                size += len(last_section_tag) + 2
        elif was_hard_split and last_section_tag and not current:
            # Remainder of a hard-split paragraph starts a fresh chunk —
            # prepend the section tag so the model retains context.
            current.append(last_section_tag)
            size += len(last_section_tag) + 2

        current.append(para)
        size += len(para) + 2

    _flush()
    return chunks[:max_chunks]


def _coerce_bytes(pdf: bytes | str | Path) -> bytes:
    if isinstance(pdf, bytes):
        return pdf
    return Path(pdf).read_bytes()


def _strip_repeated_table_headers(text: str) -> str:
    """Remove duplicate column-header rows from consecutive table blocks.

    When a multi-page table is extracted page-by-page, each page's table
    block starts with the same column-header row (e.g. the CME collateral
    schedule repeats "Asset Class | Description | Haircut Schedule | ..." on
    every page). This function detects and removes those repeated rows so the
    model sees them only once, reducing noise and token cost.

    A "column-header row" is the first pipe-delimited line of a table block
    (the line immediately after the ``[page N table M]`` tag). If the same
    normalised header line appears at the top of ≥ 2 consecutive table blocks,
    it is stripped from all blocks except the first one that carried it.
    """
    paragraphs = text.split("\n\n")
    last_col_header: str = ""
    result: list[str] = []

    for para in paragraphs:
        if not _is_table_block(para):
            last_col_header = ""
            result.append(para)
            continue

        lines = para.splitlines()
        # Find index of first pipe-delimited data line after the section tag.
        tag_idx = next(
            (i for i, l in enumerate(lines) if _TABLE_HEADER_RE.match(l.strip())),
            None,
        )
        if tag_idx is None:
            result.append(para)
            continue

        data_lines = lines[tag_idx + 1 :]
        col_line = data_lines[0].strip() if data_lines else ""
        normalised = " | ".join(p.strip() for p in col_line.split("|") if p.strip())

        if normalised and normalised == last_col_header:
            # Strip the duplicate header line (and any blank lines just below it).
            skip = 0
            for dl in data_lines:
                if dl.strip() == "" or dl.strip() == col_line.strip():
                    skip += 1
                else:
                    break
            kept = lines[: tag_idx + 1] + data_lines[skip:]
            result.append("\n".join(kept))
        else:
            last_col_header = normalised
            result.append(para)

    return "\n\n".join(result)


def _pdf_to_text_mupdf(pdf_bytes: bytes) -> tuple[str, list[bytes]]:
    """Table-aware PDF text extraction via PyMuPDF (fitz).

    Returns ``(text, image_page_pngs)`` where *text* is a multi-page string
    with pipe-delimited tables where detected, and *image_page_pngs* is a list
    of rendered PNG bytes for pages where text extraction yielded fewer than
    ``_IMAGE_PAGE_TEXT_THRESHOLD`` meaningful characters (likely scanned/image
    pages).  Callers can pass *image_page_pngs* to a vision-capable provider.

    Falls back gracefully when PyMuPDF is not installed: returns ``("", [])``.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "", []

    import io as _io

    _IMAGE_PAGE_TEXT_THRESHOLD = 200  # chars below which we treat a page as image-heavy

    parts: list[str] = []
    image_pngs: list[bytes] = []

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_no, page in enumerate(doc, start=1):
            page_parts: list[str] = []

            # Try PyMuPDF table detection first.
            try:
                tabs = page.find_tables()
                for t_no, tab in enumerate(tabs.tables, start=1):
                    rows = tab.extract() or []
                    rendered = [
                        " | ".join(
                            (cell or "").replace("\n", " ").strip()
                            for cell in row
                        )
                        for row in rows
                        if any(cell for cell in row)
                    ]
                    if rendered:
                        page_parts.append(
                            f"[page {page_no} table {t_no}]\n" + "\n".join(rendered)
                        )
            except Exception:  # noqa: BLE001
                pass

            # Layout-preserving plain text for non-table content.
            plain = (page.get_text("text", sort=True) or "").strip()
            if plain and not page_parts:
                # No tables found — use plain text.
                page_parts.append(f"[page {page_no}]\n{plain}")
            elif plain and page_parts:
                # Tables found — append any non-table text as context.
                # De-duplicate text already captured in table cells by checking length.
                if len(plain) > 100:
                    page_parts.append(f"[page {page_no} text]\n{plain}")

            if page_parts:
                parts.extend(page_parts)
            elif len(plain) < _IMAGE_PAGE_TEXT_THRESHOLD:
                # Sparse text → likely a scanned / image-only page.
                parts.append(f"[page {page_no}: image-only — no extractable text]")
                try:
                    pix = page.get_pixmap(dpi=150)
                    image_pngs.append(pix.tobytes("png"))
                except Exception:  # noqa: BLE001
                    pass

        doc.close()
    except Exception:  # noqa: BLE001 — malformed PDFs: caller uses pypdf fallback
        return "", []

    text = _strip_repeated_table_headers("\n\n".join(parts))
    return text, image_pngs


def _extract_with_vision(
    provider: _ExtractionProvider,
    text: str,
    image_pages: list[bytes],
    *,
    max_text_chars: int,
    max_chunks: int,
) -> LLMCollateralSchedule:
    """Run structured extraction over text + rendered page images.

    The full set of image pages is included in the first call (alongside the
    first text chunk); subsequent text chunks (if any) are sent without images
    to stay within context limits.
    """
    chunks = _split_chunks(text, max_text_chars, max_chunks)
    merged: LLMCollateralSchedule | None = None
    errors: list[Exception] = []

    for i, chunk in enumerate(chunks):
        imgs = image_pages if i == 0 else None
        try:
            raw = provider.extract_with_images(
                LLMCollateralSchedule,
                instruction=_INSTRUCTION,
                system=_SYSTEM_PROMPT,
                text=chunk or None,
                images=imgs,
            )
            part = _validated(raw)
        except Exception as exc:  # noqa: BLE001
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


def _pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    """Flat text fallback — tries PyMuPDF first, then pypdf."""
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join(page.get_text("text", sort=True) or "" for page in doc)
        doc.close()
        if text.strip():
            return text
    except Exception:  # noqa: BLE001
        pass
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Extracting PDF text needs 'pymupdf' or 'pypdf' "
            "(pip install pymupdf)."
        ) from exc
    import io
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
