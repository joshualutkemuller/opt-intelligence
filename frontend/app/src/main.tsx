import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "../../prototype/styles.css";

const API_BASE = "http://127.0.0.1:8000";

type Role = "assistant" | "user";

type Message = {
  role: Role;
  content: string;
  pending?: boolean;
};

type WorkflowState = {
  domain: string | null;
  title: string | null;
  collected: Record<string, unknown>;
  next_field: string | null;
  awaiting_confirmation: boolean;
  intent?: AgentIntent | null;
  plan?: ExecutionPlan | null;
  trace?: AgentTraceEvent[];
};

type AgentIntent = {
  action: string;
  domain: string | null;
  confidence: number;
  scenarios: string[];
  missing_inputs: string[];
  signals: string[];
};

type ExecutionPlan = {
  title: string;
  action: string;
  execution_mode: string;
  summary: string;
  missing_fields: string[];
  required_fields: Array<{ key: string; label: string }>;
  scenario_names: string[];
  scenario_suggestions: Array<{ name: string; reason: string; selected: boolean }>;
  steps: Array<{ name: string; description: string; status: string }>;
  ready_to_run: boolean;
};

type AgentTraceEvent = {
  event: string;
  message: string;
  details: Record<string, unknown>;
};

type Allocation = {
  label: string;
  allocated_value: number;
  allocated_fraction: number;
  metadata: Record<string, unknown>;
};

type Sensitivity = {
  parameter: string;
  shadow_price: number;
  interpretation: string;
};

type ExplanationReport = {
  summary: string;
  what_changed: string[];
  rationale: string[];
  economic_impact: Record<string, unknown>;
  binding_constraints: string[];
  risks: string[];
  alternatives: string[];
  sensitivities: string[];
  scenarios: Record<string, unknown>[];
  governance: string | null;
  source_explanation: string;
};

type ValidationCheck = {
  name: string;
  status: "pass" | "warning" | "fail";
  severity: "info" | "warning" | "error";
  message: string;
  details: Record<string, unknown>;
};

type ValidationReport = {
  passed: boolean;
  recommendation: "ready" | "review" | "blocked";
  risk_score: number;
  checks: ValidationCheck[];
  violations: string[];
  warnings: string[];
  data_quality: Record<string, unknown>;
  policy_status: string | null;
};

type ApprovalRecord = {
  request_id: string;
  execution_mode: string;
  tier: number;
  action: string;
  required: boolean;
  status: string;
  action_performed: boolean;
  approval_id: string | null;
  approver: string | null;
  reason: string;
  base_tier: number | null;
  escalated: boolean;
  escalation_reason: string;
  governance_factors: Record<string, string | number | boolean>;
  decided_at: string | null;
};

type OptimizationResult = {
  domain?: string;
  status: string;
  objective_value: number;
  baseline_value: number;
  improvement: number;
  improvement_pct: number;
  allocations: Allocation[];
  sensitivities: Sensitivity[];
  binding_constraints: string[];
  validation_report?: ValidationReport | null;
  explanation_report?: ExplanationReport | null;
  governance?: ApprovalRecord | null;
  solver_metadata: Record<string, unknown>;
  agent_trace?: AgentTraceEvent[];
};

type WorkflowSummary = {
  status: string;
  objective_value: number;
  baseline_value: number;
  improvement: number;
  improvement_pct: number;
  allocation_count: number;
  validation_recommendation: string | null;
  validation_passed: boolean;
  warning_count: number;
  violation_count: number;
};

type WorkflowStepResult = {
  step_id: string;
  domain: string;
  name: string;
  status: string;
  request: Record<string, unknown>;
  result: OptimizationResult;
  inputs_from: string[];
  dependency_effects: DependencyEffect[];
  summary: WorkflowSummary;
};

type DependencyEffect = {
  rule_type: string;
  source_step_id: string;
  target_step_id: string;
  target_context_key: string;
  previous_value: number;
  new_value: number;
  delta: number;
  reason: string;
  details: Record<string, unknown>;
};

type WorkflowTraceEvent = {
  event: string;
  message: string;
  step_id: string | null;
  domain: string | null;
  details: Record<string, unknown>;
  timestamp: string;
};

type WorkflowValidationSummary = {
  passed: boolean;
  total_steps: number;
  total_checks: number;
  warning_count: number;
  violation_count: number;
  warnings: string[];
  violations: string[];
  recommendations: Record<string, string>;
};

type WorkflowVisualPoint = {
  step_id: string;
  name: string;
  domain: string;
  status: string;
  objective_value: number;
  baseline_value: number;
  improvement: number;
  improvement_pct: number;
  allocation_count: number;
  warning_count: number;
  violation_count: number;
  validation_recommendation: string | null;
  expected_return: number | null;
  volatility: number | null;
  sharpe: number | null;
};

type WorkflowVisualSummary = {
  chart_kind: "improvement_bar" | "risk_return";
  points: WorkflowVisualPoint[];
  best_step_id: string | null;
  average_improvement_pct: number;
  total_dependency_effects: number;
  total_warnings: number;
  total_violations: number;
  has_risk_return_points: boolean;
};

type WorkflowRunResult = {
  workflow_id: string;
  name: string;
  status: "complete" | "partial" | "error";
  step_results: WorkflowStepResult[];
  validation_summary: WorkflowValidationSummary;
  dependency_summary: {
    total_effects: number;
    target_steps: string[];
    source_steps: string[];
    context_changes: DependencyEffect[];
  };
  visual_summary: WorkflowVisualSummary;
  explanation: string;
  explanation_report: WorkflowExplanationReport | null;
  trace: WorkflowTraceEvent[];
  timestamp: string;
};

type WorkflowExplanationReport = {
  summary: string;
  overall_recommendation: string;
  key_drivers: string[];
  dependency_changes: string[];
  economic_impact: Record<string, unknown>;
  risks: string[];
  next_actions: string[];
  step_summaries: Array<Record<string, unknown>>;
};

type WorkflowRunApiResponse = {
  plan: {
    workflow_id: string;
    name: string;
    description: string;
    context?: Record<string, unknown>;
    steps: Array<{
      step_id: string;
      domain: string;
      name: string;
      description: string;
      depends_on: string[];
    }>;
  };
  result: WorkflowRunResult;
};

type WorkflowScenarioComparisonRun = {
  run_id: string;
  label: string;
  workflow_id: string;
  status: string;
  timestamp: string | null;
  step_count: number;
  final_domain: string | null;
  final_objective_value: number;
  final_improvement_pct: number;
  average_improvement_pct: number;
  total_dependency_effects: number;
  warning_count: number;
  violation_count: number;
  validation_passed: boolean;
  expected_return: number | null;
  volatility: number | null;
  sharpe: number | null;
  deltas: Record<string, number>;
};

type WorkflowScenarioComparison = {
  baseline_run_id: string | null;
  best_run_id: string | null;
  run_count: number;
  comparison_ready: boolean;
  runs: WorkflowScenarioComparisonRun[];
  insights: string[];
};

type WorkflowScenarioCompareApiResponse = {
  comparison: WorkflowScenarioComparison;
};

type WorkflowExportPackageApiResponse = {
  filename: string;
  content_type: string;
  html: string;
};

type WorkflowEvidenceExportApiResponse = {
  json_filename: string;
  json_content_type: string;
  json_payload: Record<string, unknown>;
  pdf_filename: string;
  pdf_content_type: string;
  pdf_base64: string;
  csv_files: Array<{ filename: string; content_type: string; content: string }>;
  xlsx_filename: string;
  xlsx_content_type: string;
  xlsx_base64: string;
};

type PolicyExtractedField = {
  key: string;
  label: string;
  value: string | number | boolean | null;
  confidence: number;
  evidence: string;
  applied: boolean;
};

type PolicyIngestionResponse = {
  workflow_id: string;
  source_type: string;
  input_values: Record<string, string>;
  context_patch: Record<string, unknown>;
  extracted_fields: PolicyExtractedField[];
  review_summary: Record<string, unknown>;
};

type WorkflowCatalogItem = {
  workflow_id: string;
  version: number;
  name: string;
  description: string;
  domains: string[];
  tags: string[];
  default_context: Record<string, unknown>;
  inputs: WorkflowInputSpec[];
};

type WorkflowInputSpec = {
  key: string;
  label: string;
  type: string;
  default: unknown;
  required: boolean;
  options?: string[];
};

type WorkflowCatalogApiResponse = {
  workflows: WorkflowCatalogItem[];
};

type DemoPresetCatalogItem = {
  preset_id: string;
  version: number;
  name: string;
  description: string;
  audience: string;
  workflow_id: string;
  portfolio_id: string;
  seed: number;
  duration_minutes: number;
  context: Record<string, unknown>;
  talking_points: string[];
  success_criteria: string[];
};

type DemoPresetCatalogApiResponse = {
  presets: DemoPresetCatalogItem[];
};

type DemoDataPacketCatalogItem = {
  packet_id: string;
  version: number;
  name: string;
  description: string;
  audience: string;
  workflow_id: string;
  preset_id: string;
  source_type: string;
  domains: string[];
  files: Record<string, string>;
  talking_points: string[];
  success_criteria: string[];
};

type DemoDataPacketCatalogApiResponse = {
  packets: DemoDataPacketCatalogItem[];
};

type ProductionOptimizerCatalogItem = {
  optimizer_id: string;
  domain: string;
  model_name: string;
  model_version: string;
  config_version: string;
  objectives: Array<Record<string, unknown>>;
  constraints: Array<Record<string, unknown>>;
  data_contract: {
    required_datasets?: string[];
    optional_datasets?: string[];
    quality_checks?: string[];
    snapshot_required?: boolean;
  };
  solver: {
    backend?: string;
    problem_family?: string;
    vendor?: string;
    version?: string;
    parameters?: Record<string, unknown>;
  };
  execution: {
    mode?: string;
    timeout_seconds?: number;
    resource_profile?: string;
  };
};

type ProductionOptimizerCatalogApiResponse = {
  optimizers: ProductionOptimizerCatalogItem[];
};

type PresenterStatus = "ready" | "review" | "blocked";

type PresenterIssue = {
  severity: "warning" | "error";
  field: string;
  message: string;
};

type PresenterChange = {
  key: string;
  label: string;
  from: string;
  to: string;
};

type PresenterReview = {
  status: PresenterStatus;
  issues: PresenterIssue[];
  changes: PresenterChange[];
};

type WorkflowRunPayload = {
  workflow: string;
  portfolio_id: string;
  seed: number;
  execution_mode?: string;
  optimizer_runtime?: "phase1" | "production";
  production_optimizer_id?: string;
  context: Record<string, unknown>;
  policy_ingestion?: PolicyIngestionResponse | null;
};

type RunHistoryEntry = {
  id: string;
  created_at: string;
  preset_id: string;
  preset_name: string;
  workflow_id: string;
  workflow_name: string;
  portfolio_id: string;
  seed: number;
  solver: string;
  input_values: Record<string, string>;
  payload: WorkflowRunPayload;
  response: WorkflowRunApiResponse;
  status: string;
  validation_passed: boolean;
};

type ComparisonSet = {
  id: string;
  name: string;
  created_at: string;
  run_ids: string[];
};

type PresenterScriptAction = "load" | "review" | "run" | "export" | "none";

type PresenterScriptStep = {
  title: string;
  cue: string;
  proof: string;
  action: PresenterScriptAction;
  actionLabel: string;
};

type CollateralScenario = {
  id: string;
  name: string;
  description: string;
  inputs: Record<string, string>;
  before: {
    dailyLiquidity: number;
    weeklyLiquidity: number;
    level1: number;
    reusableValue: number;
    concentrationUsage: number;
    coverageBuffer: number;
    fundingCostBps: number;
  };
  after: {
    dailyLiquidity: number;
    weeklyLiquidity: number;
    level1: number;
    reusableValue: number;
    concentrationUsage: number;
    coverageBuffer: number;
    fundingCostBps: number;
  };
};

type ChatApiResponse = {
  session_id: string;
  assistant_message: string;
  state: WorkflowState;
  trace: AgentTraceEvent[];
  result: OptimizationResult | null;
  request: Record<string, unknown> | null;
  workflow_plan: WorkflowRunApiResponse["plan"] | null;
  workflow_result: WorkflowRunResult | null;
};

type ApprovalDecisionApiResponse = {
  approval_id: string;
  fingerprint: string;
  status: "approved" | "rejected";
  approver: string;
  reason: string;
};

type LlmChatApiResponse = {
  provider: string;
  model: string;
  base_url: string | null;
  response: string;
};

const defaultMessages: Message[] = [
  {
    role: "assistant",
    content:
      "Start with a business request like: I want to optimize money market cash.",
  },
];

const RUN_HISTORY_KEY = "decision-intelligence.workflowRunHistory.v1";
const COMPARISON_SETS_KEY = "decision-intelligence.comparisonSets.v1";
const MAX_RUN_HISTORY = 12;
const MAX_COMPARISON_SETS = 8;
const VIDEO_DEMO_PRESET_ID = "institutional_csv_liquidity_stress";
const COLLATERAL_HQLA_PRESET_ID = "collateral_hqla_schedule_stress";
const MONEY_MARKET_POLICY_PRESET_ID = "treasury_mmf_policy_optimization";
const TREASURY_CASH_MOVEMENT_PRESET_ID = "treasury_cash_movement_cutoff";
const MARGIN_CALL_PRESET_ID = "margin_call_capacity_triage";
const COLLATERAL_SCHEDULE_SAMPLE = `Collateral Schedule - Counterparty Stress Addendum

Mandate: Collateral and cash review for Portfolio PORT_HQLA_224.

Margin call scale is 185%. Obligations include Dealer A Bilateral CSA, Dealer B Bilateral CSA, Dealer C Bilateral CSA, LCH SwapClear cleared swaps initial margin, and CME Futures Exchange variation margin. Total cash balance is $420 million. Daily liquidity must be at least 35%. Weekly liquidity minimum 65%.

Prime fund exposure must not exceed 30%. Weighted average maturity must stay under 50 days. Single-fund limit may not exceed 45%.

Eligible collateral and haircuts: US Treasury 2%, Agency MBS 6%, IG Corporate Bonds 12%, Equity ETF 22%, Cash 0%. No single collateral asset class may exceed 48% of posted value.

Governance: Materiality notional is $420 million. Any policy override must be reviewed by treasury governance before execution.`;
const MONEY_MARKET_POLICY_SAMPLE = `Money Market Portfolio Review - Treasury Mandate

Mandate: Optimize the treasury liquidity sleeve for Portfolio PORT_MMF_901.

Current portfolio: Total investable cash balance is $625 million. The current allocation is overweight a small number of government and prime money-market funds and should be reviewed against liquidity and concentration controls.

Investment requirements: Daily liquidity must be at least 32%. Weekly liquidity minimum 68%. Prime fund exposure must not exceed 35%. Weighted average maturity must stay under 50 days. Single-fund exposure must not exceed 40% of total cash.

Optimization goal: maximize net 7-day annualized yield while satisfying liquidity, WAM, prime exposure, and concentration requirements. Use recommendation mode only.

Governance: Materiality notional is $625 million. Estimated PnL impact is $0. This is not a production constraint change.`;

const pocPresenterScript: PresenterScriptStep[] = [
  {
    title: "Load the proof path",
    cue: "Start by selecting the institutional CSV preset and show the data packet panel.",
    proof: "The demo is file-backed: three domains, six CSVs, and a deterministic preset.",
    action: "load",
    actionLabel: "Load POC Path",
  },
  {
    title: "Review before running",
    cue: "Open presenter review and call out portfolio, seed, execution mode, and guardrails.",
    proof: "The run is controlled, repeatable, and blocked if inputs violate demo guardrails.",
    action: "review",
    actionLabel: "Open Review",
  },
  {
    title: "Run the workflow",
    cue: "Run financing, collateral, then money-market allocation without changing screens.",
    proof: "Upstream stress propagates into downstream liquidity requirements before MILP solve.",
    action: "run",
    actionLabel: "Run Workflow",
  },
  {
    title: "Export evidence",
    cue: "Download the evidence packet immediately after the workflow completes.",
    proof: "The packet contains inputs, solver metadata, allocations, dependency effects, and validation.",
    action: "export",
    actionLabel: "Export Evidence",
  },
  {
    title: "Close the story",
    cue: "End by naming the architecture: agent intake, deterministic optimizers, solver layer, governance, and workflow orchestration.",
    proof: "The output is repeatable, explainable, and ready to review.",
    action: "none",
    actionLabel: "Ready",
  },
];

const fallbackWorkflowCatalog: WorkflowCatalogItem[] = [
  {
    workflow_id: "treasury_cash_movement",
    name: "Treasury Cash Movement",
    description:
      "Routes operational cash to clearing and settlement requirements through open payment rails.",
    domains: ["treasury_operations"],
    tags: ["treasury", "operations", "cash-movement", "payments", "production-adapter"],
    version: 1,
    default_context: {
      scenario: "treasury_cash_movement",
      optimizer_runtime: "production",
      production_optimizer_id: "production.treasury.cash_movement",
    },
    inputs: [
      { key: "portfolio_id", label: "Portfolio ID", type: "string", default: "PORT_TREASURY_OPS", required: true },
      { key: "seed", label: "Simulation seed", type: "integer", default: 42, required: true },
      {
        key: "treasury_operations.cutoff_hour",
        label: "Payment cutoff hour",
        type: "number",
        default: 15,
        required: true,
      },
      {
        key: "treasury_operations.stress_multiplier",
        label: "Funding stress multiplier",
        type: "fraction",
        default: 1.0,
        required: true,
      },
      {
        key: "treasury_operations.liquidity_buffer_pct",
        label: "Liquidity buffer",
        type: "fraction",
        default: 0.05,
        required: true,
      },
    ],
  },
  {
    workflow_id: "margin_call_workflow",
    name: "Margin Call Workflow",
    description:
      "Prioritizes a margin-call operations queue by exposure, SLA urgency, dispute risk, and team capacity.",
    domains: ["margin_operations"],
    tags: ["margin", "operations", "workflow", "sla", "production-adapter"],
    version: 1,
    default_context: {
      scenario: "margin_call_workflow",
      optimizer_runtime: "production",
      production_optimizer_id: "production.margin_call.workflow",
    },
    inputs: [
      { key: "portfolio_id", label: "Portfolio ID", type: "string", default: "PORT_MARGIN_OPS", required: true },
      { key: "seed", label: "Simulation seed", type: "integer", default: 42, required: true },
      {
        key: "margin_operations.team_capacity_minutes",
        label: "Team capacity minutes",
        type: "integer",
        default: 150,
        required: true,
      },
      {
        key: "margin_operations.materiality_threshold",
        label: "Materiality threshold",
        type: "currency",
        default: 25_000_000,
        required: true,
      },
      {
        key: "margin_operations.dispute_stress_multiplier",
        label: "Dispute stress multiplier",
        type: "fraction",
        default: 1.0,
        required: true,
      },
    ],
  },
  {
    workflow_id: "money_market_policy_optimization",
    name: "Money Market Policy Optimization",
    description:
      "Runs a one-step money-market optimizer from an ingested cash policy or portfolio review document.",
    domains: ["money_market"],
    tags: ["money-market", "liquidity", "policy", "pdf", "demo"],
    version: 1,
    default_context: { scenario: "money_market_policy", solver_backend: "scipy", problem_type: "lp" },
    inputs: [
      { key: "portfolio_id", label: "Portfolio ID", type: "string", default: "PORT_MMF_901", required: true },
      { key: "seed", label: "Simulation seed", type: "integer", default: 53, required: true },
      {
        key: "money_market.total_cash",
        label: "Total cash",
        type: "currency",
        default: 625_000_000,
        required: true,
      },
      {
        key: "money_market.daily_liquidity_req",
        label: "Daily liquidity floor",
        type: "fraction",
        default: 0.32,
        required: true,
      },
      {
        key: "money_market.weekly_liquidity_req",
        label: "Weekly liquidity floor",
        type: "fraction",
        default: 0.68,
        required: true,
      },
      {
        key: "money_market.max_prime_fraction",
        label: "Prime fund cap",
        type: "fraction",
        default: 0.35,
        required: true,
      },
      {
        key: "money_market.max_wam_days",
        label: "Max WAM days",
        type: "integer",
        default: 50,
        required: true,
      },
      {
        key: "money_market.max_single_fund",
        label: "Single fund cap",
        type: "fraction",
        default: 0.40,
        required: true,
      },
      {
        key: "execution_mode",
        label: "Execution mode",
        type: "select",
        default: "recommendation",
        required: true,
        options: ["recommendation", "stage", "execute", "change_constraints"],
      },
      {
        key: "governance.materiality_notional",
        label: "Materiality notional",
        type: "currency",
        default: 625_000_000,
        required: true,
      },
      {
        key: "governance.estimated_pnl_impact",
        label: "Estimated PnL impact",
        type: "currency",
        default: 0,
        required: true,
      },
      {
        key: "governance.production_constraint_change",
        label: "Production constraint change",
        type: "boolean",
        default: false,
        required: true,
      },
    ],
  },
  {
    workflow_id: "portfolio_rebalance_mvo",
    name: "Portfolio Rebalance MVO",
    description:
      "Runs a constrained mean-variance optimizer for a multi-asset portfolio rebalance.",
    domains: ["asset_allocation"],
    tags: ["asset-allocation", "mvo", "portfolio", "rebalance", "demo"],
    version: 1,
    default_context: { scenario: "mvo_rebalance", solver_backend: "scipy", problem_type: "qp" },
    inputs: [
      { key: "portfolio_id", label: "Portfolio ID", type: "string", default: "PORT_MVO_001", required: true },
      { key: "seed", label: "Simulation seed", type: "integer", default: 42, required: true },
      {
        key: "asset_allocation.portfolio_notional",
        label: "Portfolio notional",
        type: "currency",
        default: 250_000_000,
        required: true,
      },
      {
        key: "asset_allocation.target_return",
        label: "Target annual return",
        type: "fraction",
        default: 0.05,
        required: true,
      },
      {
        key: "asset_allocation.risk_aversion",
        label: "Risk aversion lambda",
        type: "number",
        default: 3.0,
        required: true,
      },
      {
        key: "asset_allocation.max_single_asset_weight",
        label: "Max single asset weight",
        type: "fraction",
        default: 0.45,
        required: true,
      },
      {
        key: "asset_allocation.min_cash_weight",
        label: "Minimum cash weight",
        type: "fraction",
        default: 0.02,
        required: true,
      },
    ],
  },
  {
    workflow_id: "collateral_liquidity_review",
    name: "Collateral Liquidity Review",
    description:
      "Runs collateral coverage first, then adjusts money-market liquidity requirements.",
    domains: ["collateral", "money_market"],
    tags: ["collateral", "liquidity", "review", "demo"],
    version: 1,
    default_context: { scenario: "collateral_review", solver_backend: "scipy", problem_type: "lp" },
    inputs: [
      { key: "portfolio_id", label: "Portfolio ID", type: "string", default: "PORT_001", required: true },
      {
        key: "collateral.obligation_scale",
        label: "Obligation scale",
        type: "fraction",
        default: 1.65,
        required: true,
      },
      {
        key: "collateral.concentration_limit",
        label: "Collateral concentration cap",
        type: "fraction",
        default: 0.55,
        required: true,
      },
      {
        key: "money_market.total_cash",
        label: "Money-market cash",
        type: "currency",
        default: 450_000_000,
        required: true,
      },
      {
        key: "money_market.daily_liquidity_req",
        label: "Daily liquidity floor",
        type: "fraction",
        default: 0.35,
        required: true,
      },
      {
        key: "money_market.weekly_liquidity_req",
        label: "Weekly liquidity floor",
        type: "fraction",
        default: 0.65,
        required: true,
      },
      {
        key: "money_market.max_prime_fraction",
        label: "Prime concentration cap",
        type: "fraction",
        default: 0.40,
        required: true,
      },
      {
        key: "money_market.max_wam_days",
        label: "Max WAM days",
        type: "integer",
        default: 55,
        required: true,
      },
      {
        key: "money_market.max_single_fund",
        label: "Single fund cap",
        type: "fraction",
        default: 0.45,
        required: true,
      },
      {
        key: "execution_mode",
        label: "Execution mode",
        type: "select",
        default: "recommendation",
        required: true,
        options: ["recommendation", "stage", "execute", "change_constraints"],
      },
      {
        key: "governance.materiality_notional",
        label: "Materiality notional",
        type: "currency",
        default: 450_000_000,
        required: true,
      },
      {
        key: "governance.estimated_pnl_impact",
        label: "Estimated PnL impact",
        type: "currency",
        default: 0,
        required: true,
      },
      {
        key: "governance.production_constraint_change",
        label: "Production constraint change",
        type: "boolean",
        default: false,
        required: true,
      },
    ],
  },
  {
    workflow_id: "funding_capacity_shock",
    name: "Funding Capacity Shock",
    description:
      "Runs stressed financing capacity first, then adjusts money-market reserves.",
    domains: ["financing", "money_market"],
    tags: ["funding", "capacity", "stress", "demo"],
    version: 1,
    default_context: {},
    inputs: [],
  },
  {
    workflow_id: "liquidity_stress_funding_workflow",
    name: "Liquidity Stress Funding Workflow",
    description:
      "Runs financing, collateral, and money-market optimizers under a shared liquidity stress context.",
    domains: ["financing", "collateral", "money_market"],
    tags: ["liquidity", "stress", "funding", "demo"],
    version: 1,
    default_context: {},
    inputs: [],
  },
];

const fallbackDemoPresets: DemoPresetCatalogItem[] = [
  {
    preset_id: TREASURY_CASH_MOVEMENT_PRESET_ID,
    version: 1,
    name: "Treasury Cash Movement Cutoff",
    description:
      "Treasury operations walkthrough routing same-day clearing and settlement funding through open payment rails.",
    audience: "Treasury operations, payments, liquidity control, and settlement teams",
    workflow_id: "treasury_cash_movement",
    portfolio_id: "PORT_TREASURY_OPS",
    seed: 42,
    duration_minutes: 4,
    context: {
      scenario: "treasury_cash_movement_cutoff",
      optimizer_runtime: "production",
      production_optimizer_id: "production.treasury.cash_movement",
      treasury_operations: {
        cutoff_hour: 15,
        stress_multiplier: 1.0,
        liquidity_buffer_pct: 0.05,
      },
      governance: {
        materiality_notional: 155_000_000,
        estimated_pnl_impact: 0,
        production_constraint_change: false,
      },
    },
    talking_points: [
      "Start with two same-day funding requirements and two source cash pools.",
      "Show how the adapter preserves buffers while selecting feasible payment rails.",
      "Export transfers, remaining liquidity, lineage, and reproducibility evidence.",
    ],
    success_criteria: [
      "Treasury workflow appears in the workflow selector.",
      "Production adapter run completes with transfer recommendations.",
      "Evidence export includes operational cash-movement rows.",
    ],
  },
  {
    preset_id: MARGIN_CALL_PRESET_ID,
    version: 1,
    name: "Margin Call Capacity Triage",
    description:
      "Margin operations walkthrough prioritizing a stressed queue inside a limited team-capacity window.",
    audience: "Margin operations, collateral management, counterparty risk, and controls teams",
    workflow_id: "margin_call_workflow",
    portfolio_id: "PORT_MARGIN_OPS",
    seed: 42,
    duration_minutes: 4,
    context: {
      scenario: "margin_call_capacity_triage",
      optimizer_runtime: "production",
      production_optimizer_id: "production.margin_call.workflow",
      margin_operations: {
        team_capacity_minutes: 150,
        materiality_threshold: 25_000_000,
        dispute_stress_multiplier: 1.0,
      },
      governance: {
        materiality_notional: 125_000_000,
        estimated_pnl_impact: 0,
        production_constraint_change: false,
      },
    },
    talking_points: [
      "Start with a margin-call queue that exceeds available operations capacity.",
      "Explain priority using exposure, SLA urgency, dispute probability, and counterparty tier.",
      "Show assigned calls, deferred calls, and evidence for escalation or deferral.",
    ],
    success_criteria: [
      "Margin workflow appears in the workflow selector.",
      "Production adapter run completes with assigned and deferred call actions.",
      "Evidence export includes operational margin queue rows.",
    ],
  },
  {
    preset_id: MONEY_MARKET_POLICY_PRESET_ID,
    version: 1,
    name: "Treasury MMF Policy Optimization",
    description:
      "Money-market desk walkthrough showing PDF policy ingestion, optimizer controls, and before/after liquidity analytics.",
    audience: "Treasury portfolio managers, liquidity risk, investment operations, and control teams",
    workflow_id: "money_market_policy_optimization",
    portfolio_id: "PORT_MMF_901",
    seed: 53,
    duration_minutes: 5,
    context: {
      scenario: "treasury_mmf_policy_optimization",
      solver_backend: "scipy",
      problem_type: "lp",
      money_market: {
        total_cash: 625_000_000,
        daily_liquidity_req: 0.32,
        weekly_liquidity_req: 0.68,
        max_prime_fraction: 0.35,
        max_wam_days: 50,
        max_single_fund: 0.40,
        max_funds: 4,
        min_allocation_fraction: 0.05,
        policy_source: "examples/policies/sample_money_market_policy.pdf",
      },
    },
    talking_points: [
      "Upload the money-market portfolio PDF and ingest cash, liquidity, prime, WAM, and concentration controls.",
      "Use local Ollama to explain the policy while deterministic validation keeps fields structured.",
      "Run the optimizer and compare baseline versus optimized yield and liquidity profile.",
    ],
    success_criteria: [
      "PDF policy fields are extracted and mapped to money-market workflow inputs.",
      "Money-market workflow completes and shows production adapter evidence.",
      "Before/after analytics are visible for yield, liquidity, WAM, prime, and allocation concentration.",
    ],
  },
  {
    preset_id: "institutional_csv_liquidity_stress",
    version: 1,
    name: "Institutional CSV Liquidity Stress",
    description:
      "CSV-backed walkthrough using anonymized financing, collateral, and money-market data with MILP fund selection.",
    audience: "Treasury, risk, funding, and investment technology stakeholders",
    workflow_id: "liquidity_stress_funding_workflow",
    portfolio_id: "PORT_REALDATA_001",
    seed: 17,
    duration_minutes: 7,
    context: {
      scenario: "institutional_csv_liquidity_stress",
      solver_backend: "scipy",
      problem_type: "lp",
      money_market: {
        total_cash: 500_000_000,
        daily_liquidity_req: 0.4,
        weekly_liquidity_req: 0.7,
        max_prime_fraction: 0.35,
        max_wam_days: 55,
        max_funds: 3,
        min_allocation_fraction: 0.1,
        problem_type: "milp",
      },
    },
    talking_points: [
      "Start by showing that each optimizer step is loading anonymized CSV input data.",
      "The final step uses SciPy MILP to select no more than three funds.",
    ],
    success_criteria: [
      "CSV-backed workflow completes all three optimizer steps.",
      "Dependency effects are visible on the money-market step.",
    ],
  },
  {
    preset_id: "institutional_csv_liquidity_base",
    version: 1,
    name: "Institutional CSV Liquidity Base Case",
    description:
      "CSV-backed comparison walkthrough using calmer funding, collateral, and liquidity inputs.",
    audience: "Treasury, risk, funding, and investment technology stakeholders",
    workflow_id: "liquidity_stress_funding_workflow",
    portfolio_id: "PORT_BASEDATA_001",
    seed: 19,
    duration_minutes: 6,
    context: {
      scenario: "institutional_csv_liquidity_base",
      solver_backend: "scipy",
      problem_type: "lp",
      money_market: {
        total_cash: 500_000_000,
        daily_liquidity_req: 0.25,
        weekly_liquidity_req: 0.55,
        max_prime_fraction: 0.45,
        max_wam_days: 60,
        max_funds: 4,
        min_allocation_fraction: 0.05,
        problem_type: "milp",
      },
    },
    talking_points: [
      "Start with the same anonymized CSV workflow under a benign funding backdrop.",
      "Use this as the baseline before switching to Institutional CSV Liquidity Stress.",
    ],
    success_criteria: [
      "CSV-backed base workflow completes all three optimizer steps.",
      "Dependency deltas are smaller than the stress packet.",
    ],
  },
  {
    preset_id: "balanced_mvo_rebalance",
    version: 1,
    name: "Balanced MVO Rebalance",
    description:
      "Portfolio-construction walkthrough showing how target return and risk controls shape a multi-asset rebalance.",
    audience: "Portfolio managers, CIO office, investment risk, and advisory teams",
    workflow_id: "portfolio_rebalance_mvo",
    portfolio_id: "PORT_MVO_001",
    seed: 42,
    duration_minutes: 5,
    context: {
      scenario: "balanced_mvo_rebalance",
      solver_backend: "scipy",
      problem_type: "qp",
      asset_allocation: {
        portfolio_notional: 250_000_000,
        target_return: 0.05,
        risk_aversion: 3.0,
        max_single_asset_weight: 0.45,
        min_cash_weight: 0.02,
      },
    },
    talking_points: [
      "Start with a balanced multi-asset portfolio construction question.",
      "Show expected return, volatility, and Sharpe as stakeholder metrics.",
    ],
    success_criteria: ["Asset allocation step completes and meets the target return."],
  },
  {
    preset_id: COLLATERAL_HQLA_PRESET_ID,
    version: 1,
    name: "Collateral HQLA Schedule Stress",
    description:
      "Markets-facing collateral stress walkthrough showing bilateral and cleared-margin schedule ingestion, haircut review, HQLA tier preservation, and downstream liquidity impact.",
    audience: "Collateral management, treasury liquidity, investment risk, and capital teams",
    workflow_id: "collateral_liquidity_review",
    portfolio_id: "PORT_HQLA_224",
    seed: 31,
    duration_minutes: 6,
    context: {
      scenario: "collateral_hqla_schedule_stress",
      solver_backend: "scipy",
      problem_type: "lp",
      collateral: {
        obligation_scale: 1.85,
        concentration_limit: 0.48,
        schedule_source: "examples/policies/sample_collateral_policy.txt",
        schedule_type: "counterparty_collateral_schedule",
        hqla_reporting: true,
      },
      money_market: {
        total_cash: 420_000_000,
        daily_liquidity_req: 0.35,
        weekly_liquidity_req: 0.65,
        max_prime_fraction: 0.30,
        max_wam_days: 50,
        max_single_fund: 0.45,
      },
    },
    talking_points: [
      "Load the collateral schedule sample and ingest bilateral, CCP, exchange, haircut, cash, and limit terms.",
      "Use local Ollama to explain how schedule controls affect the workflow.",
      "Compare before/after HQLA tier exposure and liquidity profile.",
    ],
    success_criteria: [
      "Collateral schedule fields are extracted and reviewable across bilateral and cleared-margin obligations.",
      "Collateral and money-market workflow steps complete.",
      "HQLA liquidity profile and allocation stats are visible.",
    ],
  },
  {
    preset_id: "executive_liquidity_stress",
    version: 1,
    name: "Executive Liquidity Stress",
    description:
      "Board-level walkthrough showing funding and collateral pressure flowing into liquidity allocation.",
    audience: "Executive treasury and risk stakeholders",
    workflow_id: "liquidity_stress_funding_workflow",
    portfolio_id: "PORT_EXEC_001",
    seed: 7,
    duration_minutes: 8,
    context: {
      scenario: "executive_liquidity_stress",
      financing: { total_funding_need: 325_000_000, spread_shift: 1.65, capacity_scale: 0.55 },
      collateral: { obligation_scale: 1.55, concentration_limit: 0.55 },
      money_market: { total_cash: 500_000_000, daily_liquidity_req: 0.4, weekly_liquidity_req: 0.7 },
    },
    talking_points: [
      "Run financing first to identify capacity and cost pressure.",
      "Show how upstream stress raises downstream liquidity requirements.",
    ],
    success_criteria: ["Workflow completes all three optimizer steps."],
  },
];

