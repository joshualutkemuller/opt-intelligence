# Decision Intelligence Platform — Scenario Reference Guide

This guide covers the combined front-end demo video in detail and describes each
operation storyboard demo. It is intended for audience preparation, sales
enablement, and internal knowledge transfer.

---

## Combined Front-End Demo Reel

**File:** `video_examples/combined/collateral-and-money-market-frontend-demo.mp4`
**Duration:** ~210 seconds (3.5 minutes)

### What It Is

A continuous, presentation-ready MP4 that shows the same browser-based Decision
Intelligence workspace handling two different financial optimization workflows
back to back. The video was captured from a real running front-end (React/Vite)
connected to a real FastAPI backend running local optimizer code. It is not
a screen recording of slides or a rendered animation — every panel, chat
interaction, analytics chart, and evidence table is live output from the
platform.

Each example is introduced by a two-second animated title card that names the
workflow and summarises the steps the audience is about to see.

### Structure

| Segment | Duration | Content |
|---|---|---|
| Title card — Example #1 | 2 s | "Collateral Management" |
| Example #1: Collateral HQLA | ~102 s | Live browser recording |
| Title card — Example #2 | 2 s | "Money Market Optimization" |
| Example #2: Money Market PDF | ~104 s | Live browser recording |

### Example #1 — Collateral Management (Collateral HQLA Orchestration)

**Source file:** `video_examples/collateral/collateral-hqla-frontend-orchestration-demo.mp4`

The recording drives the **Collateral** path of the front-end workspace and
demonstrates the following stages in sequence.

#### Stage-by-stage walkthrough

1. **Schedule Intake**
   The operator selects the Collateral path and lands on the Schedule Intake
   panel. A sample collateral schedule (CSV or structured upload) is ingested.
   The platform validates fields including asset class, ISIN, market value,
   haircut, and eligible-collateral flag. Deterministic extraction keeps inputs
   structured and repeatable; local Ollama can optionally assist with free-text
   interpretation if available.

2. **Obligation Review**
   The UI presents the parsed bilateral CSA, CCP clearing-house, and exchange
   margin obligations the collateral pool must satisfy. The operator can review
   net exposure by counterparty and obligation type before the optimizer runs.

3. **Production Runtime Toggle**
   The workspace shows a production-runtime toggle that switches between
   deterministic-only execution and Ollama-augmented explanation mode. When
   production mode is active, the optimizer runs against firm parameters with
   no LLM intervention in the solve step.

4. **Optimizer Execution — `collateral_liquidity_review` Workflow**
   The operator initiates the `collateral_liquidity_review` orchestration
   workflow:
   - **`collateral_001`**: the collateral optimizer allocates eligible assets
     to bilateral, CCP, and exchange obligations, respecting HQLA tier
     constraints, haircuts, and concentration limits.
   - **`money_market_001`**: using downstream liquidity context from the
     collateral step, the money-market optimizer adjusts fund allocation to
     preserve required daily and weekly liquidity buffers.
   Trace events stream in real time as each step executes.

5. **LLM-Assisted Explanation**
   After the solve, the local LLM (llama3.1:8b or similar Ollama model) reads
   the optimizer output and produces a plain-English explanation of what changed,
   why specific assets were chosen or excluded, and what the HQLA impact means
   for the portfolio. The explanation is displayed in the chat panel and does not
   alter the deterministic recommendation.

6. **Scenario Comparison**
   The analytics panel shows a before/after view of the collateral pool:
   HQLA tier 1, tier 2A, tier 2B composition; LCR buffer adequacy; allocation
   stats; and binding constraint summary. A second scenario can be loaded for
   side-by-side comparison.

7. **Lending Opportunity Detection**
   Assets allocated as collateral that carry a funding cost of ≥ 60 bps are
   flagged as foregone securities-lending opportunities. The panel shows each
   flagged asset with its lending rate, estimated annual revenue foregone, and
   severity (high ≥ 90 bps, medium 60–89 bps). The intent is to surface cases
   where posting an asset as collateral costs more than the margin obligation it
   satisfies — prompting the operator to consider a cheaper substitute.

8. **Traceability and Governance**
   A traceability panel links every recommendation to the source constraint,
   schedule row, or policy document that drove it. Governance metadata records
   optimizer version, run timestamp, approval threshold, and materiality flag.

9. **Evidence Room**
   The operator opens the evidence room to review the exportable audit package:
   schedule snapshot, validated inputs, optimizer parameters, output summary,
   LLM explanation, governance attestation, and version lineage. This package is
   designed to satisfy internal risk review and regulatory evidence requirements.

---

### Example #2 — Money Market Optimization (PDF Policy Upload)

**Source file:** `video_examples/money_market/money-market-pdf-policy-optimization-demo.mp4`

The recording drives the **Treasury MMF Policy Optimization** path and
demonstrates PDF-first policy ingestion through to evidence review.

