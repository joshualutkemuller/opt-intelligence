# Agentic Optimization Platform

## Comprehensive Strategy & Handoff Document

> **Purpose:** Provide a production-ready blueprint for building a
> reusable Decision Intelligence Platform that orchestrates multiple
> optimization engines (Collateral, Money Market, Financing, Cash,
> Margin, Hedging) using AI agents while maintaining governance,
> explainability, and mathematical rigor.

------------------------------------------------------------------------

# 1. Vision

Build a **Decision Intelligence Platform**, not a collection of AI
chatbots.

Core principle:

    Intent
        ↓
    Planning
        ↓
    Optimization
        ↓
    Validation
        ↓
    Explanation
        ↓
    Approval / Execution

The LLM is responsible for orchestration and reasoning. Deterministic
optimization engines remain responsible for mathematical correctness.

------------------------------------------------------------------------

# 2. Design Principles

-   Separate probabilistic AI from deterministic optimization.
-   Every optimizer exposes the same interface.
-   Every decision is explainable and auditable.
-   Every optimization request is versioned.
-   Every recommendation is reproducible.
-   Human approval exists for material decisions.

------------------------------------------------------------------------

# 3. Platform Architecture

``` text
User / API / Scheduled Workflow
            │
            ▼
Optimization Orchestrator
    ├── Intent Agent
    ├── Planning Agent
    ├── Data Agent
    ├── Constraint Agent
    ├── Scenario Agent
    ├── Validation Agent
    └── Explanation Agent
            │
            ▼
Structured Optimization Request
            │
            ▼
Optimization Registry
    ├── Collateral Optimizer
    ├── Money Market Optimizer
    ├── Financing Optimizer
    ├── Cash Optimizer
    ├── Margin Optimizer
    └── Hedging Optimizer
            │
            ▼
Validation
Sensitivity
Economic Attribution
Approval
Execution
```

------------------------------------------------------------------------

# 4. Optimization Orchestrator Responsibilities

-   Interpret business intent
-   Select optimization capability
-   Gather governed data
-   Build objectives
-   Compile constraints
-   Execute scenarios
-   Validate recommendations
-   Explain decisions
-   Route for approval

------------------------------------------------------------------------

# 5. Common Optimization Interface

``` python
validate_request()
prepare_data()
build_model()
solve()
validate_solution()
run_sensitivity()
explain()
```

Every optimizer should implement this interface.

------------------------------------------------------------------------

# 6. Shared Contracts

## OptimizationRequest

-   Request ID
-   Domain
-   Portfolio
-   Objective
-   Constraints
-   Scenarios
-   Execution Mode
-   Requestor
-   Timestamp

## OptimizationResult

-   Objective value
-   Baseline value
-   Improvement
-   Allocations
-   Binding constraints
-   Sensitivities
-   Validation
-   Explanation

------------------------------------------------------------------------

# 7. Optimization Domains

## Collateral Optimization

Decision variables

-   Asset allocation
-   Substitutions
-   Counterparty allocation
-   Inventory usage

Objectives

-   Funding cost
-   Haircut cost
-   Liquidity
-   Turnover
-   Opportunity cost

Constraints

-   Eligibility
-   Haircuts
-   Concentration
-   Ratings
-   Maturity
-   Currency
-   Inventory

------------------------------------------------------------------------

## Money Market Optimization

Decision variables

-   Fund allocation
-   Cash balances
-   Rebalancing

Objectives

-   Yield
-   Liquidity
-   WAM/WAL
-   Expense ratio
-   Operational cost
-   Switching cost

Constraints

-   Daily liquidity
-   Weekly liquidity
-   Client mandates
-   Minimum trade size
-   Credit quality

------------------------------------------------------------------------

## Financing Optimization

Decision variables

-   Counterparty
-   Instrument
-   Rate
-   Tenor
-   Internal vs external funding

Objectives

-   Revenue
-   Funding spread
-   Capital usage
-   Liquidity
-   Recall cost
-   Fail cost

Constraints

-   Balance sheet
-   Inventory
-   Regulations
-   Counterparty limits

