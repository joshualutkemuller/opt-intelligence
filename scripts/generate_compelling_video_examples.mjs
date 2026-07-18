#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(new URL("../frontend/app/package.json", import.meta.url));
const { chromium } = require("playwright");

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(repoRoot, "video_examples");

const scenarios = [
  {
    filename: "liquidity-stress-orchestration-example.webm",
    title: "Liquidity Stress Orchestration",
    subtitle: "Cash, collateral, and financing workflow in one governed run",
    audience: "Treasury, funding desk, market risk, and governance reviewers",
    durationSeconds: 72,
    sourceSeconds: 90,
    accent: "#5FD4CF",
    secondary: "#89D185",
    domain: "Enterprise Liquidity",
    workflow: "Stress Orchestration",
    request: "Can we protect liquidity and reduce funding drag under a market stress?",
    headlineMetrics: [
      ["Cash protected", "$500M"],
      ["Yield lift", "+19.9 bps"],
      ["Approval tier", "Tier 4"],
    ],
    timeline: [
      "Collect intent",
      "Plan steps",
      "Run dependencies",
      "Validate controls",
      "Export evidence",
    ],
    scenes: [
      {
        start: 0,
        headline: "A business question becomes a governed workflow",
        support:
          "The demo opens with plain-English intent, then converts it into sequenced optimizers and reviewer-ready controls.",
        stage: 0,
        leftTitle: "User intent",
        leftRows: [
          "Protect same-day and weekly liquidity",
          "Avoid concentration in prime funds",
          "Respect collateral pressure from stress moves",
          "Show the evidence path before action",
        ],
        rightTitle: "Agent response",
        rightRows: [
          "Classifies request as liquidity stress",
          "Builds a cross-step execution plan",
          "Selects money market, collateral, and financing engines",
          "Marks approvals before implementation",
        ],
        chat: [
          ["User", "Optimize liquidity under a funding stress."],
          ["Assistant", "I will run a sequenced stress workflow and show review gates."],
        ],
      },
      {
        start: 14,
        headline: "The plan runs in dependency order",
        support:
          "Collateral pressure and financing costs feed the money-market allocation rather than appearing as isolated charts.",
        stage: 1,
        leftTitle: "Execution plan",
        leftRows: [
          "1. Read liquidity policy and cash position",
          "2. Run collateral stress estimate",
          "3. Run financing fallback costs",
          "4. Allocate money-market balances",
        ],
        rightTitle: "Dependency context",
        rightRows: [
          "Stress liquidity buffer: $150M",
          "Prime fund cap: 40%",
          "Single fund limit: 50%",
          "Max WAM: 60 days",
        ],
        chartTitle: "Workflow progress",
        bars: [
          ["Collateral", 0.78, "#7AA2F7"],
          ["Financing", 0.56, "#E9C46A"],
          ["Cash Allocation", 0.38, "#5FD4CF"],
        ],
      },
      {
        start: 30,
        headline: "Optimization output is tied to live constraints",
        support:
          "The recommendation shows expected benefit and which limits are active, so the reviewer can see why the answer changed.",
        stage: 2,
        leftTitle: "Recommendation",
        leftRows: [
          "Optimized net yield: 5.2284%",
          "Baseline yield: 5.0291%",
          "Improvement: +19.93 bps",
          "Result status: optimal",
        ],
        rightTitle: "Binding checks",
        rightRows: [
          "Prime concentration is active",
          "Single fund limit is active",
          "Daily liquidity remains above threshold",
          "Weekly liquidity remains above threshold",
        ],
        chartTitle: "Allocation mix",
        bars: [
          ["Govt fund", 0.50, "#89D185"],
          ["Prime fund", 0.40, "#5FD4CF"],
          ["Reserve cash", 0.10, "#E9C46A"],
        ],
      },
      {
        start: 47,
        headline: "Governance is visible before the run becomes an action",
        support:
          "The workflow separates recommendation from execution and surfaces approval tier, materiality, and blocking exceptions.",
        stage: 3,
        leftTitle: "Review gate",
        leftRows: [
          "Execution mode: recommendation",
          "Materiality: $500M",
          "Estimated PnL impact: $0",
          "Production constraint change: no",
        ],
        rightTitle: "Approval logic",
        rightRows: [
          "Tier 4 because stress scenario is active",
          "Evidence export is required",
          "Policy constraints are traceable",
          "No blocked validation issues",
        ],
        chat: [
          ["Assistant", "Recommendation is ready for review."],
          ["Reviewer", "Show the binding constraints and audit narrative."],
          ["Assistant", "Export package includes plan, trace, validation, and output."],
        ],
      },
      {
        start: 61,
        headline: "The close is an evidence package, not just a chart",
        support:
          "A nontechnical audience sees the ask, the plan, the result, the controls, and the export path in under a minute and a half.",
        stage: 4,
        leftTitle: "Export contents",
        leftRows: [
          "Request summary",
          "Execution plan and trace",
          "Step results and dependencies",
          "Validation and governance narrative",
        ],
        rightTitle: "Presenter takeaway",
        rightRows: [
          "Natural-language workflow entry",
          "Deterministic optimizer backbone",
          "Explainability at every step",
          "Governance-ready proof",
        ],
      },
    ],
  },
  {
    filename: "mvo-constraint-negotiation-example.webm",
    title: "MVO Constraint Negotiation",
    subtitle: "A portfolio rebalance demo with guided tradeoff exploration",
    audience: "CIO office, portfolio managers, advisors, and investment risk teams",
    durationSeconds: 76,
    sourceSeconds: 95,
    accent: "#89D185",
    secondary: "#7AA2F7",
    domain: "Asset Allocation",
    workflow: "Balanced MVO Rebalance",
    request: "Find a multi-asset allocation, then show how to improve the tradeoff.",
    headlineMetrics: [
      ["Target return", "5.0%"],
      ["Risk aversion", "3.0"],
      ["Cash floor", "2.0%"],
    ],
    timeline: [
      "Run MVO",
      "Explain tradeoff",
      "Ask improvement",
      "Negotiate limits",
      "Review decision",
    ],
    scenes: [
      {
        start: 0,
        headline: "The demo starts as a portfolio construction conversation",
        support:
          "The user chooses a balanced MVO preset and sees the assumptions that drive risk-return tradeoffs.",
        stage: 0,
        leftTitle: "Preset inputs",
        leftRows: [
          "Portfolio notional: $250M",
          "Target annual return: 5.0%",
          "Risk aversion lambda: 3",
          "Max single asset weight: 45%",
        ],
        rightTitle: "Optimizer model",
        rightRows: [
          "Long-only constrained portfolio",
          "Objective balances return and variance",
          "Cash floor and concentration caps",
          "Deterministic simulation seed: 42",
        ],
        chat: [
          ["User", "Build a balanced portfolio but keep concentration controlled."],
          ["Assistant", "I will run the MVO rebalance and explain the active limits."],
        ],
      },
      {
        start: 15,
        headline: "Risk and return are shown as the core tradeoff",
        support:
          "The output is framed in language a committee can use: expected return, volatility, Sharpe, and constraint pressure.",
        stage: 1,
        leftTitle: "Current recommendation",
        leftRows: [
          "Expected return: 5.1%",
          "Volatility: 7.8%",
          "Sharpe: 0.42",
          "Status: optimal",
        ],
        rightTitle: "Top allocation drivers",
        rightRows: [
          "US equity adds growth",
          "Core bonds lower variance",
          "Cash floor preserves liquidity",
          "Alternatives diversify the tail",
        ],
        chartTitle: "Risk contribution",
        bars: [
          ["Equity", 0.62, "#89D185"],
          ["Bonds", 0.22, "#7AA2F7"],
          ["Alternatives", 0.12, "#E9C46A"],
          ["Cash", 0.04, "#5FD4CF"],
        ],
      },
      {
        start: 31,
        headline: "The user can ask for a better outcome",
        support:
          "Constraint negotiation turns a vague request into concrete proposed changes, with impact estimates and review status.",
        stage: 2,
        leftTitle: "Follow-up ask",
        leftRows: [
          "Can we improve utility?",
          "Keep cash at least 2%",
          "Avoid overconcentration",
          "Explain any needed relaxation",
        ],
        rightTitle: "Agent interpretation",
        rightRows: [
          "Searches controllable constraints",
          "Tests relaxation candidates",
          "Ranks by benefit and governance impact",
          "Keeps original plan available for replay",
        ],
        chat: [
          ["User", "Can we get more expected return without breaking the policy?"],
          ["Assistant", "I found two candidate changes and one is governance-light."],
        ],
      },
      {
        start: 49,
        headline: "Tradeoff options become committee-ready choices",
        support:
          "The platform makes the constraint conversation explicit instead of hiding it inside solver parameters.",
        stage: 3,
        leftTitle: "Candidate A",
        leftRows: [
          "Raise single asset cap: 45% to 50%",
          "Estimated utility lift: medium",
          "Governance tier: 3",
          "No target return change",
        ],
        rightTitle: "Candidate B",
        rightRows: [
          "Lower risk aversion: 3.0 to 2.6",
          "Estimated return lift: higher",
          "Governance tier: 4",
          "Requires risk acknowledgement",
        ],
        chartTitle: "Tradeoff score",
        bars: [
          ["Base", 0.46, "#9CB2B4"],
          ["Candidate A", 0.64, "#89D185"],
          ["Candidate B", 0.72, "#E9C46A"],
        ],
      },
      {
        start: 64,
        headline: "The final moment is an informed decision",
        support:
          "The presenter can show what changed, why it helped, and what approvals would be required before production action.",
        stage: 4,
        leftTitle: "Decision packet",
        leftRows: [
          "Base result retained",
          "Candidate scenarios compared",
          "Constraint differences highlighted",
          "Audit narrative generated",
        ],
        rightTitle: "Why it stands out",
        rightRows: [
          "Interactive after the first solve",
          "Clear risk-return language",
          "Transparent governance tradeoff",
          "Repeatable demo path",
        ],
      },
    ],
  },
  {
    filename: "policy-to-audit-evidence-example.webm",
    title: "Policy to Audit Evidence",
    subtitle: "A document-driven workflow that ends with reviewable proof",
    audience: "Model risk, compliance, treasury operations, and executive sponsors",
    durationSeconds: 68,
    sourceSeconds: 85,
    accent: "#E9C46A",
    secondary: "#5FD4CF",
    domain: "Controls and Evidence",
    workflow: "Policy Ingestion to Audit Narrative",
    request: "Use policy language to constrain the workflow and produce an audit-ready packet.",
    headlineMetrics: [
      ["Policy clauses", "8"],
      ["Controls mapped", "6"],
      ["Blocking issues", "0"],
    ],
    timeline: [
      "Ingest policy",
      "Map controls",
      "Run workflow",
      "Explain result",
      "Package proof",
    ],
    scenes: [
      {
        start: 0,
        headline: "The workflow starts from policy, not tribal knowledge",
        support:
          "The demo shows how constraints can be captured from business documentation and made visible in the run state.",
        stage: 0,
        leftTitle: "Source policy",
        leftRows: [
          "Minimum daily liquidity",
          "Issuer and fund concentration",
          "Stress scenario review requirement",
          "Materiality threshold",
        ],
        rightTitle: "Structured controls",
        rightRows: [
          "daily_liquidity_min = 30%",
          "single_fund_max = 50%",
          "stress_review_required = true",
          "materiality_notional = $250M",
        ],
        chat: [
          ["User", "Use our policy rules before running the recommendation."],
          ["Assistant", "I mapped policy clauses into workflow constraints."],
        ],
      },
      {
        start: 13,
        headline: "Extracted controls are visible before execution",
        support:
          "A reviewer can see what the agent believes the policy says, then approve, edit, or block before the workflow runs.",
        stage: 1,
        leftTitle: "Control review",
        leftRows: [
          "Rule source: policy upload",
          "Confidence: high",
          "Owner: treasury policy",
          "Effective mode: recommendation",
        ],
        rightTitle: "Validation checks",
        rightRows: [
          "All required limits present",
          "No contradictory clauses",
          "Stress review clause detected",
          "Audit references retained",
        ],
        chartTitle: "Control coverage",
        bars: [
          ["Liquidity", 1.0, "#E9C46A"],
          ["Concentration", 0.88, "#5FD4CF"],
          ["Governance", 0.78, "#89D185"],
          ["Evidence", 0.92, "#7AA2F7"],
        ],
      },
      {
        start: 28,
        headline: "The optimizer run carries policy context through each step",
        support:
          "Policy-derived constraints are part of the workflow context, so downstream recommendations inherit the same control language.",
        stage: 2,
        leftTitle: "Run result",
        leftRows: [
          "Workflow status: completed",
          "Validation summary: ready",
          "Trace events: generated",
          "Step results: persisted",
        ],
        rightTitle: "Evidence anchors",
        rightRows: [
          "Input assumptions",
          "Policy control IDs",
          "Solver metadata",
          "Governance tier decision",
        ],
        chartTitle: "Evidence maturity",
        bars: [
          ["Inputs", 0.95, "#5FD4CF"],
          ["Plan", 0.82, "#E9C46A"],
          ["Trace", 0.9, "#89D185"],
          ["Narrative", 0.76, "#7AA2F7"],
        ],
      },
      {
        start: 45,
        headline: "Audit narrative explains what happened in business terms",
        support:
          "The closeout language is designed for reviewers: what was requested, what ran, what changed, and what controls were checked.",
        stage: 3,
        leftTitle: "Narrative sections",
        leftRows: [
          "Business request",
          "Workflow plan",
          "Constraint interpretation",
          "Recommendation and approvals",
        ],
        rightTitle: "Reviewer questions answered",
        rightRows: [
          "Why did the agent choose this workflow?",
          "Which constraints shaped the result?",
          "Were there validation exceptions?",
          "What approval tier applies?",
        ],
        chat: [
          ["Reviewer", "Can I see the evidence behind the recommendation?"],
          ["Assistant", "Yes. The package links inputs, trace, validation, and output."],
        ],
      },
      {
        start: 58,
        headline: "The export package is the differentiation",
        support:
          "Most demos stop at an answer. This one shows a governed operating model for how optimization decisions get explained and reviewed.",
        stage: 4,
        leftTitle: "Package contents",
        leftRows: [
          "Policy extraction summary",
          "Workflow plan and trace",
          "Validation and approvals",
          "Optimization result JSON",
        ],
        rightTitle: "Presenter takeaway",
        rightRows: [
          "Policy-aware demos feel credible",
          "Controls reduce stakeholder anxiety",
          "Evidence makes the idea enterprise-ready",
          "All workflows can share the pattern",
        ],
      },
    ],
  },
];

fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1,
  });

  for (const scenario of scenarios) {
    await page.setContent(renderRecorderPage(), { waitUntil: "domcontentloaded" });
    const bytes = await page.evaluate(async (scenarioConfig) => {
      return window.renderScenarioVideo(scenarioConfig);
    }, scenario);
    const outputPath = path.join(outDir, scenario.filename);
    fs.writeFileSync(outputPath, Buffer.from(bytes));
    const sizeMb = fs.statSync(outputPath).size / (1024 * 1024);
    console.log(
      `Wrote video_examples/${scenario.filename} (${scenario.durationSeconds}s, ${sizeMb.toFixed(
        1,
      )} MB)`,
    );
  }
} finally {
  await browser.close();
}

function renderRecorderPage() {
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    html, body { margin: 0; background: #071014; }
    canvas { display: block; }
  </style>
</head>
<body>
<canvas id="stage" width="1280" height="720"></canvas>
<script>
const canvas = document.getElementById("stage");
const ctx = canvas.getContext("2d");
const WIDTH = canvas.width;
const HEIGHT = canvas.height;
const COLORS = {
  bg: "#071014",
  bg2: "#0B171D",
  panel: "#101B21",
  panel2: "#16252C",
  panel3: "#1C2C33",
  ink: "#F1F5F4",
  muted: "#9CB2B4",
  faint: "#678184",
  line: "#2E454B",
  red: "#F07178",
  blue: "#7AA2F7",
  green: "#89D185",
  amber: "#E9C46A",
  cyan: "#5FD4CF"
};

window.renderScenarioVideo = async function renderScenarioVideo(scenario) {
  const stream = canvas.captureStream(30);
  const mimeTypes = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"];
  const mimeType = mimeTypes.find((type) => MediaRecorder.isTypeSupported(type)) || "";
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType, videoBitsPerSecond: 2800000 } : undefined);
  const chunks = [];
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };

  const done = new Promise((resolve) => {
    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: recorder.mimeType || "video/webm" });
      const buffer = await blob.arrayBuffer();
      resolve(Array.from(new Uint8Array(buffer)));
    };
  });

  const start = performance.now();
  const durationMs = scenario.durationSeconds * 1000;
  recorder.start(1000);

  await new Promise((resolve) => {
    function tick(now) {
      const elapsedMs = Math.min(now - start, durationMs);
      drawScenario(scenario, elapsedMs / 1000, elapsedMs / durationMs);
      if (elapsedMs < durationMs) {
        requestAnimationFrame(tick);
      } else {
        resolve();
      }
    }
    requestAnimationFrame(tick);
  });

  recorder.stop();
  stream.getTracks().forEach((track) => track.stop());
  return done;
};