#### Stage-by-stage walkthrough

1. **PDF Upload and Preview**
   The operator uploads `sample_money_market_policy.pdf`. The platform displays
   the first page of the document inside the ingestion panel so the audience can
   see that a real policy document is being processed, not a pre-structured
   template.

2. **Structured Policy Ingestion**
   The ingestion engine extracts controls from the PDF:
   - Maximum WAM (weighted average maturity)
   - Daily and weekly liquidity minimums
   - Prime fund exposure limit
   - Single-fund concentration cap
   - Eligible fund universe

   Deterministic field extraction runs first; local Ollama can supplement
   interpretation of free-text policy language when available.

3. **Ollama-Assisted Policy Discussion**
   The local LLM reads the extracted controls and produces a plain-English
   summary of what the policy requires, flags any constraints that are tighter
   than typical market practice, and suggests clarifying questions the operator
   might want to resolve before the optimizer runs. This step is informational
   and does not modify the extracted constraints.

4. **Optimizer Execution — `money_market_policy_optimization` Workflow**
   The `money_market_001` optimizer allocates cash across eligible money-market
   funds subject to the PDF-derived constraints. The solve is deterministic and
   reproducible given the same inputs.

5. **Before/After Analytics**
   The analytics panel shows the portfolio state before and after the optimizer
   ran:
   - Blended gross yield
   - Daily liquidity ratio
   - Weekly liquidity ratio
   - WAM
   - Prime fund exposure
   - Top-fund concentration
   - Recommended fund count

   Each metric is displayed with its policy limit alongside so the audience can
   see that every post-optimization value respects the ingested constraints.

6. **Document-to-Constraint Traceability**
   The traceability panel links each constraint used in the solve back to the
   specific page and clause in the source PDF. This closes the loop between the
   business policy document and the mathematical optimization inputs.

7. **Governance and Evidence Room**
   The governance panel records the policy document hash, extraction run
   timestamp, optimizer parameters, approval threshold, and materiality flag.
   The evidence room packages all of these alongside the optimizer output for
   export and downstream audit.

---

### Platform Architecture (as shown in the video)

| Layer | Role |
|---|---|
| React/Vite front-end | Guided workflow UI, chat, analytics, evidence panels |
| FastAPI backend | Workflow orchestration, validation, adapter routing |
| Deterministic optimizers | Collateral, money-market, MVO solvers |
| Ollama (local LLM) | Explanation, document interpretation, guided discussion |
| Evidence layer | Governance metadata, version lineage, audit packaging |

---

### How to Regenerate

```bash
# 1. Re-record the collateral front-end video
node scripts/record_collateral_hqla_frontend_video.mjs

# 2. Re-record the money-market front-end video
python3 scripts/generate_sample_money_market_policy_pdf.py
node scripts/record_money_market_policy_frontend_video.mjs

# 3. Compose the combined reel
python3 scripts/generate_combined_frontend_demo_video.py
```

The compose script inserts the animated title cards and concatenates all
segments into a single H.264/MP4 using PyAV (libx264, CRF 18, fast preset).

---

## Operation Storyboard Demos

All three clips are in `video_examples/operations/`. They are silent,
presentation-paced storyboards rendered at 1280×720 with real local adapter
output burned into each frame.

---

### Operations Demo 1 — Treasury and Margin Operations Combined

**File:** `video_examples/operations/treasury-margin-operations-storyboard-demo.mp4`
**Duration:** ~64 seconds

**What it shows:**

A high-level proof of concept that combines the two core operational production
adapters side by side, rendered at 1.5× pacing from a 96-second storyboard
timeline. The clip is designed for an executive overview slot where the audience
needs to see that both the treasury cash-movement and margin-call adapters exist,
produce real output, and generate production-grade evidence — without having to
watch two separate demos end to end.

**Content breakdown:**

| Stage | Content |
|---|---|
| Platform framing | Production integration overview; adapter registry; workflow routing |
| Treasury cash movement | Real adapter output: cash moved, transfer count, recommended transfers, rail limits applied |
| Capacity and binding checks | Utilisation by payment rail; binding constraint identification |
| Margin call workflow | Real adapter output: assigned margin amount, deferred calls, SLA status |
| Evidence metadata | Normalised evidence package with run timestamp, version, and governance attestation |

**Adapters shown:**
- `production.treasury.cash_movement`
- `production.margin_call.workflow`

**Regenerate:**

```bash
python3 scripts/generate_operational_optimizer_video_examples.py
```

---

### Operations Demo 2 — Treasury Policy Ingestion and Cash Movement

**File:** `video_examples/operations/treasury-policy-ingestion-cash-movement-demo.mp4`
**Duration:** ~72 seconds

**What it shows:**