------------------------------------------------------------------------

# 8. Forecasting Layer

Forecasts provide optimizer inputs.

Examples:

-   Loan recall prediction
-   Borrow rate forecasting
-   Inventory demand forecasting
-   Settlement fail prediction
-   Redemption prediction
-   Liquidity forecasting

------------------------------------------------------------------------

# 9. Multi-Agent Architecture

Intent Agent

Determines user intent.

Planning Agent

Builds execution plan.

Constraint Agent

Compiles legal and business constraints.

Scenario Agent

Generates base, upside, downside, stress scenarios.

Validation Agent

Checks feasibility and policy compliance.

**Status:** ✅ deterministic structured validation engine implemented (POC).

`decision_intelligence/validation/` now builds a cross-domain
`ValidationReport` for orchestrated results. This complements optimizer-local
feasibility checks with platform-level readiness checks:

- solver status
- optimizer validation violations and warnings
- allocation presence
- allocation value and fraction bounds
- objective quality versus baseline
- scenario result health
- governance status
- explanation availability

The orchestrator attaches the report to `OptimizationResult.validation_report`
and mirrors its checks, warnings, and violations into the existing
`ValidationResult` contract. Recommendations are classified as `ready`,
`review`, or `blocked`, with a simple deterministic risk score for UI/API
consumers. The browser demo surfaces this through a "Validation / Readiness
checks" panel.

Explanation Agent

Produces natural-language rationale.

**Status:** ✅ first deterministic agent layer implemented (POC).

`decision_intelligence/agents/` now provides provider-agnostic contracts and
deterministic agents for the first agentic loop:

- `IntentAgent` classifies domain, action, scenario intent, confidence, and
  missing inputs from plain language.
- `PlanningAgent` converts intent plus collected fields into an `ExecutionPlan`
  with required inputs, missing fields, execution mode, solver options, and
  readiness state.
- `ScenarioAgent` suggests domain-relevant stress/downside/inventory scenarios.

The guided chat session now uses `ExecutionPlan.missing_fields` as its workflow
driver, exposes `intent`, `plan`, and `trace` in its browser/API snapshot, and
attaches `agent_trace` to completed API result payloads. The React demo shows an
"Agent Plan" card with missing inputs, readiness, scenario chips, plan-step
progress, and a compact "Agent Trace" card. This remains deterministic and
offline-safe; a future LLM-backed planning agent should emit the same contracts
rather than changing downstream orchestration.

------------------------------------------------------------------------

# 9a. LLM Provider Abstraction — ✅ IMPLEMENTED (POC)

**Status:** Implemented in `decision_intelligence/llm/`. The PDF intake agent
no longer imports a vendor SDK directly — all model access goes through a single
`LLMProvider` interface selected by configuration (`DI_LLM_PROVIDER`,
`DI_LLM_MODEL`, `DI_LLM_BASE_URL`, `DI_LLM_API_KEY`). Shipped providers:
`AnthropicProvider` (Claude, native PDF) and `OpenAIProvider` (OpenAI / Azure /
any OpenAI-compatible endpoint, **including local/offline models via
`DI_LLM_BASE_URL`** — Ollama, vLLM, llama.cpp). `register_provider()` allows
in-house/offline providers at runtime; with none configured, ingestion falls
back to the deterministic offline `heuristic` backend. Structured-output parity
is handled per provider (native schema decoding, else JSON-mode + Pydantic
validation). This is the single seam every future LLM agent (Intent, Planning,
Constraint, Scenario, Validation, Explanation) must reuse — none may import a
vendor SDK directly.

**Original rationale (retained):** the LLM layer had to become
**provider-agnostic and fully configurable** before the natural-language /
agent layer is built out, because every LLM-driven agent would otherwise
inherit a single-vendor lock-in.

**Requirement.** The platform must let each deployment choose whatever LLM
it has available, configured — not coded. No agent should import a specific
vendor SDK directly; all model access goes through one thin `LLMProvider`
interface.

Providers to support (selected by config, e.g. `LLM_PROVIDER` env var or a
`providers.yaml`):

