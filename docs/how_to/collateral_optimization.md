# How To: Collateral Optimization

This guide walks through the complete collateral optimization workflow — from
uploading a counterparty's eligibility schedule to running an allocation that
minimizes funding cost across all your margin obligations.

---

## Overview

The collateral optimizer answers one question: **given your inventory and what
each counterparty will accept, which assets should you post where to meet all
your margin calls at the lowest cost?**

The system has two independent layers:

| Layer | What it does | Where it lives |
|---|---|---|
| **collateral_schedule** | Ingests, normalizes, and stores per-counterparty eligibility rules (CSV, XLSX, PDF) | `src/collateral_schedule/` |
| **CollateralOptimizer** | Solves the LP allocation problem given inventory + eligibility rules | `src/decision_intelligence/optimizers/collateral/` |

You can use either layer independently. This guide covers the end-to-end flow.

---

## Step 1 — Configure the LLM provider (PDF ingestion only)

If you are uploading PDF schedules, set the provider in `config/llm.yaml`:

```yaml
provider: anthropic        # or openai
# model: claude-sonnet-5   # override the default model
```

Then set your API key in the environment (keep it out of the YAML file):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
```

CSV and XLSX schedules do not require an LLM — skip this step if you only use
structured files.

---

## Step 2 — Register a counterparty

Every schedule belongs to a counterparty. Create one if it does not already
exist:

```bash
curl -s -X POST http://localhost:8000/api/collateral/counterparties \
  -H "Content-Type: application/json" \
  -d '{"name": "Goldman Sachs", "lei": "784F5XWPLTWKTBV3E584", "jurisdiction": "US"}' \
  | jq .
```

```json
{
  "id": "cp_abc123",
  "name": "Goldman Sachs",
  "lei": "784F5XWPLTWKTBV3E584",
  "created_at": "2026-07-22T10:00:00Z"
}
```

Save the `id` — you will need it in Step 3.

---

## Step 3 — Create a margin agreement

A counterparty can have multiple agreements (one per margin type). The agreement
links the counterparty to its schedule and stores the CSA/ISDA economic terms.

```bash
curl -s -X POST http://localhost:8000/api/collateral/agreements \
  -H "Content-Type: application/json" \
  -d '{
    "counterparty_id": "cp_abc123",
    "margin_type": "VM",
    "agreement_ref": "ISDA-2002-GS-001",
    "base_currency": "USD",
    "threshold_amount": 500000,
    "mta_amount": 100000,
    "governing_law": "English"
  }' | jq .
```

**Supported margin types:** `IM`, `VM`, `REPO`, `SBL`, `CCP_IM`, `HOUSE`, `OTHER`

Save the `id` (e.g. `agr_xyz`) returned in the response.

---

## Step 4 — Upload a collateral schedule

Upload the counterparty's eligibility schedule. The API accepts CSV, XLSX, or
PDF. On the PDF path the LLM extracts structured entries automatically.

### CSV or XLSX

```bash
# CSV — paste content directly
curl -s -X POST http://localhost:8000/api/collateral/agreements/agr_xyz/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "csv_content": "Asset Class,Haircut (%),Max Maturity (Years),Eligible\nGOVT,2.0,,Yes\nCORP,5.0,5.0,Yes\nEQUITY,,,No",
    "replace": true
  }' | jq .

# XLSX — base64-encode the file
curl -s -X POST http://localhost:8000/api/collateral/agreements/agr_xyz/ingest \
  -H "Content-Type: application/json" \
  -d "{\"xlsx_base64\": \"$(base64 -w0 schedule.xlsx)\", \"filename\": \"schedule.xlsx\"}" \
  | jq .
```

### PDF (LLM extraction)

```bash
curl -s -X POST http://localhost:8000/api/collateral/agreements/agr_xyz/ingest \
  -H "Content-Type: application/json" \
  -d "{\"pdf_base64\": \"$(base64 -w0 DTC-Haircut-Schedule.pdf)\", \
       \"filename\": \"DTC-Haircut-Schedule.pdf\", \"use_llm\": true}" \
  | jq .
