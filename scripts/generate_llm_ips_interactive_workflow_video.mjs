#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(new URL("../frontend/app/package.json", import.meta.url));
const { chromium } = require("playwright");

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(repoRoot, "video_examples");
const outputMp4 = path.join(outDir, "llm-assisted-ips-interactive-optimization-example.mp4");
const tempWebm = path.join(os.tmpdir(), "llm-assisted-ips-interactive-optimization-example.webm");

const scenario = {
  durationSeconds: Number(process.env.VIDEO_DURATION_SECONDS || 86),
  accent: "#5FD4CF",
  secondary: "#89D185",
  model: "llama3.1:8b",
  baseUrl: "http://localhost:11434/v1",
  before: {
    expectedReturn: "4.72%",
    volatility: "8.35%",
    sharpe: "0.31",
    cash: "1.2%",
    maxWeight: "52%",
    status: "2 policy exceptions",
    allocation: [
      ["US Equity", 0.52, "#7AA2F7"],
      ["Core Bonds", 0.24, "#89D185"],
      ["Alternatives", 0.15, "#E9C46A"],
      ["Cash", 0.012, "#5FD4CF"],
    ],
  },
  after: {
    expectedReturn: "5.25%",
    volatility: "7.68%",
    sharpe: "0.43",
    cash: "3.0%",
    maxWeight: "40%",
    status: "Ready",
    allocation: [
      ["US Equity", 0.40, "#7AA2F7"],
      ["Core Bonds", 0.32, "#89D185"],
      ["Alternatives", 0.25, "#E9C46A"],
      ["Cash", 0.03, "#5FD4CF"],
    ],
  },
  extracted: [
    ["portfolio_id", "PORT_MVO_900", "applied"],
    ["portfolio_notional", "$250M", "applied"],
    ["target_return", "5.25%", "applied"],
    ["risk_aversion", "3.5", "applied"],
    ["max_single_asset_weight", "40%", "applied"],
    ["min_cash_weight", "3%", "applied"],
    ["unapproved_drawdown_limit", "15%", "rejected"],
  ],
};

fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1,
  });
  page.on("pageerror", (error) => console.error(error));
  await page.setContent(renderPage(), { waitUntil: "domcontentloaded" });
  const bytes = await page.evaluate(
    async (config) => window.recordLlmIpsInteractiveWorkflow(config),
    scenario,
  );
  fs.writeFileSync(tempWebm, Buffer.from(bytes));
} finally {
  await browser.close();
}

const ffmpegPath = resolveFfmpegPath();
const result = spawnSync(
  ffmpegPath,
  [
    "-y",
    "-i",
    tempWebm,
    "-vf",
    "fps=30,scale=trunc(iw/2)*2:trunc(ih/2)*2",
    "-r",
    "30",
    "-c:v",
    "libx264",
    "-preset",
    "medium",
    "-crf",
    "23",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    outputMp4,
  ],
  { encoding: "utf-8" },
);

if (result.status !== 0) {
  process.stderr.write(result.stdout || "");
  process.stderr.write(result.stderr || "");
  process.exit(result.status ?? 1);
}

fs.rmSync(tempWebm, { force: true });
const sizeMb = fs.statSync(outputMp4).size / (1024 * 1024);
console.log(
  `Wrote video_examples/llm-assisted-ips-interactive-optimization-example.mp4 (${scenario.durationSeconds}s, ${sizeMb.toFixed(
    1,
  )} MB)`,
);

function resolveFfmpegPath() {
  if (process.env.FFMPEG_PATH) return process.env.FFMPEG_PATH;
  try {
    return require("@ffmpeg-installer/ffmpeg").path;
  } catch {
    return "ffmpeg";
  }
}

function renderPage() {
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

window.recordLlmIpsInteractiveWorkflow = async function recordLlmIpsInteractiveWorkflow(scenario) {
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
      resolve(Array.from(new Uint8Array(await blob.arrayBuffer())));
    };
  });
  const start = performance.now();
  const durationMs = scenario.durationSeconds * 1000;
  recorder.start(1000);
  await new Promise((resolve, reject) => {
    const watchdog = setTimeout(() => reject(new Error("Recording timed out.")), durationMs + 15000);
    function tick(now) {
      try {
        const elapsedMs = Math.max(0, Math.min(now - start, durationMs));
        draw(scenario, elapsedMs / 1000, elapsedMs / durationMs);
        if (elapsedMs < durationMs) {
          requestAnimationFrame(tick);
        } else {
          clearTimeout(watchdog);
          resolve();
        }
      } catch (error) {
        clearTimeout(watchdog);
        reject(error);
      }
    }
    requestAnimationFrame(tick);
  });
  recorder.stop();
  stream.getTracks().forEach((track) => track.stop());
  return done;
};