-   **Anthropic** (Claude) — current default
-   **OpenAI** / Azure OpenAI
-   **Google** (Gemini / Vertex)
-   **AWS Bedrock** (multi-model)
-   **Local / offline models** — e.g. Ollama, llama.cpp, vLLM, or any
    OpenAI-compatible endpoint. This is a first-class requirement, not an
    afterthought: many deployments (regulated desks, air-gapped
    environments) cannot send documents or positions to a hosted API and
    must run a model entirely on-prem.

**Design constraints:**

-   A single `LLMProvider` protocol with two capabilities: (1) structured
    extraction against a Pydantic schema, and (2) free-text generation
    (for explanations). Providers implement these; agents depend only on
    the protocol.
-   Structured-output parity: where a provider lacks native schema-
    constrained decoding, the abstraction falls back to
    tool/function-calling or JSON-mode + validation, so callers always get
    a validated object.
-   Config-driven selection with per-agent overrides (e.g. a cheap local
    model for intent classification, a stronger hosted model for
    explanation) and graceful capability detection.
-   The existing deterministic `heuristic` (no-LLM) path must remain as the
    always-available offline fallback, independent of any provider.
-   Keys/endpoints via environment/secret config only; never hard-coded.

**Why high priority:** it de-risks vendor lock-in, unblocks on-prem /
air-gapped adoption, controls cost, and is far cheaper to introduce now
(one call site: the PDF intake agent) than after six agents each embed a
vendor SDK.

------------------------------------------------------------------------

# 10. Sequential Optimization

``` text
Demand Forecast
      ↓
Financing Optimizer
      ↓
Collateral Optimizer
      ↓
Cash Optimizer
      ↓
Liquidity Validation
      ↓
Recommendation
```

------------------------------------------------------------------------

# 11. Governance

-   Model registry
-   Prompt registry
-   Constraint registry
-   Data lineage
-   Audit logs
-   Versioning
-   Human approval
-   Reproducibility

------------------------------------------------------------------------

# 12. Human Approval Levels

  Tier   Capability                        Status
  ------ ------------------------------- ---------------
  0      Explain                          ✅ enforced
  1      Scenario analysis                ✅ enforced
  2      Recommendation                   ✅ enforced
  3      Stage transaction                ✅ enforced (approval-gated)
  4      Execute                          ✅ enforced (approval-gated)
  5      Change production constraints    ✅ enforced (approval-gated)

**Implemented (POC):** `governance/approvals.py` provides an `ApprovalPolicy`
(which tiers are gated + approver allowlist), an `ApprovalStore` (decisions
keyed by a stable action fingerprint), and a `GovernanceController` that the
orchestrator uses to enforce the tiers. Tiers 0–2 are auto-allowed; tiers 3–4
run the optimization but withhold the action until an authorized approver grants
it, at which point it is performed (`approved`) or refused (`rejected`). Every
transition is recorded in the append-only audit log, and each result carries an
immutable `ApprovalRecord`. Approvals can be supplied inline (one-shot) or via a
two-phase submit-then-rerun flow.

**Implemented (POC):** tier 5 is now represented by
`ExecutionMode.CHANGE_CONSTRAINTS` and is approval-gated by default. Governance
records also carry `base_tier`, `escalated`, `escalation_reason`, and
`governance_factors`, so downstream UI/API consumers can explain why a request
was gated. `ApprovalPolicy` supports configurable `ApprovalThreshold` rules
over context values such as notional, total funding need, or PnL-at-risk; these
rules can escalate advisory recommendations into gated approval tiers when the
materiality threshold is crossed. Requests that explicitly flag production
constraint changes are escalated to tier 5 even if the execution mode starts as
`recommendation`.

**UI/demo status (POC):** workflow templates now expose execution mode,
materiality notional, estimated PnL impact, and production-constraint-change
inputs in the browser demo. The workflow run payload carries those controls
into the API, where configured approval thresholds can escalate otherwise
advisory recommendations. The browser demo also includes a Governance Review
panel that shows selected mode, materiality, approval tier, escalation reason,
approval status, approval ID, and governance factors after a run. Dedicated
demo presets cover a normal non-escalated recommendation, a large-notional
approval review, and a Tier 5 production-constraint-change review.