const fallbackDemoDataPackets: DemoDataPacketCatalogItem[] = [
  {
    packet_id: "institutional_liquidity_base",
    version: 1,
    name: "Institutional Liquidity Base Case CSV Packet",
    description:
      "Anonymized calmer-case CSV files backing financing, collateral, and money-market inputs.",
    audience: "Treasury, risk, and funding stakeholders",
    workflow_id: "liquidity_stress_funding_workflow",
    preset_id: "institutional_csv_liquidity_base",
    source_type: "csv",
    domains: ["financing", "collateral", "money_market"],
    files: {
      financing_counterparties:
        "examples/data/institutional_liquidity_base/financing_counterparties.csv",
      financing_needs: "examples/data/institutional_liquidity_base/financing_needs.csv",
      collateral_assets: "examples/data/institutional_liquidity_base/collateral_assets.csv",
      collateral_obligations:
        "examples/data/institutional_liquidity_base/collateral_obligations.csv",
      money_market_funds: "examples/data/institutional_liquidity_base/mmf_universe.csv",
      money_market_position: "examples/data/institutional_liquidity_base/cash_position.csv",
    },
    talking_points: [
      "This run uses the same CSV-backed workflow under calmer market inputs.",
      "Use it as the comparison case before the stress run.",
    ],
    success_criteria: [
      "All CSV files load through the data-provider layer.",
      "Dependency deltas are smaller than the stress packet.",
    ],
  },
  {
    packet_id: "institutional_liquidity_stress",
    version: 1,
    name: "Institutional Liquidity Stress CSV Packet",
    description:
      "Anonymized CSV files backing financing, collateral, and money-market inputs.",
    audience: "Treasury, risk, and funding stakeholders",
    workflow_id: "liquidity_stress_funding_workflow",
    preset_id: VIDEO_DEMO_PRESET_ID,
    source_type: "csv",
    domains: ["financing", "collateral", "money_market"],
    files: {
      financing_counterparties:
        "examples/data/institutional_liquidity_stress/financing_counterparties.csv",
      financing_needs: "examples/data/institutional_liquidity_stress/financing_needs.csv",
      collateral_assets: "examples/data/institutional_liquidity_stress/collateral_assets.csv",
      collateral_obligations:
        "examples/data/institutional_liquidity_stress/collateral_obligations.csv",
      money_market_funds: "examples/data/institutional_liquidity_stress/mmf_universe.csv",
      money_market_position: "examples/data/institutional_liquidity_stress/cash_position.csv",
    },
    talking_points: [
      "This run uses CSVs rather than simulated data generators.",
      "The same workflow machinery runs against either source type.",
    ],
    success_criteria: [
      "All CSV files load through the data-provider layer.",
      "Final liquidity allocation uses MILP fund selection.",
    ],
  },
];

const fallbackProductionOptimizers: ProductionOptimizerCatalogItem[] = [
  {
    optimizer_id: "production.treasury.cash_movement",
    domain: "treasury_operations",
    model_name: "Treasury Cash Movement Optimizer",
    model_version: "0.1.0",
    config_version: "2026.07.19",
    objectives: [
      {
        name: "transfer_cost",
        direction: "minimize",
        weight: 1,
        units: "usd",
      },
    ],
    constraints: [
      { name: "funding_requirements", constraint_type: "budget", hard: true },
      { name: "source_liquidity_buffer", constraint_type: "liquidity", hard: true },
      { name: "payment_cutoff", constraint_type: "operational", hard: true },
      { name: "rail_capacity", constraint_type: "capacity", hard: true },
    ],
    data_contract: {
      required_datasets: ["cash_balances", "funding_requirements", "payment_rails"],
      optional_datasets: ["holiday_calendar", "entity_transfer_limits"],
      quality_checks: ["source cash is available", "payment rails exist before cutoff"],
      snapshot_required: true,
    },
    solver: {
      backend: "adapter_native",
      problem_family: "custom",
      vendor: "internal",
      version: "least_cost_cutoff_feasible",
      parameters: {},
    },
    execution: { mode: "in_process", timeout_seconds: 60, resource_profile: "standard" },
  },
  {
    optimizer_id: "production.margin_call.workflow",
    domain: "margin_operations",
    model_name: "Margin Call Workflow Optimizer",
    model_version: "0.1.0",
    config_version: "2026.07.19",
    objectives: [
      {
        name: "sla_breach_risk",
        direction: "minimize",
        weight: 1,
        units: "risk_score",
      },
    ],
    constraints: [
      { name: "team_capacity", constraint_type: "capacity", hard: true },
      { name: "sla_cutoff", constraint_type: "operational", hard: true },
      { name: "counterparty_escalation", constraint_type: "governance", hard: false },
      { name: "approval_required", constraint_type: "governance", hard: false },
    ],
    data_contract: {
      required_datasets: ["margin_call_queue", "ops_capacity"],
      optional_datasets: ["counterparty_risk_scores", "holiday_calendar"],
      quality_checks: ["queue amounts are nonnegative", "ops capacity is positive"],
      snapshot_required: true,
    },
    solver: {
      backend: "adapter_native",
      problem_family: "custom",
      vendor: "internal",
      version: "exposure_sla_dispute_weighted_score",
      parameters: {},
    },
    execution: { mode: "in_process", timeout_seconds: 60, resource_profile: "standard" },
  },
  {
    optimizer_id: "production.asset_allocation.mvo",
    domain: "asset_allocation",
    model_name: "Asset Allocation MVO",
    model_version: "0.1.0",
    config_version: "2026.07.18",
    objectives: [
      {
        name: "mean_variance_utility",
        direction: "maximize",
        weight: 1,
        units: "utility",
      },
    ],
    constraints: [
      { name: "budget", constraint_type: "budget", hard: true },
      { name: "target_return", constraint_type: "risk", hard: true },
      { name: "weight_bounds", constraint_type: "bounds", hard: true },
    ],
    data_contract: {
      required_datasets: ["asset_universe", "covariance_matrix"],
      optional_datasets: ["current_portfolio"],
      quality_checks: [
        "asset weights are nonnegative",
        "covariance matrix dimension matches asset universe",
      ],
      snapshot_required: true,
    },
    solver: {
      backend: "scipy",
      problem_family: "qp",
      vendor: "scipy",
      version: "SLSQP",
      parameters: { ftol: 1e-10, maxiter: 500 },
    },
    execution: { mode: "in_process", timeout_seconds: 60, resource_profile: "standard" },
  },
  {
    optimizer_id: "production.collateral.allocation",
    domain: "collateral",
    model_name: "Collateral Allocation",
    model_version: "0.1.0",
    config_version: "2026.07.18",
    objectives: [
      {
        name: "funding_cost",
        direction: "minimize",
        weight: 1,
        units: "cost",
      },
    ],
    constraints: [
      { name: "inventory", constraint_type: "budget", hard: true },
      { name: "coverage", constraint_type: "regulatory", hard: true },
      { name: "concentration", constraint_type: "custom", hard: true },
    ],
    data_contract: {
      required_datasets: ["collateral_inventory", "margin_obligations"],
      optional_datasets: ["eligibility_overrides", "haircut_policy"],
      quality_checks: ["eligible collateral inventory is available"],
      snapshot_required: true,
    },
    solver: {
      backend: "scipy",
      problem_family: "lp",
      vendor: "scipy",
      version: "HiGHS",
      parameters: {},
    },
    execution: { mode: "in_process", timeout_seconds: 60, resource_profile: "standard" },
  },
  {
    optimizer_id: "production.financing.allocation",
    domain: "financing",
    model_name: "Financing Source Optimizer",
    model_version: "0.1.0",
    config_version: "2026.07.19",
    objectives: [
      {
        name: "funding_spread_cost",
        direction: "minimize",
        weight: 1,
        units: "usd_annualized_cost",
      },
    ],
    constraints: [
      { name: "funding_need_coverage", constraint_type: "budget", hard: true },
      { name: "counterparty_capacity", constraint_type: "bounds", hard: true },
      { name: "tenor_compatibility", constraint_type: "custom", hard: true },
      { name: "single_counterparty_concentration", constraint_type: "risk", hard: true },
      { name: "capital_budget", constraint_type: "regulatory", hard: true },
    ],
    data_contract: {
      required_datasets: ["financing_counterparties", "funding_needs"],
      optional_datasets: ["counterparty_eligibility", "capital_policy_limits"],
      quality_checks: [
        "funding notionals are positive",
        "counterparty capacities are nonnegative",
        "each funding need has at least one tenor-compatible counterparty",
      ],
      snapshot_required: true,
    },
    solver: {
      backend: "scipy",
      problem_family: "lp",
      vendor: "scipy",
      version: "HiGHS",
      parameters: { method: "highs" },
    },
    execution: { mode: "in_process", timeout_seconds: 60, resource_profile: "standard" },
  },
  {
    optimizer_id: "production.money_market.allocation",
    domain: "money_market",
    model_name: "Money Market Allocation Optimizer",
    model_version: "0.1.0",
    config_version: "2026.07.18",
    objectives: [
      {
        name: "net_yield",
        direction: "maximize",
        weight: 1,
        units: "annual_percent",
      },
    ],
    constraints: [
      { name: "cash_budget", constraint_type: "budget", hard: true },
      { name: "daily_liquidity", constraint_type: "liquidity", hard: true },
      { name: "weekly_liquidity", constraint_type: "liquidity", hard: true },
      { name: "prime_concentration", constraint_type: "regulatory", hard: true },
      { name: "wam_limit", constraint_type: "risk", hard: true },
      { name: "single_fund_limit", constraint_type: "bounds", hard: true },
    ],
    data_contract: {
      required_datasets: ["money_market_fund_universe", "cash_position"],
      optional_datasets: ["fund_eligibility_overrides", "liquidity_policy_limits"],
      quality_checks: [
        "fund yields are finite",
        "liquidity percentages are between 0 and 1",
        "cash balance is positive",
      ],
      snapshot_required: true,
    },
    solver: {
      backend: "scipy",
      problem_family: "lp",
      vendor: "scipy",
      version: "HiGHS",
      parameters: { method: "highs", supports_milp: true },
    },
    execution: { mode: "in_process", timeout_seconds: 60, resource_profile: "standard" },
  },
];

