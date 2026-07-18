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
const outputMp4 = path.join(outDir, "ips-to-optimization-workflow-example.mp4");
const tempWebm = path.join(os.tmpdir(), "ips-to-optimization-workflow-example.webm");

const scenario = {
  title: "IPS to Optimization Workflow",
  subtitle: "Policy ingestion with before and after portfolio analytics",
  durationSeconds: 78,
  accent: "#5FD4CF",
  secondary: "#89D185",
  before: {
    expectedReturn: "4.72%",
    volatility: "8.35%",
    sharpe: "0.31",
    cash: "1.2%",
    maxWeight: "52%",
    policyStatus: "2 exceptions",
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
    policyStatus: "Ready",
    allocation: [
      ["US Equity", 0.40, "#7AA2F7"],
      ["Core Bonds", 0.32, "#89D185"],
      ["Alternatives", 0.25, "#E9C46A"],
      ["Cash", 0.03, "#5FD4CF"],
    ],
  },
  extractedFields: [
    ["Portfolio", "PORT_MVO_900"],
    ["Portfolio value", "$250M"],
    ["Target annual return", "5.25%"],
    ["Risk aversion lambda", "3.5"],
    ["Single asset max", "40%"],
    ["Cash floor", "3%"],
    ["Governance", "Constraint change"],
  ],
};

if (process.env.VIDEO_DURATION_SECONDS) {
  scenario.durationSeconds = Number(process.env.VIDEO_DURATION_SECONDS);
}

fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1,
  });
  page.on("pageerror", (error) => {
    console.error(error);
  });
  await page.setContent(renderPage(), { waitUntil: "domcontentloaded" });
  const bytes = await page.evaluate(async (config) => window.recordIpsAnalytics(config), scenario);
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
  `Wrote video_examples/ips-to-optimization-workflow-example.mp4 (${scenario.durationSeconds}s, ${sizeMb.toFixed(
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

window.recordIpsAnalytics = async function recordIpsAnalytics(scenario) {
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
    const watchdog = setTimeout(() => {
      reject(new Error("Recording timed out before MediaRecorder stopped."));
    }, durationMs + 15000);
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
  drawTitle(scenario, phase);
  drawPhaseContent(scenario, phase, seconds, progress);
  drawTimeline(phase, progress);
  drawFooter(scenario);
}

function getPhase(seconds) {
  if (seconds < 12) return 0;
  if (seconds < 25) return 1;
  if (seconds < 42) return 2;
  if (seconds < 59) return 3;
  return 4;
}

function drawBackground(progress) {
  const gradient = ctx.createLinearGradient(0, 0, WIDTH, HEIGHT);
  gradient.addColorStop(0, "#071014");
  gradient.addColorStop(0.55, "#0B171D");
  gradient.addColorStop(1, "#111D1F");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
  ctx.globalAlpha = 0.07;
  ctx.strokeStyle = COLORS.cyan;
  for (let x = -160 + ((progress * 280) % 140); x < WIDTH + 160; x += 140) {
    ctx.beginPath();
    ctx.moveTo(x, 90);
    ctx.lineTo(x - 250, HEIGHT);
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
  text("IPS ingestion to optimized portfolio analytics", 128, 61, 16, "500");
  pill(1012, 24, "MP4 presentation clip", COLORS.panel2, COLORS.muted);
}

function drawTitle(scenario, phase) {
  const copy = [
    ["Start with the IPS", "A policy document defines constraints before the optimizer runs."],
    ["Interpret the policy", "The agent extracts workflow inputs with evidence snippets for review."],
    ["Show the current portfolio", "Before analytics make the starting risk and policy gaps visible."],
    ["Run the governed optimizer", "The MVO workflow applies the reviewed IPS constraints."],
    ["Compare before and after", "The final frame shows what improved and what policy issues cleared."],
  ][phase];
  ctx.fillStyle = COLORS.muted;
  text("IPS to Optimization Workflow", 56, 116, 18, "700");
  ctx.fillStyle = COLORS.ink;
  text(copy[0], 56, 166, 40, "800");
  ctx.fillStyle = COLORS.muted;
  wrapText(copy[1], 58, 206, 760, 28, 20, "500");
}

function drawPhaseContent(scenario, phase, seconds, progress) {
  if (phase === 0) drawIpsDocument();
  if (phase === 1) drawExtractionReview(scenario);
  if (phase === 2) drawAnalyticsBoard("Before Portfolio", scenario.before, false);
  if (phase === 3) drawOptimizationRun(scenario, seconds);
  if (phase === 4) drawComparison(scenario);
}

function drawIpsDocument() {
  panel(56, 260, 720, 360);
  ctx.fillStyle = COLORS.faint;
  text("Sample IPS excerpt", 88, 300, 16, "700");
  const lines = [
    "Portfolio PORT_MVO_900 has portfolio value of $250 million.",
    "Target annual return should be 5.25%.",
    "Risk aversion lambda is 3.5 for this review cycle.",
    "Single asset class exposure must not exceed 40%.",
    "Cash floor must be at least 3%.",
    "This is a production constraint change.",
  ];
  lines.forEach((line, index) => {
    ctx.fillStyle = index === 3 || index === 4 ? COLORS.cyan : COLORS.ink;
    wrapText(line, 92, 346 + index * 42, 640, 24, 19, "500", 1);
  });
  panel(826, 260, 398, 360);
  ctx.fillStyle = COLORS.faint;
  text("Presenter point", 858, 300, 16, "700");
  ctx.fillStyle = COLORS.ink;
  wrapText("The IPS is not just attached as evidence. It becomes structured optimizer input, with a human review step before anything changes.", 858, 350, 320, 32, 22, "600", 6);
}

function drawExtractionReview(scenario) {
  panel(56, 260, 540, 360);
  ctx.fillStyle = COLORS.faint;
  text("Extracted fields", 88, 300, 16, "700");
  scenario.extractedFields.forEach(([label, value], index) => {
    const y = 340 + index * 36;
    ctx.fillStyle = COLORS.muted;
    text(label, 92, y, 16, "600");
    ctx.fillStyle = index >= 4 ? COLORS.cyan : COLORS.ink;
    text(value, 390, y, 18, "800");
  });
  panel(632, 260, 592, 360);
  ctx.fillStyle = COLORS.faint;
  text("Workflow context patch", 664, 300, 16, "700");
  const rows = [
    ["asset_allocation.target_return", "0.0525"],
    ["asset_allocation.risk_aversion", "3.5"],
    ["asset_allocation.max_single_asset_weight", "0.40"],
    ["asset_allocation.min_cash_weight", "0.03"],
    ["governance.production_constraint_change", "true"],
  ];
  rows.forEach(([key, value], index) => {
    const y = 352 + index * 45;
    ctx.fillStyle = COLORS.panel3;
    roundRect(664, y - 24, 508, 32, 6, true);
    ctx.fillStyle = COLORS.muted;
    text(key, 680, y - 2, 15, "600");
    ctx.fillStyle = COLORS.green;
    text(value, 1070, y - 2, 16, "800");
  });
}

function drawAnalyticsBoard(title, data, after) {
  panel(56, 260, 1168, 360);
  ctx.fillStyle = after ? COLORS.green : COLORS.amber;
  text(title, 88, 306, 26, "800");
  drawMetric(88, 336, "Expected return", data.expectedReturn, after ? COLORS.green : COLORS.amber);
  drawMetric(302, 336, "Volatility", data.volatility, after ? COLORS.green : COLORS.amber);
  drawMetric(516, 336, "Sharpe", data.sharpe, after ? COLORS.green : COLORS.amber);
  drawMetric(730, 336, "Cash", data.cash, after ? COLORS.green : COLORS.amber);
  drawMetric(944, 336, "Max weight", data.maxWeight, after ? COLORS.green : COLORS.amber);
  drawAllocations(96, 486, 500, data.allocation);
  drawPolicyStatus(690, 486, data.policyStatus, after);
}

function drawOptimizationRun(scenario, seconds) {
  const cycle = (seconds - 42) / 17;
  panel(56, 260, 520, 360);
  ctx.fillStyle = COLORS.faint;
  text("Sequential workflow", 88, 300, 16, "700");
  const steps = ["Review extracted IPS fields", "Apply constraints to MVO plan", "Run optimizer", "Validate policy and governance", "Prepare evidence package"];
  steps.forEach((step, index) => {
    const y = 350 + index * 48;
    const done = cycle * steps.length > index;
    ctx.fillStyle = done ? COLORS.green : COLORS.panel3;
    ctx.beginPath();
    ctx.arc(104, y - 8, 11, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = done ? COLORS.ink : COLORS.muted;
    text(step, 132, y, 18, done ? "700" : "500");
  });
  drawAnalyticsBoard("Optimized Portfolio", scenario.after, true);
  ctx.fillStyle = "rgba(7, 16, 20, 0.72)";
  roundRect(610, 260, 614, 360, 8, true);
}

function drawComparison(scenario) {
  panel(56, 252, 558, 374);
  panel(666, 252, 558, 374);
  drawMiniPortfolio(84, 298, "Before IPS Optimization", scenario.before, COLORS.amber);
  drawMiniPortfolio(694, 298, "After IPS Optimization", scenario.after, COLORS.green);
  panel(308, 574, 664, 86);
  ctx.fillStyle = COLORS.cyan;
  text("Portfolio analytics moved in the right direction", 340, 610, 22, "800");
  ctx.fillStyle = COLORS.ink;
  text("Return +53 bps  |  Volatility -67 bps  |  Sharpe +0.12  |  Policy exceptions cleared", 340, 638, 17, "600");
}

function drawMiniPortfolio(x, y, title, data, color) {
  ctx.fillStyle = color;
  text(title, x, y, 22, "800");
  drawMetric(x, y + 24, "Return", data.expectedReturn, color, 154);
  drawMetric(x + 172, y + 24, "Vol", data.volatility, color, 154);
  drawMetric(x + 344, y + 24, "Sharpe", data.sharpe, color, 154);
  drawAllocations(x, y + 170, 470, data.allocation);
  ctx.fillStyle = data.policyStatus === "Ready" ? COLORS.green : COLORS.red;
  pill(x, y + 286, "Policy status: " + data.policyStatus, COLORS.panel2, ctx.fillStyle);
}

function drawMetric(x, y, label, value, color, width = 190) {
  ctx.fillStyle = COLORS.panel2;
  roundRect(x, y, width, 98, 8, true);
  ctx.strokeStyle = COLORS.line;
  roundRect(x, y, width, 98, 8, false);
  ctx.fillStyle = COLORS.muted;
  text(label, x + 18, y + 31, 14, "700");
  ctx.fillStyle = color;
  text(value, x + 18, y + 74, 30, "800");
}

function drawAllocations(x, y, width, allocations) {
  allocations.forEach(([label, value, color], index) => {
    const rowY = y + index * 31;
    ctx.fillStyle = COLORS.muted;
    text(label, x, rowY + 14, 13, "700");
    ctx.fillStyle = COLORS.panel3;
    roundRect(x + 130, rowY, width - 210, 13, 7, true);
    ctx.fillStyle = color;
    roundRect(x + 130, rowY, (width - 210) * Math.min(value / 0.55, 1), 13, 7, true);
    ctx.fillStyle = COLORS.ink;
    text(Math.round(value * 1000) / 10 + "%", x + width - 62, rowY + 14, 13, "700");
  });
}

function drawPolicyStatus(x, y, status, after) {
  ctx.fillStyle = after ? COLORS.green : COLORS.red;
  text("Policy status", x, y + 6, 18, "800");
  ctx.fillStyle = COLORS.ink;
  text(status, x, y + 48, 42, "800");
  ctx.fillStyle = COLORS.muted;
  wrapText(after ? "Cash floor and concentration limits are satisfied after the optimizer applies IPS constraints." : "Current portfolio breaches the cash floor and single-asset concentration limit.", x, y + 92, 400, 28, 19, "500", 4);
}

function drawTimeline(phase, progress) {
  const labels = ["IPS", "Extract", "Before", "Optimize", "After"];
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
    text(label, stepX - 28, y + 33, 13, done ? "800" : "500");
  });
  ctx.fillStyle = COLORS.green;
  roundRect(x, y - 34, width * progress, 3, 2, true);
}

function drawFooter(scenario) {
  ctx.fillStyle = COLORS.faint;
  text("Final runtime: " + scenario.durationSeconds + "s | Silent MP4 example", 56, 712, 12, "500");
  text("Generated locally by scripts/generate_ips_optimization_analytics_video.mjs", 820, 712, 12, "500");
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
</script>
</body>
</html>`;
}