**Approval workflow status (POC):** the demo API now keeps an in-memory
approval store across workflow reruns and exposes endpoints to list pending
approvals and submit approve/reject decisions by `approval_id`. The browser
Governance Review panel can submit decisions with approver/reason fields and
rerun the same workflow so pending approvals become approved or rejected in the
result governance record.

**Next:** real approver identity / SSO instead of a name string, durable
approval storage, and role/authority policies by approval tier.

------------------------------------------------------------------------

# 13. Explainability

Every optimization should answer:

1.  What changed?
2.  Why?
3.  Which constraints were binding?
4.  Economic improvement?
5.  Risks introduced?
6.  Alternative solutions?
7.  Sensitivities?

**Status:** ✅ deterministic structured explanation engine implemented (POC).

`decision_intelligence/explanation/` now builds an `ExplanationReport` for each
orchestrated optimization result. The report preserves the optimizer's original
narrative `explanation` string while adding structured sections for:

- what changed
- rationale
- economic impact
- binding constraints
- risks
- alternatives
- sensitivities
- scenario deltas
- governance status

The orchestrator attaches this report to `OptimizationResult.explanation_report`
after scenario analysis and governance evaluation, so API responses and the
browser demo can render the same deterministic explanation structure. This is
the foundation for a future LLM-backed Explanation Agent: the LLM should polish
or tailor these structured facts, not invent the decision logic.

------------------------------------------------------------------------

# 14. Suggested Repository

``` text
decision-intelligence-platform/
├── orchestrator/
├── agents/
├── optimizers/
│   ├── collateral/
│   ├── money_market/
│   ├── financing/
│   ├── cash/
│   ├── margin/
│   └── hedging/
├── forecasting/
├── governance/
├── evaluation/
├── contracts/
├── data/
├── api/
└── ui/
```

------------------------------------------------------------------------

# 15. Delivery Roadmap

## Phase 1

-   Standardize optimization APIs
-   Build contracts
-   Registry
-   Baseline testing

## Phase 2

-   Deterministic orchestrator

## Phase 3

-   Natural-language interface
-   ✅ **LLM provider abstraction** — provider-agnostic, configurable model
    access incl. offline/on-prem models (see §9a). Implemented; reuse this
    seam as the multi-agent layer expands.

## Phase 4

-   Explainability
-   Sensitivity analysis

## Phase 5

-   ✅ **Sequential Workflow Engine (POC)** — deterministic
    `WorkflowPlan`/`WorkflowStep` contracts, ordered execution through the
    existing orchestrator, workflow trace, aggregate validation summary, and a
    browser-facing `/api/workflows/run` endpoint.
-   ✅ **Liquidity Stress Funding Workflow (POC)** — chains financing,
    collateral, and money-market optimizers under a shared stress context.
-   ✅ **Cross-Step Dependency Engine (POC)** — upstream financing and
    collateral pressure now deterministically adjust downstream money-market
    liquidity requirements, with auditable `DependencyEffect` records.
-   ✅ **Workflow Registry (POC)** — workflow templates are now discoverable
    through a central registry and browser-facing `GET /api/workflows` catalog.
-   ✅ **Workflow Templates + Selector (POC)** — added Funding Capacity Shock
    and Collateral Liquidity Review templates, surfaced through the browser
    workflow selector.
-   ✅ **Workflow Explanation Report (POC)** — workflow results now include a
    top-level `explanation_report` summarizing recommendation, drivers,
    dependency changes, risks, economic impact, and next actions.
-   ✅ **Workflow Template Configs (POC)** — registered demo workflows now have
    YAML definitions under `config/workflows`, plus a validated config loader
    for metadata, defaults, steps, dependencies, and inputs.
-   ✅ **Config-Backed Registry Metadata (POC)** — the default workflow
    registry now hydrates names, descriptions, domains, tags, and default
    context from `config/workflows` while retaining Python builder mappings.