```

A successful ingest returns:

```json
{
  "agreement_id": "agr_xyz",
  "entries_inserted": 34,
  "replaced": true,
  "summary": {
    "total_entries": 34,
    "eligible_count": 28,
    "min_haircut_pct": 2.0,
    "max_haircut_pct": 70.0,
    "avg_haircut_pct": 14.3,
    "eligible_asset_classes": ["GOVT", "AGENCY", "CORP", "MUNI"]
  }
}
```

The `replace: true` flag (default) replaces any existing entries for the
agreement and stamps the old ones with a `superseded_at` timestamp, giving you
a full version history.

### Accepted column names (CSV / XLSX)

The parser accepts many aliases for each field:

| Field | Common aliases |
|---|---|
| `asset_class` | Asset Class, Collateral Type, Security Type |
| `haircut_pct` | Haircut, Haircut (%), HC, HC (%) |
| `max_maturity_years` | Max Maturity, Maturity (Years), Maturity Years |
| `rating_floor` | Rating Floor, Minimum Rating, Min Rating |
| `eligible` | Eligible, Eligibility, Accepted, Permitted |
| `isin` | ISIN, CUSIP, Identifier, Security ID |
| `concentration_limit_pct` | Concentration Limit, Concentration (%), Conc Limit |

Run `GET /api/collateral/schema` for the full list.

---

## Step 5 — Inspect the schedule

```bash
# All entries
curl -s "http://localhost:8000/api/collateral/agreements/agr_xyz/schedule" | jq .

# Eligible entries only, filtered by asset class
curl -s "http://localhost:8000/api/collateral/agreements/agr_xyz/schedule?eligible_only=true&asset_class=GOVT" | jq .
```

Each entry has the form:

```json
{
  "id": "ce_...",
  "asset_class": "GOVT",
  "haircut_pct": 2.0,
  "max_maturity_years": 5.0,
  "rating_floor": null,
  "eligible": true,
  "notes": null
}
```

Check `GET /api/collateral/agreements/agr_xyz/history` to see a version-by-version
audit trail of every upload.

---

## Step 6 — Run the optimizer

Once a schedule is stored, pass the agreement ID to the optimizer. The optimizer
loads eligibility rules from the database, overlays them on your inventory, and
solves the LP.

### Via the API

```bash
curl -s -X POST http://localhost:8000/api/optimizations/run \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "collateral",
    "portfolio_id": "PORT_001",
    "objective_metric": "funding_cost",
    "agreement_id": "agr_xyz"
  }' | jq .
```

### Via Python

```python
from decision_intelligence.contracts import OptimizationRequest, Objective
from decision_intelligence.optimizers.collateral import CollateralOptimizer

optimizer = CollateralOptimizer()

request = OptimizationRequest(
    domain="collateral",
    portfolio_id="PORT_001",
    objective=Objective(metric="funding_cost"),
    context={
        "data_source": {
            "type": "collateral_db",
            "agreement_id": "agr_xyz",
        }
    },
)

