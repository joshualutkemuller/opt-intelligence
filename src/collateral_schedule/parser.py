"""Parse collateral schedules from CSV, XLSX, and PDF into unified entries."""

from __future__ import annotations

import base64
import csv
import io
import re
from typing import Any

from .models import COLUMN_ALIASES, normalize_asset_class, normalize_eligible, normalize_rating


def _resolve_header(raw: str) -> str | None:
    """Map a raw column header to a canonical field name, or None if unrecognised."""
    key = raw.strip().lower().replace("-", " ").replace("_", " ")
    for canonical, aliases in COLUMN_ALIASES.items():
        normalised_aliases = [a.lower().replace("_", " ") for a in aliases]
        if key in normalised_aliases:
            return canonical
    return None


def _parse_float(raw: Any) -> float | None:
    if raw is None or str(raw).strip() in ("", "-", "n/a", "na", "none"):
        return None
    cleaned = re.sub(r"[%,\s]", "", str(raw))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_bool_eligible(raw: Any) -> bool:
    return normalize_eligible(raw)


def _rows_to_entries(
    headers: list[str],
    rows: list[list[Any]],
) -> list[dict[str, Any]]:
    """Convert header + data rows into canonical entry dicts."""
    col_map: dict[int, str] = {}
    for i, h in enumerate(headers):
        canonical = _resolve_header(h)
        if canonical:
            col_map[i] = canonical

    entries: list[dict[str, Any]] = []
    for row_idx, row in enumerate(rows):
        entry: dict[str, Any] = {}
        for col_idx, canonical in col_map.items():
            if col_idx >= len(row):
                continue
            raw = row[col_idx]
            if canonical == "asset_class":
                entry["asset_class"] = normalize_asset_class(str(raw))
            elif canonical in ("haircut_pct", "max_maturity_years", "concentration_limit_pct"):
                val = _parse_float(raw)
                if val is not None:
                    entry[canonical] = val
            elif canonical == "eligible":
                entry["eligible"] = _parse_bool_eligible(raw)
            elif canonical == "rating_floor":
                stripped = str(raw).strip() if raw is not None else None
                if stripped:
                    entry["rating_floor"] = normalize_rating(stripped)
            else:
                stripped = str(raw).strip() if raw is not None else None
                if stripped:
                    entry[canonical] = stripped

        # Skip blank rows
        if not any(entry.values()):
            continue

        # Default asset_class if missing
        entry.setdefault("asset_class", "OTHER")
        entry.setdefault("eligible", True)
        entry["source_row"] = row_idx + 2  # 1-indexed, +1 for header
        entries.append(entry)

    return entries


def parse_csv(content: str | bytes) -> list[dict[str, Any]]:
    """Parse a CSV file (text or bytes) into collateral entries."""
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")  # handle BOM
    reader = csv.reader(io.StringIO(content))
    all_rows = list(reader)
    if not all_rows:
        return []
    # Skip blank leading rows
    header_idx = 0
    for i, row in enumerate(all_rows):
        if any(c.strip() for c in row):
            header_idx = i
            break
    headers = all_rows[header_idx]
    data_rows = [list(r) for r in all_rows[header_idx + 1:]]
    return _rows_to_entries(headers, data_rows)


def parse_xlsx(content: bytes) -> list[dict[str, Any]]:
    """Parse an XLSX file into collateral entries."""
    try:
        import openpyxl  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError("openpyxl is required to parse XLSX files: pip install openpyxl") from e

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.active
    all_rows: list[list[Any]] = []
    for row in ws.iter_rows(values_only=True):
        all_rows.append(list(row))

    if not all_rows:
        return []

    # Find first non-empty row as header
    header_idx = 0
    for i, row in enumerate(all_rows):
        if any(c is not None for c in row):
            header_idx = i
            break

    headers = [str(c) if c is not None else "" for c in all_rows[header_idx]]
    data_rows = [list(r) for r in all_rows[header_idx + 1:]]
    return _rows_to_entries(headers, data_rows)


def parse_pdf_text(text: str) -> list[dict[str, Any]]:
    """Extract collateral entries from plain text extracted from a PDF.

    Attempts to detect a tabular section by looking for lines that contain
    numeric haircut values.  Falls back to returning a best-effort parse.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Heuristic: find lines that look like data rows (contain a % or decimal)
    table_lines: list[str] = []
    header_line: str | None = None
    header_found = False

    for line in lines:
        has_number = bool(re.search(r"\d+\.?\d*\s*%?", line))
        is_header_candidate = any(
            alias in line.lower()
            for aliases in COLUMN_ALIASES.values()
            for alias in aliases
        )
        if not header_found and is_header_candidate:
            header_line = line
            header_found = True
        elif header_found and has_number:
            table_lines.append(line)

    if not header_line or not table_lines:
        return []

    # Split lines by 2+ spaces or tab (common in PDF-extracted tables)
    splitter = re.compile(r"\s{2,}|\t")
    headers = splitter.split(header_line)
    rows = [splitter.split(line) for line in table_lines]
    return _rows_to_entries(headers, rows)


def parse_schedule(
    content: bytes | str,
    filename: str | None = None,
    content_type: str | None = None,
    pdf_base64: str | None = None,
) -> list[dict[str, Any]]:
    """Dispatch to the appropriate parser based on file type."""

    if pdf_base64:
        # PDF provided as base64 — use pdfplumber if available, else text heuristic
        pdf_bytes = base64.b64decode(pdf_base64)
        try:
            import pdfplumber  # type: ignore[import-untyped]
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                )
        except ImportError:
            # Fallback: try to decode as text (will fail for binary PDFs)
            try:
                text = pdf_bytes.decode("utf-8", errors="replace")
            except Exception:
                text = ""
        return parse_pdf_text(text)

    if isinstance(content, str):
        return parse_csv(content)

    # Bytes — detect by filename or content-type
    name = (filename or "").lower()
    ct = (content_type or "").lower()

    if name.endswith(".xlsx") or "spreadsheetml" in ct or "excel" in ct:
        return parse_xlsx(content)

    if name.endswith(".csv") or "csv" in ct or "text/plain" in ct:
        return parse_csv(content)

    # Try CSV first, then XLSX
    try:
        result = parse_csv(content)
        if result:
            return result
    except Exception:
        pass

    try:
        return parse_xlsx(content)
    except Exception:
        pass

    return []