function draw(scenario, seconds, progress) {
  drawBackground(progress);
  drawHeader(scenario);
  const phase = getPhase(seconds);
  drawTitle(phase);
  if (phase === 0) drawBackendConfig(scenario);
  if (phase === 1) drawInteraction(scenario, seconds);
  if (phase === 2) drawLlmExtraction(scenario);
  if (phase === 3) drawValidatorReview(scenario);
  if (phase === 4) drawBeforeAnalytics(scenario);
  if (phase === 5) drawOptimizationRun(scenario, seconds);
  if (phase === 6) drawAfterComparison(scenario);
  drawTimeline(phase, progress);
  drawFooter(scenario);
}

function getPhase(seconds) {
  if (seconds < 11) return 0;
  if (seconds < 24) return 1;
  if (seconds < 37) return 2;
  if (seconds < 50) return 3;
  if (seconds < 62) return 4;
  if (seconds < 73) return 5;
  return 6;
}

function drawBackground(progress) {
  const gradient = ctx.createLinearGradient(0, 0, WIDTH, HEIGHT);
  gradient.addColorStop(0, "#071014");
  gradient.addColorStop(0.58, "#0B171D");
  gradient.addColorStop(1, "#111D1F");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
  ctx.globalAlpha = 0.07;
  ctx.strokeStyle = COLORS.cyan;
  for (let x = -180 + ((progress * 320) % 160); x < WIDTH + 180; x += 160) {
    ctx.beginPath();
    ctx.moveTo(x, 84);
    ctx.lineTo(x - 260, HEIGHT);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

function drawHeader(scenario) {
  ctx.fillStyle = "#0D1A20";
  ctx.fillRect(0, 0, WIDTH, 84);
  ctx.fillStyle = scenario.accent;
  roundRect(56, 20, 52, 44, 10, true);
  ctx.fillStyle = "#071014";
  text("DI", 71, 51, 24, "800");
  ctx.fillStyle = COLORS.ink;
  text("Decision Intelligence", 128, 36, 24, "700");
  ctx.fillStyle = COLORS.muted;
  text("LLM-assisted IPS ingestion with deterministic validation", 128, 61, 16, "500");
  pill(1008, 24, "MP4 presentation clip", COLORS.panel2, COLORS.muted);
}

function drawTitle(phase) {
  const copy = [
    ["Configure local Ollama", "The IPS backend is set to LLM mode with an OpenAI-compatible local endpoint."],
    ["Interact with the workflow", "The user asks the agent to ingest the IPS PDF and prepare an optimization review."],
    ["LLM extracts policy fields", "Ollama interprets messy IPS language and proposes structured workflow inputs."],
    ["Validator gates the output", "Code filters unsupported fields and applies only valid constraints to the workflow."],
    ["Before portfolio analytics", "The current portfolio shows policy breaches before optimization."],
    ["Run governed optimization", "The reviewed IPS patch drives a plan-based MVO rebalance."],
    ["After analytics and decision", "The final comparison shows investment impact plus policy readiness."],
  ][phase];
  ctx.fillStyle = COLORS.muted;
  text("LLM-Assisted IPS Ingestion Backend", 56, 116, 18, "700");
  ctx.fillStyle = COLORS.ink;
  text(copy[0], 56, 166, 39, "800");
  ctx.fillStyle = COLORS.muted;
  wrapText(copy[1], 58, 206, 780, 28, 20, "500");
}

function drawBackendConfig(scenario) {
  panel(56, 260, 548, 368);
  ctx.fillStyle = COLORS.faint;
  text("API request configuration", 88, 302, 16, "700");
  const rows = [
    ["backend", "llm"],
    ["provider", "openai"],
    ["model", scenario.model],
    ["base_url", scenario.baseUrl],
    ["api_key", "not-needed"],
  ];
  rows.forEach(([key, value], index) => {
    const y = 354 + index * 48;
    ctx.fillStyle = COLORS.panel3;
    roundRect(88, y - 28, 470, 34, 6, true);
    ctx.fillStyle = COLORS.muted;
    text(key, 106, y - 5, 16, "700");
    ctx.fillStyle = key === "backend" ? COLORS.cyan : COLORS.ink;
    text(value, 252, y - 5, 16, "800");
  });
  panel(644, 260, 580, 368);
  ctx.fillStyle = COLORS.faint;
  text("Why this matters", 676, 302, 16, "700");
  [
    "Ollama handles the flexible language interpretation.",
    "The response still lands in the same PolicyIngestionResult contract.",
    "The deterministic validator remains the final control gate.",
    "The optimizer only receives approved, typed workflow fields.",
  ].forEach((line, index) => bullet(676, 358 + index * 58, line, index === 0 ? COLORS.cyan : COLORS.green));
}

function drawInteraction(scenario, seconds) {
  panel(56, 260, 560, 368);
  ctx.fillStyle = COLORS.faint;
  text("Guided chat", 88, 302, 16, "700");
  const messages = [
    ["User", "Use local Ollama to ingest the IPS PDF."],
    ["Assistant", "I will run LLM-assisted IPS extraction, then validate the fields."],
    ["User", "Show before and after portfolio analytics too."],
    ["Assistant", "After review, I will run the MVO optimization workflow."],
  ];
  const visible = Math.min(messages.length, 1 + Math.floor(((seconds - 11) / 13) * 4));
  messages.slice(0, visible).forEach(([speaker, message], index) => {
    const y = 348 + index * 68;
    ctx.fillStyle = speaker === "User" ? COLORS.amber : COLORS.cyan;
    text(speaker, 90, y, 15, "800");
    ctx.fillStyle = COLORS.panel3;
    roundRect(90, y + 10, 472, 42, 8, true);
    ctx.fillStyle = COLORS.ink;
    wrapText(message, 108, y + 37, 430, 20, 15, "600", 2);
  });
  panel(660, 260, 564, 368);
  ctx.fillStyle = COLORS.faint;
  text("Uploaded source", 692, 302, 16, "700");
  drawPdfCard(692, 338);
  ctx.fillStyle = COLORS.muted;
  wrapText("The user does not need to manually type target return, cash floor, concentration limit, or governance flags. Those are read from the IPS.", 692, 468, 470, 30, 20, "500", 5);
}

function drawLlmExtraction(scenario) {
  panel(56, 254, 1168, 376);
  ctx.fillStyle = COLORS.faint;
  text("Ollama proposed fields", 88, 296, 16, "700");
  scenario.extracted.forEach(([key, value, status], index) => {
    const col = index < 4 ? 0 : 1;
    const row = index % 4;
    const x = col === 0 ? 88 : 666;
    const y = 342 + row * 62;
    ctx.fillStyle = COLORS.panel3;
    roundRect(x, y - 28, 490, 42, 6, true);
    ctx.fillStyle = COLORS.muted;
    text(key, x + 18, y - 1, 16, "700");
    ctx.fillStyle = status === "rejected" ? COLORS.red : COLORS.green;
    text(value, x + 330, y - 1, 17, "800");
    pill(x + 406, y - 22, status, COLORS.bg2, status === "rejected" ? COLORS.red : COLORS.green);
  });
  panel(342, 550, 596, 52);
  ctx.fillStyle = COLORS.cyan;
  text("LLM interpretation is useful, but not trusted blindly", 374, 584, 20, "800");
}

function drawValidatorReview(scenario) {
  panel(56, 254, 548, 376);
  ctx.fillStyle = COLORS.faint;
  text("Deterministic validator", 88, 296, 16, "700");
  [
    ["Allowed workflow keys", "passed"],
    ["Currency and percent coercion", "passed"],
    ["Required fields present", "passed"],
    ["Unsupported invented field", "rejected"],
    ["Context patch ready", "passed"],
  ].forEach(([label, status], index) => {
    const y = 350 + index * 52;
    ctx.fillStyle = status === "passed" ? COLORS.green : COLORS.red;
    ctx.beginPath();
    ctx.arc(106, y - 8, 12, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = COLORS.ink;
    text(label, 136, y, 19, "700");
    ctx.fillStyle = status === "passed" ? COLORS.green : COLORS.red;
    text(status, 452, y, 16, "800");
  });
  panel(644, 254, 580, 376);
  ctx.fillStyle = COLORS.faint;
  text("Applied context patch", 676, 296, 16, "700");
  const rows = [
    ["portfolio_id", "PORT_MVO_900"],
    ["target_return", "0.0525"],
    ["risk_aversion", "3.5"],
    ["max_single_asset_weight", "0.40"],
    ["min_cash_weight", "0.03"],
    ["backend", "llm"],
  ];
  rows.forEach(([key, value], index) => {
    const y = 344 + index * 42;
    ctx.fillStyle = COLORS.panel3;
    roundRect(676, y - 24, 492, 30, 6, true);
    ctx.fillStyle = COLORS.muted;
    text(key, 692, y - 3, 15, "700");
    ctx.fillStyle = key === "backend" ? COLORS.cyan : COLORS.green;
    text(value, 1036, y - 3, 15, "800");
  });
}

function drawBeforeAnalytics(scenario) {
  drawAnalyticsBoard("Before Optimization", scenario.before, COLORS.amber, false);
}

function drawOptimizationRun(scenario, seconds) {
  const p = clamp((seconds - 62) / 11, 0, 1);
  panel(56, 254, 500, 376);
  ctx.fillStyle = COLORS.faint;
  text("Plan-driven execution", 88, 296, 16, "700");
  const steps = [
    "Apply reviewed IPS patch",
    "Run MVO optimizer",
    "Validate policy limits",
    "Compute before/after deltas",
    "Prepare evidence package",
  ];
  steps.forEach((step, index) => {
    const done = p * steps.length >= index + 0.25;
    const y = 350 + index * 52;
    ctx.fillStyle = done ? COLORS.green : COLORS.panel3;
    ctx.beginPath();
    ctx.arc(104, y - 8, 12, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = done ? COLORS.ink : COLORS.muted;
    text(step, 134, y, 18, done ? "800" : "500");
  });
  panel(596, 254, 628, 376);
  ctx.fillStyle = COLORS.faint;
  text("Optimization output", 628, 296, 16, "700");
  drawMetric(628, 334, "Solver", "SciPy SLSQP", COLORS.cyan, 250);
  drawMetric(900, 334, "Status", "Optimal", COLORS.green, 250);
  drawMetric(628, 464, "Validation", "Ready", COLORS.green, 250);
  drawMetric(900, 464, "Audit trail", "Captured", COLORS.cyan, 250);
}

function drawAfterComparison(scenario) {
  panel(56, 246, 558, 386);
  panel(666, 246, 558, 386);
  drawMiniPortfolio(84, 292, "Before LLM-Assisted IPS", scenario.before, COLORS.amber);
  drawMiniPortfolio(694, 292, "After Optimization", scenario.after, COLORS.green);
  panel(268, 580, 744, 78);
  ctx.fillStyle = COLORS.cyan;
  text("Interaction plus analytics makes the demo concrete", 306, 614, 22, "800");
  ctx.fillStyle = COLORS.ink;
  text("Return +53 bps | Volatility -67 bps | Sharpe +0.12 | Policy exceptions cleared", 306, 642, 16, "600");
}

function drawAnalyticsBoard(title, data, color, after) {
  panel(56, 254, 1168, 376);
  ctx.fillStyle = color;
  text(title, 88, 306, 28, "800");
  drawMetric(88, 338, "Expected return", data.expectedReturn, color);
  drawMetric(306, 338, "Volatility", data.volatility, color);
  drawMetric(524, 338, "Sharpe", data.sharpe, color);
  drawMetric(742, 338, "Cash", data.cash, color);
  drawMetric(960, 338, "Max weight", data.maxWeight, color);
  drawAllocations(96, 496, 520, data.allocation);
  drawPolicyStatus(706, 496, data.status, after);
}

function drawMiniPortfolio(x, y, title, data, color) {
  ctx.fillStyle = color;
  text(title, x, y, 22, "800");
  drawMetric(x, y + 26, "Return", data.expectedReturn, color, 154);
  drawMetric(x + 172, y + 26, "Vol", data.volatility, color, 154);
  drawMetric(x + 344, y + 26, "Sharpe", data.sharpe, color, 154);
  drawAllocations(x, y + 168, 468, data.allocation);
  pill(x, y + 288, "Policy status: " + data.status, COLORS.panel2, data.status === "Ready" ? COLORS.green : COLORS.red);
}

function drawMetric(x, y, label, value, color, width = 194) {
  ctx.fillStyle = COLORS.panel2;
  roundRect(x, y, width, 100, 8, true);
  ctx.strokeStyle = COLORS.line;
  roundRect(x, y, width, 100, 8, false);
  ctx.fillStyle = COLORS.muted;
  text(label, x + 18, y + 31, 14, "700");
  ctx.fillStyle = color;
  text(value, x + 18, y + 75, 30, "800");
}

function drawAllocations(x, y, width, allocations) {
  allocations.forEach(([label, value, color], index) => {
    const rowY = y + index * 31;
    ctx.fillStyle = COLORS.muted;
    text(label, x, rowY + 14, 13, "700");
    ctx.fillStyle = COLORS.panel3;
    roundRect(x + 132, rowY, width - 210, 13, 7, true);
    ctx.fillStyle = color;
    roundRect(x + 132, rowY, (width - 210) * Math.min(value / 0.55, 1), 13, 7, true);
    ctx.fillStyle = COLORS.ink;
    text(Math.round(value * 1000) / 10 + "%", x + width - 60, rowY + 14, 13, "700");
  });
}

function drawPolicyStatus(x, y, status, after) {
  ctx.fillStyle = after ? COLORS.green : COLORS.red;
  text("Policy status", x, y + 6, 18, "800");
  ctx.fillStyle = COLORS.ink;
  text(status, x, y + 50, 39, "800");
  ctx.fillStyle = COLORS.muted;
  wrapText(after ? "Validated LLM-assisted constraints now satisfy the cash floor and concentration limit." : "Current analytics breach the IPS cash floor and single asset cap.", x, y + 94, 410, 28, 19, "500", 4);
}

function drawPdfCard(x, y) {
  ctx.fillStyle = COLORS.bg;
  roundRect(x, y, 458, 90, 8, true);
  ctx.strokeStyle = COLORS.line;
  roundRect(x, y, 458, 90, 8, false);
  ctx.fillStyle = COLORS.red;
  roundRect(x + 18, y + 20, 46, 50, 6, true);
  ctx.fillStyle = COLORS.ink;
  text("PDF", x + 25, y + 52, 14, "800");
  ctx.fillStyle = COLORS.ink;
  text("sample_full_ips.pdf", x + 82, y + 38, 19, "800");
  ctx.fillStyle = COLORS.muted;
  text("4-page Investment Policy Statement", x + 82, y + 66, 15, "500");
}

function drawTimeline(phase, progress) {
  const labels = ["Config", "Chat", "LLM", "Validate", "Before", "Run", "After"];
  const x = 56;
  const y = 674;
  const width = 1168;
  ctx.strokeStyle = COLORS.line;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x + 20, y);
  ctx.lineTo(x + width - 20, y);
  ctx.stroke();
  labels.forEach((label, index) => {
    const stepX = x + (width - 40) * (index / (labels.length - 1)) + 20;
    const done = index <= phase;
    ctx.fillStyle = done ? COLORS.cyan : COLORS.panel3;
    ctx.beginPath();
    ctx.arc(stepX, y, done ? 13 : 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = done ? COLORS.ink : COLORS.faint;
    text(label, stepX - 30, y + 33, 13, done ? "800" : "500");
  });
  ctx.fillStyle = COLORS.green;
  roundRect(x, y - 34, width * progress, 3, 2, true);
}

function drawFooter(scenario) {
  ctx.fillStyle = COLORS.faint;
  text("Final runtime: " + scenario.durationSeconds + "s | Backend: llm | Provider: local Ollama via OpenAI-compatible endpoint", 56, 712, 12, "500");
  text("Generated by scripts/generate_llm_ips_interactive_workflow_video.mjs", 866, 712, 12, "500");
}

function bullet(x, y, value, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x + 7, y - 7, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = COLORS.ink;
  wrapText(value, x + 24, y, 460, 24, 18, "600", 2);
}

function panel(x, y, w, h) {
  ctx.fillStyle = "rgba(16, 27, 33, 0.94)";
  roundRect(x, y, w, h, 8, true);
  ctx.strokeStyle = COLORS.line;
  ctx.lineWidth = 1;
  roundRect(x, y, w, h, 8, false);
}

function pill(x, y, label, fill, color) {
  ctx.font = "700 14px Inter, SF Pro Text, Arial, sans-serif";
  const w = ctx.measureText(label).width + 26;
  ctx.fillStyle = fill;
  roundRect(x, y, w, 32, 16, true);
  ctx.fillStyle = color;
  text(label, x + 13, y + 21, 14, "700");
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
  if (w <= 0 || h <= 0) return;
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
</script>
</body>
</html>`;
}
