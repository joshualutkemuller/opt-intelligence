// ── pre-trade: health gauge ──
function drawHealthGauge(canvasId, score) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  const cx = w / 2;
  const cy = h - 8;
  const r = Math.min(cx, cy) - 10;
  const startAngle = Math.PI;
  const endAngle = 2 * Math.PI;
  const scoreAngle = startAngle + (score / 100) * Math.PI;

  ctx.clearRect(0, 0, w, h);

  // track
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, endAngle);
  ctx.strokeStyle = "#dbe2ea";
  ctx.lineWidth = 10;
  ctx.lineCap = "round";
  ctx.stroke();

  // fill
  const fillColor = score >= 80 ? "#15803d" : score >= 60 ? "#b45309" : "#b91c1c";
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, scoreAngle);
  ctx.strokeStyle = fillColor;
  ctx.lineWidth = 10;
  ctx.lineCap = "round";
  ctx.stroke();
}

drawHealthGauge("healthGauge", 74);

// mark pre-trade as ready after short delay
setTimeout(() => {
  const pill = document.getElementById("pretradeStatus");
  if (pill) {
    pill.textContent = "Ready";
    pill.className = "status-pill status-optimal";
  }
}, 800);

const messages = document.querySelector("#messages");
const chatForm = document.querySelector("#chatForm");
const chatInput = document.querySelector("#chatInput");
const resetButton = document.querySelector("#resetButton");
const exportButton = document.querySelector("#exportButton");
const parsePdfButton = document.querySelector("#parsePdfButton");
const requestSummary = document.querySelector("#requestSummary");
const workflowStatus = document.querySelector("#workflowStatus");
const allocationBody = document.querySelector("#allocationBody");
const sensitivityBody = document.querySelector("#sensitivityBody");

const API_BASE = "http://127.0.0.1:8000";

const state = {
  apiConnected: false,
  sessionId: null,
  latestPayload: null,
  step: 0,
  solver: "scipy-lp",
  fields: {
    domain: "Money market",
    portfolio: "PORT_204",
    scenario: "Stress",
    totalCash: "$500M",
    dailyLiquidity: "30%",
    weeklyLiquidity: "60%",
    primeLimit: "40%",
    maxWam: "60 days",
    singleFund: "50%",
  },
};

const workflow = [
  {
    key: "portfolio",
    question: "What portfolio ID should I use?",
    defaultValue: "PORT_001",
    formatter: (value) => value.trim() || "PORT_001",
  },
  {
    key: "totalCash",
    question: "How much cash are you allocating?",
    defaultValue: "$500M",
    formatter: formatAmount,
  },
  {
    key: "dailyLiquidity",
    question: "Minimum daily liquidity?",
    defaultValue: "30%",
    formatter: formatPercent,
  },
  {
    key: "weeklyLiquidity",
    question: "Minimum weekly liquidity?",
    defaultValue: "60%",
    formatter: formatPercent,
  },
  {
    key: "primeLimit",
    question: "Maximum prime fund concentration?",
    defaultValue: "40%",
    formatter: formatPercent,
  },
  {
    key: "maxWam",
    question: "Maximum WAM in days?",
    defaultValue: "60 days",
    formatter: (value) => `${parseNumber(value, 60)} days`,
  },
  {
    key: "singleFund",
    question: "Maximum single-fund concentration?",
    defaultValue: "50%",
    formatter: formatPercent,
  },
  {
    key: "scenario",
    question: "Scenario to include?",
    defaultValue: "stress",
    formatter: formatScenario,
  },
];

const solverProfiles = {
  "scipy-lp": {
    backend: "scipy",
    problem: "lp",
    method: "HiGHS",
    objective: "5.2284%",
    baseline: "5.0291%",
    improvement: "+19.93 bps",
    status: "Optimal",
  },
  "scipy-milp": {
    backend: "scipy",
    problem: "milp",
    method: "HiGHS MILP",
    objective: "5.2140%",
    baseline: "5.0291%",
    improvement: "+18.49 bps",
    status: "Optimal",
  },
  "cvxpy-lp": {
    backend: "cvxpy",
    problem: "lp",
    method: "CLARABEL",
    objective: "5.2284%",
    baseline: "5.0291%",
    improvement: "+19.93 bps",
    status: "Optimal",
  },
};