const collateralScenarios: CollateralScenario[] = [
  {
    id: "base_schedule",
    name: "Base Schedule",
    description: "Moderate bilateral and cleared-margin call with existing concentration and liquidity limits.",
    inputs: {
      "collateral.obligation_scale": "1.3",
      "collateral.concentration_limit": "0.6",
      "money_market.total_cash": "475000000",
      "money_market.daily_liquidity_req": "0.3",
      "money_market.weekly_liquidity_req": "0.6",
      "money_market.max_prime_fraction": "0.4",
      "money_market.max_wam_days": "55",
      "money_market.max_single_fund": "0.5",
    },
    before: {
      dailyLiquidity: 0.28,
      weeklyLiquidity: 0.55,
      level1: 0.52,
      reusableValue: 318_000_000,
      concentrationUsage: 0.58,
      coverageBuffer: 0.08,
      fundingCostBps: 41,
    },
    after: {
      dailyLiquidity: 0.32,
      weeklyLiquidity: 0.62,
      level1: 0.57,
      reusableValue: 342_000_000,
      concentrationUsage: 0.54,
      coverageBuffer: 0.12,
      fundingCostBps: 37,
    },
  },
  {
    id: "stress_schedule",
    name: "Stress Schedule",
    description: "Higher bilateral dealer and CCP margin calls with tighter concentration and liquidity limits.",
    inputs: {
      "collateral.obligation_scale": "1.85",
      "collateral.concentration_limit": "0.48",
      "money_market.total_cash": "420000000",
      "money_market.daily_liquidity_req": "0.35",
      "money_market.weekly_liquidity_req": "0.65",
      "money_market.max_prime_fraction": "0.3",
      "money_market.max_wam_days": "50",
      "money_market.max_single_fund": "0.45",
    },
    before: {
      dailyLiquidity: 0.31,
      weeklyLiquidity: 0.58,
      level1: 0.54,
      reusableValue: 305_000_000,
      concentrationUsage: 0.63,
      coverageBuffer: 0.04,
      fundingCostBps: 58,
    },
    after: {
      dailyLiquidity: 0.36,
      weeklyLiquidity: 0.67,
      level1: 0.62,
      reusableValue: 348_000_000,
      concentrationUsage: 0.48,
      coverageBuffer: 0.12,
      fundingCostBps: 49,
    },
  },
  {
    id: "severe_haircut",
    name: "Severe Haircut",
    description: "Conservative CCP/exchange margin schedule with harsher reusable-value assumptions.",
    inputs: {
      "collateral.obligation_scale": "2.05",
      "collateral.concentration_limit": "0.42",
      "money_market.total_cash": "390000000",
      "money_market.daily_liquidity_req": "0.4",
      "money_market.weekly_liquidity_req": "0.7",
      "money_market.max_prime_fraction": "0.25",
      "money_market.max_wam_days": "45",
      "money_market.max_single_fund": "0.4",
    },
    before: {
      dailyLiquidity: 0.30,
      weeklyLiquidity: 0.56,
      level1: 0.50,
      reusableValue: 282_000_000,
      concentrationUsage: 0.68,
      coverageBuffer: -0.01,
      fundingCostBps: 72,
    },
    after: {
      dailyLiquidity: 0.41,
      weeklyLiquidity: 0.71,
      level1: 0.66,
      reusableValue: 331_000_000,
      concentrationUsage: 0.42,
      coverageBuffer: 0.07,
      fundingCostBps: 61,
    },
  },
  {
    id: "relaxed_concentration",
    name: "Relaxed Concentration",
    description: "Same bilateral and cleared stress with more concentration capacity for sensitivity comparison.",
    inputs: {
      "collateral.obligation_scale": "1.85",
      "collateral.concentration_limit": "0.6",
      "money_market.total_cash": "420000000",
      "money_market.daily_liquidity_req": "0.35",
      "money_market.weekly_liquidity_req": "0.65",
      "money_market.max_prime_fraction": "0.35",
      "money_market.max_wam_days": "55",
      "money_market.max_single_fund": "0.5",
    },
    before: {
      dailyLiquidity: 0.31,
      weeklyLiquidity: 0.58,
      level1: 0.54,
      reusableValue: 305_000_000,
      concentrationUsage: 0.63,
      coverageBuffer: 0.04,
      fundingCostBps: 58,
    },
    after: {
      dailyLiquidity: 0.35,
      weeklyLiquidity: 0.66,
      level1: 0.59,
      reusableValue: 358_000_000,
      concentrationUsage: 0.55,
      coverageBuffer: 0.14,
      fundingCostBps: 45,
    },
  },
];

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [apiConnected, setApiConnected] = useState(false);
  const [messages, setMessages] = useState<Message[]>(defaultMessages);
  const [input, setInput] = useState("");
  const [ollamaMessages, setOllamaMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Ask a local Ollama model about the workflow, optimizer output, or demo storyline.",
    },
  ]);
  const [ollamaInput, setOllamaInput] = useState(
    "Explain the MVO asset allocation demo in plain English.",
  );
  const [llmConfig, setLlmConfig] = useState<{
    provider: string;
    model: string;
    baseUrl: string;
    apiKey: string;
  }>({
    provider: "openai",
    model: "llama3.1:8b",
    baseUrl: "http://localhost:11434/v1",
    apiKey: "",
  });
  const [isOllamaRunning, setIsOllamaRunning] = useState(false);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [workflowRun, setWorkflowRun] = useState<WorkflowRunResult | null>(null);
  const [workflowCatalog, setWorkflowCatalog] =
    useState<WorkflowCatalogItem[]>(fallbackWorkflowCatalog);
  const [demoPresets, setDemoPresets] =
    useState<DemoPresetCatalogItem[]>(fallbackDemoPresets);
  const [demoDataPackets, setDemoDataPackets] =
    useState<DemoDataPacketCatalogItem[]>(fallbackDemoDataPackets);
  const [productionOptimizers, setProductionOptimizers] =
    useState<ProductionOptimizerCatalogItem[]>(fallbackProductionOptimizers);
  const [selectedDemoPresetId, setSelectedDemoPresetId] = useState(VIDEO_DEMO_PRESET_ID);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState(
    "liquidity_stress_funding_workflow",
  );
  const [optimizerRuntime, setOptimizerRuntime] = useState<"phase1" | "production">("phase1");
  const [selectedProductionOptimizerId, setSelectedProductionOptimizerId] =
    useState("production.asset_allocation.mvo");
  const [workflowInputValues, setWorkflowInputValues] = useState<Record<string, string>>({});
  const [policyText, setPolicyText] = useState("");
  const [policyFilename, setPolicyFilename] = useState("");
  const [policyPdfBase64, setPolicyPdfBase64] = useState<string | null>(null);
  const [policyPdfPreviewUrl, setPolicyPdfPreviewUrl] = useState<string | null>(null);
  const [policyBackend, setPolicyBackend] =
    useState<"deterministic" | "llm" | "auto">("deterministic");
  // policyModel is now sourced from llmConfig.model
  const [policyResult, setPolicyResult] = useState<PolicyIngestionResponse | null>(null);
  const [policyApplied, setPolicyApplied] = useState(false);
  const [isPolicyIngesting, setIsPolicyIngesting] = useState(false);
  const [collateralScenarioId, setCollateralScenarioId] = useState("stress_schedule");
  const [historyInputOverride, setHistoryInputOverride] =
    useState<Record<string, string> | null>(null);
  const [latestPayload, setLatestPayload] = useState<unknown>(null);
  const [latestWorkflowRunPayload, setLatestWorkflowRunPayload] =
    useState<WorkflowRunPayload | null>(null);
  const [runHistory, setRunHistory] = useState<RunHistoryEntry[]>(() => loadRunHistory());
  const [scenarioComparison, setScenarioComparison] =
    useState<WorkflowScenarioComparison | null>(null);
  const [comparisonSets, setComparisonSets] = useState<ComparisonSet[]>(() =>
    loadComparisonSets(),
  );
  const [selectedComparisonSetId, setSelectedComparisonSetId] = useState<string>("auto");
  const [solver, setSolver] = useState(solverKeyForWorkflow(fallbackDemoPresets[0].workflow_id));
  const [isRunning, setIsRunning] = useState(false);
  const [isWorkflowRunning, setIsWorkflowRunning] = useState(false);
  const [isWorkflowStreaming, setIsWorkflowStreaming] = useState(false);
  const [streamSteps, setStreamSteps] = useState<
    Array<{
      step_id: string;
      domain: string;
      name: string;
      status: "running" | "complete" | "pending";
      objective_value?: number | null;
      improvement_pct?: number | null;
    }>
  >([]);
  const [isExportingPackage, setIsExportingPackage] = useState(false);
  const [isExportingEvidence, setIsExportingEvidence] = useState(false);
  const [scriptModeEnabled, setScriptModeEnabled] = useState(true);
  const [scriptStepIndex, setScriptStepIndex] = useState(0);
  const [presenterReviewOpen, setPresenterReviewOpen] = useState(false);

  useEffect(() => {
    return () => {
      if (policyPdfPreviewUrl) URL.revokeObjectURL(policyPdfPreviewUrl);
    };
  }, [policyPdfPreviewUrl]);
  const didCreateSession = useRef(false);
  const messagesRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (didCreateSession.current) return;
    didCreateSession.current = true;
    void createSession();
    void loadWorkflowCatalog();
    void loadDemoPresets();
    void loadDemoDataPackets();
    void loadProductionOptimizers();
  }, []);

  useEffect(() => {
    const messagePane = messagesRef.current;
    if (messagePane) {
      messagePane.scrollTop = messagePane.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    const selectedWorkflow = workflowCatalog.find(
      (item) => item.workflow_id === selectedWorkflowId,
    ) || fallbackWorkflowCatalog[0];
    const selectedPreset = demoPresets.find(
      (item) => item.preset_id === selectedDemoPresetId,
    ) || fallbackDemoPresets[0];
    if (historyInputOverride) {
      setWorkflowInputValues(historyInputOverride);
      setHistoryInputOverride(null);
      return;
    }
    setWorkflowInputValues(buildWorkflowInputValues(selectedWorkflow.inputs, selectedPreset));
  }, [
    demoPresets,
    historyInputOverride,
    selectedDemoPresetId,
    selectedWorkflowId,
    workflowCatalog,
  ]);

  useEffect(() => {
    void loadScenarioComparison(runHistory, selectedComparisonSetId, comparisonSets);
  }, [comparisonSets, runHistory, selectedComparisonSetId]);

  useEffect(() => {
    const workflowItem =
      workflowCatalog.find((item) => item.workflow_id === selectedWorkflowId) ||
      fallbackWorkflowCatalog[0];
    const available = productionOptimizers.filter((optimizer) =>
      workflowItem.domains.includes(optimizer.domain),
    );
    if (available.length && !available.some((item) => item.optimizer_id === selectedProductionOptimizerId)) {
      setSelectedProductionOptimizerId(available[0].optimizer_id);
    }
    if (!workflowHasProductionRuntime(workflowItem, productionOptimizers)) {
      setOptimizerRuntime("phase1");
    }
  }, [
    productionOptimizers,
    selectedProductionOptimizerId,
    selectedWorkflowId,
    workflowCatalog,
  ]);

  async function createSession() {
    try {
      const response = await fetch(`${API_BASE}/api/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seed: 42, default_portfolio: "PORT_001" }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as ChatApiResponse;
      setSessionId(body.session_id);
      setApiConnected(true);
      setWorkflow(body.state);
      setMessages([
        {
          role: "assistant",
          content: "Connected to the local Python optimizer API.",
        },
        { role: "assistant", content: body.assistant_message },
      ]);
    } catch {
      setApiConnected(false);
      setMessages([
        ...defaultMessages,
        {
          role: "assistant",
          content:
            "API server not detected. Start uvicorn to use real optimizer results.",
        },
      ]);
    }
  }

  async function loadWorkflowCatalog() {
    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/workflows`,
        { method: "GET" },
        5000,
      );
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as WorkflowCatalogApiResponse;
      if (body.workflows.length) {
        setWorkflowCatalog(body.workflows);
        setSelectedWorkflowId((current) =>
          body.workflows.some((item) => item.workflow_id === current)
            ? current
            : body.workflows[0].workflow_id,
        );
      }
    } catch {
      setWorkflowCatalog(fallbackWorkflowCatalog);
    }
  }

  async function loadDemoPresets() {
    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/demo-presets`,
        { method: "GET" },
        5000,
      );
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as DemoPresetCatalogApiResponse;
      if (body.presets.length) {
        setDemoPresets(body.presets);
        setSelectedDemoPresetId((current) =>
          body.presets.some((item) => item.preset_id === current)
            ? current
            : body.presets.some((item) => item.preset_id === VIDEO_DEMO_PRESET_ID)
              ? VIDEO_DEMO_PRESET_ID
              : body.presets[0].preset_id,
        );
        setSelectedWorkflowId((current) => {
          const preset = body.presets.find((item) => item.preset_id === selectedDemoPresetId)
            || body.presets.find((item) => item.preset_id === VIDEO_DEMO_PRESET_ID)
            || body.presets[0];
          return current === preset.workflow_id ? current : preset.workflow_id;
        });
      }
    } catch {
      setDemoPresets(fallbackDemoPresets);
    }
  }

  async function loadDemoDataPackets() {
    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/demo-data-packets`,
        { method: "GET" },
        5000,
      );
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as DemoDataPacketCatalogApiResponse;
      if (body.packets.length) {
        setDemoDataPackets(body.packets);
      }
    } catch {
      setDemoDataPackets(fallbackDemoDataPackets);
    }
  }

  async function loadProductionOptimizers() {
    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/production-optimizers`,
        { method: "GET" },
        5000,
      );
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as ProductionOptimizerCatalogApiResponse;
      if (body.optimizers.length) {
        setProductionOptimizers(body.optimizers);
      }
    } catch {
      setProductionOptimizers(fallbackProductionOptimizers);
    }
  }

  async function loadScenarioComparison(
    entries: RunHistoryEntry[],
    comparisonSetId: string,
    sets: ComparisonSet[],
  ) {
    const comparable = entries.filter((entry) => entry.response?.result?.step_results?.length);
    const comparisonSet = sets.find((item) => item.id === comparisonSetId);
    const selected = comparisonSet
      ? comparisonSet.run_ids
          .map((runId) => comparable.find((entry) => entry.id === runId))
          .filter((entry): entry is RunHistoryEntry => Boolean(entry))
      : comparable.slice(0, 4);
    if (selected.length < 2) {
      setScenarioComparison(null);
      return;
    }

    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/workflows/compare`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            runs: selected.map((entry) => entry.response.result),
            labels: selected.map(
              (entry) => `${entry.preset_name} (${formatHistoryTimestamp(entry.created_at)})`,
            ),
            run_ids: selected.map((entry) => entry.id),
          }),
        },
        5000,
      );
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as WorkflowScenarioCompareApiResponse;
      setScenarioComparison(body.comparison);
    } catch {
      setScenarioComparison(null);
    }
  }

  function selectVideoDemoPath() {
    const preset =
      demoPresets.find((item) => item.preset_id === VIDEO_DEMO_PRESET_ID) ||
      demoPresets.find((item) => item.workflow_id === "liquidity_stress_funding_workflow");
    if (!preset) return;
    const workflow = workflowCatalog.find((item) => item.workflow_id === preset.workflow_id);
    setSelectedDemoPresetId(preset.preset_id);
    setSelectedWorkflowId(preset.workflow_id);
    setSolver(solverKeyForWorkflow(preset.workflow_id));
    setWorkflowInputValues(buildWorkflowInputValues(workflow?.inputs || [], preset));
    setResult(null);
    setWorkflowRun(null);
    setLatestPayload(null);
    setLatestWorkflowRunPayload(null);
    setScriptModeEnabled(true);
    setScriptStepIndex(1);
    setPresenterReviewOpen(true);
    setMessages((items) => [
      ...items,
      {
        role: "assistant",
        content:
          "POC video path loaded: CSV data packet, liquidity stress workflow, and MILP money-market selection. Review the inputs, then run the demo.",
      },
    ]);
  }

  function selectCollateralHqlaPath() {
    const preset =
      demoPresets.find((item) => item.preset_id === COLLATERAL_HQLA_PRESET_ID) ||
      demoPresets.find((item) => item.workflow_id === "collateral_liquidity_review");
    if (!preset) return;
    const workflow = workflowCatalog.find((item) => item.workflow_id === preset.workflow_id);
    setSelectedDemoPresetId(preset.preset_id);
    setSelectedWorkflowId(preset.workflow_id);
    setSolver(solverKeyForWorkflow(preset.workflow_id));
    setWorkflowInputValues(buildWorkflowInputValues(workflow?.inputs || [], preset));
    setPolicyText(COLLATERAL_SCHEDULE_SAMPLE);
    setPolicyFilename("sample_collateral_schedule.txt");
    setPolicyPdfBase64(null);
    setPolicyPdfPreviewUrl(null);
    setPolicyResult(null);
    setPolicyApplied(false);
    setPolicyBackend("auto");
    setCollateralScenarioId("stress_schedule");
    setOllamaInput(
      "Explain how this collateral schedule changes the liquidity optimization workflow.",
    );
    setResult(null);
    setWorkflowRun(null);
    setLatestPayload(null);
    setLatestWorkflowRunPayload(null);
    setScriptModeEnabled(false);
    setPresenterReviewOpen(true);
    setMessages((items) => [
      ...items,
      {
        role: "assistant",
        content:
          "Collateral HQLA path loaded. The schedule sample is ready for ingestion; review extracted limits, ask Ollama for the storyline, then run the collateral liquidity workflow.",
      },
    ]);
  }

  function selectMoneyMarketPolicyPath() {
    const preset =
      demoPresets.find((item) => item.preset_id === MONEY_MARKET_POLICY_PRESET_ID) ||
      demoPresets.find((item) => item.workflow_id === "money_market_policy_optimization");
    if (!preset) return;
    const workflow = workflowCatalog.find((item) => item.workflow_id === preset.workflow_id);
    setSelectedDemoPresetId(preset.preset_id);
    setSelectedWorkflowId(preset.workflow_id);
    setSolver(solverKeyForWorkflow(preset.workflow_id));
    setWorkflowInputValues(buildWorkflowInputValues(workflow?.inputs || [], preset));
    setPolicyText(MONEY_MARKET_POLICY_SAMPLE);
    setPolicyFilename("sample_money_market_policy.pdf");
    setPolicyPdfBase64(null);
    setPolicyPdfPreviewUrl(null);
    setPolicyResult(null);
    setPolicyApplied(false);
    setPolicyBackend("auto");
    setOllamaInput(
      "Explain this money-market policy and what the optimizer will change.",
    );
    setResult(null);
    setWorkflowRun(null);
    setLatestPayload(null);
    setLatestWorkflowRunPayload(null);
    setScriptModeEnabled(false);
    setPresenterReviewOpen(true);
    setMessages((items) => [
      ...items,
      {
        role: "assistant",
        content:
          "Money-market policy path loaded. Upload or ingest the sample PDF, review extracted liquidity controls, ask Ollama for the storyline, then run the money-market workflow.",
      },
    ]);
  }

  function resetVideoDemoScript() {
    const preset =
      demoPresets.find((item) => item.preset_id === VIDEO_DEMO_PRESET_ID) ||
      demoPresets.find((item) => item.workflow_id === "liquidity_stress_funding_workflow");
    if (!preset) return;
    const workflow = workflowCatalog.find((item) => item.workflow_id === preset.workflow_id);
    setSelectedDemoPresetId(preset.preset_id);
    setSelectedWorkflowId(preset.workflow_id);
    setSolver(solverKeyForWorkflow(preset.workflow_id));
    setWorkflowInputValues(buildWorkflowInputValues(workflow?.inputs || [], preset));
    setResult(null);
    setWorkflowRun(null);
    setLatestPayload(null);
    setLatestWorkflowRunPayload(null);
    setPresenterReviewOpen(false);
    setScriptModeEnabled(true);
    setScriptStepIndex(0);
    setMessages((items) => [
      ...items,
      {
        role: "assistant",
        content:
          "POC script reset. Start at step 1, then load the CSV path when you are ready.",
      },
    ]);
  }

  function runPresenterScriptAction(action: PresenterScriptAction) {
    if (action === "load") {
      selectVideoDemoPath();
    } else if (action === "review") {
      openPresenterReview();
      setScriptStepIndex(2);
    } else if (action === "run") {
      void runSequentialWorkflow();
    } else if (action === "export") {
      void exportEvidencePacket();
    }
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isRunning) return;
    const message = input.trim();
    if (!message) return;
    setInput("");
    setMessages((items) => [...items, { role: "user", content: message }]);

    if (!apiConnected || !sessionId) {
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content:
            "Static mode is active. Start the API server, then reset this session.",
        },
      ]);
      return;
    }

    setIsRunning(true);
    const pendingMessage: Message = {
      role: "assistant",
      content: "Working...",
      pending: true,
    };
    setMessages((items) => [...items, pendingMessage]);
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/chat/sessions/${sessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          optimizer_runtime: optimizerRuntime,
          production_optimizer_id: selectedProductionOptimizerId || undefined,
        }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as ChatApiResponse;
      setWorkflow(body.state);
      setMessages((items) => replacePendingMessage(items, body.assistant_message));
      if (body.workflow_result) {
        const workflowResponse = {
          plan: body.workflow_plan || {
            workflow_id: body.workflow_result.workflow_id,
            name: body.workflow_result.name,
            description: "",
            steps: [],
          },
          result: body.workflow_result,
        } as WorkflowRunApiResponse;
        const finalStep = [...body.workflow_result.step_results].reverse()[0];
        setWorkflowRun(body.workflow_result);
        setLatestPayload(workflowResponse);
        setLatestWorkflowRunPayload({
          workflow: body.workflow_result.workflow_id,
          portfolio_id: String(finalStep?.request?.portfolio_id || "PORT_001"),
          seed: Number(body.workflow_plan?.context?.seed || 42),
          execution_mode: "recommendation",
          context: {},
        });
        setSelectedWorkflowId(body.workflow_result.workflow_id);
        if (finalStep?.result) {
          setResult(finalStep.result);
        }
        return;
      }
      if (body.result) {
        setResult(body.result);
        setLatestPayload(body);
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setMessages((items) =>
        replacePendingMessage(
          items,
          `The API request did not complete (${detail}). Check that http://127.0.0.1:8000 is running, then try Reset.`,
        ),
      );
    } finally {
      setIsRunning(false);
    }
  }

  async function submitOllamaMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isOllamaRunning) return;
    const message = ollamaInput.trim();
    if (!message) return;
    setOllamaInput("");
    setOllamaMessages((items) => [...items, { role: "user", content: message }]);

    setIsOllamaRunning(true);
    setOllamaMessages((items) => [
      ...items,
      { role: "assistant", content: `Thinking with ${llmConfig.provider} / ${llmConfig.model}…`, pending: true },
    ]);

    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/llm/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            provider: llmConfig.provider,
            model: llmConfig.model,
            base_url: llmConfig.baseUrl || undefined,
            api_key: llmConfig.apiKey || undefined,
            max_tokens: 512,
            system:
              "You are a concise portfolio optimization assistant. Explain concepts plainly for a nontechnical market stakeholder.",
          }),
        },
        45000,
      );
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || String(response.status));
      }
      const body = (await response.json()) as LlmChatApiResponse;
      setOllamaMessages((items) =>
        replacePendingMessage(items, `[${body.model}] ${body.response}`),
      );
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setOllamaMessages((items) =>
        replacePendingMessage(
          items,
          `LLM chat did not complete (${detail}). Check that ${llmConfig.provider} is reachable at ${llmConfig.baseUrl || "default endpoint"} and the model "${llmConfig.model}" is available.`,
        ),
      );
    } finally {
      setIsOllamaRunning(false);
    }
  }

  async function submitApprovalDecisions(
    approvalIds: string[],
    granted: boolean,
    approver: string,
    reason: string,
  ) {
    if (!approvalIds.length) {
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: "No pending approval IDs are available for this workflow run.",
        },
      ]);
      return;
    }
    if (!approver.trim()) {
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: "Enter an approver name before submitting an approval decision.",
        },
      ]);
      return;
    }

    try {
      const responses = await Promise.all(
        approvalIds.map(async (approvalId) => {
          const response = await fetchWithTimeout(
            `${API_BASE}/api/approvals/decisions`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                approval_id: approvalId,
                approver,
                reason,
                granted,
              }),
            },
            10000,
          );
          if (!response.ok) throw new Error(await response.text());
          return (await response.json()) as ApprovalDecisionApiResponse;
        }),
      );
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: `${granted ? "Approved" : "Rejected"} ${responses.length} governance decision${responses.length === 1 ? "" : "s"}. Rerun the workflow to apply the decision state.`,
        },
      ]);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: `Approval decision did not submit (${detail}).`,
        },
      ]);
    }
  }

  function resetSession() {
    setResult(null);
    setWorkflowRun(null);
    setLatestPayload(null);
    setLatestWorkflowRunPayload(null);
    setPresenterReviewOpen(false);
    void createSession();
  }

  async function handlePolicyFileChange(file: File | null) {
    if (!file) return;
    setPolicyFilename(file.name);
    setPolicyResult(null);
    setPolicyApplied(false);
    if (policyPdfPreviewUrl) {
      URL.revokeObjectURL(policyPdfPreviewUrl);
      setPolicyPdfPreviewUrl(null);
    }
    if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
      const dataUrl = await readFileAsDataUrl(file);
      setPolicyPdfBase64(dataUrl.split(",")[1] || "");
      setPolicyPdfPreviewUrl(URL.createObjectURL(file));
      setPolicyText("");
      return;
    }
    const text = await file.text();
    setPolicyPdfBase64(null);
    setPolicyPdfPreviewUrl(null);
    setPolicyText(text);
  }

  async function ingestPolicyDocument() {
    if (isPolicyIngesting) return;
    if (!policyText.trim() && !policyPdfBase64) {
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: "Upload an IPS PDF/text file or paste policy text before ingesting.",
        },
      ]);
      return;
    }

    setIsPolicyIngesting(true);
    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/policy/ingest`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            workflow_id: selectedWorkflow.workflow_id,
            text: policyPdfBase64 ? undefined : policyText,
            pdf_base64: policyPdfBase64 || undefined,
            filename: policyFilename || undefined,
            backend: policyBackend,
            provider: policyBackend === "deterministic" ? undefined : llmConfig.provider,
            model: policyBackend === "deterministic" ? undefined : llmConfig.model,
            base_url: policyBackend === "deterministic" ? undefined : (llmConfig.baseUrl || undefined),
            api_key: policyBackend === "deterministic" ? undefined : (llmConfig.apiKey || undefined),
          }),
        },
        policyBackend === "deterministic" ? 15000 : 60000,
      );
      if (!response.ok) throw new Error(await response.text());
      const body = (await response.json()) as PolicyIngestionResponse;
      setPolicyResult(body);
      setPolicyApplied(false);
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: `IPS ingestion complete using ${String(body.review_summary.backend || policyBackend)}. Review ${body.extracted_fields.length} extracted fields, then apply them to the workflow inputs.`,
        },
      ]);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: `IPS ingestion did not complete (${detail}).`,
        },
      ]);
    } finally {
      setIsPolicyIngesting(false);
    }
  }

  function applyPolicyInputs() {
    if (!policyResult) return;
    const nextValues = {
      ...workflowInputValues,
      ...policyResult.input_values,
    };
    if (policyResult.workflow_id !== selectedWorkflowId) {
      setHistoryInputOverride(nextValues);
      setSelectedWorkflowId(policyResult.workflow_id);
    } else {
      setWorkflowInputValues(nextValues);
    }
    setPolicyApplied(true);
    setMessages((items) => [
      ...items,
      {
        role: "assistant",
        content:
          "Applied IPS fields to the workflow inputs. Run presenter review to confirm guardrails before executing.",
      },
    ]);
  }

  function applyCollateralScenario(scenario: CollateralScenario) {
    setCollateralScenarioId(scenario.id);
    setWorkflowInputValues((current) => ({
      ...current,
      ...scenario.inputs,
    }));
    setResult(null);
    setWorkflowRun(null);
    setLatestPayload(null);
    setLatestWorkflowRunPayload(null);
    setMessages((items) => [
      ...items,
      {
        role: "assistant",
        content: `${scenario.name} applied to the collateral workflow inputs. Open presenter review before running the updated workflow.`,
      },
    ]);
  }

  function exportJson() {
    const payload = latestPayload || { workflow, result };
    downloadTextFile(
      "decision-intelligence-result.json",
      JSON.stringify(payload, null, 2),
      "application/json",
    );
  }

  async function exportDemoPackage() {
    const workflowResponse = workflowRunResponseFromLatest(latestPayload);
    if (!workflowResponse || !workflowRun) {
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: "Run or restore a sequential workflow before exporting a demo package.",
        },
      ]);
      return;
    }

    setIsExportingPackage(true);
    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/workflows/export-package`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            response: workflowResponse,
            payload:
              latestWorkflowRunPayload ||
              latestWorkflowRunPayloadFromHistory(runHistory, workflowRun) ||
              {},
            preset: selectedPreset,
            workflow: selectedWorkflow,
            comparison: comparisonExportPayload(
              scenarioComparison,
              selectedComparisonSetId,
              comparisonSets,
            ),
          }),
        },
        10000,
      );
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as WorkflowExportPackageApiResponse;
      downloadTextFile(body.filename, body.html, body.content_type || "text/html");
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: `Exported ${body.filename} for stakeholder sharing.`,
        },
      ]);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: `Demo package export did not complete (${detail}). Check the API server and try again.`,
        },
      ]);
    } finally {
      setIsExportingPackage(false);
    }
  }

  async function exportEvidencePacket() {
    const workflowResponse = workflowRunResponseFromLatest(latestPayload);
    if (!workflowResponse || !workflowRun) {
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: "Run or restore a sequential workflow before exporting evidence.",
        },
      ]);
      return;
    }

    setIsExportingEvidence(true);
    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/workflows/export-evidence`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            response: workflowResponse,
            payload:
              latestWorkflowRunPayload ||
              latestWorkflowRunPayloadFromHistory(runHistory, workflowRun) ||
              {},
            preset: selectedPreset,
            workflow: selectedWorkflow,
            comparison: comparisonExportPayload(
              scenarioComparison,
              selectedComparisonSetId,
              comparisonSets,
            ),
          }),
        },
        10000,
      );
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as WorkflowEvidenceExportApiResponse;
      downloadTextFile(
        body.json_filename,
        JSON.stringify(body.json_payload, null, 2),
        body.json_content_type || "application/json",
      );
      downloadBase64File(
        body.pdf_filename,
        body.pdf_base64,
        body.pdf_content_type || "application/pdf",
      );
      body.csv_files.forEach((file) => {
        downloadTextFile(file.filename, file.content, file.content_type || "text/csv");
      });
      downloadBase64File(
        body.xlsx_filename,
        body.xlsx_base64,
        body.xlsx_content_type ||
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      );
      setScriptStepIndex((current) => Math.max(current, 4));
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: `Exported ${body.json_filename}, ${body.pdf_filename}, ${body.xlsx_filename}, and ${body.csv_files.length} CSV files.`,
        },
      ]);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: `Evidence export did not complete (${detail}). Check the API server and try again.`,
        },
      ]);
    } finally {
      setIsExportingEvidence(false);
    }
  }

  function openPresenterReview() {
    if (selectedPreset.preset_id === VIDEO_DEMO_PRESET_ID) {
      setScriptModeEnabled(true);
      setScriptStepIndex((current) => Math.max(current, 1));
    }
    setPresenterReviewOpen(true);
    setMessages((items) => [
      ...items,
      {
        role: "assistant",
        content:
          presenterReview.status === "blocked"
            ? "Presenter review is blocked. Fix the highlighted inputs before running this demo."
            : "Presenter review is ready. Confirm the preset, changed fields, and guardrails before running.",
      },
    ]);
  }

  async function runSequentialWorkflow() {
    if (isWorkflowRunning) return;
    if (presenterReview.status === "blocked") {
      setPresenterReviewOpen(true);
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content:
            "This workflow is blocked by presenter guardrails. Fix the input errors, then run again.",
        },
      ]);
      return;
    }
    const selectedWorkflow = workflowCatalog.find(
      (item) => item.workflow_id === selectedWorkflowId,
    ) || fallbackWorkflowCatalog[0];
    const selectedPreset = demoPresets.find(
      (item) => item.preset_id === selectedDemoPresetId,
    ) || fallbackDemoPresets[0];
    const payload = buildWorkflowPayload(
      selectedWorkflow.workflow_id,
      workflow?.collected || {},
      solverProfiles[solver],
      selectedPreset,
      workflowInputValues,
      selectedWorkflow.inputs,
      optimizerRuntime,
      selectedProductionOptimizerId,
      productionOptimizers,
    );
    const payloadWithPolicy = attachPolicyIngestion(payload, policyResult, policyApplied);
    setIsWorkflowRunning(true);
    setMessages((items) => [
      ...items,
      { role: "user", content: `Run ${selectedPreset.name}.` },
      {
        role: "assistant",
        content: `Running ${selectedPreset.name} in sequence...`,
        pending: true,
      },
    ]);

    setIsWorkflowStreaming(true);
    setStreamSteps([]);
    try {
      const response = await fetch(`${API_BASE}/api/workflows/run-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payloadWithPolicy),
      });
      if (!response.ok) throw new Error(String(response.status));
      if (!response.body) throw new Error("No response body for streaming");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";
        for (const chunk of chunks) {
          const line = chunk.trim();
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6)) as {
              event: string;
              step_id?: string;
              domain?: string;
              name?: string;
              step_index?: number;
              step_count?: number;
              status?: string;
              objective_value?: number | null;
              improvement_pct?: number | null;
              result?: WorkflowRunResult;
            };
            if (event.event === "step_started" && event.step_id) {
              setStreamSteps((prev) => [
                ...prev.filter((s) => s.step_id !== event.step_id),
                {
                  step_id: event.step_id!,
                  domain: event.domain ?? "",
                  name: event.name ?? "",
                  status: "running",
                },
              ]);
            } else if (event.event === "step_completed" && event.step_id) {
              setStreamSteps((prev) =>
                prev.map((s) =>
                  s.step_id === event.step_id
                    ? {
                        ...s,
                        status: "complete",
                        objective_value: event.objective_value,
                        improvement_pct: event.improvement_pct,
                      }
                    : s,
                ),
              );
            } else if (event.event === "workflow_completed" && event.result) {
              const body: WorkflowRunApiResponse = {
                plan: {
                  workflow_id: event.result.workflow_id,
                  name: event.result.name,
                  description: "",
                  steps: [],
                },
                result: event.result,
              };
              const finalStep = [...event.result.step_results].reverse()[0];
              setPresenterReviewOpen(false);
              setWorkflowRun(event.result);
              if (finalStep?.result) {
                setResult(finalStep.result);
              }
              setLatestPayload(body);
              setLatestWorkflowRunPayload(payloadWithPolicy);
              if (selectedPreset.preset_id === VIDEO_DEMO_PRESET_ID) {
                setScriptModeEnabled(true);
                setScriptStepIndex((current) => Math.max(current, 3));
              }
              addRunHistoryEntry(
                createRunHistoryEntry({
                  preset: selectedPreset,
                  workflow: selectedWorkflow,
                  solverKey: solver,
                  inputValues: workflowInputValues,
                  payload: payloadWithPolicy,
                  response: body,
                }),
              );
              setMessages((items) =>
                replacePendingMessage(
                  items,
                  `Sequential workflow complete. ${event.result!.step_results.length} optimizer steps ran with aggregate validation ${event.result!.validation_summary.passed ? "passing" : "requiring review"}.`,
                ),
              );
            }
          } catch {
            // ignore parse errors for malformed SSE lines
          }
        }
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setMessages((items) =>
        replacePendingMessage(
          items,
          `The sequential workflow did not complete (${detail}). Check the API server and try again.`,
        ),
      );
    } finally {
      setIsWorkflowRunning(false);
      setIsWorkflowStreaming(false);
    }
  }

  function addRunHistoryEntry(entry: RunHistoryEntry) {
    setRunHistory((current) => persistRunHistory([entry, ...current]));
  }

  function restoreRunHistoryEntry(entry: RunHistoryEntry) {
    setSelectedDemoPresetId(entry.preset_id);
    setSelectedWorkflowId(entry.workflow_id);
    setHistoryInputOverride(entry.input_values);
    setWorkflowRun(entry.response.result);
    setLatestWorkflowRunPayload(entry.payload);
    const finalStep = [...entry.response.result.step_results].reverse()[0];
    if (finalStep?.result) {
      setResult(finalStep.result);
    }
    setLatestPayload(entry.response);
    setPresenterReviewOpen(false);
    setMessages((items) => [
      ...items,
      {
        role: "assistant",
        content: `Restored ${entry.preset_name} from ${formatHistoryTimestamp(entry.created_at)}.`,
      },
    ]);
  }

  async function replayRunHistoryEntry(entry: RunHistoryEntry) {
    if (isWorkflowRunning) return;
    setIsWorkflowRunning(true);
    setMessages((items) => [
      ...items,
      { role: "user", content: `Replay ${entry.preset_name}.` },
      {
        role: "assistant",
        content: `Replaying ${entry.preset_name} with the stored payload...`,
        pending: true,
      },
    ]);

    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/workflows/run`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(entry.payload),
        },
        20000,
      );
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as WorkflowRunApiResponse;
      const finalStep = [...body.result.step_results].reverse()[0];
      setSelectedDemoPresetId(entry.preset_id);
      setSelectedWorkflowId(entry.workflow_id);
      setHistoryInputOverride(entry.input_values);
      setWorkflowRun(body.result);
      if (finalStep?.result) {
        setResult(finalStep.result);
      }
      setLatestPayload(body);
      setLatestWorkflowRunPayload(entry.payload);
      addRunHistoryEntry({
        ...entry,
        id: makeHistoryId(),
        created_at: new Date().toISOString(),
        response: body,
        status: body.result.status,
        validation_passed: body.result.validation_summary.passed,
      });
      setMessages((items) =>
        replacePendingMessage(
          items,
          `Replay complete. ${body.result.step_results.length} optimizer steps ran with aggregate validation ${body.result.validation_summary.passed ? "passing" : "requiring review"}.`,
        ),
      );
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setMessages((items) =>
        replacePendingMessage(
          items,
          `Replay did not complete (${detail}). Check the API server and try again.`,
        ),
      );
    } finally {
      setIsWorkflowRunning(false);
    }
  }

  function clearRunHistory() {
    setRunHistory(persistRunHistory([]));
    setComparisonSets(persistComparisonSets([]));
    setSelectedComparisonSetId("auto");
  }

  function createComparisonSet(name: string) {
    const comparable = runHistory.filter((entry) => entry.response?.result?.step_results?.length);
    const selected = comparable.slice(0, 4);
    if (selected.length < 2) {
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: "Run or restore at least two workflows before saving a comparison set.",
        },
      ]);
      return;
    }
    const set: ComparisonSet = {
      id: makeHistoryId(),
      name: name.trim() || `Comparison ${comparisonSets.length + 1}`,
      created_at: new Date().toISOString(),
      run_ids: selected.map((entry) => entry.id),
    };
    setComparisonSets((current) => persistComparisonSets([set, ...current]));
    setSelectedComparisonSetId(set.id);
    setMessages((items) => [
      ...items,
      {
        role: "assistant",
        content: `Saved comparison set ${set.name} with ${set.run_ids.length} runs.`,
      },
    ]);
  }

  function deleteComparisonSet(setId: string) {
    setComparisonSets((current) => persistComparisonSets(current.filter((item) => item.id !== setId)));
    if (selectedComparisonSetId === setId) {
      setSelectedComparisonSetId("auto");
    }
  }

  const solverProfile = solverProfiles[solver];
  const selectedWorkflow = workflowCatalog.find(
    (item) => item.workflow_id === selectedWorkflowId,
  ) || fallbackWorkflowCatalog[0];
  const selectedPreset = demoPresets.find(
    (item) => item.preset_id === selectedDemoPresetId,
  ) || fallbackDemoPresets[0];
  const selectedDataPacket =
    demoDataPackets.find((item) => item.preset_id === selectedPreset.preset_id) || null;
  const isCollateralHqlaSelected =
    selectedWorkflow.workflow_id === "collateral_liquidity_review" ||
    selectedPreset.preset_id === COLLATERAL_HQLA_PRESET_ID;
  const isMoneyMarketPolicySelected =
    selectedWorkflow.workflow_id === "money_market_policy_optimization" ||
    selectedPreset.preset_id === MONEY_MARKET_POLICY_PRESET_ID;
  const selectedProductionOptimizer =
    productionOptimizers.find((item) => item.optimizer_id === selectedProductionOptimizerId) ||
    productionOptimizers.find((item) => selectedWorkflow.domains.includes(item.domain)) ||
    null;
  const collected = workflow?.collected || {};
  const display = useMemo(
    () => buildDisplayState(collected, selectedWorkflow, selectedPreset),
    [collected, selectedPreset, selectedWorkflow],
  );
  const dashboard = result || mockResultForWorkflow(selectedWorkflow.workflow_id);
  const presenterReview = useMemo(
    () => validatePresenterInputs(
      selectedWorkflow.inputs,
      workflowInputValues,
      selectedPreset,
    ),
    [selectedPreset, selectedWorkflow.inputs, workflowInputValues],
  );
  const latestAssistantPrompt =
    [...messages].reverse().find((message) => message.role === "assistant")?.content || "";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark">DI</div>
          <div>
            <h1>Decision Intelligence</h1>
            <p>Optimization demo workspace</p>
          </div>
        </div>
        <div className="topbar-controls" aria-label="Workspace controls">
          <button className="icon-button" type="button" onClick={resetSession}>
            Reset
          </button>
          <button className="primary-button" type="button" onClick={exportJson}>
            Export JSON
          </button>
          <button
            className="primary-button"
            type="button"
            onClick={exportDemoPackage}
            disabled={!workflowRun || isExportingPackage || isExportingEvidence}
          >
            {isExportingPackage ? "Exporting" : "Export Package"}
          </button>
          <button
            className="primary-button"
            type="button"
            onClick={exportEvidencePacket}
            disabled={!workflowRun || isExportingEvidence || isExportingPackage}
          >
            {isExportingEvidence ? "Exporting" : "Export Evidence"}
          </button>
        </div>
      </header>

      <main className="workspace">
        <aside className="sidebar" aria-label="Workflow state">
          <section className="panel compact">
            <div className="panel-heading">
              <span className="eyebrow">Workflow</span>
              <StatusStrip
                label={result ? "Complete" : apiConnected ? "API ready" : "Static"}
                statusClass={result ? "status-optimal" : "status-ready"}
              />
            </div>
            <dl className="state-list">
              <StateRow label="Domain" value={display.domain} />
              <StateRow label="Portfolio" value={display.portfolio} />
              <StateRow label="Scenario" value={display.scenario} />
              <StateRow label="Governance" value="Recommendation" />
            </dl>
          </section>

          <DataPacketPanel packet={selectedDataPacket} />

          <DemoPresetSelector
            presets={demoPresets}
            selectedPresetId={selectedDemoPresetId}
            onChange={(presetId) => {
              setSelectedDemoPresetId(presetId);
              const preset = demoPresets.find((item) => item.preset_id === presetId);
              if (preset) {
                setSelectedWorkflowId(preset.workflow_id);
                setSolver(solverKeyForWorkflow(preset.workflow_id));
                setResult(null);
                setWorkflowRun(null);
              }
            }}
            disabled={isWorkflowRunning}
          />

          <WorkflowSelector
            workflows={workflowCatalog}
            selectedWorkflowId={selectedWorkflowId}
            onChange={(workflowId) => {
              setSelectedWorkflowId(workflowId);
              setSolver(solverKeyForWorkflow(workflowId));
              const preset = demoPresets.find((item) => item.workflow_id === workflowId);
              if (preset) setSelectedDemoPresetId(preset.preset_id);
              setResult(null);
              setWorkflowRun(null);
            }}
            disabled={isWorkflowRunning}
          />

          <WorkflowInputPanel
            inputs={selectedWorkflow.inputs}
            values={workflowInputValues}
            onChange={(key, value) =>
              setWorkflowInputValues((current) => ({ ...current, [key]: value }))
            }
            onReset={() =>
              setWorkflowInputValues(buildWorkflowInputValues(selectedWorkflow.inputs, selectedPreset))
            }
            onReview={openPresenterReview}
            reviewStatus={presenterReview.status}
            disabled={isWorkflowRunning}
          />

          <ProductionAdapterPanel
            workflow={selectedWorkflow}
            optimizers={productionOptimizers}
            selectedOptimizerId={selectedProductionOptimizerId}
            runtime={optimizerRuntime}
            workflowRun={workflowRun}
            onRuntimeChange={setOptimizerRuntime}
            onOptimizerChange={setSelectedProductionOptimizerId}
            disabled={isWorkflowRunning}
          />

          <PolicyIngestionPanel
            selectedWorkflow={selectedWorkflow}
            text={policyText}
            filename={policyFilename}
            backend={policyBackend}
            llmModel={llmConfig.model}
            result={policyResult}
            applied={policyApplied}
            isIngesting={isPolicyIngesting}
            disabled={isWorkflowRunning}
            documentKind={isCollateralHqlaSelected ? "collateral_schedule" : "ips"}
            onTextChange={(value) => {
              setPolicyText(value);
              setPolicyPdfBase64(null);
              if (policyPdfPreviewUrl) {
                URL.revokeObjectURL(policyPdfPreviewUrl);
                setPolicyPdfPreviewUrl(null);
              }
              setPolicyResult(null);
              setPolicyApplied(false);
            }}
            pdfPreviewUrl={policyPdfPreviewUrl}
            onFileChange={handlePolicyFileChange}
            onBackendChange={setPolicyBackend}
            onIngest={ingestPolicyDocument}
            onApply={applyPolicyInputs}
            onLoadSample={isCollateralHqlaSelected ? selectCollateralHqlaPath : undefined}
          />

          <RunHistoryPanel
            entries={runHistory}
            onRestore={restoreRunHistoryEntry}
            onReplay={replayRunHistoryEntry}
            onClear={clearRunHistory}
            disabled={isWorkflowRunning}
          />

          <PlanPanel workflow={workflow} />

          <TracePanel workflow={workflow} result={result} />

          <section className="panel compact">
            <div className="panel-heading">
              <span className="eyebrow">Solver</span>
            </div>
            <div className="segmented" role="group" aria-label="Solver selection">
              {Object.entries(solverProfiles).map(([key, profile]) => (
                <button
                  className={`segmented-button ${solver === key ? "active" : ""}`}
                  type="button"
                  key={key}
                  onClick={() => setSolver(key)}
                >
                  {profile.label}
                </button>
              ))}
            </div>
            <dl className="state-list solver-meta">
              <StateRow label="Backend" value={String(dashboard.solver_metadata.solver_backend || solverProfile.backend)} />
              <StateRow label="Problem" value={String(dashboard.solver_metadata.problem_type || solverProfile.problem)} />
              <StateRow label="Method" value={String(dashboard.solver_metadata.solver_method || solverProfile.method)} />
            </dl>
          </section>

          <section className="panel compact">
            <div className="panel-heading">
              <span className="eyebrow">Request Summary</span>
            </div>
            <ul className="summary-list">
              {display.summary.map(([label, value]) => (
                <li key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </li>
              ))}
            </ul>
          </section>
        </aside>

        <section className="main-stage" aria-label="Demo workspace">
          <VideoStoryPanel
            selectedPreset={selectedPreset}
            selectedDataPacket={selectedDataPacket}
            workflowRun={workflowRun}
            onSelectPath={selectVideoDemoPath}
            onSelectCollateralPath={selectCollateralHqlaPath}
            onSelectMoneyMarketPath={selectMoneyMarketPolicyPath}
            onReview={openPresenterReview}
            scriptModeEnabled={scriptModeEnabled}
            onToggleScript={() => setScriptModeEnabled((enabled) => !enabled)}
            disabled={isWorkflowRunning}
          />

          {scriptModeEnabled ? (
            <PresenterScriptPanel
              steps={pocPresenterScript}
              activeIndex={scriptStepIndex}
              workflowRun={workflowRun}
              selectedDataPacket={selectedDataPacket}
              isRunning={isWorkflowRunning}
              isExportingEvidence={isExportingEvidence}
              onStepChange={setScriptStepIndex}
              onAction={runPresenterScriptAction}
              onReset={resetVideoDemoScript}
            />
          ) : null}

          <section className="chat-panel panel">
            <div className="section-header">
              <div>
                <span className="eyebrow">Guided Chat</span>
                <h2>{workflow?.title || "Optimization workflow"}</h2>
              </div>
              <div className="quick-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setInput("I want to optimize money market cash")}
                >
                  Start
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setInput("ingest examples/sample_brief.pdf and solve")}
                >
                  PDF
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={selectCollateralHqlaPath}
                  disabled={isWorkflowRunning}
                >
                  Collateral
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={selectMoneyMarketPolicyPath}
                  disabled={isWorkflowRunning}
                >
                  MMF PDF
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={openPresenterReview}
                  disabled={isWorkflowRunning}
                >
                  {isWorkflowRunning ? "Running" : "Review"}
                </button>
              </div>
            </div>

            <ChatIntakeProgress workflow={workflow} />
            {isWorkflowStreaming && <StreamingWorkflowProgress steps={streamSteps} />}

            <div className="messages" aria-live="polite" ref={messagesRef}>
              {messages.map((message, index) => (
                <article className={`message ${message.role}`} key={`${message.role}-${index}`}>
                  <span className="message-label">
                    {message.role === "user" ? "User" : "Assistant"}
                  </span>
                  <p>{message.content}</p>
                </article>
              ))}
            </div>

            <div className="current-prompt" aria-live="polite">
              <span>Current prompt</span>
              <strong>{latestAssistantPrompt}</strong>
            </div>

            <form className="chat-input" onSubmit={submitMessage}>
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Type an answer or business request"
                aria-label="Chat input"
              />
              <button className="primary-button" type="submit" disabled={isRunning}>
                {isRunning ? "Running" : "Send"}
              </button>
            </form>
          </section>

          <LLMSettingsPanel config={llmConfig} onChange={setLlmConfig} />

          <section className="ollama-panel panel" aria-label="Local LLM chat">
            <div className="section-header">
              <div>
                <span className="eyebrow">Local LLM</span>
                <h2>LLM Chat</h2>
              </div>
              <span className="model-badge">{llmConfig.provider} · {llmConfig.model}</span>
            </div>

            <div className="messages ollama-messages" aria-live="polite">
              {ollamaMessages.map((message, index) => (
                <article className={`message ${message.role}`} key={`${message.role}-${index}`}>
                  <span className="message-label">
                    {message.role === "user" ? "User" : llmConfig.provider}
                  </span>
                  <p>{message.content}</p>
                </article>
              ))}
            </div>

            <form className="chat-input" onSubmit={submitOllamaMessage}>
              <input
                value={ollamaInput}
                onChange={(event) => setOllamaInput(event.target.value)}
                placeholder="Ask the local model a demo question"
                aria-label="Ollama chat input"
              />
              <button className="primary-button" type="submit" disabled={isOllamaRunning}>
                {isOllamaRunning ? "Thinking" : "Ask LLM"}
              </button>
            </form>
          </section>

          {isCollateralHqlaSelected ? (
            <>
              <CollateralHqlaAnalyticsPanel
                workflowRun={workflowRun}
                policyResult={policyResult}
                policyApplied={policyApplied}
                selectedPreset={selectedPreset}
              />
              <CollateralScenarioComparisonPanel
                scenarios={collateralScenarios}
                selectedScenarioId={collateralScenarioId}
                inputValues={workflowInputValues}
                workflowRun={workflowRun}
                onApplyScenario={applyCollateralScenario}
                disabled={isWorkflowRunning}
              />
            </>
          ) : null}

          {isMoneyMarketPolicySelected ? (
            <MoneyMarketPolicyAnalyticsPanel
              workflowRun={workflowRun}
              policyResult={policyResult}
              policyApplied={policyApplied}
              selectedPreset={selectedPreset}
              inputValues={workflowInputValues}
            />
          ) : null}

          {policyResult ? (
            <DocumentConstraintTraceabilityPanel
              policyResult={policyResult}
              selectedWorkflow={selectedWorkflow}
            />
          ) : null}

          <section className="dashboard-grid">
            <ResultPanel result={dashboard} />
            <ConstraintPanel result={dashboard} />
          </section>

          <OperationalActionTablePanel
            workflowRun={workflowRun}
            result={result}
            selectedWorkflow={selectedWorkflow}
          />

          <WorkflowTimelinePanel
            workflowRun={workflowRun}
            selectedWorkflow={selectedWorkflow}
            selectedPreset={selectedPreset}
          />

          <GovernanceReviewPanel
            workflowRun={workflowRun}
            selectedWorkflow={selectedWorkflow}
            inputValues={workflowInputValues}
            onDecision={submitApprovalDecisions}
            onRerun={runSequentialWorkflow}
            disabled={isWorkflowRunning}
          />

          <WorkflowComparisonPanel
            workflowRun={workflowRun}
            scenarioComparison={scenarioComparison}
            comparisonSets={comparisonSets}
            selectedComparisonSetId={selectedComparisonSetId}
            onSelectComparisonSet={setSelectedComparisonSetId}
            onCreateComparisonSet={createComparisonSet}
            onDeleteComparisonSet={deleteComparisonSet}
          />

          {presenterReviewOpen ? (
            <PresenterReviewPanel
              review={presenterReview}
              selectedWorkflow={selectedWorkflow}
              selectedPreset={selectedPreset}
              solverProfile={solverProfile}
              onRun={runSequentialWorkflow}
              onClose={() => setPresenterReviewOpen(false)}
              disabled={isWorkflowRunning}
            />
          ) : null}

          <WorkflowExplanationPanel workflowRun={workflowRun} />

          <EvidenceRoomPanel
            workflowRun={workflowRun}
            result={result}
            payload={latestWorkflowRunPayload}
            policyResult={policyResult}
            selectedPreset={selectedPreset}
            selectedWorkflow={selectedWorkflow}
            selectedProductionOptimizer={selectedProductionOptimizer}
            llmConfig={llmConfig}
            latestWorkflowRunPayload={latestWorkflowRunPayload}
          />

          <ValidationPanel result={dashboard} />

          <ExplanationPanel result={dashboard} />

          <section className="table-grid">
            <AllocationTable result={dashboard} />
            <SensitivityTable result={dashboard} />
          </section>
        </section>
      </main>
    </div>
  );
}

function replacePendingMessage(messages: Message[], content: string): Message[] {
  const next = [...messages];
  for (let index = next.length - 1; index >= 0; index -= 1) {
    if (next[index].pending) {
      next[index] = { role: "assistant", content };
      return next;
    }
  }
  return [...next, { role: "assistant", content }];
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs = 10000,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timeout);
  }
}

function downloadTextFile(filename: string, contents: string, contentType: string) {
  const blob = new Blob([contents], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadBase64File(filename: string, base64: string, contentType: string) {
  const binary = window.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const blob = new Blob([bytes], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("Unable to read file."));
    reader.readAsDataURL(file);
  });
}

function workflowRunResponseFromLatest(value: unknown): WorkflowRunApiResponse | null {
  if (!isRecord(value)) return null;
  if (!isRecord(value.plan) || !isRecord(value.result)) return null;
  if (!Array.isArray(value.result.step_results)) return null;
  return value as WorkflowRunApiResponse;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function latestWorkflowRunPayloadFromHistory(
  history: RunHistoryEntry[],
  workflowRun: WorkflowRunResult,
): WorkflowRunPayload | null {
  return history.find((entry) => entry.response.result.timestamp === workflowRun.timestamp)?.payload || null;
}

function comparisonExportPayload(
  comparison: WorkflowScenarioComparison | null,
  selectedComparisonSetId: string,
  sets: ComparisonSet[],
): Record<string, unknown> {
  if (!comparison?.comparison_ready) return {};
  const selectedSet = sets.find((item) => item.id === selectedComparisonSetId);
  return {
    id: selectedSet?.id || "auto",
    name: selectedSet?.name || "Auto comparison",
    created_at: selectedSet?.created_at || new Date().toISOString(),
    run_ids: selectedSet?.run_ids || comparison.runs.map((run) => run.run_id),
    comparison,
  };
}

function loadRunHistory(): RunHistoryEntry[] {
  try {
    const raw = window.localStorage.getItem(RUN_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, MAX_RUN_HISTORY) : [];
  } catch {
    return [];
  }
}

function persistRunHistory(entries: RunHistoryEntry[]): RunHistoryEntry[] {
  const next = entries.slice(0, MAX_RUN_HISTORY);
  try {
    window.localStorage.setItem(RUN_HISTORY_KEY, JSON.stringify(next));
  } catch {
    // Keep the in-memory history for the session when browser storage is blocked.
  }
  return next;
}

function loadComparisonSets(): ComparisonSet[] {
  try {
    const raw = window.localStorage.getItem(COMPARISON_SETS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, MAX_COMPARISON_SETS) : [];
  } catch {
    return [];
  }
}

function persistComparisonSets(entries: ComparisonSet[]): ComparisonSet[] {
  const next = entries.slice(0, MAX_COMPARISON_SETS);
  try {
    window.localStorage.setItem(COMPARISON_SETS_KEY, JSON.stringify(next));
  } catch {
    // Keep the in-memory comparison sets for the session when storage is blocked.
  }
  return next;
}

function createRunHistoryEntry({
  preset,
  workflow,
  solverKey,
  inputValues,
  payload,
  response,
}: {
  preset: DemoPresetCatalogItem;
  workflow: WorkflowCatalogItem;
  solverKey: string;
  inputValues: Record<string, string>;
  payload: WorkflowRunPayload;
  response: WorkflowRunApiResponse;
}): RunHistoryEntry {
  return {
    id: makeHistoryId(),
    created_at: new Date().toISOString(),
    preset_id: preset.preset_id,
    preset_name: preset.name,
    workflow_id: workflow.workflow_id,
    workflow_name: workflow.name,
    portfolio_id: payload.portfolio_id,
    seed: payload.seed,
    solver: solverKey,
    input_values: inputValues,
    payload,
    response,
    status: response.result.status,
    validation_passed: response.result.validation_summary.passed,
  };
}

function makeHistoryId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatHistoryTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function buildWorkflowPayload(
  workflowId: string,
  collected: Record<string, unknown>,
  solverProfile: { backend: string; problem: string; method: string },
  preset?: DemoPresetCatalogItem,
  inputValues: Record<string, string> = {},
  workflowInputs: WorkflowInputSpec[] = [],
  optimizerRuntime: "phase1" | "production" = "phase1",
  productionOptimizerId = "",
  productionOptimizers: ProductionOptimizerCatalogItem[] = fallbackProductionOptimizers,
): WorkflowRunPayload {
  const presetContext = toRecord(preset?.context);
  const presetMoneyMarket = toRecord(presetContext.money_market);
  const compiled = compileWorkflowInputs(workflowInputs, inputValues, preset);
  const compiledContext = toRecord(compiled.context);
  const mergedContext = deepMerge(presetContext, compiledContext);
  const compiledMoneyMarket = toRecord(mergedContext.money_market);

  const workflowDomains = workflowDomainsForId(workflowId, preset);
  const supportsProduction = workflowDomains.some((domain) =>
    productionOptimizers.some((optimizer) => optimizer.domain === domain),
  );
  const selectedProductionOptimizer =
    productionOptimizers.find((optimizer) => optimizer.optimizer_id === productionOptimizerId) ||
    productionOptimizers.find((optimizer) => workflowDomains.includes(optimizer.domain));
  const effectiveRuntime = optimizerRuntime === "production" && supportsProduction
    ? "production"
    : "phase1";
  const explicitProductionOptimizerId =
    effectiveRuntime === "production" && workflowDomains.length === 1
      ? selectedProductionOptimizer?.optimizer_id
      : undefined;

  return {
    workflow: preset?.workflow_id || workflowId,
    portfolio_id: String(compiled.portfolio_id || collected.portfolio_id || preset?.portfolio_id || "PORT_204"),
    seed: Number(compiled.seed || collected.seed || preset?.seed || 42),
    execution_mode: compiled.execution_mode || "recommendation",
    optimizer_runtime: effectiveRuntime,
    production_optimizer_id: explicitProductionOptimizerId,
    context: {
      ...mergedContext,
      ...(effectiveRuntime === "production"
        ? {
            optimizer_runtime: "production",
            ...(explicitProductionOptimizerId
              ? { production_optimizer_id: explicitProductionOptimizerId }
              : {}),
          }
        : {}),
      solver_backend: solverProfile.backend,
      problem_type: solverProfile.problem,
      money_market: {
        ...presetMoneyMarket,
        ...compiledMoneyMarket,
        total_cash: numberFrom(
          compiledMoneyMarket.total_cash,
          collected.total_cash,
          presetMoneyMarket.total_cash,
          500_000_000,
        ),
        daily_liquidity_req: numberFrom(
          compiledMoneyMarket.daily_liquidity_req,
          collected.daily_liquidity_req,
          presetMoneyMarket.daily_liquidity_req,
          0.4,
        ),
        weekly_liquidity_req: numberFrom(
          compiledMoneyMarket.weekly_liquidity_req,
          collected.weekly_liquidity_req,
          presetMoneyMarket.weekly_liquidity_req,
          0.7,
        ),
        max_prime_fraction: numberFrom(
          compiledMoneyMarket.max_prime_fraction,
          collected.max_prime_fraction,
          presetMoneyMarket.max_prime_fraction,
          0.4,
        ),
        max_wam_days: numberFrom(
          compiledMoneyMarket.max_wam_days,
          collected.max_wam_days,
          presetMoneyMarket.max_wam_days,
          60,
        ),
        max_single_fund: numberFrom(
          compiledMoneyMarket.max_single_fund,
          collected.max_single_fund,
          presetMoneyMarket.max_single_fund,
          0.50,
        ),
      },
    },
  };
}

function attachPolicyIngestion(
  payload: WorkflowRunPayload,
  policy: PolicyIngestionResponse | null,
  applied: boolean,
): WorkflowRunPayload {
  if (!policy) return payload;
  const policyContext = toRecord(policy.context_patch);
  const metadata = toRecord(policyContext.policy_ingestion);
  const context = applied
    ? deepMerge(payload.context, policyContext)
    : deepMerge(payload.context, {
        policy_ingestion: {
          ...metadata,
          applied_to_workflow: false,
          extracted_field_count: policy.extracted_fields.length,
          ready: Boolean(policy.review_summary.ready),
        },
      });
  return {
    ...payload,
    portfolio_id: applied
      ? policy.input_values.portfolio_id || payload.portfolio_id
      : payload.portfolio_id,
    context,
    policy_ingestion: policy,
  };
}

function workflowDomainsForId(
  workflowId: string,
  preset?: DemoPresetCatalogItem,
): string[] {
  if (workflowId === "portfolio_rebalance_mvo") return ["asset_allocation"];
  if (workflowId === "money_market_policy_optimization") return ["money_market"];
  if (workflowId === "collateral_liquidity_review") return ["collateral", "money_market"];
  if (workflowId === "treasury_cash_movement") return ["treasury_operations"];
  if (workflowId === "margin_call_workflow") return ["margin_operations"];
  if (workflowId === "funding_capacity_shock") return ["financing", "money_market"];
  if (workflowId === "liquidity_stress_funding_workflow") {
    return ["financing", "collateral", "money_market"];
  }
  const contextDomain = toRecord(preset?.context).domain;
  return contextDomain ? [String(contextDomain)] : ["money_market"];
}

function workflowSupportsProductionRuntime(
  workflow: WorkflowCatalogItem,
  productionOptimizers: ProductionOptimizerCatalogItem[],
): boolean {
  return workflow.domains.length > 0 && workflow.domains.every((domain) =>
    productionOptimizers.some((optimizer) => optimizer.domain === domain),
  );
}

function workflowHasProductionRuntime(
  workflow: WorkflowCatalogItem,
  productionOptimizers: ProductionOptimizerCatalogItem[],
): boolean {
  return workflow.domains.some((domain) =>
    productionOptimizers.some((optimizer) => optimizer.domain === domain),
  );
}

function constraintTraceForPolicyField(
  key: string,
  workflow: WorkflowCatalogItem,
): { constraint: string; family: string; step: string; domain: string } {
  const explicit: Record<string, { constraint: string; family: string; domain: string }> = {
    portfolio_id: {
      constraint: "Portfolio scope",
      family: "request identity",
      domain: "workflow",
    },
    "collateral.obligation_scale": {
      constraint: "Collateral coverage requirement",
      family: "coverage",
      domain: "collateral",
    },
    "collateral.concentration_limit": {
      constraint: "Asset-class concentration cap",
      family: "concentration",
      domain: "collateral",
    },
    "money_market.total_cash": {
      constraint: "Cash budget",
      family: "budget",
      domain: "money_market",
    },
    "money_market.daily_liquidity_req": {
      constraint: "Daily liquidity floor",
      family: "liquidity",
      domain: "money_market",
    },
    "money_market.weekly_liquidity_req": {
      constraint: "Weekly liquidity floor",
      family: "liquidity",
      domain: "money_market",
    },
    "money_market.max_prime_fraction": {
      constraint: "Prime concentration cap",
      family: "regulatory",
      domain: "money_market",
    },
    "money_market.max_wam_days": {
      constraint: "Weighted-average maturity limit",
      family: "risk",
      domain: "money_market",
    },
    "money_market.max_single_fund": {
      constraint: "Single fund concentration cap",
      family: "bounds",
      domain: "money_market",
    },
    "asset_allocation.target_return": {
      constraint: "Target return floor",
      family: "risk-return",
      domain: "asset_allocation",
    },
    "asset_allocation.max_single_asset_weight": {
      constraint: "Single asset weight cap",
      family: "bounds",
      domain: "asset_allocation",
    },
    "asset_allocation.min_cash_weight": {
      constraint: "Cash allocation floor",
      family: "bounds",
      domain: "asset_allocation",
    },
    "asset_allocation.risk_aversion": {
      constraint: "Risk-aversion objective weight",
      family: "objective",
      domain: "asset_allocation",
    },
    "asset_allocation.portfolio_notional": {
      constraint: "Portfolio budget",
      family: "budget",
      domain: "asset_allocation",
    },
    "governance.materiality_notional": {
      constraint: "Approval materiality threshold",
      family: "governance",
      domain: "governance",
    },
    "governance.estimated_pnl_impact": {
      constraint: "Approval impact threshold",
      family: "governance",
      domain: "governance",
    },
    "governance.production_constraint_change": {
      constraint: "Tier 5 constraint-change gate",
      family: "governance",
      domain: "governance",
    },
  };
  const fallbackDomain = key.includes(".") ? key.split(".")[0] : workflow.domains[0] || "workflow";
  const item = explicit[key] || {
    constraint: titleCase(key.split(".").at(-1)?.replaceAll("_", " ") || key),
    family: "workflow input",
    domain: fallbackDomain,
  };
  const step = workflow.domains.includes(item.domain)
    ? `${titleCase(item.domain.replaceAll("_", " "))} optimizer step`
    : titleCase(item.domain.replaceAll("_", " "));
  return { ...item, step };
}

function productionEvidenceFromWorkflowRun(
  workflowRun: WorkflowRunResult | null,
): Record<string, unknown> | null {
  const steps = workflowRun?.step_results || [];
  for (const step of steps) {
    const evidence = productionEvidenceFromResult(step.result);
    if (evidence) return evidence;
  }
  return null;
}

function productionEvidenceFromResult(
  result: OptimizationResult | null,
): Record<string, unknown> | null {
  const evidence = result?.solver_metadata?.production_evidence;
  return isRecord(evidence) ? evidence : null;
}

function shortFingerprint(value: unknown): string {
  const text = String(value || "");
  if (!text) return "not captured";
  if (text.length <= 18) return text;
  return `${text.slice(0, 10)}...${text.slice(-6)}`;
}

function buildWorkflowInputValues(
  inputs: WorkflowInputSpec[],
  preset?: DemoPresetCatalogItem,
): Record<string, string> {
  return Object.fromEntries(
    inputs.map((input) => {
      const value = valueForWorkflowInput(input, preset);
      return [input.key, value === undefined || value === null ? "" : String(value)];
    }),
  );
}

function validatePresenterInputs(
  inputs: WorkflowInputSpec[],
  values: Record<string, string>,
  preset: DemoPresetCatalogItem,
): PresenterReview {
  const issues: PresenterIssue[] = [];
  const changes = changedWorkflowInputs(inputs, values, preset);

  for (const input of inputs) {
    const raw = values[input.key] ?? "";
    if (input.required && raw.trim() === "") {
      issues.push({
        severity: "error",
        field: input.label,
        message: `${input.label} is required.`,
      });
      continue;
    }

    if (raw.trim() === "") continue;
    if (inputType(input.type) === "number") {
      const numeric = Number(raw);
      if (!Number.isFinite(numeric)) {
        issues.push({
          severity: "error",
          field: input.label,
          message: `${input.label} must be a valid number.`,
        });
        continue;
      }
      if (input.type === "integer" && !Number.isInteger(numeric)) {
        issues.push({
          severity: "error",
          field: input.label,
          message: `${input.label} must be a whole number.`,
        });
      }
      if (
        input.type === "currency" &&
        numeric === 0 &&
        !input.key.includes("estimated_pnl_impact")
      ) {
        issues.push({
          severity: "error",
          field: input.label,
          message: `${input.label} must be greater than zero.`,
        });
      }
      if (input.type === "currency" && numeric < 0) {
        issues.push({
          severity: "error",
          field: input.label,
          message: `${input.label} cannot be negative.`,
        });
      }
      if (input.type === "currency" && numeric > 2_000_000_000) {
        issues.push({
          severity: "warning",
          field: input.label,
          message: `${input.label} is unusually large for this demo preset.`,
        });
      }
      if (input.type === "fraction" && (numeric <= 0 || numeric > 2)) {
        issues.push({
          severity: "error",
          field: input.label,
          message: `${input.label} should be a decimal multiplier between 0 and 2.`,
        });
      }
      if (input.type === "percent" && (numeric < 0 || numeric > 100)) {
        issues.push({
          severity: "error",
          field: input.label,
          message: `${input.label} should be between 0 and 100.`,
        });
      }
    }
  }

  const compiled = compileWorkflowInputs(inputs, values, preset);
  const context = deepMerge(toRecord(preset.context), compiled.context);
  addWorkflowGuardrails(context, issues);

  return {
    status: issues.some((issue) => issue.severity === "error")
      ? "blocked"
      : issues.length
        ? "review"
        : "ready",
    issues,
    changes,
  };
}

function changedWorkflowInputs(
  inputs: WorkflowInputSpec[],
  values: Record<string, string>,
  preset: DemoPresetCatalogItem,
): PresenterChange[] {
  return inputs.flatMap((input) => {
    const original = valueForWorkflowInput(input, preset);
    const current = values[input.key] ?? "";
    const originalText = original === undefined || original === null ? "" : String(original);
    if (current === originalText) return [];
    return [{
      key: input.key,
      label: input.label,
      from: originalText || "blank",
      to: current || "blank",
    }];
  });
}

function addWorkflowGuardrails(
  context: Record<string, unknown>,
  issues: PresenterIssue[],
): void {
  const moneyMarket = toRecord(context.money_market);
  const financing = toRecord(context.financing);
  const collateral = toRecord(context.collateral);
  const assetAllocation = toRecord(context.asset_allocation);

  const dailyLiquidity = optionalNumber(moneyMarket.daily_liquidity_req);
  const weeklyLiquidity = optionalNumber(moneyMarket.weekly_liquidity_req);
  const totalCash = optionalNumber(moneyMarket.total_cash);
  const maxPrime = optionalNumber(moneyMarket.max_prime_fraction);
  const maxWam = optionalNumber(moneyMarket.max_wam_days);
  const fundingNeed = optionalNumber(financing.total_funding_need);
  const capacityScale = optionalNumber(financing.capacity_scale);
  const obligationScale = optionalNumber(collateral.obligation_scale);
  const targetReturn = optionalNumber(assetAllocation.target_return);
  const riskAversion = optionalNumber(assetAllocation.risk_aversion);
  const maxSingleAsset = optionalNumber(assetAllocation.max_single_asset_weight);
  const minCashWeight = optionalNumber(assetAllocation.min_cash_weight);

  if (dailyLiquidity !== undefined && weeklyLiquidity !== undefined) {
    if (dailyLiquidity > weeklyLiquidity) {
      issues.push({
        severity: "error",
        field: "Liquidity requirements",
        message: "Daily liquidity cannot exceed weekly liquidity.",
      });
    }
    if (dailyLiquidity > 0.85 || weeklyLiquidity > 0.95) {
      issues.push({
        severity: "warning",
        field: "Liquidity requirements",
        message: "Liquidity requirements are very high; confirm this is intentional.",
      });
    }
  }

  if (totalCash !== undefined && totalCash < 50_000_000) {
    issues.push({
      severity: "warning",
      field: "Money-market cash",
      message: "Cash is low for a stakeholder demo and may reduce allocation variety.",
    });
  }

  if (maxPrime !== undefined && (maxPrime < 0 || maxPrime > 1)) {
    issues.push({
      severity: "error",
      field: "Prime concentration",
      message: "Prime concentration must be between 0 and 1.",
    });
  }

  if (maxWam !== undefined && (maxWam <= 0 || maxWam > 120)) {
    issues.push({
      severity: "error",
      field: "WAM limit",
      message: "WAM limit must be between 1 and 120 days.",
    });
  }

  if (fundingNeed !== undefined && totalCash !== undefined && fundingNeed > totalCash * 1.5) {
    issues.push({
      severity: "warning",
      field: "Funding need",
      message: "Funding need is much larger than cash reserves; explain this stress framing.",
    });
  }

  if (capacityScale !== undefined && capacityScale < 0.25) {
    issues.push({
      severity: "warning",
      field: "Capacity scale",
      message: "Capacity is extremely constrained and may create a severe stress story.",
    });
  }

  if (obligationScale !== undefined && obligationScale > 1.9) {
    issues.push({
      severity: "warning",
      field: "Obligation scale",
      message: "Collateral obligations are near the upper demo range.",
    });
  }

  if (targetReturn !== undefined && (targetReturn <= 0 || targetReturn > 0.15)) {
    issues.push({
      severity: targetReturn > 0.15 ? "error" : "warning",
      field: "Target return",
      message: "Target return should be a realistic annual decimal for this MVO demo.",
    });
  }

  if (riskAversion !== undefined && (riskAversion < 0 || riskAversion > 10)) {
    issues.push({
      severity: "error",
      field: "Risk aversion",
      message: "Risk aversion should be between 0 and 10.",
    });
  }

  if (maxSingleAsset !== undefined && (maxSingleAsset < 0.20 || maxSingleAsset > 1)) {
    issues.push({
      severity: "error",
      field: "Single asset cap",
      message: "Single asset cap should be between 20% and 100%.",
    });
  }

  if (minCashWeight !== undefined && (minCashWeight < 0 || minCashWeight > 0.30)) {
    issues.push({
      severity: "error",
      field: "Cash floor",
      message: "Cash floor should be between 0% and 30% for this demo.",
    });
  }
}

function optionalNumber(value: unknown): number | undefined {
  if (value === undefined || value === null || value === "") return undefined;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
}

function valueForWorkflowInput(input: WorkflowInputSpec, preset?: DemoPresetCatalogItem): unknown {
  if (input.key === "portfolio_id") return preset?.portfolio_id ?? input.default;
  if (input.key === "seed") return preset?.seed ?? input.default;
  const contextValue = getNestedValue(toRecord(preset?.context), input.key);
  return contextValue ?? input.default;
}

function compileWorkflowInputs(
  inputs: WorkflowInputSpec[],
  values: Record<string, string>,
  preset?: DemoPresetCatalogItem,
): {
  portfolio_id?: string;
  seed?: number;
  execution_mode?: string;
  context: Record<string, unknown>;
} {
  const compiled: {
    portfolio_id?: string;
    seed?: number;
    execution_mode?: string;
    context: Record<string, unknown>;
  } = {
    context: {},
  };
  for (const input of inputs) {
    const raw = values[input.key];
    const fallback = valueForWorkflowInput(input, preset);
    const value = parseWorkflowInputValue(raw === "" ? fallback : raw, input.type);
    if (value === undefined || value === null || value === "") continue;

    if (input.key === "portfolio_id") {
      compiled.portfolio_id = String(value);
    } else if (input.key === "seed") {
      compiled.seed = Number(value);
    } else if (input.key === "execution_mode") {
      compiled.execution_mode = String(value);
    } else {
      setNestedValue(compiled.context, input.key, value);
    }
  }
  return compiled;
}

function parseWorkflowInputValue(value: unknown, type: string): unknown {
  if (type === "integer") return Math.trunc(Number(value));
  if (["number", "currency", "fraction", "percent"].includes(type)) return Number(value);
  if (type === "boolean") {
    if (typeof value === "boolean") return value;
    return String(value).trim().toLowerCase() === "true";
  }
  return value;
}

function deepMerge(
  base: Record<string, unknown>,
  override: Record<string, unknown>,
): Record<string, unknown> {
  const output = { ...base };
  for (const [key, value] of Object.entries(override)) {
    const existing = output[key];
    if (
      existing &&
      value &&
      typeof existing === "object" &&
      typeof value === "object" &&
      !Array.isArray(existing) &&
      !Array.isArray(value)
    ) {
      output[key] = deepMerge(
        existing as Record<string, unknown>,
        value as Record<string, unknown>,
      );
    } else {
      output[key] = value;
    }
  }
  return output;
}

function getNestedValue(source: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((current, part) => {
    if (!current || typeof current !== "object" || Array.isArray(current)) return undefined;
    return (current as Record<string, unknown>)[part];
  }, source);
}

function setNestedValue(target: Record<string, unknown>, path: string, value: unknown): void {
  const parts = path.split(".");
  let cursor = target;
  parts.slice(0, -1).forEach((part) => {
    if (!cursor[part] || typeof cursor[part] !== "object" || Array.isArray(cursor[part])) {
      cursor[part] = {};
    }
    cursor = cursor[part] as Record<string, unknown>;
  });
  cursor[parts[parts.length - 1]] = value;
}

function toRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value as Record<string, unknown>;
}

function recordArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => toRecord(item)).filter((item) => Object.keys(item).length > 0);
}

function numberFrom(...values: unknown[]): number {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "") {
      return Number(value);
    }
  }
  return 0;
}

function VideoStoryPanel({
  selectedPreset,
  selectedDataPacket,
  workflowRun,
  onSelectPath,
  onSelectCollateralPath,
  onSelectMoneyMarketPath,
  onReview,
  scriptModeEnabled,
  onToggleScript,
  disabled,
}: {
  selectedPreset: DemoPresetCatalogItem;
  selectedDataPacket: DemoDataPacketCatalogItem | null;
  workflowRun: WorkflowRunResult | null;
  onSelectPath: () => void;
  onSelectCollateralPath: () => void;
  onSelectMoneyMarketPath: () => void;
  onReview: () => void;
  scriptModeEnabled: boolean;
  onToggleScript: () => void;
  disabled: boolean;
}) {
  const finalStep = workflowRun?.step_results.at(-1);
  const finalSolver = finalStep?.result.solver_metadata;
  const isCollateralHqla =
    selectedPreset.preset_id === COLLATERAL_HQLA_PRESET_ID ||
    selectedPreset.workflow_id === "collateral_liquidity_review";
  const isMoneyMarketPolicy =
    selectedPreset.preset_id === MONEY_MARKET_POLICY_PRESET_ID ||
    selectedPreset.workflow_id === "money_market_policy_optimization";
  const proofPoints = [
    isMoneyMarketPolicy
      ? {
          label: "1",
          title: "PDF Policy Intake",
          body: "Cash, liquidity floors, WAM, prime cap, and single-fund limits are reviewable before solve",
          status: "ready",
        }
      : isCollateralHqla
      ? {
          label: "1",
          title: "Schedule Controls",
          body: "Haircuts, eligibility, cash floors, WAM, and concentration caps are reviewable before solve",
          status: "ready",
        }
      : {
          label: "1",
          title: "CSV Data Packet",
          body: selectedDataPacket
            ? `${selectedDataPacket.domains.length} domains, ${Object.keys(selectedDataPacket.files).length} files`
            : "Select the institutional CSV preset",
          status: selectedDataPacket ? "ready" : "review",
        },
    isMoneyMarketPolicy
      ? {
          label: "2",
          title: "Money-Market Analytics",
          body: workflowRun
            ? "Before/after yield, liquidity, WAM, and concentration stats are ready"
            : "Run the workflow to populate post-optimization analytics",
          status: workflowRun ? "ready" : "review",
        }
      : isCollateralHqla
      ? {
          label: "2",
          title: "HQLA Analytics",
          body: workflowRun
            ? "Before/after liquidity and HQLA tier profile are ready"
            : "Run the workflow to update post-optimization stats",
          status: workflowRun ? "ready" : "review",
        }
      : {
          label: "2",
          title: "MILP Final Step",
          body: finalSolver
            ? `${finalSolver.solver_backend}/${finalSolver.problem_type}`
            : "Money-market step uses scipy/milp",
          status: finalSolver?.problem_type === "milp" ? "ready" : "review",
        },
    isMoneyMarketPolicy
      ? {
          label: "3",
          title: "Document Evidence",
          body: workflowRun
            ? "Policy fields, solver metadata, governance, and trace are in evidence"
            : "PDF ingestion maps source text to optimizer controls",
          status: workflowRun ? "ready" : "review",
        }
      : isCollateralHqla
      ? {
          label: "3",
          title: "Collateral Orchestration",
          body: workflowRun
            ? `${workflowRun.dependency_summary.total_effects} liquidity effects applied`
            : "Collateral pressure adjusts downstream money-market liquidity",
          status: workflowRun?.dependency_summary.total_effects ? "ready" : "review",
        }
      : {
          label: "3",
          title: "Workflow Dependencies",
          body: workflowRun
            ? `${workflowRun.dependency_summary.total_effects} effects applied`
            : "Financing and collateral adjust liquidity",
          status: workflowRun?.dependency_summary.total_effects ? "ready" : "review",
        },
  ];

  return (
    <section className="panel video-story-panel">
      <div className="video-story-copy">
        <span className="eyebrow">
          {isMoneyMarketPolicy
            ? "Money-Market Video Path"
            : isCollateralHqla
              ? "Collateral Video Path"
              : "POC Video Path"}
        </span>
        <h2>
          {isMoneyMarketPolicy
            ? "PDF-to-allocation story"
            : isCollateralHqla
              ? "Schedule-to-HQLA story"
              : "Real-data workflow story"}
        </h2>
        <p>
          {isMoneyMarketPolicy
            ? "Use this lane for the money-market recording: upload a portfolio policy PDF, ingest the required liquidity controls, ask the local LLM for plain-English framing, then run the optimizer with before/after allocation analytics."
            : isCollateralHqla
              ? "Use this lane for the collateral recording: load the schedule sample, ingest constraints, ask the local LLM for plain-English framing, then run the collateral-to-liquidity workflow with before/after HQLA analytics."
              : "Use this lane for the recording: load the anonymized CSV packet, run the liquidity stress workflow, then call out dependency effects and the final MILP-selected money-market allocation."}
        </p>
        <div className="video-story-actions">
          <button className="primary-button" type="button" onClick={onSelectPath} disabled={disabled}>
            Load POC Path
          </button>
          <button
            className="primary-button"
            type="button"
            onClick={onSelectCollateralPath}
            disabled={disabled}
          >
            Load Collateral HQLA
          </button>
          <button
            className="primary-button"
            type="button"
            onClick={onSelectMoneyMarketPath}
            disabled={disabled}
          >
            Load MMF Policy
          </button>
          <button className="secondary-button" type="button" onClick={onReview} disabled={disabled}>
            Review & Run
          </button>
          <button className="secondary-button" type="button" onClick={onToggleScript}>
            {scriptModeEnabled ? "Hide Script" : "Show Script"}
          </button>
        </div>
      </div>
      <div className="video-proof-grid">
        {proofPoints.map((point) => (
          <div className={`video-proof-card ${point.status}`} key={point.title}>
            <span>{point.label}</span>
            <strong>{point.title}</strong>
            <p>{point.body}</p>
          </div>
        ))}
      </div>
      <div className="video-story-preset">
        <strong>{selectedPreset.name}</strong>
        <span>{selectedPreset.audience}</span>
      </div>
    </section>
  );
}

function PresenterScriptPanel({
  steps,
  activeIndex,
  workflowRun,
  selectedDataPacket,
  isRunning,
  isExportingEvidence,
  onStepChange,
  onAction,
  onReset,
}: {
  steps: PresenterScriptStep[];
  activeIndex: number;
  workflowRun: WorkflowRunResult | null;
  selectedDataPacket: DemoDataPacketCatalogItem | null;
  isRunning: boolean;
  isExportingEvidence: boolean;
  onStepChange: (index: number) => void;
  onAction: (action: PresenterScriptAction) => void;
  onReset: () => void;
}) {
  const step = steps[activeIndex] || steps[0];
  const finalStep = workflowRun?.step_results.at(-1);
  const finalSolver = finalStep?.result.solver_metadata;
  const statusItems = [
    {
      label: "Data",
      value: selectedDataPacket ? "CSV packet loaded" : "Select CSV packet",
      ready: Boolean(selectedDataPacket),
    },
    {
      label: "Workflow",
      value: workflowRun ? `${workflowRun.step_results.length} steps complete` : "Not run",
      ready: workflowRun?.status === "complete",
    },
    {
      label: "Dependencies",
      value: workflowRun
        ? `${workflowRun.dependency_summary.total_effects} effects`
        : "Pending",
      ready: Boolean(workflowRun?.dependency_summary.total_effects),
    },
    {
      label: "Solver",
      value: finalSolver
        ? `${finalSolver.solver_backend}/${finalSolver.problem_type}`
        : "MILP pending",
      ready: finalSolver?.problem_type === "milp",
    },
  ];
  const actionDisabled =
    step.action === "none" ||
    isRunning ||
    isExportingEvidence ||
    (step.action === "export" && !workflowRun);

  return (
    <section className="panel presenter-script-panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Presenter Script</span>
          <h2>{step.title}</h2>
        </div>
        <div className="script-controls">
          <button
            className="secondary-button"
            type="button"
            onClick={() => onStepChange(Math.max(0, activeIndex - 1))}
            disabled={activeIndex === 0}
          >
            Back
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => onStepChange(Math.min(steps.length - 1, activeIndex + 1))}
            disabled={activeIndex === steps.length - 1}
          >
            Next
          </button>
          <button className="text-button" type="button" onClick={onReset}>
            Reset Script
          </button>
        </div>
      </div>

      <div className="script-layout">
        <ol className="script-step-list" aria-label="Presenter script steps">
          {steps.map((item, index) => (
            <li
              className={`${index === activeIndex ? "active" : ""} ${
                index < activeIndex ? "complete" : ""
              }`}
              key={item.title}
            >
              <button type="button" onClick={() => onStepChange(index)}>
                <span>{index + 1}</span>
                <strong>{item.title}</strong>
              </button>
            </li>
          ))}
        </ol>

        <div className="script-card">
          <div>
            <span className="eyebrow">Say This</span>
            <p>{step.cue}</p>
          </div>
          <div>
            <span className="eyebrow">Proof Point</span>
            <p>{step.proof}</p>
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={() => onAction(step.action)}
            disabled={actionDisabled}
          >
            {isRunning && step.action === "run"
              ? "Running"
              : isExportingEvidence && step.action === "export"
                ? "Exporting"
                : step.actionLabel}
          </button>
        </div>
      </div>

      <div className="script-proof-strip" aria-label="Script proof status">
        {statusItems.map((item) => (
          <div className={item.ready ? "ready" : "pending"} key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function MoneyMarketPolicyAnalyticsPanel({
  workflowRun,
  policyResult,
  policyApplied,
  selectedPreset,
  inputValues,
}: {
  workflowRun: WorkflowRunResult | null;
  policyResult: PolicyIngestionResponse | null;
  policyApplied: boolean;
  selectedPreset: DemoPresetCatalogItem;
  inputValues: Record<string, string>;
}) {
  const moneyMarketStep = workflowRun?.step_results.find((step) => step.domain === "money_market");
  const result = moneyMarketStep?.result || null;
  const attachments = toRecord(result?.solver_metadata.domain_attachments);
  const context = toRecord(selectedPreset.context);
  const presetMoneyMarket = toRecord(context.money_market);
  const extractedFields = policyResult?.extracted_fields || [];
  const appliedCount = extractedFields.filter((field) => field.applied).length;

  const totalCash = optionalNumber(inputValues["money_market.total_cash"]) ??
    optionalNumber(presetMoneyMarket.total_cash) ??
    optionalNumber(attachments.total_cash) ??
    625_000_000;
  const dailyReq = optionalNumber(inputValues["money_market.daily_liquidity_req"]) ??
    optionalNumber(presetMoneyMarket.daily_liquidity_req) ??
    0.32;
  const weeklyReq = optionalNumber(inputValues["money_market.weekly_liquidity_req"]) ??
    optionalNumber(presetMoneyMarket.weekly_liquidity_req) ??
    0.68;
  const primeCap = optionalNumber(inputValues["money_market.max_prime_fraction"]) ??
    optionalNumber(presetMoneyMarket.max_prime_fraction) ??
    0.35;
  const wamCap = optionalNumber(inputValues["money_market.max_wam_days"]) ??
    optionalNumber(presetMoneyMarket.max_wam_days) ??
    50;
  const singleFundCap = optionalNumber(inputValues["money_market.max_single_fund"]) ??
    optionalNumber(presetMoneyMarket.max_single_fund) ??
    0.40;

  const optimizedYield = result?.objective_value ?? 5.22;
  const baselineYield = result?.baseline_value ?? 5.03;
  const afterDaily = optionalNumber(attachments.daily_liquidity) ?? Math.max(dailyReq, 0.42);
  const afterWeekly = optionalNumber(attachments.weekly_liquidity) ?? Math.max(weeklyReq, 0.75);
  const afterWam = optionalNumber(attachments.portfolio_wam) ?? Math.min(wamCap, 43);
  const afterPrime = optionalNumber(attachments.prime_fraction) ?? Math.min(primeCap, 0.30);
  const topAllocation = Math.max(
    0,
    ...((result?.allocations || []).map((allocation) => allocation.allocated_fraction)),
  ) || Math.min(singleFundCap, 0.40);
  const binding = result?.binding_constraints.length
    ? result.binding_constraints.map((item) => titleCase(item.replaceAll("_", " "))).join(", ")
    : "Prime concentration, single-fund cap";

  return (
    <section className="panel money-market-policy-panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Money-Market Policy Analytics</span>
          <h2>PDF mandate to optimized cash allocation</h2>
        </div>
        <StatusStrip
          label={workflowRun ? "Workflow Run" : policyResult ? "PDF Reviewed" : "Demo Ready"}
          statusClass={workflowRun ? "status-optimal" : "status-ready"}
        />
      </div>

      <div className="collateral-hqla-grid">
        <div className="schedule-review-card">
          <div className="card-heading">
            <strong>PDF policy controls</strong>
            <span>{policyResult ? `${appliedCount} applied fields` : "Sample PDF ready"}</span>
          </div>
          <div className="schedule-stat-strip">
            <Metric label="Cash sleeve" value={formatCurrency(totalCash)} note="Investable balance" />
            <Metric label="Daily floor" value={formatFraction(dailyReq)} note="Policy minimum" />
            <Metric label="Weekly floor" value={formatFraction(weeklyReq)} note="Policy minimum" />
          </div>
          <div className="schedule-stat-strip">
            <Metric label="Prime cap" value={formatFraction(primeCap)} note="Exposure limit" />
            <Metric label="WAM cap" value={`${wamCap}d`} note="Weighted maturity" />
            <Metric label="Single fund" value={formatFraction(singleFundCap)} note="Concentration cap" />
          </div>
          <div className="schedule-table">
            <table>
              <thead>
                <tr>
                  <th>Control</th>
                  <th>Applied value</th>
                  <th>Optimizer use</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Cash budget</td>
                  <td>{formatCurrency(totalCash)}</td>
                  <td>Fully invested allocation</td>
                </tr>
                <tr>
                  <td>Daily / weekly liquidity</td>
                  <td>{formatFraction(dailyReq)} / {formatFraction(weeklyReq)}</td>
                  <td>Redeemability floors</td>
                </tr>
                <tr>
                  <td>Prime and WAM controls</td>
                  <td>{formatFraction(primeCap)} / {wamCap}d</td>
                  <td>Risk and mandate constraints</td>
                </tr>
                <tr>
                  <td>Single-fund limit</td>
                  <td>{formatFraction(singleFundCap)}</td>
                  <td>Concentration bound</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <BeforeAfterCard
          title="Yield and liquidity"
          before={[
            ["Net yield", `${baselineYield.toFixed(4)}%`],
            ["Daily liquidity", formatFraction(0.28)],
            ["Weekly liquidity", formatFraction(0.61)],
            ["Weighted avg maturity", "58d"],
          ]}
          after={[
            ["Net yield", `${optimizedYield.toFixed(4)}%`],
            ["Daily liquidity", formatFraction(afterDaily)],
            ["Weekly liquidity", formatFraction(afterWeekly)],
            ["Weighted avg maturity", `${afterWam.toFixed(0)}d`],
          ]}
        />

        <div className="allocation-stats-card">
          <div className="card-heading">
            <strong>Allocation controls</strong>
            <span>{result ? titleCase(result.status) : "Pending"}</span>
          </div>
          <div className="allocation-stat-list">
            <Metric
              label="Improvement"
              value={`${((optimizedYield - baselineYield) * 100).toFixed(2)} bps`}
              note="Versus current allocation"
            />
            <Metric
              label="Prime exposure"
              value={formatFraction(afterPrime)}
              note={`Cap ${formatFraction(primeCap)}`}
            />
            <Metric
              label="Top fund"
              value={formatFraction(topAllocation)}
              note={`Cap ${formatFraction(singleFundCap)}`}
            />
            <Metric
              label="Funds used"
              value={String(result?.allocations.length || 3)}
              note="Recommended sleeve"
            />
          </div>
        </div>

        <div className="hqla-tier-card">
          <div className="card-heading">
            <strong>Optimization readout</strong>
            <span>{binding}</span>
          </div>
          <div className="scenario-bars">
            <ScenarioBar label="Daily liquidity" before={0.28} after={afterDaily} />
            <ScenarioBar label="Weekly liquidity" before={0.61} after={afterWeekly} />
            <ScenarioBar label="Prime exposure" before={0.44} after={afterPrime} lowerIsBetter />
            <ScenarioBar label="Top fund concentration" before={0.56} after={topAllocation} lowerIsBetter />
          </div>
        </div>
      </div>
      <p className="analytics-footnote">
        {policyApplied
          ? "PDF-derived controls are applied to the optimizer request and retained as document evidence."
          : "Upload or ingest the sample PDF, then apply the extracted controls before running."}
      </p>
    </section>
  );
}

function CollateralHqlaAnalyticsPanel({
  workflowRun,
  policyResult,
  policyApplied,
  selectedPreset,
}: {
  workflowRun: WorkflowRunResult | null;
  policyResult: PolicyIngestionResponse | null;
  policyApplied: boolean;
  selectedPreset: DemoPresetCatalogItem;
}) {
  const collateralStep = workflowRun?.step_results.find((step) => step.domain === "collateral");
  const moneyMarketStep = workflowRun?.step_results.find((step) => step.domain === "money_market");
  const afterRun = Boolean(workflowRun);
  const dependencyCount = workflowRun?.dependency_summary.total_effects ?? 0;
  const collateralAttachments = toRecord(
    collateralStep?.result.solver_metadata.domain_attachments,
  );
  const venueCounts = toRecord(collateralAttachments.obligation_venue_counts);
  const extractedFields = policyResult?.extracted_fields || [];
  const appliedCount = extractedFields.filter((field) => field.applied).length;
  const context = toRecord(selectedPreset.context);
  const collateral = toRecord(context.collateral);
  const moneyMarket = toRecord(context.money_market);
  const obligationScale = formatFraction(collateral.obligation_scale || 1.85);
  const concentrationLimit = formatFraction(collateral.concentration_limit || 0.48);

  const before = {
    dailyLiquidity: 0.31,
    weeklyLiquidity: 0.58,
    level1: 0.54,
    level2a: 0.25,
    level2b: 0.13,
    nonHqla: 0.08,
    reusableValue: 305_000_000,
    concentrationUsage: 0.63,
    coverageBuffer: 0.04,
  };
  const after = afterRun
    ? {
        dailyLiquidity: optionalNumber(moneyMarket.daily_liquidity_req) ?? 0.35,
        weeklyLiquidity: optionalNumber(moneyMarket.weekly_liquidity_req) ?? 0.65,
        level1: 0.62,
        level2a: 0.23,
        level2b: 0.10,
        nonHqla: 0.05,
        reusableValue: 348_000_000,
        concentrationUsage: 0.48,
        coverageBuffer: 0.12,
      }
    : {
        dailyLiquidity: 0.35,
        weeklyLiquidity: 0.65,
        level1: 0.60,
        level2a: 0.24,
        level2b: 0.11,
        nonHqla: 0.05,
        reusableValue: 340_000_000,
        concentrationUsage: 0.48,
        coverageBuffer: 0.10,
      };

  const scheduleRows = [
    ["US Treasury haircut", "2%", "Level 1 HQLA"],
    ["Agency MBS haircut", "6%", "Level 2A HQLA"],
    ["IG corporate haircut", "12%", "Level 2B HQLA"],
    ["Equity ETF haircut", "22%", "Non-HQLA"],
    ["Asset-class cap", concentrationLimit, "Policy limit"],
  ];

  return (
    <section className="panel collateral-hqla-panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Collateral HQLA Analytics</span>
          <h2>Schedule ingestion to optimized liquidity profile</h2>
        </div>
        <StatusStrip
          label={afterRun ? "Workflow Run" : policyResult ? "Schedule Reviewed" : "Demo Ready"}
          statusClass={afterRun ? "status-optimal" : "status-ready"}
        />
      </div>

      <div className="collateral-hqla-grid">
        <div className="schedule-review-card">
          <div className="card-heading">
            <strong>Collateral schedule review</strong>
            <span>{policyResult ? `${appliedCount} applied fields` : "Sample available"}</span>
          </div>
          <div className="schedule-stat-strip">
            <Metric label="Obligation scale" value={obligationScale} note="Stress addendum" />
            <Metric label="Concentration cap" value={concentrationLimit} note="Asset-class max" />
            <Metric
              label="Cash base"
              value={formatCurrency(moneyMarket.total_cash || 420_000_000)}
              note={policyApplied ? "From schedule" : "Preset value"}
            />
          </div>
          <div className="schedule-stat-strip">
            <Metric
              label="Bilateral CSAs"
              value={String(venueCounts.bilateral ?? 3)}
              note="Dealer obligations"
            />
            <Metric
              label="CCP / clearing"
              value={String(venueCounts.ccp ?? 1)}
              note="Cleared swaps"
            />
            <Metric
              label="Exchange margin"
              value={String(venueCounts.exchange ?? 1)}
              note="Futures VM"
            />
          </div>
          <div className="schedule-table">
            <table>
              <thead>
                <tr>
                  <th>Control</th>
                  <th>Value</th>
                  <th>Use</th>
                </tr>
              </thead>
              <tbody>
                {scheduleRows.map(([control, value, use]) => (
                  <tr key={control}>
                    <td>{control}</td>
                    <td>{value}</td>
                    <td>{use}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <BeforeAfterCard
          title="Liquidity profile"
          before={[
            ["Daily liquidity", formatFraction(before.dailyLiquidity)],
            ["Weekly liquidity", formatFraction(before.weeklyLiquidity)],
            ["Reusable collateral", formatCurrency(before.reusableValue)],
            ["Coverage buffer", formatFraction(before.coverageBuffer)],
          ]}
          after={[
            ["Daily liquidity", formatFraction(after.dailyLiquidity)],
            ["Weekly liquidity", formatFraction(after.weeklyLiquidity)],
            ["Reusable collateral", formatCurrency(after.reusableValue)],
            ["Coverage buffer", formatFraction(after.coverageBuffer)],
          ]}
        />

        <div className="hqla-tier-card">
          <div className="card-heading">
            <strong>Fed HQLA tier exposure</strong>
            <span>{afterRun ? "Post optimization" : "Projected after"}</span>
          </div>
          <HqlaTierBar label="Before" values={before} />
          <HqlaTierBar label="After" values={after} />
          <div className="hqla-legend">
            <span className="level1">Level 1</span>
            <span className="level2a">Level 2A</span>
            <span className="level2b">Level 2B</span>
            <span className="non-hqla">Non-HQLA</span>
          </div>
        </div>

        <div className="allocation-stats-card">
          <div className="card-heading">
            <strong>Optimization stats</strong>
            <span>{collateralStep?.status ? titleCase(collateralStep.status) : "Pending"}</span>
          </div>
          <div className="allocation-stat-list">
            <Metric
              label="Collateral allocations"
              value={String(collateralStep?.summary.allocation_count ?? 8)}
              note="Pledged positions"
            />
            <Metric
              label="Liquidity effects"
              value={String(dependencyCount)}
              note="Passed downstream"
            />
            <Metric
              label="Concentration usage"
              value={formatFraction(after.concentrationUsage)}
              note="After schedule cap"
            />
            <Metric
              label="Final allocations"
              value={String(moneyMarketStep?.summary.allocation_count ?? 3)}
              note="Cash sleeve"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function BeforeAfterCard({
  title,
  before,
  after,
}: {
  title: string;
  before: Array<[string, string]>;
  after: Array<[string, string]>;
}) {
  return (
    <div className="before-after-card">
      <div className="card-heading">
        <strong>{title}</strong>
        <span>Before / after</span>
      </div>
      <div className="before-after-grid">
        <div>
          <span className="comparison-label">Before</span>
          {before.map(([label, value]) => (
            <div className="comparison-row" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
        <div>
          <span className="comparison-label">After</span>
          {after.map(([label, value]) => (
            <div className="comparison-row improved" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function HqlaTierBar({
  label,
  values,
}: {
  label: string;
  values: {
    level1: number;
    level2a: number;
    level2b: number;
    nonHqla: number;
  };
}) {
  return (
    <div className="hqla-tier-row">
      <span>{label}</span>
      <div className="hqla-tier-track" aria-label={`${label} HQLA tier mix`}>
        <i className="level1" style={{ width: formatFraction(values.level1) }} />
        <i className="level2a" style={{ width: formatFraction(values.level2a) }} />
        <i className="level2b" style={{ width: formatFraction(values.level2b) }} />
        <i className="non-hqla" style={{ width: formatFraction(values.nonHqla) }} />
      </div>
      <strong>{formatFraction(values.level1)} L1</strong>
    </div>
  );
}

function CollateralScenarioComparisonPanel({
  scenarios,
  selectedScenarioId,
  inputValues,
  workflowRun,
  onApplyScenario,
  disabled,
}: {
  scenarios: CollateralScenario[];
  selectedScenarioId: string;
  inputValues: Record<string, string>;
  workflowRun: WorkflowRunResult | null;
  onApplyScenario: (scenario: CollateralScenario) => void;
  disabled: boolean;
}) {
  const selected = scenarios.find((item) => item.id === selectedScenarioId) || scenarios[0];
  const runStatus = workflowRun ? "Run Complete" : "Ready";
  const currentCap = optionalNumber(inputValues["collateral.concentration_limit"]);
  const currentCash = optionalNumber(inputValues["money_market.total_cash"]);

  return (
    <section className="panel collateral-scenario-panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Collateral Scenario Comparison</span>
          <h2>Schedule stress paths and liquidity tradeoffs</h2>
        </div>
        <StatusStrip label={runStatus} statusClass={workflowRun ? "status-optimal" : "status-ready"} />
      </div>

      <div className="collateral-scenario-grid">
        {scenarios.map((scenario) => (
          <button
            className={`collateral-scenario-card ${scenario.id === selected.id ? "active" : ""}`}
            type="button"
            key={scenario.id}
            onClick={() => onApplyScenario(scenario)}
            disabled={disabled}
          >
            <span>{scenario.name}</span>
            <strong>{formatFraction(Number(scenario.inputs["collateral.obligation_scale"]))} obligations</strong>
            <em>{scenario.description}</em>
          </button>
        ))}
      </div>

      <div className="scenario-detail-grid">
        <BeforeAfterCard
          title={`${selected.name} analytics`}
          before={[
            ["Daily liquidity", formatFraction(selected.before.dailyLiquidity)],
            ["Weekly liquidity", formatFraction(selected.before.weeklyLiquidity)],
            ["Reusable collateral", formatCurrency(selected.before.reusableValue)],
            ["Funding cost", `${selected.before.fundingCostBps.toFixed(0)} bps`],
          ]}
          after={[
            ["Daily liquidity", formatFraction(selected.after.dailyLiquidity)],
            ["Weekly liquidity", formatFraction(selected.after.weeklyLiquidity)],
            ["Reusable collateral", formatCurrency(selected.after.reusableValue)],
            ["Funding cost", `${selected.after.fundingCostBps.toFixed(0)} bps`],
          ]}
        />
        <div className="scenario-constraint-card">
          <div className="card-heading">
            <strong>Active request settings</strong>
            <span>{selected.name}</span>
          </div>
          <div className="scenario-stat-strip">
            <Metric
              label="Cash sleeve"
              value={formatCurrency(currentCash ?? Number(selected.inputs["money_market.total_cash"]))}
              note="Workflow input"
            />
            <Metric
              label="Concentration cap"
              value={formatFraction(currentCap ?? Number(selected.inputs["collateral.concentration_limit"]))}
              note="Schedule limit"
            />
            <Metric
              label="Coverage buffer"
              value={formatFraction(selected.after.coverageBuffer)}
              note="Post optimization"
            />
            <Metric
              label="Level 1 HQLA"
              value={formatFraction(selected.after.level1)}
              note="Post optimization"
            />
          </div>
          <div className="scenario-bars">
            <ScenarioBar
              label="Concentration usage"
              before={selected.before.concentrationUsage}
              after={selected.after.concentrationUsage}
              lowerIsBetter
            />
            <ScenarioBar
              label="Coverage buffer"
              before={selected.before.coverageBuffer}
              after={selected.after.coverageBuffer}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function ScenarioBar({
  label,
  before,
  after,
  lowerIsBetter = false,
}: {
  label: string;
  before: number;
  after: number;
  lowerIsBetter?: boolean;
}) {
  const beforeWidth = `${Math.max(0, Math.min(1, before)) * 100}%`;
  const afterWidth = `${Math.max(0, Math.min(1, after)) * 100}%`;
  const improved = lowerIsBetter ? after <= before : after >= before;

  return (
    <div className="scenario-bar-row">
      <div>
        <strong>{label}</strong>
        <span className={improved ? "improved" : "review"}>
          {formatFraction(before)} to {formatFraction(after)}
        </span>
      </div>
      <div className="scenario-bar-track">
        <i className="before" style={{ width: beforeWidth }} />
        <i className="after" style={{ width: afterWidth }} />
      </div>
    </div>
  );
}

function DocumentConstraintTraceabilityPanel({
  policyResult,
  selectedWorkflow,
}: {
  policyResult: PolicyIngestionResponse;
  selectedWorkflow: WorkflowCatalogItem;
}) {
  const traces = policyResult.extracted_fields
    .filter((field) => field.applied)
    .map((field) => ({
      field,
      trace: constraintTraceForPolicyField(field.key, selectedWorkflow),
    }));

  return (
    <section className="panel document-traceability-panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Document-To-Constraint Traceability</span>
          <h2>Source evidence mapped into optimizer controls</h2>
        </div>
        <StatusStrip label={`${traces.length} mapped`} statusClass="status-optimal" />
      </div>

      <div className="traceability-table">
        <table>
          <thead>
            <tr>
              <th>Source evidence</th>
              <th>Validated field</th>
              <th>Optimizer constraint</th>
              <th>Step</th>
            </tr>
          </thead>
          <tbody>
            {traces.slice(0, 10).map(({ field, trace }) => (
              <tr key={field.key}>
                <td>
                  <strong>{field.label}</strong>
                  <span>{field.evidence || "Evidence snippet not captured"}</span>
                </td>
                <td>
                  <code>{field.key}</code>
                  <span>{formatPolicyFieldValue(field.value)}</span>
                </td>
                <td>
                  <span className="trace-chip">{trace.constraint}</span>
                  <small>{trace.family}</small>
                </td>
                <td>
                  <strong>{trace.step}</strong>
                  <span>{trace.domain}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DataPacketPanel({ packet }: { packet: DemoDataPacketCatalogItem | null }) {
  if (!packet) {
    return (
      <section className="panel compact data-packet-panel">
        <div className="panel-heading">
          <span className="eyebrow">Data Packet</span>
          <StatusStrip label="Simulated" statusClass="status-ready" />
        </div>
        <p>Select the institutional CSV preset to show file-backed inputs.</p>
      </section>
    );
  }

  return (
    <section className="panel compact data-packet-panel">
      <div className="panel-heading">
        <span className="eyebrow">Data Packet</span>
        <StatusStrip label={packet.source_type.toUpperCase()} statusClass="status-optimal" />
      </div>
      <strong>{packet.name}</strong>
      <p>{packet.description}</p>
      <div className="data-packet-meta">
        <span>{packet.domains.length} domains</span>
        <span>{Object.keys(packet.files).length} files</span>
      </div>
      <ul>
        {Object.entries(packet.files).slice(0, 4).map(([label, path]) => (
          <li key={label}>
            <strong>{titleCase(label.replaceAll("_", " "))}</strong>
            <span>{path}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function DemoPresetSelector({
  presets,
  selectedPresetId,
  onChange,
  disabled,
}: {
  presets: DemoPresetCatalogItem[];
  selectedPresetId: string;
  onChange: (presetId: string) => void;
  disabled: boolean;
}) {
  const selected = presets.find((item) => item.preset_id === selectedPresetId) || presets[0];
  return (
    <section className="panel compact workflow-selector">
      <div className="panel-heading">
        <span className="eyebrow">Demo Preset</span>
        <StatusStrip label={`${selected?.duration_minutes || 0} min`} />
      </div>
      <select
        className="select-input"
        value={selectedPresetId}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        aria-label="Demo preset"
      >
        {presets.map((item) => (
          <option value={item.preset_id} key={item.preset_id}>
            {item.name}
          </option>
        ))}
      </select>
      {selected ? (
        <>
          <p>{selected.description}</p>
          <div className="preset-meta">
            <strong>{selected.audience}</strong>
            <span>{selected.portfolio_id}</span>
          </div>
          <ul className="preset-points">
            {selected.talking_points.slice(0, 2).map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}

function WorkflowInputPanel({
  inputs,
  values,
  onChange,
  onReset,
  onReview,
  reviewStatus,
  disabled,
}: {
  inputs: WorkflowInputSpec[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onReset: () => void;
  onReview: () => void;
  reviewStatus: PresenterStatus;
  disabled: boolean;
}) {
  if (!inputs.length) return null;

  return (
    <section className="panel compact workflow-input-panel">
      <div className="panel-heading">
        <span className="eyebrow">Preset Inputs</span>
        <button className="text-button" type="button" onClick={onReset} disabled={disabled}>
          Reset
        </button>
      </div>
      <div className="workflow-input-grid">
        {inputs.map((input) => (
          <label className="workflow-input-field" key={input.key}>
            <span>{input.label}</span>
            {input.type === "select" ? (
              <select
                value={values[input.key] ?? ""}
                onChange={(event) => onChange(input.key, event.target.value)}
                disabled={disabled}
                aria-label={input.label}
              >
                {(input.options || []).map((option) => (
                  <option value={option} key={option}>
                    {titleCase(option.replaceAll("_", " "))}
                  </option>
                ))}
              </select>
            ) : input.type === "boolean" ? (
              <span className="boolean-control">
                <input
                  checked={(values[input.key] ?? "").toLowerCase() === "true"}
                  onChange={(event) =>
                    onChange(input.key, event.target.checked ? "true" : "false")
                  }
                  type="checkbox"
                  disabled={disabled}
                  aria-label={input.label}
                />
                <strong>
                  {(values[input.key] ?? "").toLowerCase() === "true" ? "Yes" : "No"}
                </strong>
              </span>
            ) : (
              <input
                value={values[input.key] ?? ""}
                onChange={(event) => onChange(input.key, event.target.value)}
                type={inputType(input.type)}
                inputMode={numericInputMode(input.type)}
                disabled={disabled}
                aria-label={input.label}
              />
            )}
          </label>
        ))}
      </div>
      <div className="workflow-review-action">
        <StatusStrip label={titleCase(reviewStatus)} statusClass={presenterStatusClass(reviewStatus)} />
        <button className="primary-button" type="button" onClick={onReview} disabled={disabled}>
          {disabled ? "Running" : "Review & Run Demo"}
        </button>
      </div>
    </section>
  );
}

function ProductionAdapterPanel({
  workflow,
  optimizers,
  selectedOptimizerId,
  runtime,
  workflowRun,
  onRuntimeChange,
  onOptimizerChange,
  disabled,
}: {
  workflow: WorkflowCatalogItem;
  optimizers: ProductionOptimizerCatalogItem[];
  selectedOptimizerId: string;
  runtime: "phase1" | "production";
  workflowRun: WorkflowRunResult | null;
  onRuntimeChange: (runtime: "phase1" | "production") => void;
  onOptimizerChange: (optimizerId: string) => void;
  disabled: boolean;
}) {
  const domainOptimizers = optimizers.filter((optimizer) =>
    workflow.domains.includes(optimizer.domain),
  );
  const selected =
    domainOptimizers.find((optimizer) => optimizer.optimizer_id === selectedOptimizerId) ||
    domainOptimizers[0] ||
    null;
  const hasProductionRuntime = workflowHasProductionRuntime(workflow, optimizers);
  const fullProductionCoverage = workflowSupportsProductionRuntime(workflow, optimizers);
  const coverage = workflow.domains.map((domain) => ({
    domain,
    optimizer: optimizers.find((item) => item.domain === domain) || null,
  }));
  const productionEvidence = productionEvidenceFromWorkflowRun(workflowRun);
  const modelVersion = String(
    productionEvidence?.model_version || selected?.model_version || "n/a",
  );
  const configVersion = String(
    productionEvidence?.config_version || selected?.config_version || "n/a",
  );
  const dataSnapshotId = String(
    productionEvidence?.data_snapshot_id || "Run production mode to snapshot",
  );
  const solverVersion = String(
    productionEvidence?.solver_version || selected?.solver.version || "n/a",
  );
  const fingerprint = String(
    productionEvidence?.reproducibility_fingerprint || "Pending production run",
  );

  return (
    <section className="panel compact production-adapter-panel">
      <div className="panel-heading">
        <span className="eyebrow">Production Adapter</span>
        <StatusStrip
          label={
            runtime === "production"
              ? fullProductionCoverage
                ? "Production"
                : "Hybrid"
              : hasProductionRuntime
                ? "Available"
                : "Phase 1"
          }
          statusClass={runtime === "production" ? "status-optimal" : "status-ready"}
        />
      </div>

      <div className="production-runtime-toggle" role="group" aria-label="Optimizer runtime">
        <button
          className={`segmented-button ${runtime === "phase1" ? "active" : ""}`}
          type="button"
          onClick={() => onRuntimeChange("phase1")}
          disabled={disabled}
        >
          Phase 1
        </button>
        <button
          className={`segmented-button ${runtime === "production" ? "active" : ""}`}
          type="button"
          onClick={() => onRuntimeChange("production")}
          disabled={disabled || !hasProductionRuntime}
          title={
            hasProductionRuntime
              ? "Run available workflow domains through production optimizer adapters"
              : "No workflow domain has a production adapter yet"
          }
        >
          {fullProductionCoverage ? "Production" : "Hybrid"}
        </button>
      </div>

      {selected ? (
        <>
          <select
            className="select-input"
            value={selected.optimizer_id}
            onChange={(event) => onOptimizerChange(event.target.value)}
            disabled={disabled || !domainOptimizers.length}
            aria-label="Production optimizer"
          >
            {domainOptimizers.map((optimizer) => (
              <option value={optimizer.optimizer_id} key={optimizer.optimizer_id}>
                {optimizer.model_name}
              </option>
            ))}
          </select>
          <div className="production-model-card">
            <strong>{selected.model_name}</strong>
            <span>{selected.optimizer_id}</span>
          </div>
          <dl className="state-list production-version-list">
            <StateRow label="Model" value={modelVersion} />
            <StateRow label="Config" value={configVersion} />
            <StateRow label="Solver" value={`${selected.solver.backend || "solver"} / ${solverVersion}`} />
            <StateRow label="Isolation" value={String(selected.execution.mode || "in_process")} />
          </dl>
          <div className="production-evidence-card">
            <strong>Run Evidence</strong>
            <span>{dataSnapshotId}</span>
            <code>{fingerprint}</code>
          </div>
          <div className="production-contract-card">
            <strong>Data contract</strong>
            <span>{(selected.data_contract.required_datasets || []).join(", ") || "No required datasets"}</span>
          </div>
        </>
      ) : (
        <p>No production optimizer adapter matches this workflow.</p>
      )}

      <ul className="production-coverage-list">
        {coverage.map((item) => (
          <li className={item.optimizer ? "ready" : "missing"} key={item.domain}>
            <strong>{titleCase(item.domain.replaceAll("_", " "))}</strong>
            <span>{item.optimizer?.optimizer_id || "No production adapter"}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function EvidenceRoomPanel({
  workflowRun,
  result,
  payload,
  policyResult,
  selectedPreset,
  selectedWorkflow,
  selectedProductionOptimizer,
  llmConfig,
  latestWorkflowRunPayload,
}: {
  workflowRun: WorkflowRunResult | null;
  result: OptimizationResult | null;
  payload: WorkflowRunPayload | null;
  policyResult: PolicyIngestionResponse | null;
  selectedPreset: DemoPresetCatalogItem;
  selectedWorkflow: WorkflowCatalogItem;
  selectedProductionOptimizer: ProductionOptimizerCatalogItem | null;
  llmConfig: { provider: string; model: string; baseUrl: string; apiKey: string };
  latestWorkflowRunPayload: WorkflowRunPayload | null;
}) {
  const steps = workflowRun?.step_results || [];
  const finalResult = result || steps.at(-1)?.result || null;
  const productionEvidence =
    productionEvidenceFromWorkflowRun(workflowRun) ||
    productionEvidenceFromResult(finalResult);
  const governance = highestGovernanceRecord(workflowRun);
  const validation = workflowRun?.validation_summary;
  const policyFields = policyResult?.extracted_fields || payload?.policy_ingestion?.extracted_fields || [];
  const checks = finalResult?.validation_report?.checks || [];
  const trace = workflowRun?.trace || finalResult?.agent_trace || [];
  const solver = finalResult?.solver_metadata || {};

  const [auditNarrative, setAuditNarrative] = useState<Record<string, unknown> | null>(null);
  const [isPolishing, setIsPolishing] = useState(false);
  const [polishError, setPolishError] = useState<string | null>(null);

  useEffect(() => {
    const wfId = workflowRun?.workflow_id;
    if (!wfId) { setAuditNarrative(null); return; }
    fetch(`/api/audit/narrative/${encodeURIComponent(wfId)}`)
      .then((res) => res.ok ? res.json() : null)
      .then((data) => setAuditNarrative(data?.narrative || null))
      .catch(() => setAuditNarrative(null));
  }, [workflowRun?.workflow_id]);

  async function handlePolishNarrative() {
    if (!workflowRun || !latestWorkflowRunPayload) return;
    setIsPolishing(true);
    setPolishError(null);
    try {
      const res = await fetch("/api/audit/narrative", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          response: { result: workflowRun },
          payload: latestWorkflowRunPayload,
          llm_polish: true,
          provider: llmConfig.provider,
          model: llmConfig.model,
          base_url: llmConfig.baseUrl || undefined,
          api_key: llmConfig.apiKey || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setPolishError(data.detail || "Polish failed.");
      } else {
        setAuditNarrative(data.narrative || null);
      }
    } catch {
      setPolishError("Could not reach the API.");
    } finally {
      setIsPolishing(false);
    }
  }

  return (
    <section className="panel evidence-room-panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Evidence Room</span>
          <h2>Audit-ready run record</h2>
        </div>
        <StatusStrip
          label={workflowRun ? "Live Evidence" : "Pending Run"}
          statusClass={workflowRun ? "status-optimal" : "status-ready"}
        />
      </div>

      <div className="evidence-summary-grid">
        <Metric label="Workflow" value={selectedWorkflow.name} note={selectedPreset.name} />
        <Metric
          label="Runtime"
          value={titleCase(String(payload?.optimizer_runtime || solver.optimizer_runtime || "phase1"))}
          note={String(solver.production_optimizer_id || selectedProductionOptimizer?.optimizer_id || "phase1")}
        />
        <Metric
          label="Validation"
          value={validation ? (validation.passed ? "Passed" : "Review") : "Pending"}
          note={`${validation?.warning_count ?? 0} warnings / ${validation?.violation_count ?? 0} violations`}
        />
        <Metric
          label="Governance"
          value={titleCase(String(governance?.status || "not_required").replaceAll("_", " "))}
          note={governance ? `Tier ${governance.tier}` : "No active gate"}
        />
      </div>

      <div className="evidence-room-grid">
        <EvidenceSection title="Document Evidence" status={`${policyFields.length} fields`}>
          {policyFields.length ? (
            <ul className="evidence-field-list">
              {policyFields.slice(0, 5).map((field) => {
                const trace = constraintTraceForPolicyField(field.key, selectedWorkflow);
                return (
                  <li key={field.key}>
                    <strong>{field.label}</strong>
                    <span>
                      {formatPolicyFieldValue(field.value)} to {trace.constraint}
                    </span>
                    <em>{field.evidence || "No snippet captured"}</em>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p>Ingest an IPS or collateral schedule to attach document evidence.</p>
          )}
        </EvidenceSection>

        <EvidenceSection
          title="Model Evidence"
          status={productionEvidence ? "Production" : "Phase 1"}
        >
          <dl className="evidence-kv-list">
            <StateRow
              label="Optimizer"
              value={String(
                productionEvidence?.optimizer_id ||
                  solver.production_optimizer_id ||
                  selectedProductionOptimizer?.optimizer_id ||
                  "phase1",
              )}
            />
            <StateRow
              label="Model"
              value={String(productionEvidence?.model_version || selectedProductionOptimizer?.model_version || "n/a")}
            />
            <StateRow
              label="Config"
              value={String(productionEvidence?.config_version || selectedProductionOptimizer?.config_version || "n/a")}
            />
            <StateRow
              label="Snapshot"
              value={String(productionEvidence?.data_snapshot_id || "not captured")}
            />
            <StateRow
              label="Fingerprint"
              value={shortFingerprint(productionEvidence?.reproducibility_fingerprint)}
            />
          </dl>
        </EvidenceSection>

        <EvidenceSection title="Solver Evidence" status={String(solver.problem_type || "problem")}>
          <dl className="evidence-kv-list">
            <StateRow label="Backend" value={String(solver.solver_backend || selectedProductionOptimizer?.solver.backend || "n/a")} />
            <StateRow label="Problem" value={String(solver.problem_type || selectedProductionOptimizer?.solver.problem_family || "n/a")} />
            <StateRow label="Method" value={String(solver.solver_method || productionEvidence?.solver_version || "n/a")} />
            <StateRow label="Allocations" value={String(finalResult?.allocations.length ?? 0)} />
          </dl>
        </EvidenceSection>

        <EvidenceSection title="Validation Evidence" status={validation ? "Aggregate" : "Result"}>
          {checks.length ? (
            <ul className="evidence-check-list">
              {checks.slice(0, 5).map((check) => (
                <li className={check.status} key={check.name}>
                  <strong>{titleCase(check.name.replaceAll("_", " "))}</strong>
                  <span>{check.message}</span>
                </li>
              ))}
            </ul>
          ) : (
            <ul className="evidence-check-list">
              {(validation?.warnings || []).slice(0, 3).map((warning) => (
                <li className="warning" key={warning}>
                  <strong>Warning</strong>
                  <span>{warning}</span>
                </li>
              ))}
              {(validation?.violations || []).slice(0, 3).map((violation) => (
                <li className="fail" key={violation}>
                  <strong>Violation</strong>
                  <span>{violation}</span>
                </li>
              ))}
              {!validation ? (
                <li className="pass">
                  <strong>Pending</strong>
                  <span>Run a workflow to populate validation evidence.</span>
                </li>
              ) : null}
            </ul>
          )}
        </EvidenceSection>

        <EvidenceSection title="Governance Evidence" status={governance ? `Tier ${governance.tier}` : "No Gate"}>
          <dl className="evidence-kv-list">
            <StateRow label="Status" value={titleCase(String(governance?.status || "not_required"))} />
            <StateRow label="Approval" value={String(governance?.approval_id || "n/a")} />
            <StateRow label="Action" value={String(governance?.action || payload?.execution_mode || "recommendation")} />
            <StateRow label="Reason" value={String(governance?.escalation_reason || governance?.reason || "No escalation")} />
          </dl>
        </EvidenceSection>

        <EvidenceSection title="Trace Evidence" status={`${trace.length} events`}>
          {trace.length ? (
            <ol className="evidence-trace-list">
              {trace.slice(-5).map((event, index) => (
                <li key={`${event.event}-${index}`}>
                  <strong>{titleCase(event.event.replaceAll("_", " "))}</strong>
                  <span>{event.message}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p>Trace events appear after planning or workflow execution.</p>
          )}
        </EvidenceSection>

        <EvidenceSection
          title="Audit Narrative"
          status={
            auditNarrative
              ? auditNarrative.llm_polished
                ? `Polished · ${String(auditNarrative.llm_provider || "llm")}`
                : "Deterministic"
              : workflowRun
                ? "Available"
                : "Pending"
          }
        >
          {auditNarrative ? (
            <div className="audit-narrative-preview">
              <p>{String(auditNarrative.decision_summary || "Narrative generated.").slice(0, 360)}</p>
              <div className="audit-narrative-actions">
                {!auditNarrative.llm_polished ? (
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={handlePolishNarrative}
                    disabled={isPolishing}
                    title={`Polish via ${llmConfig.provider} (${llmConfig.model})`}
                  >
                    {isPolishing ? "Polishing…" : "Polish with LLM"}
                  </button>
                ) : (
                  <span className="status-chip status-optimal">LLM polished</span>
                )}
                {polishError ? <span className="status-chip status-block">{polishError}</span> : null}
              </div>
            </div>
          ) : (
            <div className="audit-narrative-preview">
              <p>{workflowRun ? "Narrative persisted. Click below to polish with a local LLM." : "Run a workflow to generate the audit narrative."}</p>
              {workflowRun ? (
                <div className="audit-narrative-actions">
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={handlePolishNarrative}
                    disabled={isPolishing}
                    title={`Polish via ${llmConfig.provider} (${llmConfig.model})`}
                  >
                    {isPolishing ? "Polishing…" : "Polish with LLM"}
                  </button>
                  {polishError ? <span className="status-chip status-block">{polishError}</span> : null}
                </div>
              ) : null}
            </div>
          )}
        </EvidenceSection>
      </div>
    </section>
  );
}

function EvidenceSection({
  title,
  status,
  children,
}: {
  title: string;
  status: string;
  children: React.ReactNode;
}) {
  return (
    <div className="evidence-section">
      <div className="card-heading">
        <strong>{title}</strong>
        <span>{status}</span>
      </div>
      {children}
    </div>
  );
}

function LLMSettingsPanel({
  config,
  onChange,
}: {
  config: { provider: string; model: string; baseUrl: string; apiKey: string };
  onChange: (config: { provider: string; model: string; baseUrl: string; apiKey: string }) => void;
}) {
  function set(key: string, value: string) {
    onChange({ ...config, [key]: value });
  }

  return (
    <section className="panel compact llm-settings-panel">
      <div className="panel-heading">
        <span className="eyebrow">LLM Settings</span>
        <span className="model-badge">{config.provider} · {config.model || "no model"}</span>
      </div>

      <div className="llm-settings-fields">
        <label>
          <span>Protocol</span>
          <select
            value={config.provider}
            onChange={(e) => set("provider", e.target.value)}
            aria-label="LLM protocol"
          >
            <option value="openai">openai-compatible</option>
            <option value="anthropic">anthropic</option>
          </select>
        </label>
        <label>
          <span>Model</span>
          <input
            value={config.model}
            onChange={(e) => set("model", e.target.value)}
            placeholder="Any model string your endpoint accepts"
            aria-label="LLM model"
          />
        </label>
        <label className="llm-settings-wide">
          <span>Base URL</span>
          <input
            value={config.baseUrl}
            onChange={(e) => set("baseUrl", e.target.value)}
            placeholder="https://your-gateway/v1  (blank = provider default)"
            aria-label="LLM base URL"
          />
        </label>
        <label>
          <span>API Key</span>
          <input
            type="password"
            value={config.apiKey}
            onChange={(e) => set("apiKey", e.target.value)}
            placeholder="Blank = use env var"
            aria-label="LLM API key"
          />
        </label>
      </div>
      <p className="llm-settings-hint">
        Any OpenAI-compatible gateway: set Protocol to <code>openai-compatible</code>, paste your gateway URL, and type whatever model string it accepts.
      </p>
    </section>
  );
}

function PolicyIngestionPanel({
  selectedWorkflow,
  text,
  filename,
  backend,
  llmModel,
  result,
  applied,
  isIngesting,
  disabled,
  documentKind,
  pdfPreviewUrl,
  onTextChange,
  onFileChange,
  onBackendChange,
  onIngest,
  onApply,
  onLoadSample,
}: {
  selectedWorkflow: WorkflowCatalogItem;
  text: string;
  filename: string;
  backend: "deterministic" | "llm" | "auto";
  llmModel: string;
  result: PolicyIngestionResponse | null;
  applied: boolean;
  isIngesting: boolean;
  disabled: boolean;
  documentKind: "ips" | "collateral_schedule";
  pdfPreviewUrl: string | null;
  onTextChange: (value: string) => void;
  onFileChange: (file: File | null) => void;
  onBackendChange: (value: "deterministic" | "llm" | "auto") => void;
  onIngest: () => void;
  onApply: () => void;
  onLoadSample?: () => void;
}) {
  const ready = Boolean(result?.review_summary.ready);
  const missing = asStringArray(result?.review_summary.missing_required);
  const warnings = asStringArray(result?.review_summary.warnings);
  const isCollateralSchedule = documentKind === "collateral_schedule";
  const title = isCollateralSchedule ? "Schedule Intake" : "IPS Ingestion";
  const uploadLabel = isCollateralSchedule
    ? "Upload collateral schedule PDF or text"
    : "Upload IPS PDF or text";
  const placeholder = isCollateralSchedule
    ? "Paste collateral schedule language here if you are not uploading a file."
    : "Paste IPS language here if you are not uploading a file.";
  const ingestLabel = isCollateralSchedule ? "Ingest Schedule" : "Ingest IPS";
  const appliedLabel = isCollateralSchedule ? "Apply Schedule" : "Apply Fields";
  const samplePdfPreview =
    filename === "sample_money_market_policy.pdf"
      ? "/demo-assets/sample_money_market_policy_preview.png"
      : null;
  return (
    <section className="panel compact policy-ingestion-panel">
      <div className="panel-heading">
        <span className="eyebrow">{title}</span>
        <StatusStrip
          label={result ? (ready ? "Ready" : "Review") : "Upload"}
          statusClass={result ? (ready ? "status-optimal" : "status-ready") : "status-ready"}
        />
      </div>

      <label className="policy-file-drop">
        <span>{filename || uploadLabel}</span>
        <input
          type="file"
          accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
          onChange={(event) => onFileChange(event.target.files?.[0] || null)}
          disabled={disabled || isIngesting}
          aria-label="Upload IPS document"
        />
      </label>

      {pdfPreviewUrl ? (
        <div className="policy-pdf-preview" aria-label="Uploaded PDF preview">
          <div className="policy-pdf-preview-header">
            <strong>PDF Preview</strong>
            <span>{filename}</span>
          </div>
          {samplePdfPreview ? (
            <img src={samplePdfPreview} alt={`${filename} first page preview`} />
          ) : (
            <object
              data={`${pdfPreviewUrl}#toolbar=0&navpanes=0&scrollbar=0&page=1`}
              type="application/pdf"
              aria-label={`${filename} first page preview`}
            >
              <p>{filename} is attached and ready for ingestion.</p>
            </object>
          )}
        </div>
      ) : null}

      <textarea
        value={text}
        onChange={(event) => onTextChange(event.target.value)}
        placeholder={placeholder}
        aria-label={isCollateralSchedule ? "Collateral schedule text" : "IPS policy text"}
        disabled={disabled || isIngesting}
      />

      <div className="policy-mode-grid">
        <label>
          <span>Backend</span>
          <select
            value={backend}
            onChange={(event) =>
              onBackendChange(event.target.value as "deterministic" | "llm" | "auto")
            }
            disabled={disabled || isIngesting}
            aria-label="IPS ingestion backend"
          >
            <option value="deterministic">Deterministic</option>
            <option value="llm">LLM assisted</option>
            <option value="auto">Auto</option>
          </select>
        </label>
        <label>
          <span>Model</span>
          <input
            value={llmModel}
            readOnly
            disabled={backend === "deterministic"}
            aria-label="IPS ingestion model (set in LLM Settings)"
            title="Configure model in the LLM Settings panel"
          />
        </label>
      </div>

      <div className="policy-actions">
        {onLoadSample ? (
          <button
            className="secondary-button"
            type="button"
            onClick={onLoadSample}
            disabled={disabled || isIngesting}
          >
            Load Sample
          </button>
        ) : null}
        <button
          className="secondary-button"
          type="button"
          onClick={onIngest}
          disabled={disabled || isIngesting}
        >
          {isIngesting ? "Ingesting" : ingestLabel}
        </button>
        <button
          className="primary-button"
          type="button"
          onClick={onApply}
          disabled={disabled || isIngesting || !result || applied}
        >
          {applied ? "Applied" : appliedLabel}
        </button>
      </div>

      {result ? (
        <div className="policy-review">
          <div className="policy-review-summary">
            <strong>{selectedWorkflow.name}</strong>
            <span>
              {result.extracted_fields.length} fields from {result.source_type};{" "}
              {String(result.review_summary.backend || backend)}
            </span>
          </div>
          {missing.length || warnings.length ? (
            <ul className="policy-issue-list">
              {missing.map((item) => (
                <li className="error" key={item}>{item} missing</li>
              ))}
              {warnings.map((item) => (
                <li className="warning" key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          <ul className="policy-field-list">
            {result.extracted_fields.slice(0, 8).map((field) => (
              <li key={field.key}>
                <strong>{field.label}</strong>
                <span>{formatPolicyFieldValue(field.value)}</span>
                <em>{Math.round(field.confidence * 100)}% confidence</em>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function inputType(type: string): "number" | "text" {
  return ["integer", "number", "currency", "fraction", "percent"].includes(type)
    ? "number"
    : "text";
}

function numericInputMode(type: string): "decimal" | "numeric" | "text" {
  if (type === "integer") return "numeric";
  return inputType(type) === "number" ? "decimal" : "text";
}

function RunHistoryPanel({
  entries,
  onRestore,
  onReplay,
  onClear,
  disabled,
}: {
  entries: RunHistoryEntry[];
  onRestore: (entry: RunHistoryEntry) => void;
  onReplay: (entry: RunHistoryEntry) => void;
  onClear: () => void;
  disabled: boolean;
}) {
  const [selectedId, setSelectedId] = useState("");

  useEffect(() => {
    if (!entries.length) {
      setSelectedId("");
      return;
    }
    setSelectedId((current) =>
      entries.some((entry) => entry.id === current) ? current : entries[0].id,
    );
  }, [entries]);

  const selected = entries.find((entry) => entry.id === selectedId);

  return (
    <section className="panel compact run-history-panel">
      <div className="panel-heading">
        <span className="eyebrow">Run History</span>
        <StatusStrip label={String(entries.length)} />
      </div>
      {entries.length ? (
        <>
          <select
            className="select-input"
            value={selectedId}
            onChange={(event) => setSelectedId(event.target.value)}
            disabled={disabled}
            aria-label="Run history"
          >
            {entries.map((entry) => (
              <option value={entry.id} key={entry.id}>
                {entry.preset_name} - {formatHistoryTimestamp(entry.created_at)}
              </option>
            ))}
          </select>
          {selected ? (
            <div className="history-card">
              <strong>{selected.workflow_name}</strong>
              <span>{selected.portfolio_id} / seed {selected.seed}</span>
              <span>
                {selected.validation_passed ? "Validation passed" : "Review required"} /{" "}
                {titleCase(selected.status)}
              </span>
            </div>
          ) : null}
          <div className="history-actions">
            <button
              className="secondary-button"
              type="button"
              onClick={() => selected && onRestore(selected)}
              disabled={disabled || !selected}
            >
              Restore
            </button>
            <button
              className="primary-button"
              type="button"
              onClick={() => selected && onReplay(selected)}
              disabled={disabled || !selected}
            >
              Replay
            </button>
            <button
              className="text-button"
              type="button"
              onClick={onClear}
              disabled={disabled}
            >
              Clear
            </button>
          </div>
        </>
      ) : (
        <p>Completed workflow runs will appear here for restore and replay.</p>
      )}
    </section>
  );
}

function WorkflowSelector({
  workflows,
  selectedWorkflowId,
  onChange,
  disabled,
}: {
  workflows: WorkflowCatalogItem[];
  selectedWorkflowId: string;
  onChange: (workflowId: string) => void;
  disabled: boolean;
}) {
  const selected = workflows.find((item) => item.workflow_id === selectedWorkflowId) || workflows[0];
  return (
    <section className="panel compact workflow-selector">
      <div className="panel-heading">
        <span className="eyebrow">Workflow Template</span>
        <StatusStrip label={String(workflows.length)} />
      </div>
      <select
        className="select-input"
        value={selectedWorkflowId}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        aria-label="Workflow template"
      >
        {workflows.map((item) => (
          <option value={item.workflow_id} key={item.workflow_id}>
            {item.name}
          </option>
        ))}
      </select>
      {selected ? (
        <>
          <p>{selected.description}</p>
          <div className="workflow-domain-tags" aria-label="Workflow domains">
            {selected.domains.map((domain) => (
              <span key={domain}>{titleCase(domain.replaceAll("_", " "))}</span>
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}

function PresenterReviewPanel({
  review,
  selectedWorkflow,
  selectedPreset,
  solverProfile,
  onRun,
  onClose,
  disabled,
}: {
  review: PresenterReview;
  selectedWorkflow: WorkflowCatalogItem;
  selectedPreset: DemoPresetCatalogItem;
  solverProfile: { label: string; backend: string; problem: string; method: string };
  onRun: () => void;
  onClose: () => void;
  disabled: boolean;
}) {
  const runDisabled = disabled || review.status === "blocked";
  return (
    <section className="panel presenter-review-panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Presenter Review</span>
          <h2>Confirm the demo run</h2>
        </div>
        <StatusStrip label={titleCase(review.status)} statusClass={presenterStatusClass(review.status)} />
      </div>

      <div className="presenter-context-grid">
        <Metric label="Preset" value={selectedPreset.name} note={selectedPreset.audience} />
        <Metric label="Workflow" value={selectedWorkflow.name} note={selectedWorkflow.workflow_id} />
        <Metric label="Portfolio" value={selectedPreset.portfolio_id} note={`Seed ${selectedPreset.seed}`} />
        <Metric label="Solver" value={solverProfile.label} note={`${solverProfile.backend}/${solverProfile.problem}`} />
      </div>

      <div className="presenter-review-grid">
        <div>
          <h3>Changed Fields</h3>
          {review.changes.length ? (
            <ul className="presenter-list">
              {review.changes.map((change) => (
                <li key={change.key}>
                  <strong>{change.label}</strong>
                  <span>{change.from} to {change.to}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>No preset fields changed.</p>
          )}
        </div>
        <div>
          <h3>Guardrails</h3>
          {review.issues.length ? (
            <ul className="presenter-list">
              {review.issues.map((issue) => (
                <li className={issue.severity} key={`${issue.field}-${issue.message}`}>
                  <strong>{issue.field}</strong>
                  <span>{issue.message}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>All inputs are in the expected demo range.</p>
          )}
        </div>
      </div>

      <div className="presenter-actions">
        <button className="secondary-button" type="button" onClick={onClose} disabled={disabled}>
          Close
        </button>
        <button className="primary-button" type="button" onClick={onRun} disabled={runDisabled}>
          {review.status === "blocked" ? "Fix Inputs" : disabled ? "Running" : "Run Demo"}
        </button>
      </div>
    </section>
  );
}

function presenterStatusClass(status: PresenterStatus): string {
  if (status === "ready") return "status-optimal";
  if (status === "blocked") return "status-error";
  return "status-ready";
}

function ChatIntakeProgress({ workflow }: { workflow: WorkflowState | null }) {
  if (!workflow || !workflow.domain || workflow.awaiting_confirmation) return null;
  const requiredFields = workflow.plan?.required_fields ?? [];
  if (requiredFields.length === 0) return null;
  const collected = workflow.collected ?? {};
  const nextField = workflow.next_field;
  return (
    <div className="chat-intake-progress">
      <span className="intake-progress-label">Intake Progress</span>
      <div className="intake-field-rows">
        {requiredFields.map((field) => {
          const isCollected = field.key in collected;
          const isNext = !isCollected && field.key === nextField;
          const cls = isCollected
            ? "intake-field-row intake-field--collected"
            : isNext
              ? "intake-field-row intake-field--next"
              : "intake-field-row intake-field--pending";
          const icon = isCollected ? "✓" : isNext ? "→" : "·";
          return (
            <div key={field.key} className={cls}>
              <span className="intake-field-icon">{icon}</span>
              <span className="intake-field-label">{field.label}</span>
              {isCollected && (
                <span className="intake-field-value">
                  {String(collected[field.key])}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StreamingWorkflowProgress({
  steps,
}: {
  steps: Array<{
    step_id: string;
    domain: string;
    name: string;
    status: "running" | "complete" | "pending";
    objective_value?: number | null;
    improvement_pct?: number | null;
  }>;
}) {
  if (steps.length === 0) return null;
  return (
    <div className="streaming-progress">
      <span className="streaming-progress-label">Running workflow…</span>
      {steps.map((step) => (
        <div
          key={step.step_id}
          className={`streaming-step streaming-step--${step.status}`}
        >
          <span className="streaming-step-icon">
            {step.status === "complete" ? "✓" : step.status === "running" ? "⟳" : "·"}
          </span>
          <span className="streaming-step-name">{step.name || step.domain}</span>
          {step.status === "complete" && step.improvement_pct != null && (
            <span className="streaming-step-improvement">
              +{step.improvement_pct.toFixed(1)} bps
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function PlanPanel({ workflow }: { workflow: WorkflowState | null }) {
  const plan = workflow?.plan;
  const missingFields = plan?.missing_fields || [];
  const nextLabels =
    plan?.required_fields
      .filter((field) => missingFields.includes(field.key))
      .slice(0, 4)
      .map((field) => field.label) || [];
  return (
    <section className="panel compact plan-panel">
      <div className="panel-heading">
        <span className="eyebrow">Agent Plan</span>
        <StatusStrip
          label={plan?.ready_to_run ? "Ready" : `${missingFields.length || 0} inputs`}
          statusClass={plan?.ready_to_run ? "status-optimal" : "status-ready"}
        />
      </div>
      <p>{plan?.summary || "Start a request to generate an execution plan."}</p>
      {nextLabels.length > 0 ? (
        <ul>
          {nextLabels.map((label) => (
            <li key={label}>{label}</li>
          ))}
        </ul>
      ) : null}
      {plan?.steps?.length ? (
        <div className="plan-steps">
          {plan.steps.map((step) => (
            <div className={`plan-step ${step.status}`} key={step.name}>
              <span />
              <strong>{titleCase(step.name.replaceAll("_", " "))}</strong>
            </div>
          ))}
        </div>
      ) : null}
      {plan?.scenario_suggestions?.length ? (
        <div className="scenario-chips">
          {plan.scenario_suggestions.slice(0, 3).map((scenario) => (
            <span className={scenario.selected ? "selected" : ""} key={scenario.name}>
              {titleCase(scenario.name.replaceAll("_", " "))}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function WorkflowTimelinePanel({
  workflowRun,
  selectedWorkflow,
  selectedPreset,
}: {
  workflowRun: WorkflowRunResult | null;
  selectedWorkflow: WorkflowCatalogItem;
  selectedPreset: DemoPresetCatalogItem;
}) {
  const summary = workflowRun?.validation_summary;
  return (
    <section className="panel workflow-run-panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Sequential Workflow</span>
          <h2>{workflowRun?.name || selectedWorkflow.name}</h2>
        </div>
        <StatusStrip
          label={workflowRun ? titleCase(workflowRun.status) : "Not run"}
          statusClass={workflowStatusClass(workflowRun?.status)}
        />
      </div>

      <div className="workflow-validation-strip">
        <Metric
          label="Steps"
          value={String(summary?.total_steps ?? selectedWorkflow.domains.length)}
          note={workflowRun ? "Completed" : "Planned"}
        />
        <Metric
          label="Dependencies"
          value={String(workflowRun?.dependency_summary.total_effects ?? 0)}
          note="Context changes"
        />
        <Metric
          label="Warnings"
          value={String(summary?.warning_count ?? 0)}
          note="Aggregate"
        />
        <Metric
          label="Violations"
          value={String(summary?.violation_count ?? 0)}
          note="Blocking"
        />
      </div>

      {workflowRun ? (
        <>
          <div className="workflow-timeline" aria-label="Sequential workflow progress">
            {workflowRun.step_results.map((step, index) => (
              <div className={`workflow-step ${step.status}`} key={step.step_id}>
                <div className="workflow-step-marker" aria-hidden="true">
                  <span>{index + 1}</span>
                </div>
                <div className="workflow-step-body">
                  <div className="workflow-step-heading">
                    <div>
                      <strong>{step.name}</strong>
                      <span>{titleCase(step.domain.replaceAll("_", " "))}</span>
                    </div>
                    <StatusStrip
                      label={titleCase(step.status)}
                      statusClass={stepStatusClass(step.status)}
                    />
                  </div>
                  <div className="workflow-step-metrics">
                    <span>Objective {formatNumber(step.summary.objective_value)}</span>
                    <span>Improvement {step.summary.improvement_pct.toFixed(2)}%</span>
                    <span>{step.summary.allocation_count} allocations</span>
                    <span>{titleCase(step.summary.validation_recommendation || "ready")}</span>
                  </div>
                  {step.inputs_from.length ? (
                    <p>Inputs carried from {step.inputs_from.join(", ")}.</p>
                  ) : null}
                  {step.dependency_effects.length ? (
                    <ul className="workflow-dependency-list">
                      {step.dependency_effects.map((effect) => (
                        <li
                          key={`${effect.source_step_id}-${effect.target_context_key}-${effect.new_value}`}
                        >
                          <strong>{titleCase(effect.target_context_key.replaceAll("_", " "))}</strong>
                          <span>
                            {formatFraction(effect.previous_value)} to{" "}
                            {formatFraction(effect.new_value)} from{" "}
                            {effect.source_step_id.replaceAll("_", " ")}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          <div className="workflow-trace-grid">
            <div>
              <h3>Trace</h3>
              <ol>
                {workflowRun.trace.slice(-6).map((event, index) => (
                  <li key={`${event.event}-${index}`}>
                    <strong>{titleCase(event.event.replaceAll("_", " "))}</strong>
                    <span>{event.message}</span>
                  </li>
                ))}
              </ol>
            </div>
            <div>
              <h3>Validation Summary</h3>
              <ul>
                <li>{summary?.passed ? "All aggregate checks passed." : "Review required."}</li>
                {(summary?.warnings || []).slice(0, 3).map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
                {(summary?.violations || []).slice(0, 3).map((violation) => (
                  <li key={violation}>{violation}</li>
                ))}
              </ul>
            </div>
          </div>

          <p className="workflow-explanation">{workflowRun.explanation}</p>
        </>
      ) : (
        <p className="workflow-empty">
          {`Run the workflow action to execute ${selectedPreset.name} using the ${selectedWorkflow.name} template.`}
        </p>
      )}
    </section>
  );
}

function GovernanceReviewPanel({
  workflowRun,
  selectedWorkflow,
  inputValues,
  onDecision,
  onRerun,
  disabled,
}: {
  workflowRun: WorkflowRunResult | null;
  selectedWorkflow: WorkflowCatalogItem;
  inputValues: Record<string, string>;
  onDecision: (
    approvalIds: string[],
    granted: boolean,
    approver: string,
    reason: string,
  ) => void;
  onRerun: () => void;
  disabled: boolean;
}) {
  const [approver, setApprover] = useState("demo.approver");
  const [reason, setReason] = useState("Reviewed materiality and controls.");
  const [orchRouting, setOrchRouting] = useState<Record<string, unknown> | null>(null);
  const [orchAdvancing, setOrchAdvancing] = useState(false);

  const governance = highestGovernanceRecord(workflowRun);
  const pendingRecords = pendingGovernanceRecords(workflowRun);
  const pendingApprovalIds = pendingRecords.flatMap((record) =>
    record.approval_id ? [record.approval_id] : [],
  );
  const executionMode = inputValues.execution_mode || "recommendation";
  const materialityNotional = inputValues["governance.materiality_notional"] || "";
  const pnlImpact = inputValues["governance.estimated_pnl_impact"] || "";
  const productionChange = inputValues["governance.production_constraint_change"] === "true";
  const status = governance?.status || (productionChange ? "review" : "not_required");

  useEffect(() => {
    if (!workflowRun) { setOrchRouting(null); return; }
    fetch("/api/governance/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result: workflowRun }),
    })
      .then((res) => res.json())
      .then((data) => setOrchRouting(data))
      .catch(() => setOrchRouting(null));
  }, [workflowRun]);

  async function handleOrchAdvance(granted: boolean) {
    const approvalId = String(orchRouting?.approval_id || "");
    if (!approvalId || !approver.trim()) return;
    setOrchAdvancing(true);
    try {
      const res = await fetch("/api/governance/advance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: approvalId, approver, granted, reason }),
      });
      const data = await res.json();
      setOrchRouting((prev) => prev ? { ...prev, status: data.status, action_performed: data.action_performed } : prev);
    } finally {
      setOrchAdvancing(false);
    }
  }

  return (
    <section className="panel governance-review-panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Governance Review</span>
          <h2>Approval and materiality controls</h2>
        </div>
        <StatusStrip
          label={titleCase(status.replaceAll("_", " "))}
          statusClass={governanceStatusClass(status)}
        />
      </div>

      <div className="governance-metric-grid">
        <Metric
          label="Execution mode"
          value={titleCase((governance?.execution_mode || executionMode).replaceAll("_", " "))}
          note={selectedWorkflow.name}
        />
        <Metric
          label="Tier"
          value={governance ? String(governance.tier) : productionChange ? "5" : "2"}
          note={
            governance?.escalated
              ? `Escalated from ${governance.base_tier}`
              : "Current setting"
          }
        />
        <Metric
          label="Materiality"
          value={materialityNotional ? formatCurrency(materialityNotional) : "n/a"}
          note={pnlImpact ? `${formatCurrency(pnlImpact)} PnL impact` : "PnL impact optional"}
        />
      </div>

      <div className="governance-detail-grid">
        <div className="governance-card">
          <strong>{governance?.action || "recommendation"}</strong>
          <span>
            {governance
              ? governance.action_performed
                ? "Action is allowed or completed."
                : "Action is withheld pending approval."
              : productionChange
                ? "Production constraint changes will require Tier 5 approval."
                : "Run the workflow to evaluate approval requirements."}
          </span>
        </div>
        <div className="governance-card">
          <strong>Escalation</strong>
          <span>
            {governance?.escalation_reason ||
              (productionChange
                ? "production constraint change"
                : "No escalation reason yet.")}
          </span>
        </div>
        <div className="governance-card">
          <strong>Approval</strong>
          <span>{governance?.approval_id || "No approval ID issued yet."}</span>
        </div>
      </div>

      {governance && Object.keys(governance.governance_factors).length ? (
        <ul className="governance-factor-list">
          {Object.entries(governance.governance_factors).map(([key, value]) => (
            <li key={key}>
              <strong>{titleCase(key.replaceAll("_", " "))}</strong>
              <span>{formatGovernanceFactor(value)}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {orchRouting ? (
        <div className="governance-orchestrator-card">
          <div className="card-heading">
            <strong>Auto-Routed Tier (Orchestrator)</strong>
            <span className={orchRouting.status === "auto_allowed" ? "status-chip status-optimal" : orchRouting.status === "approved" ? "status-chip status-optimal" : orchRouting.status === "rejected" ? "status-chip status-block" : "status-chip status-warn"}>
              {String(orchRouting.status).replaceAll("_", " ")}
            </span>
          </div>
          <dl className="evidence-kv-list">
            <StateRow label="Tier" value={String(orchRouting.tier ?? "—")} />
            <StateRow label="Base tier" value={String(orchRouting.base_tier ?? "—")} />
            <StateRow label="Action" value={String(orchRouting.action ?? "—")} />
            <StateRow label="Escalated" value={orchRouting.escalated ? "Yes" : "No"} />
            {orchRouting.escalation_reason ? <StateRow label="Escalation reason" value={String(orchRouting.escalation_reason)} /> : null}
            {orchRouting.approval_id ? <StateRow label="Approval ID" value={String(orchRouting.approval_id)} /> : null}
          </dl>
          {orchRouting.required && orchRouting.status === "pending" ? (
            <div className="approval-decision-box" style={{ marginTop: "0.75rem" }}>
              <div className="approval-decision-fields">
                <label>
                  <span>Approver</span>
                  <input value={approver} onChange={(e) => setApprover(e.target.value)} disabled={orchAdvancing} aria-label="Approver name" />
                </label>
                <label>
                  <span>Reason</span>
                  <input value={reason} onChange={(e) => setReason(e.target.value)} disabled={orchAdvancing} aria-label="Approval reason" />
                </label>
              </div>
              <div className="approval-actions">
                <button className="primary-button" type="button" onClick={() => handleOrchAdvance(true)} disabled={orchAdvancing || !approver.trim()}>Approve</button>
                <button className="secondary-button" type="button" onClick={() => handleOrchAdvance(false)} disabled={orchAdvancing || !approver.trim()}>Reject</button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {governance?.required ? (
        <div className="approval-decision-box">
          <div className="approval-decision-fields">
            <label>
              <span>Approver</span>
              <input
                value={approver}
                onChange={(event) => setApprover(event.target.value)}
                disabled={disabled || pendingApprovalIds.length === 0}
                aria-label="Approver name"
              />
            </label>
            <label>
              <span>Reason</span>
              <input
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                disabled={disabled || pendingApprovalIds.length === 0}
                aria-label="Approval reason"
              />
            </label>
          </div>
          <div className="approval-actions">
            <button
              className="primary-button"
              type="button"
              onClick={() => onDecision(pendingApprovalIds, true, approver, reason)}
              disabled={disabled || pendingApprovalIds.length === 0}
            >
              Approve
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => onDecision(pendingApprovalIds, false, approver, reason)}
              disabled={disabled || pendingApprovalIds.length === 0}
            >
              Reject
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={onRerun}
              disabled={disabled || !workflowRun}
            >
              Rerun
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function WorkflowComparisonPanel({
  workflowRun,
  scenarioComparison,
  comparisonSets,
  selectedComparisonSetId,
  onSelectComparisonSet,
  onCreateComparisonSet,
  onDeleteComparisonSet,
}: {
  workflowRun: WorkflowRunResult | null;
  scenarioComparison: WorkflowScenarioComparison | null;
  comparisonSets: ComparisonSet[];
  selectedComparisonSetId: string;
  onSelectComparisonSet: (setId: string) => void;
  onCreateComparisonSet: (name: string) => void;
  onDeleteComparisonSet: (setId: string) => void;
}) {
  const [newSetName, setNewSetName] = useState("Base vs Stress");
  const visual = workflowRun?.visual_summary;
  const points = visual?.points || [];
  const scenarioRuns = scenarioComparison?.runs || [];
  const selectedSet = comparisonSets.find((item) => item.id === selectedComparisonSetId);
  const maxAbsImprovement = Math.max(
    1,
    ...points.map((point) => Math.abs(point.improvement_pct)),
  );

  return (
    <section className="panel workflow-comparison-panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Workflow Comparison</span>
          <h2>Scenario and step impact</h2>
        </div>
        <StatusStrip
          label={
            scenarioComparison?.comparison_ready
              ? `${scenarioComparison.run_count} Runs`
              : workflowRun
              ? titleCase(visual?.chart_kind.replaceAll("_", " ") || "Summary")
              : "Pending"
          }
          statusClass={workflowStatusClass(workflowRun?.status)}
        />
      </div>

      {scenarioComparison?.comparison_ready && scenarioRuns.length ? (
        <div className="scenario-comparison-block">
          <div className="scenario-comparison-head">
            <div>
              <h3>{selectedSet?.name || "Saved Run Comparison"}</h3>
              <p>
                {selectedSet
                  ? "Baseline is the first run in this named set."
                  : "Auto mode uses the newest comparable history entries."}
              </p>
            </div>
            <StatusStrip label="History" statusClass="status-optimal" />
          </div>
          <div className="comparison-set-controls">
            <select
              value={selectedComparisonSetId}
              onChange={(event) => onSelectComparisonSet(event.target.value)}
              aria-label="Comparison set"
            >
              <option value="auto">Auto: newest comparable runs</option>
              {comparisonSets.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <input
              value={newSetName}
              onChange={(event) => setNewSetName(event.target.value)}
              aria-label="New comparison set name"
            />
            <button
              className="secondary-button"
              type="button"
              onClick={() => onCreateComparisonSet(newSetName)}
            >
              Save Set
            </button>
            <button
              className="text-button"
              type="button"
              onClick={() => onDeleteComparisonSet(selectedComparisonSetId)}
              disabled={selectedComparisonSetId === "auto"}
            >
              Delete
            </button>
          </div>
          <div className="scenario-comparison-table">
            <table>
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Final Step</th>
                  <th>Improvement</th>
                  <th>Delta</th>
                  <th>Deps</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {scenarioRuns.map((run) => (
                  <tr
                    className={run.run_id === scenarioComparison.best_run_id ? "best" : ""}
                    key={run.run_id}
                  >
                    <td>
                      <strong>{run.label}</strong>
                      <span>{titleCase(run.status)}</span>
                    </td>
                    <td>{titleCase((run.final_domain || "workflow").replaceAll("_", " "))}</td>
                    <td>{run.final_improvement_pct.toFixed(2)}%</td>
                    <td>{formatSigned(run.deltas.final_improvement_pct, "%")}</td>
                    <td>{run.total_dependency_effects}</td>
                    <td>
                      {run.warning_count + run.violation_count}
                      {run.validation_passed ? " / pass" : " / review"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="scenario-insights">
            {scenarioComparison.insights.map((insight) => (
              <li key={insight}>{insight}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {visual && points.length ? (
        <>
          <div className="workflow-impact-strip">
            <Metric
              label="Avg improvement"
              value={`${visual.average_improvement_pct.toFixed(2)}%`}
              note="Across completed steps"
            />
            <Metric
              label="Dependencies"
              value={String(visual.total_dependency_effects)}
              note="Applied effects"
            />
            <Metric
              label="Warnings"
              value={String(visual.total_warnings)}
              note="Across steps"
            />
          </div>

          <div className="workflow-comparison-grid">
            <div className="workflow-impact-bars" aria-label="Workflow step impact chart">
              {points.map((point) => (
                <div
                  className={`workflow-impact-row ${point.step_id === visual.best_step_id ? "best" : ""}`}
                  key={point.step_id}
                >
                  <div className="workflow-impact-label">
                    <strong>{point.name}</strong>
                    <span>{titleCase(point.domain.replaceAll("_", " "))}</span>
                  </div>
                  <div className="workflow-impact-track">
                    <div
                      className="workflow-impact-fill"
                      style={{
                        width: `${Math.min(
                          100,
                          Math.abs(point.improvement_pct / maxAbsImprovement) * 100,
                        )}%`,
                      }}
                    />
                  </div>
                  <div className="workflow-impact-value">
                    <strong>{point.improvement_pct.toFixed(2)}%</strong>
                    <span>{formatObjective(point.objective_value)}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="workflow-point-table">
              <h3>Step Details</h3>
              <table>
                <thead>
                  <tr>
                    <th>Step</th>
                    <th>Allocations</th>
                    <th>Review</th>
                    <th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((point) => (
                    <tr key={point.step_id}>
                      <td>{titleCase(point.domain.replaceAll("_", " "))}</td>
                      <td>{point.allocation_count}</td>
                      <td>{titleCase(point.validation_recommendation || "ready")}</td>
                      <td>{point.warning_count + point.violation_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {visual.has_risk_return_points ? <RiskReturnPlot points={points} /> : null}
        </>
      ) : (
        <p className="workflow-empty">
          Run any workflow to compare objective impact, validation posture, and
          step-level analytics across the completed optimizer chain.
        </p>
      )}
    </section>
  );
}

function RiskReturnPlot({ points }: { points: WorkflowVisualPoint[] }) {
  const plotted = points.filter(
    (point) => point.expected_return !== null && point.volatility !== null,
  );
  if (!plotted.length) return null;

  const returns = plotted.map((point) => point.expected_return || 0);
  const volatilities = plotted.map((point) => point.volatility || 0);
  const minReturn = Math.min(...returns);
  const maxReturn = Math.max(...returns);
  const minVolatility = Math.min(...volatilities);
  const maxVolatility = Math.max(...volatilities);

  return (
    <div className="risk-return-card">
      <div>
        <h3>Risk / Return View</h3>
        <p>Shown when a workflow step exposes expected return and volatility.</p>
      </div>
      <div className="risk-return-plot" aria-label="Risk return comparison plot">
        {plotted.map((point) => {
          const left = scalePlotValue(point.volatility || 0, minVolatility, maxVolatility);
          const bottom = scalePlotValue(point.expected_return || 0, minReturn, maxReturn);
          return (
            <span
              className="risk-return-dot"
              style={{ left: `${left}%`, bottom: `${bottom}%` }}
              title={`${point.name}: ${formatPercent(point.expected_return || 0)} return, ${formatPercent(point.volatility || 0)} volatility`}
              key={point.step_id}
            >
              {point.domain.slice(0, 2).toUpperCase()}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function scalePlotValue(value: number, min: number, max: number): number {
  if (max === min) return 50;
  return 8 + ((value - min) / (max - min)) * 84;
}

function WorkflowExplanationPanel({
  workflowRun,
}: {
  workflowRun: WorkflowRunResult | null;
}) {
  const report = workflowRun?.explanation_report;
  const economicImpact = report?.economic_impact || {};
  return (
    <section className="panel workflow-explanation-panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Workflow Explanation</span>
          <h2>What the workflow concluded</h2>
        </div>
        <StatusStrip
          label={workflowRun ? titleCase(workflowRun.status) : "Pending"}
          statusClass={workflowStatusClass(workflowRun?.status)}
        />
      </div>

      <p className="explanation-summary">
        {report?.summary || "Run a workflow to generate a cross-step explanation."}
      </p>

      {report ? (
        <>
          <div className="workflow-recommendation">
            <strong>Recommendation</strong>
            <span>{report.overall_recommendation}</span>
          </div>
          <div className="workflow-impact-strip">
            <Metric
              label="Favorable steps"
              value={String(economicImpact.favorable_steps ?? 0)}
              note="Objective improved"
            />
            <Metric
              label="Dependency effects"
              value={String(economicImpact.dependency_effect_count ?? 0)}
              note="Context changes"
            />
            <Metric
              label="Step summaries"
              value={String(report.step_summaries.length)}
              note="Explained"
            />
          </div>
          <div className="explanation-grid">
            <ExplanationList title="Drivers" items={report.key_drivers} />
            <ExplanationList title="Dependency Changes" items={report.dependency_changes} />
            <ExplanationList title="Risks" items={report.risks} />
            <ExplanationList title="Next Actions" items={report.next_actions} />
          </div>
        </>
      ) : null}
    </section>
  );
}

function TracePanel({
  workflow,
  result,
}: {
  workflow: WorkflowState | null;
  result: OptimizationResult | null;
}) {
  const trace = result?.agent_trace || workflow?.trace || [];
  return (
    <section className="panel compact trace-panel">
      <div className="panel-heading">
        <span className="eyebrow">Agent Trace</span>
        <StatusStrip label={String(trace.length)} />
      </div>
      {trace.length ? (
        <ol>
          {trace.slice(-5).map((event, index) => (
            <li key={`${event.event}-${index}`}>
              <strong>{titleCase(event.event.replaceAll("_", " "))}</strong>
              <span>{event.message}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p>Trace events appear after the agent starts planning.</p>
      )}
    </section>
  );
}

function workflowStatusClass(status: WorkflowRunResult["status"] | undefined) {
  if (status === "error") return "status-error";
  if (status === "partial") return "status-ready";
  if (status === "complete") return "status-optimal";
  return "";
}

function governanceStatusClass(status: string | undefined) {
  if (status === "pending" || status === "review") return "status-ready";
  if (status === "rejected") return "status-error";
  return "status-optimal";
}

function highestGovernanceRecord(workflowRun: WorkflowRunResult | null): ApprovalRecord | null {
  const records = workflowRun?.step_results
    .map((step) => step.result.governance)
    .filter((record): record is ApprovalRecord => Boolean(record)) || [];
  return records.sort((left, right) => right.tier - left.tier)[0] || null;
}

function pendingGovernanceRecords(workflowRun: WorkflowRunResult | null): ApprovalRecord[] {
  return workflowRun?.step_results
    .map((step) => step.result.governance)
    .filter((record): record is ApprovalRecord => Boolean(record))
    .filter((record) => record.status === "pending" && Boolean(record.approval_id)) || [];
}

function formatGovernanceFactor(value: string | number | boolean): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (Math.abs(value) >= 1_000_000) return formatCurrency(value);
    return value.toLocaleString();
  }
  return value;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

function stepStatusClass(status: string) {
  if (status === "optimal") return "status-optimal";
  if (status === "error" || status === "infeasible" || status === "unbounded") {
    return "status-error";
  }
  return "status-ready";
}

function ValidationPanel({ result }: { result: OptimizationResult }) {
  const report = result.validation_report;
  const checks = report?.checks.length
    ? report.checks
    : [
        {
          name: "demo_mode",
          status: "pass" as const,
          severity: "info" as const,
          message: "Validation checks will update after a completed run.",
          details: {},
        },
      ];

  return (
    <section className="panel validation-panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Validation</span>
          <h2>Readiness checks</h2>
        </div>
        <StatusStrip
          label={titleCase(report?.recommendation || "ready")}
          statusClass={validationStatusClass(report?.recommendation)}
        />
      </div>
      <div className="validation-summary">
        <Metric
          label="Risk score"
          value={(report?.risk_score ?? 0).toFixed(2)}
          note="0 low, 5 high"
        />
        <Metric
          label="Violations"
          value={String(report?.violations.length ?? 0)}
          note="Blocking issues"
        />
        <Metric
          label="Warnings"
          value={String(report?.warnings.length ?? 0)}
          note="Review items"
        />
      </div>
      <div className="validation-checks">
        {checks.slice(0, 6).map((check) => (
          <div className={`validation-check ${check.status}`} key={check.name}>
            <strong>{titleCase(check.name.replaceAll("_", " "))}</strong>
            <span>{check.message}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function ExplanationPanel({ result }: { result: OptimizationResult }) {
  const report = result.explanation_report;
  const rationale = report?.rationale.length
    ? report.rationale
    : [
        "The recommendation follows the optimizer objective while preserving configured constraints.",
      ];
  const risks = report?.risks.length
    ? report.risks
    : ["No deterministic validation risks were detected."];
  const alternatives = report?.alternatives.length
    ? report.alternatives
    : ["Run downside and stress scenarios to compare robustness."];

  return (
    <section className="panel explanation-panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Explanation</span>
          <h2>Why this recommendation</h2>
        </div>
      </div>
      <p className="explanation-summary">
        {report?.summary || "Structured explanation will appear after a completed run."}
      </p>
      <div className="explanation-grid">
        <ExplanationList title="Rationale" items={rationale} />
        <ExplanationList title="Risks" items={risks} />
        <ExplanationList title="Alternatives" items={alternatives} />
      </div>
    </section>
  );
}

function validationStatusClass(status: string | undefined) {
  if (status === "blocked") return "status-error";
  if (status === "review") return "status-ready";
  return "status-optimal";
}

function ExplanationList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="explanation-list">
      <h3>{title}</h3>
      <ul>
        {items.slice(0, 4).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function StateRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function StatusStrip({
  label,
  statusClass = "",
}: {
  label: string;
  statusClass?: string;
}) {
  return (
    <span className={`status-strip ${statusClass}`.trim()}>
      <span aria-hidden="true" />
      <strong>{label}</strong>
    </span>
  );
}

function ResultPanel({ result }: { result: OptimizationResult }) {
  const metrics = resultPanelMetrics(result);
  return (
    <section className="panel result-panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Recommendation</span>
          <h2>Optimization result</h2>
        </div>
        <StatusStrip label={titleCase(result.status)} statusClass="status-optimal" />
      </div>

      <div className="metric-grid">
        {metrics.map((metric) => (
          <Metric
            label={metric.label}
            value={metric.value}
            note={metric.note}
            accent={metric.accent}
            key={metric.label}
          />
        ))}
      </div>

      <div className="allocation-bars" aria-label="Allocation chart">
        {result.allocations.slice(0, 3).map((allocation, index) => (
          <div className="bar-row" key={allocation.label}>
            <span>{allocation.label}</span>
            <div className="bar-track">
              <div
                className={`bar-fill ${index === 1 ? "alternate" : index === 2 ? "muted" : ""}`}
                style={{ width: `${Math.min(100, allocation.allocated_fraction * 100)}%` }}
              />
            </div>
            <strong>{formatCurrency(allocation.allocated_value)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function resultPanelMetrics(
  result: OptimizationResult,
): Array<{ label: string; value: string; note: string; accent?: boolean }> {
  const expectedReturn = optionalNumber(result.solver_metadata.expected_return);
  const volatility = optionalNumber(result.solver_metadata.volatility);
  const sharpe = optionalNumber(result.solver_metadata.sharpe);

  if (result.domain === "asset_allocation" || expectedReturn !== undefined) {
    return [
      {
        label: "Expected return",
        value: expectedReturn !== undefined ? formatPercent(expectedReturn) : "n/a",
        note: "Annualized",
      },
      {
        label: "Volatility",
        value: volatility !== undefined ? formatPercent(volatility) : "n/a",
        note: "Annualized risk",
      },
      {
        label: "Sharpe",
        value: sharpe !== undefined ? sharpe.toFixed(2) : "n/a",
        note: `Utility ${result.objective_value.toFixed(4)}`,
        accent: true,
      },
    ];
  }

  if (result.domain === "collateral" || result.domain === "financing") {
    const labelPrefix = result.domain === "collateral" ? "Collateral" : "Funding";
    return [
      {
        label: "Optimized cost",
        value: formatCurrency(result.objective_value),
        note: `${labelPrefix} objective`,
      },
      {
        label: "Baseline cost",
        value: formatCurrency(result.baseline_value),
        note: "Naive allocation",
      },
      {
        label: "Cost reduction",
        value: formatCurrency(result.improvement),
        note: `${result.improvement_pct.toFixed(2)}%`,
        accent: true,
      },
    ];
  }

  if (result.domain && result.domain !== "money_market") {
    return [
      {
        label: "Optimized objective",
        value: formatObjective(result.objective_value),
        note: titleCase(result.domain.replaceAll("_", " ")),
      },
      {
        label: "Baseline objective",
        value: formatObjective(result.baseline_value),
        note: "Reference case",
      },
      {
        label: "Improvement",
        value: formatObjective(result.improvement),
        note: `${result.improvement_pct.toFixed(2)}%`,
        accent: true,
      },
    ];
  }

  return [
    {
      label: "Optimized yield",
      value: `${result.objective_value.toFixed(4)}%`,
      note: "Net annualized",
    },
    {
      label: "Baseline yield",
      value: `${result.baseline_value.toFixed(4)}%`,
      note: "Current allocation",
    },
    {
      label: "Improvement",
      value: `${result.improvement >= 0 ? "+" : ""}${(result.improvement * 100).toFixed(2)} bps`,
      note: `${result.improvement_pct.toFixed(2)}%`,
      accent: true,
    },
  ];
}

function Metric({
  label,
  value,
  note,
  accent = false,
}: {
  label: string;
  value: string;
  note: string;
  accent?: boolean;
}) {
  return (
    <div className={`metric ${accent ? "accent" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}

type ConstraintRelaxationProposal = {
  parameter: string;
  proposed_change: string;
  estimated_impact: number;
  estimated_impact_units: string;
  governance_tier: number;
  governance_reason: string;
  rationale: string;
  source: string;
  confidence: number;
};

type ConstraintNegotiationResult = {
  domain: string;
  target_improvement: number;
  target_units: string;
  proposals: ConstraintRelaxationProposal[];
  recommendation: string;
  blockers: string[];
};

function tierClass(tier: number): string {
  if (tier <= 2) return "status-optimal";
  if (tier <= 3) return "status-ready";
  if (tier === 4) return "status-warn";
  return "status-block";
}

function tierLabel(tier: number): string {
  const labels: Record<number, string> = {
    0: "Tier 0 – Explain",
    1: "Tier 1 – Scenario",
    2: "Tier 2 – Recommend",
    3: "Tier 3 – Stage",
    4: "Tier 4 – Execute",
    5: "Tier 5 – Policy Change",
  };
  return labels[tier] ?? `Tier ${tier}`;
}

function ConstraintPanel({ result }: { result: OptimizationResult }) {
  const constraints = result.binding_constraints.length
    ? result.binding_constraints
    : ["prime_concentration", "single_fund_limit"];

  const [negotiation, setNegotiation] = useState<ConstraintNegotiationResult | null>(null);
  const [negotiating, setNegotiating] = useState(false);
  const [negotiationError, setNegotiationError] = useState<string | null>(null);
  const [targetImprovement, setTargetImprovement] = useState<string>("");
  const [targetUnits, setTargetUnits] = useState<string>("bps");
  const [showNegotiate, setShowNegotiate] = useState(false);

  async function runNegotiation() {
    setNegotiating(true);
    setNegotiationError(null);
    try {
      const response = await fetch(`${API_BASE}/api/constraints/negotiate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          result: result as unknown as Record<string, unknown>,
          target_improvement: parseFloat(targetImprovement) || 0,
          target_units: targetUnits,
          max_proposals: 5,
        }),
      });
      if (!response.ok) throw new Error(`API error ${response.status}`);
      const data = (await response.json()) as { negotiation: ConstraintNegotiationResult };
      setNegotiation(data.negotiation);
    } catch (err) {
      setNegotiationError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setNegotiating(false);
    }
  }

  return (
    <section className="panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Constraints</span>
          <h2>Binding checks</h2>
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={() => {
            setShowNegotiate((v) => !v);
            setNegotiation(null);
            setNegotiationError(null);
          }}
        >
          What would need to change?
        </button>
      </div>

      <div className="constraint-stack">
        {constraints.map((constraint) => (
          <div className="constraint-item" key={constraint}>
            <strong>{titleCase(constraint.replaceAll("_", " "))}</strong>
            <span>Constraint is active in the optimal recommendation.</span>
          </div>
        ))}
      </div>

      {showNegotiate && (
        <div className="negotiation-panel">
          <div className="negotiation-header">
            <span className="eyebrow">Constraint Negotiation</span>
            <p className="negotiation-subtitle">
              Rank constraint relaxations by estimated impact and governance tier required.
            </p>
          </div>

          <div className="negotiation-inputs">
            <label className="negotiation-label">
              Target improvement
              <input
                type="number"
                className="negotiation-input"
                placeholder="e.g. 15"
                value={targetImprovement}
                onChange={(e) => setTargetImprovement(e.target.value)}
                min={0}
                step={1}
              />
            </label>
            <label className="negotiation-label">
              Units
              <select
                className="negotiation-select"
                value={targetUnits}
                onChange={(e) => setTargetUnits(e.target.value)}
              >
                <option value="bps">bps</option>
                <option value="utility">utility</option>
                <option value="cost_savings">cost savings</option>
                <option value="objective">objective</option>
              </select>
            </label>
            <button
              className="primary-button"
              type="button"
              onClick={runNegotiation}
              disabled={negotiating}
            >
              {negotiating ? "Analyzing…" : "Analyze"}
            </button>
          </div>

          {negotiationError && (
            <p className="negotiation-error">{negotiationError}</p>
          )}

          {negotiation && (
            <div className="negotiation-results">
              <p className="negotiation-recommendation">{negotiation.recommendation}</p>

              {negotiation.blockers.length > 0 && (
                <div className="negotiation-blockers">
                  {negotiation.blockers.map((b, i) => (
                    <p key={i} className="negotiation-blocker">{b}</p>
                  ))}
                </div>
              )}

              <div className="proposal-stack">
                {negotiation.proposals.map((proposal, i) => (
                  <div className="proposal-card" key={`${proposal.parameter}-${i}`}>
                    <div className="proposal-card-header">
                      <strong className="proposal-parameter">
                        {titleCase(proposal.parameter.replaceAll("_", " "))}
                      </strong>
                      <span className={`status-chip ${tierClass(proposal.governance_tier)}`}>
                        {tierLabel(proposal.governance_tier)}
                      </span>
                    </div>

                    <p className="proposal-change">{proposal.proposed_change}</p>

                    <div className="proposal-meta">
                      {proposal.estimated_impact > 0 && (
                        <span className="proposal-impact">
                          ~{proposal.estimated_impact.toFixed(2)} {proposal.estimated_impact_units} estimated
                        </span>
                      )}
                      <span className="proposal-confidence">
                        {Math.round(proposal.confidence * 100)}% confidence
                      </span>
                      <span className="proposal-source">
                        {proposal.source === "sensitivity" ? "sensitivity analysis" : "binding constraint"}
                      </span>
                    </div>

                    <p className="proposal-rationale">{proposal.rationale}</p>
                    <p className="proposal-governance-reason">{proposal.governance_reason}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function OperationalActionTablePanel({
  workflowRun,
  result,
  selectedWorkflow,
}: {
  workflowRun: WorkflowRunResult | null;
  result: OptimizationResult | null;
  selectedWorkflow: WorkflowCatalogItem;
}) {
  const operationalStep = workflowRun?.step_results.find((step) =>
    ["treasury_operations", "margin_operations"].includes(step.domain),
  );
  const operationalResult = operationalStep?.result ||
    (result && ["treasury_operations", "margin_operations"].includes(result.domain || "")
      ? result
      : null);
  const domain = operationalStep?.domain || operationalResult?.domain || "";
  const workflowIsOperational = selectedWorkflow.domains.some((item) =>
    ["treasury_operations", "margin_operations"].includes(item),
  );
  if (!workflowIsOperational && !operationalResult) return null;

  const attachments = toRecord(operationalResult?.solver_metadata.domain_attachments);
  const rows = recordArray(attachments.operational_action_table);
  const title = domain === "margin_operations"
    ? "Margin-call action queue"
    : "Treasury cash movement actions";
  const statusLabel = operationalResult ? `${rows.length} actions` : "Pending run";

  return (
    <section className="panel operational-action-panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Operational Actions</span>
          <h2>{title}</h2>
        </div>
        <StatusStrip
          label={statusLabel}
          statusClass={operationalResult ? "status-optimal" : "status-ready"}
        />
      </div>

      {operationalResult && rows.length ? (
        domain === "margin_operations" ? (
          <MarginCallActionTable rows={rows} />
        ) : (
          <TreasuryActionTable rows={rows} />
        )
      ) : (
        <p className="workflow-empty">
          Run the operational workflow to review table-ready actions before
          exporting the evidence package.
        </p>
      )}
    </section>
  );
}

function TreasuryActionTable({ rows }: { rows: Record<string, unknown>[] }) {
  return (
    <div className="table-wrap operational-action-table">
      <table>
        <thead>
          <tr>
            <th>Requirement</th>
            <th>Source</th>
            <th>Target</th>
            <th>Rail</th>
            <th>Amount</th>
            <th>Cost</th>
            <th>Cutoff</th>
            <th>Remaining</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${String(row.requirement_id || "transfer")}-${index}`}>
              <td>{String(row.requirement_id || "-")}</td>
              <td>
                <strong>{String(row.source_account || "-")}</strong>
                <span>{String(row.source_entity || "")}</span>
              </td>
              <td>{String(row.target_account || "-")}</td>
              <td>{String(row.rail || "-")}</td>
              <td>{formatCurrency(row.amount)}</td>
              <td>{formatCurrency(row.cost)}</td>
              <td>
                <strong>{titleCase(String(row.cutoff_status || "open").replaceAll("_", " "))}</strong>
                <span>{formatCutoffHours(row.rail_cutoff_hour, row.requirement_cutoff_hour)}</span>
              </td>
              <td>{formatCurrency(row.remaining_source_liquidity)}</td>
              <td>{titleCase(String(row.recommended_action || "execute_transfer").replaceAll("_", " "))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MarginCallActionTable({ rows }: { rows: Record<string, unknown>[] }) {
  return (
    <div className="table-wrap operational-action-table">
      <table>
        <thead>
          <tr>
            <th>Call</th>
            <th>Counterparty</th>
            <th>Status</th>
            <th>Amount</th>
            <th>Due</th>
            <th>Risk</th>
            <th>Dispute</th>
            <th>Capacity</th>
            <th>Action</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${String(row.call_id || "call")}-${index}`}>
              <td>{String(row.call_id || "-")}</td>
              <td>{String(row.counterparty || "-")}</td>
              <td>
                <strong>{titleCase(String(row.queue_status || "-"))}</strong>
                <span>{row.assigned_order ? `Order ${row.assigned_order}` : ""}</span>
              </td>
              <td>{formatCurrency(row.amount)}</td>
              <td>{formatHours(row.due_in_hours)}</td>
              <td>
                <strong>{titleCase(String(row.risk_tier || "medium"))}</strong>
                <span>{formatScore(row.priority_score)}</span>
              </td>
              <td>{formatFraction(row.dispute_probability)}</td>
              <td>{formatMinutes(row.capacity_minutes)}</td>
              <td>{titleCase(String(row.recommended_action || "-").replaceAll("_", " "))}</td>
              <td>{titleCase(String(row.reason || "-").replaceAll("_", " "))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AllocationTable({ result }: { result: OptimizationResult }) {
  return (
    <section className="panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Allocations</span>
          <h2>Recommended portfolio</h2>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Fund</th>
              <th>Amount</th>
              <th>Weight</th>
              <th>Yield</th>
              <th>WAM</th>
            </tr>
          </thead>
          <tbody>
            {result.allocations.map((allocation) => (
              <tr key={allocation.label}>
                <td>{allocation.label}</td>
                <td>{formatCurrency(allocation.allocated_value)}</td>
                <td>{formatFraction(allocation.allocated_fraction)}</td>
                <td>{formatMaybePercent(allocation.metadata.yield_7day)}</td>
                <td>{allocation.metadata.wam_days ? `${allocation.metadata.wam_days}d` : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SensitivityTable({ result }: { result: OptimizationResult }) {
  return (
    <section className="panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Sensitivity</span>
          <h2>Decision drivers</h2>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Parameter</th>
              <th>Shadow price</th>
              <th>Interpretation</th>
            </tr>
          </thead>
          <tbody>
            {result.sensitivities.map((item) => (
              <tr key={item.parameter}>
                <td>{titleCase(item.parameter.replaceAll("_", " "))}</td>
                <td>{item.shadow_price.toFixed(4)}</td>
                <td>{item.interpretation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function buildDisplayState(
  collected: Record<string, unknown>,
  selectedWorkflow: WorkflowCatalogItem,
  selectedPreset: DemoPresetCatalogItem,
) {
  const presetContext = toRecord(selectedPreset.context);
  const assetAllocation = toRecord(presetContext.asset_allocation);
  const moneyMarket = toRecord(presetContext.money_market);
  const collateral = toRecord(presetContext.collateral);
  const treasury = toRecord(presetContext.treasury_operations);
  const margin = toRecord(presetContext.margin_operations);
  const fallbackDomain = selectedWorkflow.domains[0] || "money_market";
  const rawDomain = String(collected.domain || fallbackDomain);
  const domain = titleCase(rawDomain.replaceAll("_", " "));

  if (rawDomain === "asset_allocation") {
    return {
      domain,
      portfolio: String(collected.portfolio_id || selectedPreset.portfolio_id || "PORT_MVO_001"),
      scenario: formatPresetScenario(collected.scenario_names, presetContext.scenario),
      summary: [
        [
          "Portfolio notional",
          formatCurrency(
            collected.portfolio_notional || assetAllocation.portfolio_notional || 250_000_000,
          ),
        ],
        [
          "Target return",
          formatFraction(collected.target_return || assetAllocation.target_return || 0.05),
        ],
        [
          "Risk aversion",
          String(collected.risk_aversion || assetAllocation.risk_aversion || 3),
        ],
        [
          "Asset cap",
          formatFraction(
            collected.max_single_asset_weight ||
              assetAllocation.max_single_asset_weight ||
              0.45,
          ),
        ],
        [
          "Cash floor",
          formatFraction(collected.min_cash_weight || assetAllocation.min_cash_weight || 0.02),
        ],
        ["Solver", "SciPy QP"],
      ],
    };
  }

  if (rawDomain === "collateral") {
    return {
      domain,
      portfolio: String(collected.portfolio_id || selectedPreset.portfolio_id || "PORT_HQLA_224"),
      scenario: formatPresetScenario(collected.scenario_names, presetContext.scenario),
      summary: [
        [
          "Obligation scale",
          formatFraction(collateral.obligation_scale || collected.obligation_scale || 1.65),
        ],
        [
          "Concentration cap",
          formatFraction(collateral.concentration_limit || collected.concentration_limit || 0.55),
        ],
        [
          "Total cash",
          formatCurrency(collected.total_cash || moneyMarket.total_cash || 420_000_000),
        ],
        [
          "Daily liquidity",
          formatFraction(collected.daily_liquidity_req || moneyMarket.daily_liquidity_req || 0.35),
        ],
        [
          "Weekly liquidity",
          formatFraction(collected.weekly_liquidity_req || moneyMarket.weekly_liquidity_req || 0.65),
        ],
        ["HQLA reporting", collateral.hqla_reporting ? "Enabled" : "Review"],
      ],
    };
  }

  if (rawDomain === "treasury_operations") {
    return {
      domain,
      portfolio: String(collected.portfolio_id || selectedPreset.portfolio_id || "PORT_TREASURY_OPS"),
      scenario: formatPresetScenario(collected.scenario_names, presetContext.scenario),
      summary: [
        ["Funding need", formatCurrency(155_000_000)],
        ["Cutoff hour", `${treasury.cutoff_hour || 15}:00`],
        [
          "Stress multiplier",
          formatFraction(treasury.stress_multiplier || collected.stress_multiplier || 1),
        ],
        [
          "Liquidity buffer",
          formatFraction(treasury.liquidity_buffer_pct || collected.liquidity_buffer_pct || 0.05),
        ],
        ["Payment rails", "CHIPS / FEDWIRE"],
        ["Runtime", "Production adapter"],
      ],
    };
  }

  if (rawDomain === "margin_operations") {
    return {
      domain,
      portfolio: String(collected.portfolio_id || selectedPreset.portfolio_id || "PORT_MARGIN_OPS"),
      scenario: formatPresetScenario(collected.scenario_names, presetContext.scenario),
      summary: [
        ["Queue amount", formatCurrency(125_000_000)],
        [
          "Team capacity",
          `${margin.team_capacity_minutes || collected.team_capacity_minutes || 150} min`,
        ],
        [
          "Materiality",
          formatCurrency(margin.materiality_threshold || collected.materiality_threshold || 25_000_000),
        ],
        [
          "Dispute stress",
          formatFraction(
            margin.dispute_stress_multiplier || collected.dispute_stress_multiplier || 1,
          ),
        ],
        ["Priority factors", "Exposure / SLA / dispute / tier"],
        ["Runtime", "Production adapter"],
      ],
    };
  }

  return {
    domain,
    portfolio: String(collected.portfolio_id || selectedPreset.portfolio_id || "PORT_204"),
    scenario: formatPresetScenario(collected.scenario_names, presetContext.scenario),
    summary: [
      ["Total cash", formatCurrency(collected.total_cash || moneyMarket.total_cash || 500_000_000)],
      [
        "Daily liquidity",
        formatFraction(collected.daily_liquidity_req || moneyMarket.daily_liquidity_req || 0.3),
      ],
      [
        "Weekly liquidity",
        formatFraction(collected.weekly_liquidity_req || moneyMarket.weekly_liquidity_req || 0.6),
      ],
      [
        "Prime limit",
        formatFraction(collected.max_prime_fraction || moneyMarket.max_prime_fraction || 0.4),
      ],
      [
        "Max WAM",
        collected.max_wam_days || moneyMarket.max_wam_days
          ? `${collected.max_wam_days || moneyMarket.max_wam_days} days`
          : "60 days",
      ],
      ["Single fund", formatFraction(collected.max_single_fund || moneyMarket.max_single_fund || 0.5)],
    ],
  };
}

function formatCurrency(value: unknown) {
  const number = Number(value);
  if (Number.isNaN(number)) return String(value || "-");
  if (number >= 1_000_000_000) return `$${(number / 1_000_000_000).toFixed(1)}B`;
  if (number >= 1_000_000) return `$${(number / 1_000_000).toFixed(0)}M`;
  return `$${number.toLocaleString()}`;
}

function formatPolicyFieldValue(value: string | number | boolean | null): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (Math.abs(value) >= 1_000_000) return formatCurrency(value);
    if (value > 0 && value <= 1) return formatFraction(value);
    return String(value);
  }
  if (value === null || value === undefined) return "-";
  return String(value);
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

function formatSigned(value: number | undefined, suffix = "") {
  if (value === undefined || Number.isNaN(value)) return "baseline";
  if (value === 0) return `+0.00${suffix}`;
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}${suffix}`;
}

function formatFraction(value: unknown) {
  const number = Number(value);
  if (Number.isNaN(number)) return String(value || "-");
  if (number <= 1) return `${Math.round(number * 100)}%`;
  return `${number}%`;
}

function formatMaybePercent(value: unknown) {
  const number = Number(value);
  if (Number.isNaN(number)) return "-";
  return `${number.toFixed(2)}%`;
}

function formatHours(value: unknown) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  if (number <= 0) return "Past due";
  if (number === 1) return "1h";
  return `${number.toFixed(number % 1 === 0 ? 0 : 1)}h`;
}

function formatMinutes(value: unknown) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${number.toFixed(0)}m`;
}

function formatScore(value: unknown) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `Score ${number.toFixed(2)}`;
}

function formatCutoffHours(railCutoff: unknown, requirementCutoff: unknown) {
  const rail = Number(railCutoff);
  const requirement = Number(requirementCutoff);
  if (!Number.isFinite(rail) && !Number.isFinite(requirement)) return "";
  if (!Number.isFinite(requirement)) return `Rail ${rail}:00`;
  if (!Number.isFinite(rail)) return `Required ${requirement}:00`;
  return `Rail ${rail}:00 / required ${requirement}:00`;
}

function formatNumber(value: unknown) {
  const number = Number(value);
  if (Number.isNaN(number)) return String(value || "-");
  if (Math.abs(number) >= 1_000_000) return number.toExponential(2);
  return number.toFixed(4);
}

function formatObjective(value: unknown) {
  const number = Number(value);
  if (Number.isNaN(number)) return "-";
  if (Math.abs(number) < 1) return number.toFixed(4);
  if (Math.abs(number) < 100) return number.toFixed(2);
  return number.toExponential(2);
}

function formatScenarioList(value: unknown) {
  if (!Array.isArray(value) || value.length === 0) return "Stress";
  return value.map((item) => titleCase(String(item).replaceAll("_", " "))).join(", ");
}

function formatPresetScenario(value: unknown, fallback: unknown) {
  if (Array.isArray(value)) return formatScenarioList(value);
  if (fallback) return titleCase(String(fallback).replaceAll("_", " "));
  return "Base";
}

function titleCase(value: string) {
  return value
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const solverProfiles: Record<string, { label: string; backend: string; problem: string; method: string }> = {
  "scipy-lp": { label: "SciPy LP", backend: "scipy", problem: "lp", method: "HiGHS" },
  "scipy-qp": {
    label: "SciPy QP",
    backend: "scipy",
    problem: "qp",
    method: "SLSQP",
  },
  "scipy-milp": {
    label: "SciPy MILP",
    backend: "scipy",
    problem: "milp",
    method: "HiGHS MILP",
  },
  "cvxpy-lp": { label: "CVXPY LP", backend: "cvxpy", problem: "lp", method: "CLARABEL" },
};

function solverKeyForWorkflow(workflowId: string): string {
  return workflowId === "portfolio_rebalance_mvo" ? "scipy-qp" : "scipy-lp";
}

function mockResultForWorkflow(workflowId: string): OptimizationResult {
  return workflowId === "portfolio_rebalance_mvo" ? mockAssetAllocationResult : mockResult;
}

const mockAssetAllocationResult: OptimizationResult = {
  domain: "asset_allocation",
  status: "optimal",
  objective_value: 0.0468,
  baseline_value: 0.0415,
  improvement: 0.0053,
  improvement_pct: 12.77,
  binding_constraints: ["target_return", "max_single_asset_weight", "min_cash_weight"],
  validation_report: {
    passed: true,
    recommendation: "ready",
    risk_score: 0,
    checks: [
      {
        name: "solver_status",
        status: "pass",
        severity: "info",
        message: "MVO solver returned an optimal allocation.",
        details: {},
      },
      {
        name: "target_return",
        status: "pass",
        severity: "info",
        message: "Expected return meets the configured target.",
        details: { target_return: 0.05 },
      },
      {
        name: "weight_limits",
        status: "pass",
        severity: "info",
        message: "Asset-class weights are within configured bounds.",
        details: {},
      },
    ],
    violations: [],
    warnings: [],
    data_quality: {
      allocation_count: 6,
      has_sensitivities: true,
      has_scenarios: false,
      has_explanation: true,
    },
    policy_status: null,
  },
  explanation_report: {
    summary:
      "MVO placeholder view balances expected return, volatility, and diversification for the selected portfolio rebalance demo.",
    what_changed: [
      "Allocated across six broad asset classes.",
      "Equity exposure is capped by the single-asset concentration limit.",
    ],
    rationale: [
      "The allocation maximizes mean-variance utility while meeting target return and cash floor controls.",
      "Diversifying across bonds, credit, and alternatives reduces portfolio volatility.",
    ],
    economic_impact: {
      expected_return: 0.056,
      volatility: 0.088,
      sharpe: 0.52,
    },
    binding_constraints: ["target_return", "max_single_asset_weight", "min_cash_weight"],
    risks: ["Target return and concentration limits are active and should be reviewed."],
    alternatives: ["Lower risk aversion to increase growth exposure, or raise cash floor for defense."],
    sensitivities: ["Relaxing the asset cap can increase expected return but raises concentration risk."],
    scenarios: [],
    governance: null,
    source_explanation: "Asset allocation MVO placeholder result for the selected demo.",
  },
  solver_metadata: {
    solver_backend: "scipy",
    problem_type: "qp",
    solver_method: "SLSQP",
    expected_return: 0.056,
    volatility: 0.088,
    sharpe: 0.52,
  },
  allocations: [
    {
      label: "US Equity",
      allocated_value: 87_500_000,
      allocated_fraction: 0.35,
      metadata: { asset_class: "equity" },
    },
    {
      label: "Core Bonds",
      allocated_value: 62_500_000,
      allocated_fraction: 0.25,
      metadata: { asset_class: "fixed_income" },
    },
    {
      label: "Credit",
      allocated_value: 37_500_000,
      allocated_fraction: 0.15,
      metadata: { asset_class: "credit" },
    },
    {
      label: "International Equity",
      allocated_value: 30_000_000,
      allocated_fraction: 0.12,
      metadata: { asset_class: "equity" },
    },
    {
      label: "Alternatives",
      allocated_value: 20_000_000,
      allocated_fraction: 0.08,
      metadata: { asset_class: "alternatives" },
    },
    {
      label: "Cash",
      allocated_value: 12_500_000,
      allocated_fraction: 0.05,
      metadata: { asset_class: "cash" },
    },
  ],
  sensitivities: [
    {
      parameter: "target_return",
      shadow_price: 0.018,
      interpretation: "A higher target return requires more risk budget.",
    },
    {
      parameter: "max_single_asset_weight",
      shadow_price: 0.011,
      interpretation: "Relaxing the asset cap can improve utility.",
    },
    {
      parameter: "min_cash_weight",
      shadow_price: -0.006,
      interpretation: "A higher cash floor reduces expected return.",
    },
  ],
};

const mockResult: OptimizationResult = {
  domain: "money_market",
  status: "optimal",
  objective_value: 5.2284,
  baseline_value: 5.0291,
  improvement: 0.1993,
  improvement_pct: 3.96,
  binding_constraints: ["prime_concentration", "single_fund_limit"],
  validation_report: {
    passed: true,
    recommendation: "ready",
    risk_score: 0,
    checks: [
      {
        name: "solver_status",
        status: "pass",
        severity: "info",
        message: "Solver returned an optimal result.",
        details: {},
      },
      {
        name: "allocation_fractions",
        status: "pass",
        severity: "info",
        message: "Allocation fractions are within expected bounds.",
        details: { total_fraction: 1 },
      },
      {
        name: "objective_quality",
        status: "pass",
        severity: "info",
        message: "Optimization result is at least as good as the baseline.",
        details: { improvement_pct: 3.96 },
      },
    ],
    violations: [],
    warnings: [],
    data_quality: {
      allocation_count: 3,
      has_sensitivities: true,
      has_scenarios: false,
      has_explanation: true,
    },
    policy_status: null,
  },
  explanation_report: {
    summary: "Money market optimizer allocated $500M across 3 funds.",
    what_changed: [
      "Allocated 3 positions totaling $500.0M.",
      "BNY Mellon Government Fund 3: $250.0M (50.0%).",
    ],
    rationale: [
      "The recommendation prioritizes the highest-contributing feasible allocations while preserving portfolio constraints.",
      "Binding constraints shaped the final allocation: prime_concentration, single_fund_limit.",
    ],
    economic_impact: {
      objective_value: 5.2284,
      baseline_value: 5.0291,
      improvement: 0.1993,
      improvement_pct: 3.96,
    },
    binding_constraints: ["prime_concentration", "single_fund_limit"],
    risks: [
      "Concentration review: BNY Mellon Government Fund 3 receives 50.0%.",
      "Active binding constraints may limit flexibility if assumptions change.",
    ],
    alternatives: [
      "Relaxing prime fund limit by 10pp improves yield by 3.22bps.",
      "Run a scenario with relaxed binding constraints to quantify the cost of policy limits.",
    ],
    sensitivities: ["Relaxing prime fund limit by 10pp improves yield by 3.22bps."],
    scenarios: [],
    governance: null,
    source_explanation: "Money market optimizer allocated $500M across 3 funds.",
  },
  solver_metadata: { solver_backend: "scipy", problem_type: "lp", solver_method: "HiGHS" },
  allocations: [
    {
      label: "BNY Mellon Government Fund 3",
      allocated_value: 250_000_000,
      allocated_fraction: 0.5,
      metadata: { yield_7day: 5.23, wam_days: 47 },
    },
    {
      label: "BNY Mellon Prime Fund 7",
      allocated_value: 200_000_000,
      allocated_fraction: 0.4,
      metadata: { yield_7day: 5.57, wam_days: 58 },
    },
    {
      label: "BNY Mellon Government Fund 2",
      allocated_value: 50_000_000,
      allocated_fraction: 0.1,
      metadata: { yield_7day: 5.03, wam_days: 36 },
    },
  ],
  sensitivities: [
    {
      parameter: "daily_liquidity_req",
      shadow_price: 0,
      interpretation: "No current yield impact from a 5pp relaxation.",
    },
    {
      parameter: "weekly_liquidity_req",
      shadow_price: 0,
      interpretation: "No current yield impact from a 5pp relaxation.",
    },
    {
      parameter: "max_prime_fraction",
      shadow_price: 32.24,
      interpretation: "Relaxing by 10pp improves yield by 3.22bps.",
    },
  ],
};

createRoot(document.getElementById("root")!).render(<App />);
