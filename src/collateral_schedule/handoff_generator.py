"""
Handoff document generator for the collateral_schedule package.

Generation strategy (in order):
  1. LLM — uses any provider passed in (Anthropic, OpenAI, Ollama, etc.)
     via the decision_intelligence.llm interface if available.
  2. Deterministic template — fully self-contained, no LLM required.

The output is Markdown; callers can render it to HTML, PDF, or DOCX.
"""

from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path
from typing import Any

from .models import COLUMN_ALIASES, ASSET_CLASS_ALIASES, MarginType

# ── Schema snapshot used by both paths ───────────────────────────────────────

_MARGIN_TYPES = [m.value for m in MarginType]

_COLUMN_TABLE = "\n".join(
    f"| `{canonical}` | {', '.join(f'`{a}`' for a in aliases[:5])}{' …' if len(aliases) > 5 else ''} |"
    for canonical, aliases in COLUMN_ALIASES.items()
)

_ASSET_CLASS_TABLE = "\n".join(
    f"| `{cls.value}` | {alias} |"
    for alias, cls in list(ASSET_CLASS_ALIASES.items())[:12]
) + "\n| … | … |"

_DDL = textwrap.dedent("""\
    counterparties (id, name, lei, jurisdiction, created_at)
    margin_agreements (id, counterparty_id, margin_type, agreement_ref,
        base_currency, threshold_amount, mta_amount, rounding_amount,
        governing_law, effective_date, created_at)
    collateral_entries (id, agreement_id, asset_class, isin, currency,
        rating_floor, max_maturity_years, haircut_pct,
        concentration_limit_pct, eligible, notes, source_row, created_at)
""")

_ENDPOINTS = textwrap.dedent("""\
    POST   /api/collateral/counterparties                    Create counterparty
    GET    /api/collateral/counterparties                    List counterparties
    POST   /api/collateral/agreements                        Create agreement
    GET    /api/collateral/agreements?counterparty_id=&margin_type=
    GET    /api/collateral/agreements/{id}
    POST   /api/collateral/agreements/{id}/ingest            Upload schedule file
    GET    /api/collateral/agreements/{id}/schedule?asset_class=&eligible_only=
    DELETE /api/collateral/agreements/{id}/schedule
    GET    /api/collateral/schema                            Column alias reference
""")


# ── LLM path ─────────────────────────────────────────────────────────────────

_SYSTEM = """\
You are a senior software architect writing a production-grade technical handoff \
document. Be precise, structured, and complete. Use Markdown with clear headings. \
Do not pad with filler phrases. Assume the reader is a developer who will \
implement or extend this system.
"""

_PROMPT_TEMPLATE = """\
Write a full technical handoff document for the **collateral_schedule** Python \
package. This is a standalone library (peer to, not inside, the \
decision_intelligence package) that ingests eligible collateral schedules per \
counterparty and margin type, normalises them to a unified data model, and \
persists them in SQLite. It is part of a broader opt-intelligence project but \
designed so it can be imported independently by any consumer.

Use the following verified facts verbatim — do not hallucinate alternatives:

**Package location:** src/collateral_schedule/  (standalone, not nested inside decision_intelligence)

**Supported margin types:** {margin_types}

**SQLite tables:**
{ddl}

**Accepted column aliases (sample):**
| Canonical field | Accepted headers (sample) |
|---|---|
{column_table}

**Asset class normalisation (sample):**
| Canonical | Input strings |
|---|---|
{asset_class_table}

**REST API endpoints (consumed by decision_intelligence.api):**
{endpoints}

**File formats supported for ingestion:** CSV (text), XLSX (base64), PDF (base64, text extraction)

**Key design decisions to document:**
1. The library has zero hard dependencies on decision_intelligence — all imports of the LLM or API layer are in the consumer (app.py), not in collateral_schedule itself.
2. Column headers are normalised at parse time via COLUMN_ALIASES — source files need not match a strict schema.
3. Eligibility is preserved as a first-class field so ineligible assets are stored (for audit) but can be filtered at query time.
4. replace=True on ingest atomically clears old entries for an agreement before inserting new ones, preventing stale data.
5. The SQLite database path defaults to ~/.decision_intelligence/collateral.db but is overridable for testing or multi-tenant use.

**Sections to include:**
1. Purpose & scope
2. Package structure (file-by-file)
3. Data model (ER diagram in Mermaid, then DDL)
4. Margin types reference table
5. Ingestion pipeline (flow diagram in Mermaid, then algorithm)
6. Column normalisation rules
7. Asset class mapping
8. REST API reference (all 9 endpoints with request/response shapes)
9. Standalone usage examples (Python snippets, no decision_intelligence dependency)
10. Integration with decision_intelligence (what the consumer wires)
11. Extension points (adding new margin types, LLM-assisted PDF parsing, new file formats)
12. Testing approach
13. Known limitations & next steps
14. Glossary

Today's date: {today}
"""


