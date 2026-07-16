const messages = document.querySelector("#messages");
const chatForm = document.querySelector("#chatForm");
const chatInput = document.querySelector("#chatInput");
const resetButton = document.querySelector("#resetButton");
const exportButton = document.querySelector("#exportButton");
const parsePdfButton = document.querySelector("#parsePdfButton");
const requestSummary = document.querySelector("#requestSummary");
const workflowStatus = document.querySelector("#workflowStatus");

const state = {
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

function completeRun() {
  workflowStatus.textContent = "Complete";
  workflowStatus.className = "status-pill status-optimal";
  addMessage(
    "assistant",
    "Confirmed. The optimizer found an allocation that improves yield while satisfying liquidity, WAM, and concentration limits.",
  );
}

function handleChatSubmit(event) {
  event.preventDefault();
  const raw = chatInput.value.trim();
  if (!raw) return;

  addMessage("user", raw);
  chatInput.value = "";

  if (raw.toLowerCase() === "reset") {
    resetSession();
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

function resetSession() {
  state.step = 0;
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
  const payload = {
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

function formatAmount(value) {
  const raw = value.toLowerCase().replace(/[$,\s]/g, "");
  const number = Number.parseFloat(raw);
  if (Number.isNaN(number)) return "$500M";
  if (raw.includes("billion") || raw.endsWith("b")) return `$${number.toLocaleString()}B`;
  if (raw.includes("million") || raw.endsWith("m")) return `$${number.toLocaleString()}M`;
  if (number >= 1000000) return `$${(number / 1000000).toLocaleString()}M`;
  return `$${number.toLocaleString()}`;
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
