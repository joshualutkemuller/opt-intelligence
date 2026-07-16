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

type OptimizationResult = {
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
  solver_metadata: Record<string, unknown>;
};

type ChatApiResponse = {
  session_id: string;
  assistant_message: string;
  state: WorkflowState;
  result: OptimizationResult | null;
  request: Record<string, unknown> | null;
};

const defaultMessages: Message[] = [
  {
    role: "assistant",
    content:
      "Start with a business request like: I want to optimize money market cash.",
  },
];

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [apiConnected, setApiConnected] = useState(false);
  const [messages, setMessages] = useState<Message[]>(defaultMessages);
  const [input, setInput] = useState("");
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [latestPayload, setLatestPayload] = useState<unknown>(null);
  const [solver, setSolver] = useState("scipy-lp");
  const [isRunning, setIsRunning] = useState(false);
  const didCreateSession = useRef(false);
  const messagesRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (didCreateSession.current) return;
    didCreateSession.current = true;
    void createSession();
  }, []);

  useEffect(() => {
    const messagePane = messagesRef.current;
    if (messagePane) {
      messagePane.scrollTop = messagePane.scrollHeight;
    }
  }, [messages]);

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

  function resetSession() {
    setResult(null);
    setLatestPayload(null);
    void createSession();
  }

  function exportJson() {
    const payload = latestPayload || { workflow, result };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "decision-intelligence-result.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  const collected = workflow?.collected || {};
  const display = useMemo(() => buildDisplayState(collected), [collected]);
  const solverProfile = solverProfiles[solver];
  const dashboard = result || mockResult;
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

          <section className="dashboard-grid">
            <ResultPanel result={dashboard} />
            <ConstraintPanel result={dashboard} />
          </section>

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
        <Metric label="Optimized yield" value={`${result.objective_value.toFixed(4)}%`} note="Net annualized" />
        <Metric label="Baseline yield" value={`${result.baseline_value.toFixed(4)}%`} note="Current allocation" />
        <Metric
          label="Improvement"
          value={`${result.improvement >= 0 ? "+" : ""}${(result.improvement * 100).toFixed(2)} bps`}
          note={`${result.improvement_pct.toFixed(2)}%`}
          accent
        />
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
  "scipy-milp": {
    label: "SciPy MILP",
    backend: "scipy",
    problem: "milp",
    method: "HiGHS MILP",
  },
  "cvxpy-lp": { label: "CVXPY LP", backend: "cvxpy", problem: "lp", method: "CLARABEL" },
};

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