problem = optimizer.prepare_problem(request)
result  = optimizer.solve(problem)
print(result)
```

The optimizer returns an allocation: for each asset, what fraction to post
against each obligation. Total funding cost and per-obligation coverage are
included in the result.

### Objective metrics

| Metric | Minimizes |
|---|---|
| `funding_cost` | Total funding cost in basis points × market value (default) |
| `haircut_cost` | Total value consumed by haircuts |
| `opportunity_cost` | Proxy via funding cost; excludes high-demand SBL assets |

---

## Step 7 — Work with multiple counterparties

Repeat Steps 2–5 for each counterparty. The optimizer can be called with one
`agreement_id` at a time — combine results across agreements to build a
portfolio-level allocation view.

Typical multi-counterparty setup:

```
Counterparty A (VM) → agr_001
Counterparty B (VM) → agr_002
Counterparty C (IM) → agr_003
CCP (CCP_IM)        → agr_004
```

Run a separate optimization per agreement, or aggregate obligations manually
and pass a simulated multi-obligation inventory.

---

## Step 8 — Updating a schedule

When a counterparty issues a new schedule, re-upload it with `replace: true`
(the default). The old entries are retained with a `superseded_at` timestamp
and the new entries become the live set. No history is lost.

```bash
curl -s -X POST http://localhost:8000/api/collateral/agreements/agr_xyz/ingest \
  -H "Content-Type: application/json" \
  -d "{\"pdf_base64\": \"$(base64 -w0 new-schedule.pdf)\", \"replace\": true}" \
  | jq .
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `503 No LLM provider is configured` | PDF upload with `use_llm: true` but no key set | Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, or add `api_key` to `config/llm.yaml` |
| `422 No collateral entries could be parsed` | LLM returned nothing; PDF may be image-only or non-standard | Check the PDF has a table; try a different model in `config/llm.yaml` |
| `502 LLM extraction failed` | Provider returned an error | Check API key validity and model name in `config/llm.yaml` |
| Optimizer returns infeasible | No eligible assets cover the obligation | Verify the schedule has `eligible: true` entries matching your inventory asset classes |
| Haircuts look wrong (e.g. 98% instead of 2%) | Source PDF uses "% of market value" (margin) instead of haircut | The LLM path auto-corrects values > 50% on eligible entries; check the `notes` field for `[auto-corrected]` tags |
| Duplicate entries after re-upload | Used `replace: false` when intending to replace | Re-upload with `"replace": true` |

---

## Python quick-start (standalone, no API)

```python
from collateral_schedule import CollateralDatabase, parse_schedule, parse_pdf_with_llm
from decision_intelligence.llm import resolve_provider

# 1. Set up the database
db = CollateralDatabase()  # ~/.decision_intelligence/collateral.db

# 2. Register counterparty and agreement
cp  = db.create_counterparty("Goldman Sachs")
agr = db.create_agreement(cp["id"], margin_type="VM", agreement_ref="GS-VM-001")

# 3a. Ingest a CSV schedule
entries = parse_schedule(open("schedule.csv").read(), filename="schedule.csv")

# 3b. Or ingest a PDF with LLM
provider = resolve_provider()          # reads config/llm.yaml + env vars
entries  = parse_pdf_with_llm(open("schedule.pdf", "rb").read(), provider)

db.insert_entries(agr["id"], entries, replace=True)

# 4. Inspect
print(db.summary(agr["id"]))

# 5. Optimize
from decision_intelligence.contracts import OptimizationRequest, Objective
from decision_intelligence.optimizers.collateral import CollateralOptimizer

result = CollateralOptimizer().solve(
    CollateralOptimizer().prepare_problem(
        OptimizationRequest(
            domain="collateral",
            portfolio_id="PORT_001",
            objective=Objective(metric="funding_cost"),
            context={"data_source": {"type": "collateral_db", "agreement_id": agr["id"]}},
        )
    )
)
print(result)
```

---

## Eval harness (measuring LLM accuracy)

Gold-labelled reference schedules live in `examples/collateral/gold/`. Run the
eval to measure extraction quality against them:

```bash
python scripts/eval_collateral_llm.py --mode improved
```

The script prints precision, recall, F1, haircut MAE, maturity accuracy, and
rating accuracy per document, plus a mean row across all gold sets. Use
`--mode baseline` to compare against the pre-LLM text-heuristic path.

---

## Data model reference

```
counterparties
  id, name, lei, jurisdiction, created_at

margin_agreements
  id, counterparty_id, margin_type, agreement_ref,
  base_currency, threshold_amount, mta_amount,
  rounding_amount, governing_law, effective_date,
  schedule_version, created_at

collateral_entries
  id, agreement_id, asset_class, isin, currency,
  rating_floor, max_maturity_years, haircut_pct,
  concentration_limit_pct, eligible, notes,
  source_row, created_at, superseded_at
```

`superseded_at` is `NULL` on live entries and stamped with a timestamp on
replaced entries, preserving full version history without deleting any data.