-   ✅ **Config Inputs in Workflow Catalog (POC)** — `GET /api/workflows` now
    exposes config `version` and user-facing `inputs` for every registered
    workflow template.
-   ✅ **Demo Presets (POC)** — repeatable stakeholder walkthroughs are now
    packaged in `config/demo_presets`, exposed through `GET /api/demo-presets`,
    and selectable in the browser demo before executing a workflow.
-   ✅ **Editable Workflow Inputs (POC)** — the browser demo now renders
    workflow catalog `inputs` as editable preset fields, prefills them from the
    selected demo preset, and compiles edits into the workflow run payload.
-   ✅ **Presenter Guardrails (POC)** — editable preset inputs now validate
    required fields, numeric formats, sensible ranges, and workflow-specific
    stress consistency before execution. The browser demo opens a presenter
    review panel showing Ready/Review/Blocked status, changed fields, selected
    context, warnings, and a final Run Demo action.
-   ✅ **Local Run History + Replay (POC)** — completed workflow demos are now
    persisted in browser `localStorage` with preset, workflow, inputs, payload,
    result, timestamp, and validation status. The browser demo can restore a
    prior result or replay the exact stored payload.
-   ✅ **Shareable Demo Export Packages (POC)** — `/api/workflows/export-package`
    now generates a self-contained HTML stakeholder package from a workflow run,
    preset, payload, and workflow catalog item. The browser demo exposes this as
    **Export Package** after a sequential workflow completes.
-   ✅ **One-Command Local Demo Startup (POC)** — `make demo-ui` now launches the
    local FastAPI backend and React/Vite frontend together through
    `scripts/run_demo_ui.sh`, with cleanup on exit.
-   ✅ **Asset Allocation MVO Browser Workflow (POC)** — the
    `portfolio_rebalance_mvo` workflow template and `balanced_mvo_rebalance`
    demo preset now surface the Asset Allocation MVO optimizer in the browser
    workflow selector with editable inputs for notional, target return,
    risk-aversion, single-asset cap, and cash floor.
-   ✅ **Workflow Visual Comparison (POC)** — workflow results now include a
    generic `visual_summary` with step-level objective impact, validation
    posture, dependency counts, allocation counts, and optional risk/return
    points when available. The browser demo renders this for every workflow,
    with an MVO risk/return plot as a special case instead of a one-off view.
-   ✅ **Scenario Side-by-Side Comparison (POC)** — saved/replayed workflow
    results can now be submitted to `/api/workflows/compare` to produce a
    deterministic comparison summary, baseline deltas, best-run marker,
    validation burden, dependency-effect counts, and risk/return metrics where
    available. The browser demo uses local run history to surface base vs stress
    vs replayed scenarios in the workflow comparison panel.
-   Next: add named comparison sets and export the comparison table inside the
    evidence PDF/package.

## Phase 6

-   Event-driven autonomous recommendations

------------------------------------------------------------------------

# 15b. Orchestration Expansion Opportunities

Six high-leverage areas where the existing orchestration infrastructure
can be extended to materially increase platform value. Each opportunity
is grounded in already-built components; no new architectural layer is
required.

---

## 1. Multi-Domain Workflow Chaining via Chat

**What:** Surface the existing `WorkflowLibrary` workflows through the
conversational interface. Today `ChatSession.reply()` routes only to
single-domain optimizers; `library.py` already defines cross-domain
chains (financing → collateral → money market) but they are unreachable
from chat.

**How:** Add a `multi_domain_workflow` `AgentAction` type in
`IntentAgent`. Add a routing branch in `ChatSession.reply()` that calls
`WorkflowRunner` and streams `WorkflowStepResult` events back into the
chat trace. The `CrossStepDependencyEngine` propagates upstream results
automatically — no solver changes needed.

**Key files:** `src/decision_intelligence/chat/engine.py` ·
`src/decision_intelligence/agents/intent.py` ·
`src/decision_intelligence/workflows/library.py` ·
`src/decision_intelligence/workflows/runner.py`