def _build_prompt() -> str:
    return _PROMPT_TEMPLATE.format(
        margin_types=", ".join(_MARGIN_TYPES),
        ddl=_DDL,
        column_table=_COLUMN_TABLE,
        asset_class_table=_ASSET_CLASS_TABLE,
        endpoints=_ENDPOINTS,
        today=date.today().isoformat(),
    )


def _generate_with_llm(provider: Any, max_tokens: int = 8000) -> str:
    prompt = _build_prompt()
    return provider.generate(prompt, system=_SYSTEM, max_tokens=max_tokens)


# ── Deterministic template path ───────────────────────────────────────────────

def _generate_from_template() -> str:
    today = date.today().isoformat()
    margin_list = "\n".join(f"- **{m}**" for m in _MARGIN_TYPES)

    raw = textwrap.dedent(f"""\
    # collateral_schedule — Technical Handoff Document

    **Generated:** {today}
    **Package:** `src/collateral_schedule/`
    **Status:** Production-ready (v1)

    ---

    ## 1. Purpose & Scope

    `collateral_schedule` is a **standalone Python library** for ingesting,
    normalising, and persisting eligible collateral schedules on a
    per-counterparty, per-margin-type basis. It is part of the
    opt-intelligence project but has **zero imports from `decision_intelligence`**
    and can be used independently by any consumer (CLI, API, notebook, etc.).

    **What it does:**
    - Accepts collateral schedules as CSV, XLSX, or PDF
    - Normalises heterogeneous column headers to a canonical schema
    - Maps free-text asset class labels to a controlled vocabulary
    - Persists data in a local SQLite database (WAL mode)
    - Exposes a clean Python API for CRUD and summary queries

    **What it does not do:**
    - Drive optimisation (that stays in `decision_intelligence.optimizers`)
    - Authenticate users or enforce access control
    - Connect to external data sources

    ---

    ## 2. Package Structure

    ```
    src/collateral_schedule/
    ├── __init__.py          Public API: CollateralDatabase, AssetClass,
    │                        MarginType, parse_schedule
    ├── models.py            Enums, COLUMN_ALIASES, ASSET_CLASS_ALIASES,
    │                        normalisers
    ├── database.py          CollateralDatabase — SQLite CRUD + schema init
    ├── parser.py            parse_csv / parse_xlsx / parse_pdf_text /
    │                        parse_schedule dispatcher
    └── handoff_generator.py This generator (LLM + deterministic paths)
    ```

    **Consumed by (not part of this package):**
    - `src/decision_intelligence/api/app.py` — REST endpoints
    - `examples/collateral/` — sample schedule files

    ---

    ## 3. Data Model

    ### Entity-relationship diagram

    ```mermaid
    erDiagram
        COUNTERPARTIES {{
            TEXT id PK
            TEXT name
            TEXT lei
            TEXT jurisdiction
            TEXT created_at
        }}
        MARGIN_AGREEMENTS {{
            TEXT id PK
            TEXT counterparty_id FK
            TEXT margin_type
            TEXT agreement_ref
            TEXT base_currency
            REAL threshold_amount
            REAL mta_amount
            REAL rounding_amount
            TEXT governing_law
            TEXT effective_date
            TEXT created_at
        }}
        COLLATERAL_ENTRIES {{
            TEXT id PK
            TEXT agreement_id FK
            TEXT asset_class
            TEXT isin
            TEXT currency
            TEXT rating_floor
            REAL max_maturity_years
            REAL haircut_pct
            REAL concentration_limit_pct
            INTEGER eligible
            TEXT notes
            INTEGER source_row
            TEXT created_at
        }}
        COUNTERPARTIES ||--o{{ MARGIN_AGREEMENTS : "has"
        MARGIN_AGREEMENTS ||--o{{ COLLATERAL_ENTRIES : "contains"
    ```

    ### DDL summary

    ```
    {_DDL}    ```

    **Indexes:**
    - `idx_entries_agreement` on `collateral_entries(agreement_id)`
    - `idx_agreements_counterparty` on `margin_agreements(counterparty_id)`

    ---

    ## 4. Margin Types

    {margin_list}

    Each agreement links exactly one counterparty to one margin type.
    A counterparty may have multiple agreements (e.g. both an IM and a VM
    schedule with the same dealer).

    ---

    ## 5. Ingestion Pipeline

    ```mermaid
    flowchart TD
        A[Caller: CSV / XLSX / PDF bytes] --> B{{parse_schedule dispatcher}}
        B -->|.csv or text| C[parse_csv]
        B -->|.xlsx or base64| D[parse_xlsx]
        B -->|pdf_base64| E[parse_pdf_text]
        C --> F[_rows_to_entries]
        D --> F
        E --> F
        F --> G[_resolve_header — map column names]
        G --> H[normalize_asset_class]
        G --> I[_parse_float — haircut / maturity / concentration]
        G --> J[_parse_bool_eligible]
        H & I & J --> K[list of entry dicts]
        K --> L[CollateralDatabase.insert_entries]
        L -->|replace=True| M[DELETE old entries, INSERT new]
        L -->|replace=False| N[APPEND new entries]
    ```

    **Algorithm:**
    1. Detect file type from filename extension or MIME type; try CSV then XLSX as fallback.
    2. Find the first non-empty row as the header row (skips blank leading rows).
    3. For each header cell, call `_resolve_header()` which lowercases, strips, and compares against all entries in `COLUMN_ALIASES`.
    4. For each data row, apply type-specific converters: float parsing strips `%`, `,`, and whitespace; eligibility accepts `0/1`, `true/false`, `yes/no`, `eligible/ineligible`.
    5. Rows where no field resolved are skipped.
    6. `asset_class` is mapped via `normalize_asset_class()` which tries exact match then prefix match against `ASSET_CLASS_ALIASES`; unrecognised values become `OTHER`.

    ---

    ## 6. Column Normalisation Rules

    Any of the following header spellings is accepted for each canonical field:

    | Canonical field | Accepted headers (sample) |
    |---|---|
    {_COLUMN_TABLE}

    Headers are compared case-insensitively with hyphens and underscores
    replaced by spaces.

    ---

    ## 7. Asset Class Mapping

    | Canonical | Example input strings |
    |---|---|
    {_ASSET_CLASS_TABLE}

    Matching is exact then prefix. Unrecognised → `OTHER`.

    ---

    ## 8. REST API Reference

    All endpoints are mounted on the `decision_intelligence` FastAPI app.
    The `collateral_schedule` library itself has no HTTP layer.

    ```
    {_ENDPOINTS}    ```

    ### Key request/response shapes

    **POST /api/collateral/counterparties**
    ```json
    // Request
    {{ "name": "Goldman Sachs", "lei": "784F5XWPLTWKTBV3E584", "jurisdiction": "US" }}
    // Response
    {{ "id": "cp_abc123", "name": "Goldman Sachs", "lei": "...", "created_at": "..." }}
    ```

    **POST /api/collateral/agreements**
    ```json
    // Request
    {{
      "counterparty_id": "cp_abc123", "margin_type": "VM",
      "agreement_ref": "ISDA-2002-001", "base_currency": "USD",
      "threshold_amount": 500000, "mta_amount": 100000,
      "governing_law": "English"
    }}
    ```

    **POST /api/collateral/agreements/{{id}}/ingest**
    ```json
    // CSV path
    {{ "csv_content": "Asset Class,Haircut (%)\\nGOVT,2.0\\n...", "replace": true }}
    // XLSX path
    {{ "xlsx_base64": "<base64>", "filename": "schedule.xlsx", "replace": true }}
    // PDF path
    {{ "pdf_base64": "<base64>", "filename": "schedule.pdf", "replace": true }}
    // Response
    {{ "agreement_id": "agr_xyz", "entries_inserted": 12, "replaced": true,
       "summary": {{ "total_entries": 12, "eligible_count": 9,
                     "min_haircut_pct": 0.0, "max_haircut_pct": 20.0,
                     "avg_haircut_pct": 6.75,
                     "eligible_asset_classes": ["CASH","GOVT","CORP","MMF"] }} }}
    ```

    **GET /api/collateral/agreements/{{id}}/schedule?eligible_only=true**
    ```json
    {{ "agreement_id": "agr_xyz",
       "entries": [
         {{ "id": "ce_...", "asset_class": "GOVT", "isin": "US912828ZT",
            "currency": "USD", "rating_floor": "A-", "max_maturity_years": 30,
            "haircut_pct": 2.0, "concentration_limit_pct": 40.0,
            "eligible": true, "notes": "UST on-the-run" }}
       ],
       "summary": {{ ... }} }}
    ```

    ---

    ## 9. Standalone Usage (no decision_intelligence)

    ```python
    from collateral_schedule import CollateralDatabase, parse_schedule

    # 1. Initialise DB (defaults to ~/.decision_intelligence/collateral.db)
    db = CollateralDatabase("/path/to/collateral.db")

    # 2. Register a counterparty
    cp = db.create_counterparty("Goldman Sachs", lei="784F5XWPLTWKTBV3E584")

    # 3. Create a VM agreement
    agr = db.create_agreement(
        counterparty_id=cp["id"],
        margin_type="VM",
        agreement_ref="ISDA-2002-001",
        base_currency="USD",
        threshold_amount=500_000,
        mta_amount=100_000,
        governing_law="English",
    )

    # 4. Parse and ingest a schedule
    with open("vm_schedule.csv") as f:
        entries = parse_schedule(f.read(), filename="vm_schedule.csv")
    db.insert_entries(agr["id"], entries, replace=True)

    # 5. Query eligible GOVT entries
    rows = db.list_entries(agr["id"], asset_class="GOVT", eligible_only=True)
    for row in rows:
        print(row["isin"], row["haircut_pct"])

    # 6. Get summary
    print(db.summary(agr["id"]))
    ```

    ---

    ## 10. Integration with decision_intelligence

    The `decision_intelligence.api.app` module wires the library into REST:

    ```python
    # app.py (consumer — not part of collateral_schedule)
    from collateral_schedule import CollateralDatabase, parse_schedule

    _COLLATERAL_DB = CollateralDatabase()   # singleton at app startup
    ```

    The 9 REST endpoints in app.py are thin adapters: they validate Pydantic
    schemas, call `_COLLATERAL_DB` methods, and serialise responses.
    No business logic lives in app.py — it all stays in `collateral_schedule`.

    **Future integration:** the `CollateralOptimizer` can replace its CSV
    fixture reads with `_COLLATERAL_DB.list_entries(agreement_id, eligible_only=True)`
    once counterparty context is threaded through the `OptimizationRequest`.

    ---

    ## 11. Extension Points

    | Extension | Where to change |
    |---|---|
    | New margin type | Add to `MarginType` enum in `models.py` |
    | New column alias | Add to `COLUMN_ALIASES` dict in `models.py` |
    | New asset class | Add to `AssetClass` enum + `ASSET_CLASS_ALIASES` in `models.py` |
    | LLM-assisted PDF parsing | Add `parse_pdf_with_llm(pdf_bytes, provider)` in `parser.py`; call before `parse_pdf_text` fallback |
    | New file format (XML, JSON) | Add `parse_xml` / `parse_json` in `parser.py`; extend dispatcher in `parse_schedule` |
    | Multi-tenant DB | Pass a tenant-specific `path` to `CollateralDatabase(path=...)` |
    | Postgres | Replace `sqlite3` with `psycopg2`/`asyncpg` in `database.py`; SQL is ANSI-compatible |

    ---

    ## 12. Testing Approach

    **Unit tests** (no DB, no HTTP):
    - `parse_csv` with all-alias headers → verify canonical fields populated
    - `parse_csv` with missing `haircut_pct` column → verify skipped gracefully
    - `normalize_asset_class("government bonds")` → `"GOVT"`
    - `normalize_eligible("No")` → `False`

    **Integration tests** (in-memory SQLite via `CollateralDatabase(":memory:")`):
    - Round-trip: create counterparty → agreement → insert entries → list entries → summary
    - `replace=True` clears old entries before inserting new ones
    - Filter `eligible_only=True` returns only rows where `eligible=1`

    **Sample files** (in `examples/collateral/`):
    - `sample_vm_schedule.csv` — 12 rows, VM, mixed eligible/ineligible
    - `sample_repo_schedule.csv` — 11 rows, REPO, GC + haircut tiers

    Run against the API with `curl -X POST /api/collateral/agreements/{{id}}/ingest`
    using the sample files to verify end-to-end.

    ---

    ## 13. Known Limitations & Next Steps

    | # | Limitation | Suggested fix |
    |---|---|---|
    | 1 | PDF parser uses text-heuristic extraction; structured PDFs with embedded tables parse poorly | Integrate pdfplumber table extraction or LLM-assisted parsing |
    | 2 | No version history for schedule entries | Add `version` integer to `margin_agreements`; keep old entries with a `superseded_at` timestamp |
    | 3 | No ISIN validation | Integrate `isin` PyPI package or checksum validator in `parser.py` |
    | 4 | No rating normalisation (S&P vs Moody's vs Fitch) | Add `normalize_rating(raw)` in `models.py` mapping `"Aaa"→"AAA"`, `"Baa3"→"BBB-"` etc. |
    | 5 | Collateral optimizer still reads from CSV fixtures | Thread `agreement_id` through `OptimizationRequest.context`; update `CollateralOptimizer` to call `_COLLATERAL_DB.list_entries` |
    | 6 | Single-file SQLite can't scale to thousands of counterparties | Add Postgres adapter in `database.py` (schema is ANSI SQL) |
    | 7 | No UI for editing individual entries post-ingest | Add inline edit / delete row to `CollateralSchedulePanel` in the frontend |

    ---

    ## 14. Glossary

    | Term | Definition |
    |---|---|
    | **IM** | Initial Margin — collateral posted to cover potential future exposure |
    | **VM** | Variation Margin — daily mark-to-market collateral under a CSA |
    | **REPO** | Repurchase agreement — short-term borrowing secured by collateral |
    | **SBL** | Securities Borrowing & Lending — lending securities against collateral |
    | **CCP_IM** | Central Counterparty Initial Margin — margin posted to a CCP/exchange |
    | **CSA** | Credit Support Annex — ISDA agreement governing VM collateral |
    | **Haircut** | Percentage reduction applied to the market value of collateral |
    | **MTA** | Minimum Transfer Amount — smallest margin call that triggers a transfer |
    | **GC** | General Collateral — standard-quality collateral for repo |
    | **ISDA** | International Swaps and Derivatives Association |
    | **LEI** | Legal Entity Identifier — 20-character ISO 17442 code |
    | **WAL** | Write-Ahead Logging — SQLite journal mode for concurrency safety |
    """)
    return "\n".join(l.lstrip("    ") if l.startswith("    ") else l for l in raw.splitlines())