function addMessage(role, content) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "User" : "Assistant";
  const body = document.createElement("p");
  body.textContent = content;
  article.append(label, body);
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
}

function addAssistantQuestion(item) {
  addMessage("assistant", `${item.question} default: ${item.defaultValue}`);
}

function updateSummary() {
  document.querySelector("#stateDomain").textContent = state.fields.domain;
  document.querySelector("#statePortfolio").textContent = state.fields.portfolio;
  document.querySelector("#stateScenario").textContent = state.fields.scenario;

  const rows = [
    ["Total cash", state.fields.totalCash],
    ["Daily liquidity", state.fields.dailyLiquidity],
    ["Weekly liquidity", state.fields.weeklyLiquidity],
    ["Prime limit", state.fields.primeLimit],
    ["Max WAM", state.fields.maxWam],
    ["Single fund", state.fields.singleFund],
  ];

  requestSummary.replaceChildren(
    ...rows.map(([label, value]) => {
      const li = document.createElement("li");
      const span = document.createElement("span");
      const strong = document.createElement("strong");
      span.textContent = label;
      strong.textContent = value;
      li.append(span, strong);
      return li;
    }),
  );
}

function updateSummaryFromApi(apiState) {
  const collected = apiState?.collected || {};
  const domain = apiState?.domain || "money_market";
  state.fields.domain = titleCase(domain.replaceAll("_", " "));
  state.fields.portfolio = collected.portfolio_id || state.fields.portfolio;
  state.fields.scenario = formatScenarioList(collected.scenario_names);
  state.fields.totalCash = formatCurrency(collected.total_cash);
  state.fields.dailyLiquidity = formatFraction(collected.daily_liquidity_req);
  state.fields.weeklyLiquidity = formatFraction(collected.weekly_liquidity_req);
  state.fields.primeLimit = formatFraction(collected.max_prime_fraction);
  state.fields.maxWam = collected.max_wam_days ? `${collected.max_wam_days} days` : state.fields.maxWam;
  state.fields.singleFund = formatFraction(collected.max_single_fund);

  if (apiState?.awaiting_confirmation) {
    workflowStatus.textContent = "Confirm";
    workflowStatus.className = "status-pill status-ready";
  } else if (apiState?.domain) {
    workflowStatus.textContent = "Collecting";
    workflowStatus.className = "status-pill status-ready";
  }
  updateSummary();
}

function completeRun() {
  workflowStatus.textContent = "Complete";
  workflowStatus.className = "status-pill status-optimal";
  addMessage(
    "assistant",
    "Confirmed. The optimizer found an allocation that improves yield while satisfying liquidity, WAM, and concentration limits.",
  );
}

async function handleChatSubmit(event) {
  event.preventDefault();
  const raw = chatInput.value.trim();
  if (!raw) return;

  addMessage("user", raw);
  chatInput.value = "";

  if (raw.toLowerCase() === "reset") {
    await resetSession();
    return;
  }

  if (state.apiConnected) {
    await sendApiMessage(raw);
    return;
  }

  if (raw.toLowerCase() === "yes" && state.step >= workflow.length) {
    completeRun();
    return;
  }

  if (state.step === 0 && raw.toLowerCase().includes("money market")) {
    addMessage("assistant", "I will guide a money market allocation workflow.");
    addAssistantQuestion(workflow[0]);
    return;
  }

  const item = workflow[state.step];
  if (!item) {
    addMessage("assistant", "Type yes to run this request, or reset to start over.");
    return;
  }

  state.fields[item.key] = item.formatter(raw);
  state.step += 1;
  updateSummary();

  const next = workflow[state.step];
  if (next) {
    addAssistantQuestion(next);
    return;
  }

  addMessage(
    "assistant",
    `I have enough to run. Domain: money market. Portfolio: ${state.fields.portfolio}. Cash: ${state.fields.totalCash}. Solver: ${solverProfiles[state.solver].backend}/${solverProfiles[state.solver].problem}. Type yes to run.`,
  );
}