A focused storyboard that follows the complete lifecycle of a treasury payment
policy from raw source document through to a structured, evidence-ready same-day
cash movement recommendation.

**Content breakdown:**

| Stage | Content |
|---|---|
| Policy ingestion | Source: `sample_treasury_payment_policy.md`; cutoff time extraction, buffer ratio extraction, rail-limit extraction |
| Preflight validation | Validated policy fields; structured inputs ready for optimizer |
| Optimizer execution | `production.treasury.cash_movement` adapter runs deterministic cash movement solve |
| Recommended transfers | Transfer list with amount, rail, counterparty, and status |
| Before/after framing | Cash deployed vs. available; binding rail limits; buffer adequacy |
| Evidence output | Evidence-ready output with policy document hash, run timestamp, and model lineage |

**Source policy document:** `examples/policies/sample_treasury_payment_policy.md`

**Key controls extracted:**
- Same-day payment cutoff times by rail (Fedwire, CHIPS, SWIFT)
- Intraday liquidity buffer minimum
- Payment rail capacity limits
- Concentration limits by counterparty

**Regenerate:**

```bash
python3 scripts/generate_operational_optimizer_video_examples.py
```

---

### Operations Demo 3 — Margin Call SLA Triage and Policy

**File:** `video_examples/operations/margin-call-sla-triage-policy-demo.mp4`
**Duration:** ~72 seconds

**What it shows:**

A focused storyboard showing how the platform ingests a margin call SLA
procedure document, extracts deterministic operational constraints, triages a
stressed call queue, and produces an evidence-ready set of operational controls.

**Content breakdown:**

| Stage | Content |
|---|---|
| SLA procedure ingestion | Source: `sample_margin_call_sla_procedure.md`; acknowledgement deadline, resolution deadline, escalation path, and dispute protocol extraction |
| Deterministic constraint extraction | Structured SLA fields; call classification tiers (priority, standard, disputed) |
| Stressed queue triage | Queue of margin calls under a stressed scenario; each call classified by size, age, counterparty, and SLA tier |
| Assigned and deferred calls | Calls recommended for same-day resolution vs. deferred with justification |
| Governance controls | Breach thresholds; escalation triggers; evidence packaging |
| Evidence output | Operational controls evidence with SLA document hash, triage parameters, and run metadata |

**Source policy document:** `examples/policies/sample_margin_call_sla_procedure.md`

**Key controls extracted:**
- Acknowledgement SLA by counterparty tier
- Resolution deadline by call size band
- Escalation path and breach notification rules
- Dispute protocol and hold classification

**Regenerate:**

```bash
python3 scripts/generate_operational_optimizer_video_examples.py
```

---

## Additional Video Library

The following clips are available in the repository for supplementary use.

### Collateral Storyboards (`video_examples/collateral/storyboards/`)

| File | Duration | Summary |
|---|---|---|
| `collateral-liquidity-hqla-orchestration-example.mp4` | ~88 s | Schedule upload, Ollama chat, orchestration, before/after liquidity analytics, HQLA tier exposure, allocation stats, governance review |
| `collateral-schedule-ingestion-stress-example.mp4` | ~82 s | Schedule ingestion, haircut and concentration-limit extraction, preflight, optimization, before/after HQLA analytics |
| `liquidity-stress-orchestration-example.mp4` | ~72 s | Cross-workflow liquidity stress story combining collateral and money-market steps |

### MVO Storyboards (`video_examples/mvo/storyboards/`)

| File | Duration | Summary |
|---|---|---|
| `ips-pdf-upload-optimization-workflow-example.mp4` | ~84 s | Full IPS PDF upload, ingestion review, optimization workflow, before/after portfolio analytics |
| `ips-to-optimization-workflow-example.mp4` | ~78 s | IPS ingestion, before analytics, optimization, after analytics |
| `mvo-constraint-negotiation-example.mp4` | ~76 s | MVO tradeoff exploration and constraint negotiation |
| `governed-mvo-presentation-example.mp4` | Short | Alternate presentation clip for the governed MVO workflow |

### Audit (`video_examples/audit/`)

| File | Duration | Summary |
|---|---|---|
| `policy-to-audit-evidence-example.mp4` | ~68 s | Policy ingestion through audit evidence packaging |

---

## Presenter Notes

- All live-front-end recordings use a **1600×900** browser viewport with the
  left navigation sidebar hidden so the main content fills the full frame.
- All storyboard clips use a **1280×720** rendered canvas.
- The combined MP4 normalises both to **1600×900** on encode, so the storyboard
  clips are upscaled slightly.
- Local Ollama interactions in the recordings use `llama3.1:8b`. If Ollama is
  not running, the platform falls back to deterministic extraction silently — the
  UI shows the results without error.
- The optimizer layer is intentionally separated from the LLM layer: AI assists
  with explanation and document interpretation; mathematical recommendations are
  always produced by deterministic optimizer code.