**Value:** A user can type "run the full liquidity stress funding
workflow" and get a three-step sequenced optimization with dependency
propagation, all in one chat turn.

**Status:** ✅ **POC implemented** — `IntentAgent` now recognizes
registered multi-domain workflow requests, `ChatSession` can compile a
`WorkflowPlan` directly from a chat prompt, the chat API executes that
plan through `SequentialWorkflowRunner`, and the browser UI routes the
returned `workflow_result` into the same sequential workflow timeline
used by manual demos.

**Next:** add field-by-field chat collection for workflow template
inputs, plus optional streaming/progressive step events while the
runner executes each optimizer.

---

## 2. Constraint Negotiation / Inversion

**What:** Let the orchestrator answer "I need X additional bps — which
constraints could I relax, and by how much?" The `ExplanationEngine`
already computes shadow prices (dual values) for every binding
constraint; an inversion agent reads those and proposes a ranked menu of
relaxations.

**How:** Add a `ConstraintNegotiationAgent` that accepts a target
improvement (e.g. +15 bps), reads `ExplanationEngine.sensitivities`,
and returns combinations of constraint relaxations ordered by
governance impact. Integrate with `GovernanceController` so each
proposal is tagged with the approval tier it would require.

**Key files:** `src/decision_intelligence/explanation/engine.py` ·
`src/decision_intelligence/governance/approvals.py`

**Value:** Transforms the platform from "here is the constrained
optimum" to "here is what you would need to change to close the gap" —
a direct decision-support capability for portfolio managers and
treasurers.

**Status:** ✅ **Constraint Negotiation / Inversion (POC implemented)** — the
platform now exposes `/api/constraints/negotiate`, which accepts a completed
optimizer result, reads sensitivities and binding constraints, and returns a
ranked set of relaxation proposals with estimated impact, rationale, source
evidence, confidence, and required governance tier. The first deterministic
rule set covers money-market liquidity/concentration limits, financing capacity
constraints, collateral requirements, and MVO risk/return controls.

**Next:** wire this into the browser as a "What would need to change?" action,
then add re-solve-backed proposal bundles that test combinations of relaxations
against a requested bps or utility target.

---

## 3. Governance Escalation Orchestration

**What:** The `GovernanceController` defines six execution tiers
(`explain=0` through `change_constraints=5`) but the current UI only
reaches `recommendation` (tier 2). An orchestration layer should
automatically route proposed actions to the correct tier based on
materiality and magnitude, and manage the two-phase approval flow for
higher tiers.

**How:** Add a `GovernanceOrchestrator` that inspects the
`ExecutionPlan` magnitude, domain, and governance policy to determine
the required tier; surfaces a staged approval prompt to the relevant
approver role; and advances to `stage` or `execute` tiers only after
sign-off is recorded in `ApprovalStore`.

**Key files:** `src/decision_intelligence/governance/approvals.py` ·
`src/decision_intelligence/governance/audit.py`

**Value:** Completes the governance loop. The platform can be safely
handed to execution teams — not just analysts — because material trades
cannot bypass the approval chain.

---

## 4. IPS / Document Ingestion Agent

**What:** Replace the placeholder "Upload IPS" button in the frontend
with a real agent that extracts constraint parameters from Investment
Policy Statement PDFs and populates `WorkflowSpec` fields directly.

**How:** Add an `IPSIngestionAgent` that accepts a document (PDF or
text), uses an LLM via `LLMProvider` to extract structured constraint
data (concentration limits, WAM caps, credit quality minimums, liquidity
floors), and writes them into the constraint schema. Surface the
extracted fields for human review before they are applied.

**Key files:** `src/decision_intelligence/llm/provider.py` ·
`src/decision_intelligence/workflows/types.py`

**Value:** Eliminates manual re-keying of policy documents. A new
mandate can be onboarded in minutes instead of days, with an auditable
extraction trace.