# ── Public entry point ────────────────────────────────────────────────────────

def generate_handoff(
    provider: Any = None,
    provider_name: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    max_tokens: int = 8000,
    output_path: Path | str | None = None,
) -> str:
    """Generate the collateral_schedule handoff document.

    Tries LLM generation first (if *provider* or provider credentials are
    supplied), then falls back to the deterministic template.

    Args:
        provider: An already-instantiated LLMProvider object.
        provider_name: ``"anthropic"`` | ``"openai"`` | ``"ollama"`` etc.
            Ignored if *provider* is given directly.
        model: Model name passed to the provider.
        base_url: Custom base URL (for Ollama / Azure / compatible endpoints).
        api_key: API key (falls back to environment variable).
        max_tokens: Maximum tokens for LLM generation (default 8000).
        output_path: If given, write the Markdown document to this path.

    Returns:
        The Markdown document as a string.
    """
    doc: str | None = None

    # 1. Try LLM
    if provider is not None:
        try:
            doc = _generate_with_llm(provider, max_tokens=max_tokens)
        except Exception as exc:
            print(f"[collateral_schedule] LLM generation failed ({exc}); using template.")

    elif provider_name:
        try:
            from decision_intelligence.llm import resolve_provider
            resolved = resolve_provider(
                provider=provider_name,
                model=model,
                base_url=base_url,
                api_key=api_key,
            )
            doc = _generate_with_llm(resolved, max_tokens=max_tokens)
        except Exception as exc:
            print(f"[collateral_schedule] LLM generation failed ({exc}); using template.")

    # 2. Deterministic fallback
    if doc is None:
        doc = _generate_from_template()

    if output_path:
        Path(output_path).write_text(doc, encoding="utf-8")

    return doc