function drawScenario(scenario, seconds, progress) {
  const scene = getScene(scenario.scenes, seconds);
  const sceneProgress = getSceneProgress(scenario.scenes, scene, seconds);
  drawBackground(scenario, progress);
  drawTopBar(scenario);
  drawHero(scenario, scene, sceneProgress);
  drawMetrics(scenario, progress);
  drawMainPanels(scenario, scene, sceneProgress);
  drawTimeline(scenario, scene.stage, progress);
  drawFooter(scenario, progress);
}

function getScene(scenes, seconds) {
  let selected = scenes[0];
  for (const scene of scenes) {
    if (seconds >= scene.start) selected = scene;
  }
  return selected;
}

function getSceneProgress(scenes, scene, seconds) {
  const index = scenes.indexOf(scene);
  const next = scenes[index + 1];
  const end = next ? next.start : Math.max(scene.start + 8, 999);
  return clamp((seconds - scene.start) / (end - scene.start), 0, 1);
}

function drawBackground(scenario, progress) {
  const gradient = ctx.createLinearGradient(0, 0, WIDTH, HEIGHT);
  gradient.addColorStop(0, "#071014");
  gradient.addColorStop(0.55, "#0B171D");
  gradient.addColorStop(1, "#111D1F");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);

  ctx.globalAlpha = 0.07;
  ctx.strokeStyle = scenario.accent;
  ctx.lineWidth = 1;
  for (let x = -120 + ((progress * 240) % 120); x < WIDTH + 120; x += 120) {
    ctx.beginPath();
    ctx.moveTo(x, 96);
    ctx.lineTo(x - 240, HEIGHT);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

function drawTopBar(scenario) {
  ctx.fillStyle = "#0D1A20";
  ctx.fillRect(0, 0, WIDTH, 84);
  ctx.fillStyle = scenario.accent;
  roundRect(56, 20, 52, 44, 10, true);
  ctx.fillStyle = "#071014";
  text("DI", 71, 51, 24, "bold");
  ctx.fillStyle = COLORS.ink;
  text("Decision Intelligence", 128, 36, 24, "600");
  ctx.fillStyle = COLORS.muted;
  text(scenario.domain, 128, 61, 16, "500");
  pill(WIDTH - 318, 24, "silent presentation clip", COLORS.panel2, COLORS.muted);
  pill(WIDTH - 142, 24, "1.25x pacing", COLORS.panel2, scenario.accent);
}

function drawHero(scenario, scene, sceneProgress) {
  const y = 112;
  ctx.fillStyle = COLORS.muted;
  text(scenario.workflow, 56, y, 18, "600");
  ctx.fillStyle = COLORS.ink;
  wrapText(scene.headline, 56, y + 45, 760, 44, 38, "700");
  ctx.fillStyle = COLORS.muted;
  wrapText(scene.support, 58, y + 142, 760, 27, 20, "400");

  const cardX = 910;
  const cardY = 112;
  panel(cardX, cardY, 314, 150);
  ctx.fillStyle = COLORS.faint;
  text("Presenter setup", cardX + 24, cardY + 35, 17, "600");
  ctx.fillStyle = COLORS.ink;
  wrapText(scenario.audience, cardX + 24, cardY + 72, 264, 25, 18, "500");

  const shimmer = 0.35 + Math.sin(sceneProgress * Math.PI) * 0.2;
  ctx.globalAlpha = shimmer;
  ctx.fillStyle = scenario.accent;
  roundRect(56, 308, 740 * sceneProgress, 4, 2, true);
  ctx.globalAlpha = 1;
}

function drawMetrics(scenario, progress) {
  const startX = 56;
  scenario.headlineMetrics.forEach((metric, index) => {
    const x = startX + index * 250;
    const y = 348;
    panel(x, y, 226, 94);
    ctx.fillStyle = COLORS.muted;
    text(metric[0], x + 20, y + 32, 15, "600");
    ctx.fillStyle = index === 0 ? scenario.accent : index === 1 ? scenario.secondary : COLORS.amber;
    text(metric[1], x + 20, y + 72, 32, "800");
  });

  panel(830, 308, 394, 134);
  ctx.fillStyle = COLORS.faint;
  text("Opening request", 854, 340, 16, "600");
  ctx.fillStyle = COLORS.ink;
  wrapText(scenario.request, 854, 374, 342, 27, 20, "500");
}

function drawMainPanels(scenario, scene, sceneProgress) {
  const y = 470;
  const leftW = scene.chat ? 420 : 520;
  panel(56, y, leftW, 166);
  panel(56 + leftW + 24, y, leftW, 166);
  drawListPanel(56, y, leftW, scene.leftTitle, scene.leftRows, scenario.accent);
  drawListPanel(56 + leftW + 24, y, leftW, scene.rightTitle, scene.rightRows, scenario.secondary);

  if (scene.chat) {
    panel(920, y, 304, 166);
    ctx.fillStyle = COLORS.faint;
    text("Guided chat", 944, y + 31, 15, "700");
    let lineY = y + 60;
    scene.chat.forEach(([speaker, message], index) => {
      ctx.fillStyle = speaker === "User" || speaker === "Reviewer" ? COLORS.amber : scenario.accent;
      text(speaker, 944, lineY, 13, "700");
      ctx.fillStyle = COLORS.ink;
      wrapText(message, 944, lineY + 20, 254, 19, 13, "500");
      lineY += index === 0 ? 53 : 48;
    });
  } else {
    panel(920, y, 304, 166);
    ctx.fillStyle = COLORS.faint;
    text(scene.chartTitle || "Scenario view", 944, y + 31, 15, "700");
    drawBars(944, y + 58, 244, scene.bars || [], sceneProgress);
  }
}

function drawListPanel(x, y, width, title, rows, accent) {
  ctx.fillStyle = accent;
  roundRect(x + 20, y + 22, 5, 24, 3, true);
  ctx.fillStyle = COLORS.ink;
  text(title, x + 36, y + 42, 18, "700");
  rows.slice(0, 4).forEach((row, index) => {
    const rowY = y + 72 + index * 23;
    ctx.fillStyle = COLORS.line;
    roundRect(x + 22, rowY - 10, 7, 7, 4, true);
    ctx.fillStyle = COLORS.muted;
    wrapText(row, x + 42, rowY, width - 68, 19, 14, "500", 1);
  });
}

function drawBars(x, y, width, bars, sceneProgress) {
  bars.forEach(([label, value, color], index) => {
    const rowY = y + index * 26;
    ctx.fillStyle = COLORS.muted;
    text(label, x, rowY + 13, 12, "600");
    ctx.fillStyle = COLORS.panel3;
    roundRect(x + 94, rowY, width - 94, 12, 6, true);
    ctx.fillStyle = color;
    roundRect(x + 94, rowY, (width - 94) * value * easeOut(sceneProgress), 12, 6, true);
  });
}

function drawTimeline(scenario, activeStage, progress) {
  const x = 56;
  const y = 660;
  const width = 1168;
  const count = scenario.timeline.length;
  ctx.strokeStyle = COLORS.line;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x + 20, y);
  ctx.lineTo(x + width - 20, y);
  ctx.stroke();

  scenario.timeline.forEach((label, index) => {
    const stepX = x + (width - 40) * (index / (count - 1)) + 20;
    const complete = index <= activeStage;
    ctx.fillStyle = complete ? scenario.accent : COLORS.panel3;
    ctx.beginPath();
    ctx.arc(stepX, y, complete ? 13 : 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = complete ? COLORS.ink : COLORS.faint;
    text(label, stepX - 58, y + 34, 13, complete ? "700" : "500");
  });

  ctx.fillStyle = scenario.secondary;
  roundRect(x, y - 34, width * progress, 3, 2, true);
}

function drawFooter(scenario, progress) {
  ctx.fillStyle = COLORS.faint;
  text("Final runtime: " + scenario.durationSeconds + "s from a " + scenario.sourceSeconds + "s story arc", 56, 704, 12, "500");
  ctx.fillStyle = COLORS.faint;
  text("Generated locally from scripts/generate_compelling_video_examples.mjs", 850, 704, 12, "500");
}

function panel(x, y, w, h) {
  ctx.fillStyle = "rgba(16, 27, 33, 0.94)";
  roundRect(x, y, w, h, 8, true);
  ctx.strokeStyle = COLORS.line;
  ctx.lineWidth = 1;
  roundRect(x, y, w, h, 8, false);
}

function pill(x, y, label, fill, color) {
  ctx.font = "600 14px Inter, SF Pro Text, Arial, sans-serif";
  const w = ctx.measureText(label).width + 26;
  ctx.fillStyle = fill;
  roundRect(x, y, w, 32, 16, true);
  ctx.fillStyle = color;
  text(label, x + 13, y + 21, 14, "600");
}

function text(value, x, y, size, weight = "400") {
  ctx.font = weight + " " + size + "px Inter, SF Pro Text, Helvetica Neue, Arial, sans-serif";
  ctx.fillText(value, x, y);
}

function wrapText(value, x, y, maxWidth, lineHeight, size, weight = "400", maxLines = 3) {
  ctx.font = weight + " " + size + "px Inter, SF Pro Text, Helvetica Neue, Arial, sans-serif";
  const words = value.split(" ");
  let line = "";
  let lines = 0;
  for (const word of words) {
    const test = line ? line + " " + word : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, y);
      y += lineHeight;
      line = word;
      lines += 1;
      if (lines >= maxLines - 1) break;
    } else {
      line = test;
    }
  }
  if (line && lines < maxLines) ctx.fillText(line, x, y);
}

function roundRect(x, y, w, h, r, fill) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
  if (fill) ctx.fill();
  else ctx.stroke();
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function easeOut(value) {
  return 1 - Math.pow(1 - clamp(value, 0, 1), 3);
}
</script>
</body>
</html>`;
}