**Status:** ✅ **Policy Ingestion Agent (POC implemented)** — the API now
exposes `/api/policy/ingest`, which accepts pasted policy/IPS text or a base64
PDF payload, extracts workflow-ready input values, returns evidence snippets and
confidence scores for presenter review, and emits a nested `context_patch` that
can be applied to registered workflow templates before execution. The first
deterministic extraction map covers liquidity stress funding, funding capacity,
collateral liquidity review, and portfolio rebalance MVO workflows.

**Next:** wire the browser "Upload IPS" affordance to this endpoint, add
LLM-assisted extraction behind the same response contract for less formulaic
policy language, and persist the reviewed extraction into the run evidence
packet.

---

## 5. Portfolio Drift Monitoring + Proactive Re-triggering

**What:** Use the `AuditLog` and the pre-trade analytics metrics already
displayed in the frontend to run scheduled monitoring. When a portfolio
drifts past a configurable threshold (e.g. a holding crosses 90% of its
concentration cap, or yield gap widens beyond a threshold), the
orchestrator proactively surfaces a re-optimization recommendation.

**How:** Add a `DriftMonitor` that compares current portfolio state
against the last audit snapshot, computes metric deltas, and emits an
`AgentTraceEvent` of type `proactive_alert` when a threshold is crossed.
Wire this to the `ChatSession` so the alert appears as an unsolicited
orchestrator message, with a one-click path to trigger re-optimization.

**Key files:** `src/decision_intelligence/governance/audit.py` ·
`frontend/prototype/index.html` (pre-trade panel) ·
`src/decision_intelligence/agents/tracing.py`

**Value:** Moves the platform from reactive (user asks) to proactive
(orchestrator alerts). Directly addresses the "portfolio drift goes
unnoticed until end-of-day" risk.

---

## 6. Audit Narrative Generation

**What:** Convert the append-only `AgentTraceEvent` /
`WorkflowTraceEvent` logs into compliance-readable prose narratives on
demand. Today the audit log is structured data; compliance teams need
human-readable summaries of what was decided, why, and who approved it.

**How:** Add an `AuditNarrativeAgent` that accepts a session or workflow
ID, reads all trace events from `AuditLog`, and uses `LLMProvider` to
generate a structured narrative (decision summary, constraint context,
approval chain, outcome, risk flags). Output formats: PDF-ready markdown
and JSON for downstream systems.

**Key files:** `src/decision_intelligence/governance/audit.py` ·
`src/decision_intelligence/llm/provider.py` ·
`src/decision_intelligence/explanation/engine.py`

**Value:** Closes the regulatory reporting loop. A compliance officer
can pull a plain-English account of any optimization decision with full
provenance, without reading raw event logs.

**Status:** ✅ **Audit Narrative Generation (POC implemented)** — workflow API
responses can now be submitted to `/api/audit/narrative` to produce a
deterministic compliance-readable narrative with decision summary, constraint
context, approval chain, risk flags, timeline, outcome, markdown, and structured
JSON provenance. The generator uses existing workflow traces, validation
summary, dependency effects, explanation report, and governance records.

**Next:** add an LLMProvider polishing option behind the same schema, persist
narratives by workflow/session ID, and include the markdown section in evidence
PDF/package exports.

------------------------------------------------------------------------

# 16. Initial Backlog

1.  OptimizationRequest schema
2.  Constraint schema
3.  Objective compiler
4.  Optimizer registry
5.  Collateral wrapper
6.  Money market wrapper
7.  Financing wrapper
8.  Scenario engine
9.  ✅ Validation engine — deterministic cross-domain readiness checks (POC)
10. Explanation engine
11. ✅ **LLMProvider abstraction** — vendor-agnostic, config-driven,
    offline-capable model access (see §9a) — implemented

------------------------------------------------------------------------

# 17. Long-Term Vision

A governed operating system for optimization where new capabilities can
be registered without redesigning the platform.

Future optimizers include:

-   Treasury optimization
-   FX optimization
-   Repo optimization
-   Securities lending optimization
-   Margin optimization
-   Capital optimization
-   Cross-product optimization

The orchestrator coordinates all capabilities while preserving
governance, auditability, explainability, and mathematical correctness.
