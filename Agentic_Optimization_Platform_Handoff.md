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

Explanation Agent

Produces natural-language rationale.

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
  5      Change production constraints    ⬜ not yet

**Implemented (POC):** `governance/approvals.py` provides an `ApprovalPolicy`
(which tiers are gated + approver allowlist), an `ApprovalStore` (decisions
keyed by a stable action fingerprint), and a `GovernanceController` that the
orchestrator uses to enforce the tiers. Tiers 0–2 are auto-allowed; tiers 3–4
run the optimization but withhold the action until an authorized approver grants
it, at which point it is performed (`approved`) or refused (`rejected`). Every
transition is recorded in the append-only audit log, and each result carries an
immutable `ApprovalRecord`. Approvals can be supplied inline (one-shot) or via a
two-phase submit-then-rerun flow.

**Next:** tier 5 (production-constraint changes), notional/PnL-threshold policies
that escalate approval level by transaction size, and real approver identity /
SSO instead of a name string.

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

-   Multi-optimizer workflows

## Phase 6

-   Event-driven autonomous recommendations

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
9.  Validation engine
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
