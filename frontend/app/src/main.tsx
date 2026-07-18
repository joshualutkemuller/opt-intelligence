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

type WorkflowExportPackageApiResponse = {
  filename: string;
  content_type: string;
  html: string;
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
  context: Record<string, unknown>;
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
const MAX_RUN_HISTORY = 12;

const fallbackWorkflowCatalog: WorkflowCatalogItem[] = [
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
    default_context: {},
    inputs: [],
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
  const [ollamaModel, setOllamaModel] = useState("llama3.1:8b");
  const [isOllamaRunning, setIsOllamaRunning] = useState(false);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [workflowRun, setWorkflowRun] = useState<WorkflowRunResult | null>(null);
  const [workflowCatalog, setWorkflowCatalog] =
    useState<WorkflowCatalogItem[]>(fallbackWorkflowCatalog);
  const [demoPresets, setDemoPresets] =
    useState<DemoPresetCatalogItem[]>(fallbackDemoPresets);
  const [selectedDemoPresetId, setSelectedDemoPresetId] = useState(
    fallbackDemoPresets[0].preset_id,
  );
  const [selectedWorkflowId, setSelectedWorkflowId] = useState(
    fallbackDemoPresets[0].workflow_id,
  );
  const [workflowInputValues, setWorkflowInputValues] = useState<Record<string, string>>({});
  const [historyInputOverride, setHistoryInputOverride] =
    useState<Record<string, string> | null>(null);
  const [latestPayload, setLatestPayload] = useState<unknown>(null);
  const [latestWorkflowRunPayload, setLatestWorkflowRunPayload] =
    useState<WorkflowRunPayload | null>(null);
  const [runHistory, setRunHistory] = useState<RunHistoryEntry[]>(() => loadRunHistory());
  const [solver, setSolver] = useState(solverKeyForWorkflow(fallbackDemoPresets[0].workflow_id));
  const [isRunning, setIsRunning] = useState(false);
  const [isWorkflowRunning, setIsWorkflowRunning] = useState(false);
  const [isExportingPackage, setIsExportingPackage] = useState(false);
  const [presenterReviewOpen, setPresenterReviewOpen] = useState(false);
  const didCreateSession = useRef(false);
  const messagesRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (didCreateSession.current) return;
    didCreateSession.current = true;
    void createSession();
    void loadWorkflowCatalog();
    void loadDemoPresets();
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
            : body.presets[0].preset_id,
        );
        setSelectedWorkflowId((current) => {
          const preset = body.presets.find((item) => item.preset_id === selectedDemoPresetId)
            || body.presets[0];
          return current === preset.workflow_id ? current : preset.workflow_id;
        });
      }
    } catch {
      setDemoPresets(fallbackDemoPresets);
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
        body: JSON.stringify({ message }),
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
      { role: "assistant", content: "Thinking locally with Ollama...", pending: true },
    ]);

    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/llm/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            provider: "openai",
            model: ollamaModel,
            base_url: "http://localhost:11434/v1",
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
          `Ollama chat did not complete (${detail}). Confirm Ollama is running on http://localhost:11434 and that the model exists.`,
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

  function openPresenterReview() {
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
    );
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

    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/workflows/run`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
        20000,
      );
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as WorkflowRunApiResponse;
      const finalStep = [...body.result.step_results].reverse()[0];
      setPresenterReviewOpen(false);
      setWorkflowRun(body.result);
      if (finalStep?.result) {
        setResult(finalStep.result);
      }
      setLatestPayload(body);
      setLatestWorkflowRunPayload(payload);
      addRunHistoryEntry(
        createRunHistoryEntry({
          preset: selectedPreset,
          workflow: selectedWorkflow,
          solverKey: solver,
          inputValues: workflowInputValues,
          payload,
          response: body,
        }),
      );
      setMessages((items) =>
        replacePendingMessage(
          items,
          `Sequential workflow complete. ${body.result.step_results.length} optimizer steps ran with aggregate validation ${body.result.validation_summary.passed ? "passing" : "requiring review"}.`,
        ),
      );
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
  }

  const collected = workflow?.collected || {};
  const display = useMemo(() => buildDisplayState(collected), [collected]);
  const solverProfile = solverProfiles[solver];
  const dashboard = result || mockResult;
  const selectedWorkflow = workflowCatalog.find(
    (item) => item.workflow_id === selectedWorkflowId,
  ) || fallbackWorkflowCatalog[0];
  const selectedPreset = demoPresets.find(
    (item) => item.preset_id === selectedDemoPresetId,
  ) || fallbackDemoPresets[0];
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
            disabled={!workflowRun || isExportingPackage}
          >
            {isExportingPackage ? "Exporting" : "Export Package"}
          </button>
        </div>
      </header>

      <main className="workspace">
        <aside className="sidebar" aria-label="Workflow state">
          <section className="panel compact">
            <div className="panel-heading">
              <span className="eyebrow">Workflow</span>
              <span className={`status-pill ${result ? "status-optimal" : "status-ready"}`}>
                {result ? "Complete" : apiConnected ? "API ready" : "Static"}
              </span>
            </div>
            <dl className="state-list">
              <StateRow label="Domain" value={display.domain} />
              <StateRow label="Portfolio" value={display.portfolio} />
              <StateRow label="Scenario" value={display.scenario} />
              <StateRow label="Governance" value="Recommendation" />
            </dl>
          </section>

          <DemoPresetSelector
            presets={demoPresets}
            selectedPresetId={selectedDemoPresetId}
            onChange={(presetId) => {
              setSelectedDemoPresetId(presetId);
              const preset = demoPresets.find((item) => item.preset_id === presetId);
              if (preset) {
                setSelectedWorkflowId(preset.workflow_id);
                setSolver(solverKeyForWorkflow(preset.workflow_id));
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
                  onClick={openPresenterReview}
                  disabled={isWorkflowRunning}
                >
                  {isWorkflowRunning ? "Running" : "Review"}
                </button>
              </div>
            </div>

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

          <section className="ollama-panel panel" aria-label="Local Ollama chat">
            <div className="section-header">
              <div>
                <span className="eyebrow">Local LLM</span>
                <h2>Ollama Chat</h2>
              </div>
              <label className="model-control">
                <span>Model</span>
                <input
                  value={ollamaModel}
                  onChange={(event) => setOllamaModel(event.target.value)}
                  aria-label="Ollama model"
                />
              </label>
            </div>

            <div className="messages ollama-messages" aria-live="polite">
              {ollamaMessages.map((message, index) => (
                <article className={`message ${message.role}`} key={`${message.role}-${index}`}>
                  <span className="message-label">
                    {message.role === "user" ? "User" : "Ollama"}
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
                {isOllamaRunning ? "Thinking" : "Ask Ollama"}
              </button>
            </form>
          </section>

          <section className="dashboard-grid">
            <ResultPanel result={dashboard} />
            <ConstraintPanel result={dashboard} />
          </section>

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

          <WorkflowComparisonPanel workflowRun={workflowRun} />

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
): WorkflowRunPayload {
  const presetContext = toRecord(preset?.context);
  const presetMoneyMarket = toRecord(presetContext.money_market);
  const compiled = compileWorkflowInputs(workflowInputs, inputValues, preset);
  const compiledContext = toRecord(compiled.context);
  const mergedContext = deepMerge(presetContext, compiledContext);
  const compiledMoneyMarket = toRecord(mergedContext.money_market);

  return {
    workflow: preset?.workflow_id || workflowId,
    portfolio_id: String(compiled.portfolio_id || collected.portfolio_id || preset?.portfolio_id || "PORT_204"),
    seed: Number(compiled.seed || collected.seed || preset?.seed || 42),
    execution_mode: compiled.execution_mode || "recommendation",
    context: {
      ...mergedContext,
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
      },
    },
  };
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
      if (input.type === "currency" && numeric <= 0) {
        issues.push({
          severity: "error",
          field: input.label,
          message: `${input.label} must be greater than zero.`,
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

function numberFrom(...values: unknown[]): number {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "") {
      return Number(value);
    }
  }
  return 0;
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
        <span className="status-pill">{selected?.duration_minutes || 0} min</span>
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
              <input
                checked={(values[input.key] ?? "").toLowerCase() === "true"}
                onChange={(event) => onChange(input.key, event.target.checked ? "true" : "false")}
                type="checkbox"
                disabled={disabled}
                aria-label={input.label}
              />
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
        <span className={`status-pill ${presenterStatusClass(reviewStatus)}`}>
          {titleCase(reviewStatus)}
        </span>
        <button className="primary-button" type="button" onClick={onReview} disabled={disabled}>
          {disabled ? "Running" : "Review & Run Demo"}
        </button>
      </div>
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
        <span className="status-pill">{entries.length}</span>
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
        <span className="status-pill">{workflows.length}</span>
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
        <span className={`status-pill ${presenterStatusClass(review.status)}`}>
          {titleCase(review.status)}
        </span>
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
        <span className={`status-pill ${plan?.ready_to_run ? "status-optimal" : "status-ready"}`}>
          {plan?.ready_to_run ? "Ready" : `${missingFields.length || 0} inputs`}
        </span>
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
        <span className={`status-pill ${workflowStatusClass(workflowRun?.status)}`}>
          {workflowRun ? titleCase(workflowRun.status) : "Not run"}
        </span>
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
                    <span className={`status-pill ${stepStatusClass(step.status)}`}>
                      {titleCase(step.status)}
                    </span>
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
          Run the workflow action to execute {selectedPreset.name} using the
          {selectedWorkflow.name} template.
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

  return (
    <section className="panel governance-review-panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Governance Review</span>
          <h2>Approval and materiality controls</h2>
        </div>
        <span className={`status-pill ${governanceStatusClass(status)}`}>
          {titleCase(status.replaceAll("_", " "))}
        </span>
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
}: {
  workflowRun: WorkflowRunResult | null;
}) {
  const visual = workflowRun?.visual_summary;
  const points = visual?.points || [];
  const maxAbsImprovement = Math.max(
    1,
    ...points.map((point) => Math.abs(point.improvement_pct)),
  );

  return (
    <section className="panel workflow-comparison-panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Workflow Comparison</span>
          <h2>Step impact across the run</h2>
        </div>
        <span className={`status-pill ${workflowStatusClass(workflowRun?.status)}`}>
          {workflowRun ? titleCase(visual?.chart_kind.replaceAll("_", " ") || "Summary") : "Pending"}
        </span>
      </div>

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
        <span className={`status-pill ${workflowStatusClass(workflowRun?.status)}`}>
          {workflowRun ? titleCase(workflowRun.status) : "Pending"}
        </span>
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
        <span className="status-pill">{trace.length}</span>
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
        <span className={`status-pill ${validationStatusClass(report?.recommendation)}`}>
          {titleCase(report?.recommendation || "ready")}
        </span>
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

function ResultPanel({ result }: { result: OptimizationResult }) {
  const metrics = resultPanelMetrics(result);
  return (
    <section className="panel result-panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Recommendation</span>
          <h2>Optimization result</h2>
        </div>
        <span className="status-pill status-optimal">{titleCase(result.status)}</span>
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

function ConstraintPanel({ result }: { result: OptimizationResult }) {
  const constraints = result.binding_constraints.length
    ? result.binding_constraints
    : ["prime_concentration", "single_fund_limit"];
  return (
    <section className="panel">
      <div className="section-header tight">
        <div>
          <span className="eyebrow">Constraints</span>
          <h2>Binding checks</h2>
        </div>
      </div>
      <div className="constraint-stack">
        {constraints.map((constraint) => (
          <div className="constraint-item" key={constraint}>
            <strong>{titleCase(constraint.replaceAll("_", " "))}</strong>
            <span>Constraint is active in the optimal recommendation.</span>
          </div>
        ))}
      </div>
    </section>
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

function buildDisplayState(collected: Record<string, unknown>) {
  const domain = titleCase(String(collected.domain || "money market").replaceAll("_", " "));
  return {
    domain,
    portfolio: String(collected.portfolio_id || "PORT_204"),
    scenario: formatScenarioList(collected.scenario_names),
    summary: [
      ["Total cash", formatCurrency(collected.total_cash || 500_000_000)],
      ["Daily liquidity", formatFraction(collected.daily_liquidity_req || 0.3)],
      ["Weekly liquidity", formatFraction(collected.weekly_liquidity_req || 0.6)],
      ["Prime limit", formatFraction(collected.max_prime_fraction || 0.4)],
      ["Max WAM", collected.max_wam_days ? `${collected.max_wam_days} days` : "60 days"],
      ["Single fund", formatFraction(collected.max_single_fund || 0.5)],
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

function formatPercent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
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

const mockResult: OptimizationResult = {
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