async function resetSession() {
  state.step = 0;
  state.latestPayload = null;
  state.fields = {
    domain: "Money market",
    portfolio: "PORT_204",
    scenario: "Stress",
    totalCash: "$500M",
    dailyLiquidity: "30%",
    weeklyLiquidity: "60%",
    primeLimit: "40%",
    maxWam: "60 days",
    singleFund: "50%",
  };
  workflowStatus.textContent = "Collecting";
  workflowStatus.className = "status-pill status-ready";
  messages.replaceChildren();
  addMessage("assistant", "I will guide a money market allocation workflow.");
  addAssistantQuestion(workflow[0]);
  updateSummary();

  if (state.apiConnected) {
    await createApiSession({ clearMessages: true });
  }
}

function setSolver(solverKey) {
  state.solver = solverKey;
  const profile = solverProfiles[solverKey];
  document.querySelector("#solverBackend").textContent = profile.backend;
  document.querySelector("#solverProblem").textContent = profile.problem;
  document.querySelector("#solverMethod").textContent = profile.method;
  document.querySelector("#metricObjective").textContent = profile.objective;
  document.querySelector("#metricBaseline").textContent = profile.baseline;
  document.querySelector("#metricImprovement").textContent = profile.improvement;
  document.querySelector("#resultStatus").textContent = profile.status;

  document.querySelectorAll(".segmented-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.solver === solverKey);
  });
}

function parsePdf() {
  addMessage(
    "assistant",
    "Parsed sample_brief.pdf. Domain: money market. Objective: maximize net yield. Constraints: 40% prime limit, 30% daily liquidity, 50% weekly liquidity, 60 day WAM, 45% single-fund limit.",
  );
  state.fields.portfolio = "PORT_204";
  state.fields.scenario = "Liquidity stress";
  updateSummary();
}

function exportResult() {
  const payload = state.latestPayload || {
    domain: "money_market",
    portfolio: state.fields.portfolio,
    solver: solverProfiles[state.solver],
    request: state.fields,
    result: {
      status: "optimal",
      objective_value: 5.2284,
      baseline_value: 5.0291,
      improvement_pct: 3.96,
      allocations: [
        { fund: "BNY Mellon Government Fund 3", amount: 250000000, weight: 0.5 },
        { fund: "BNY Mellon Prime Fund 7", amount: 200000000, weight: 0.4 },
        { fund: "BNY Mellon Government Fund 2", amount: 50000000, weight: 0.1 },
      ],
    },
  };

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "decision-intelligence-result.json";
  link.click();
  URL.revokeObjectURL(url);
}

async function createApiSession({ clearMessages = false } = {}) {
  try {
    const response = await fetch(`${API_BASE}/api/chat/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seed: 42, default_portfolio: "PORT_001" }),
    });
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    const body = await response.json();
    state.apiConnected = true;
    state.sessionId = body.session_id;
    workflowStatus.textContent = "API ready";
    workflowStatus.className = "status-pill status-optimal";
    if (clearMessages) {
      messages.replaceChildren();
      addMessage("assistant", body.assistant_message);
    } else {
      addMessage("assistant", "Connected to the local Python optimizer API.");
    }
  } catch {
    state.apiConnected = false;
    state.sessionId = null;
    addMessage("assistant", "API server not detected. Running in static prototype mode.");
  }
}

async function sendApiMessage(message) {
  if (!state.sessionId) {
    await createApiSession();
  }

  const response = await fetch(`${API_BASE}/api/chat/sessions/${state.sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    addMessage("assistant", `The API returned ${response.status}. Falling back to static mode.`);
    state.apiConnected = false;
    return;
  }

  const body = await response.json();
  addMessage("assistant", body.assistant_message);
  updateSummaryFromApi(body.state);

  if (body.result) {
    state.latestPayload = body;
    workflowStatus.textContent = "Complete";
    workflowStatus.className = "status-pill status-optimal";
    renderResult(body.result);
  }
}

function renderResult(result) {
  document.querySelector("#resultStatus").textContent = titleCase(result.status);
  document.querySelector("#metricObjective").textContent = `${Number(result.objective_value).toFixed(4)}%`;
  document.querySelector("#metricBaseline").textContent = `${Number(result.baseline_value).toFixed(4)}%`;
  document.querySelector("#metricImprovement").textContent =
    `${result.improvement >= 0 ? "+" : ""}${(Number(result.improvement) * 100).toFixed(2)} bps`;

  const metadata = result.solver_metadata || {};
  document.querySelector("#solverBackend").textContent = metadata.solver_backend || "scipy";
  document.querySelector("#solverProblem").textContent = metadata.problem_type || "lp";
  document.querySelector("#solverMethod").textContent = metadata.solver_method || metadata.solver || "HiGHS";

  allocationBody.replaceChildren(
    ...result.allocations.map((allocation) => {
      const row = document.createElement("tr");
      const cells = [
        allocation.label,
        formatCurrency(allocation.allocated_value),
        formatFraction(allocation.allocated_fraction),
        formatMaybePercent(allocation.metadata?.yield_7day),
        allocation.metadata?.wam_days ? `${allocation.metadata.wam_days}d` : "-",
      ];
      row.append(...cells.map(tableCell));
      return row;
    }),
  );

  sensitivityBody.replaceChildren(
    ...result.sensitivities.map((item) => {
      const row = document.createElement("tr");
      row.append(
        tableCell(titleCase(item.parameter.replaceAll("_", " "))),
        tableCell(Number(item.shadow_price).toFixed(4)),
        tableCell(item.interpretation || "-"),
      );
      return row;
    }),
  );
}

function formatAmount(value) {
  const raw = value.toLowerCase().replace(/[$,\s]/g, "");
  const number = Number.parseFloat(raw);
  if (Number.isNaN(number)) return "$500M";
  if (raw.includes("billion") || raw.endsWith("b")) return `$${number.toLocaleString()}B`;
  if (raw.includes("million") || raw.endsWith("m")) return `$${number.toLocaleString()}M`;
  if (number >= 1000000) return `$${(number / 1000000).toLocaleString()}M`;
  return `$${number.toLocaleString()}`;
}

function formatCurrency(value) {
  if (value === undefined || value === null || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  if (number >= 1_000_000_000) return `$${(number / 1_000_000_000).toFixed(1)}B`;
  if (number >= 1_000_000) return `$${(number / 1_000_000).toFixed(0)}M`;
  return `$${number.toLocaleString()}`;
}

function formatFraction(value) {
  if (value === undefined || value === null || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  if (number <= 1) return `${Math.round(number * 100)}%`;
  return `${number}%`;
}

function formatMaybePercent(value) {
  if (value === undefined || value === null || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return `${number.toFixed(2)}%`;
}

function formatScenarioList(value) {
  if (!Array.isArray(value) || value.length === 0) return "None";
  return value.map((item) => titleCase(String(item).replaceAll("_", " "))).join(", ");
}

function formatPercent(value) {
  const number = parseNumber(value, 0);
  return `${number}%`;
}

function formatScenario(value) {
  const raw = value.trim().toLowerCase();
  if (!raw || raw === "none" || raw === "no") return "None";
  if (raw.includes("credit")) return "Credit stress";
  if (raw.includes("downside")) return "Downside";
  if (raw.includes("inventory")) return "Inventory";
  return "Stress";
}

function parseNumber(value, fallback) {
  const match = String(value).match(/[\d.]+/);
  if (!match) return fallback;
  const parsed = Number.parseFloat(match[0]);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function tableCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
}

function titleCase(value) {
  return String(value)
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

document.querySelectorAll(".segmented-button").forEach((button) => {
  button.addEventListener("click", () => setSolver(button.dataset.solver));
});

document.querySelectorAll("[data-fill]").forEach((button) => {
  button.addEventListener("click", () => {
    chatInput.value = button.dataset.fill;
    chatInput.focus();
  });
});

chatForm.addEventListener("submit", handleChatSubmit);
resetButton.addEventListener("click", resetSession);
parsePdfButton.addEventListener("click", parsePdf);
exportButton.addEventListener("click", exportResult);

updateSummary();
createApiSession();
