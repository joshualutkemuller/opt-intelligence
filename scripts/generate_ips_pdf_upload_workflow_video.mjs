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
const pdfPath = path.join(repoRoot, "examples/policies/sample_full_ips.pdf");
const outDir = path.join(repoRoot, "video_examples");
const outputMp4 = path.join(outDir, "ips-pdf-upload-optimization-workflow-example.mp4");
const tempWebm = path.join(os.tmpdir(), "ips-pdf-upload-optimization-workflow-example.webm");

const scenario = {
  title: "Full IPS PDF to Optimization Workflow",
  subtitle: "Upload, ingest, review, optimize, and compare portfolio analytics",
  durationSeconds: Number(process.env.VIDEO_DURATION_SECONDS || 84),
  pdfName: "sample_full_ips.pdf",
  pdfSize: formatBytes(fs.statSync(pdfPath).size),
  accent: "#5FD4CF",
  secondary: "#89D185",
  extractedFields: [
    ["portfolio_id", "PORT_MVO_900", "90%"],
    ["portfolio_notional", "$250M", "86%"],
    ["target_return", "5.25%", "86%"],
    ["risk_aversion", "3.5", "86%"],
    ["max_single_asset_weight", "40%", "86%"],
    ["min_cash_weight", "3%", "86%"],
    ["materiality_notional", "$250M", "82%"],
    ["production_constraint_change", "true", "78%"],
  ],
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
  const bytes = await page.evaluate(async (config) => window.recordIpsPdfWorkflow(config), scenario);
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
  `Wrote video_examples/ips-pdf-upload-optimization-workflow-example.mp4 (${scenario.durationSeconds}s, ${sizeMb.toFixed(
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

function formatBytes(value) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
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

window.recordIpsPdfWorkflow = async function recordIpsPdfWorkflow(scenario) {
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
  if (phase === 0) drawUpload(scenario, seconds);
  if (phase === 1) drawPdfPreview(scenario, seconds);
  if (phase === 2) drawExtraction(scenario);
  if (phase === 3) drawBeforeAnalytics(scenario);
  if (phase === 4) drawWorkflowRun(scenario, seconds);
  if (phase === 5) drawAfterComparison(scenario);
  drawTimeline(phase, progress);
  drawFooter(scenario);
}

function getPhase(seconds) {
  if (seconds < 12) return 0;
  if (seconds < 25) return 1;
  if (seconds < 39) return 2;
  if (seconds < 53) return 3;
  if (seconds < 68) return 4;
  return 5;
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
  for (let x = -180 + ((progress * 300) % 150); x < WIDTH + 180; x += 150) {
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
  text("Full IPS PDF upload to governed optimization", 128, 61, 16, "500");
  pill(1008, 24, "MP4 presentation clip", COLORS.panel2, COLORS.muted);
}

function drawTitle(phase) {
  const copy = [
    ["Upload the full IPS PDF", "The demo starts with a real bundled PDF file rather than manually typed assumptions."],
    ["Preview the source document", "The full policy is visible as pages before extraction starts."],
    ["Ingest and review extracted fields", "The agent maps policy language into workflow-ready constraints with confidence."],
    ["Show before portfolio analytics", "The current portfolio analytics reveal why optimization is needed."],
    ["Run the optimization workflow", "Reviewed IPS constraints drive a governed MVO rebalance."],
    ["Compare before and after", "The final view shows investment impact and policy readiness."],
  ][phase];
  ctx.fillStyle = COLORS.muted;
  text("IPS PDF to Optimization Workflow", 56, 116, 18, "700");
  ctx.fillStyle = COLORS.ink;
  text(copy[0], 56, 166, 40, "800");
  ctx.fillStyle = COLORS.muted;
  wrapText(copy[1], 58, 206, 780, 28, 20, "500");
}

function drawUpload(scenario, seconds) {
  const localProgress = clamp(seconds / 12, 0, 1);
  panel(56, 264, 720, 342);
  ctx.fillStyle = COLORS.panel2;
  roundRect(106, 318, 620, 194, 10, true);
  ctx.strokeStyle = localProgress > 0.3 ? COLORS.cyan : COLORS.line;
  ctx.lineWidth = 2;
  roundRect(106, 318, 620, 194, 10, false);
  ctx.fillStyle = COLORS.cyan;
  text("Upload IPS PDF", 142, 362, 28, "800");
  ctx.fillStyle = COLORS.muted;
  text("Drop file here or select from computer", 142, 398, 18, "500");
  drawPdfFileCard(148, 434, scenario.pdfName, scenario.pdfSize, localProgress);
  const progress = clamp((localProgress - 0.28) / 0.58, 0, 1);
  ctx.fillStyle = COLORS.panel3;
  roundRect(148, 552, 536, 14, 7, true);
  ctx.fillStyle = COLORS.green;
  roundRect(148, 552, 536 * progress, 14, 7, true);
  ctx.fillStyle = COLORS.ink;
  text(progress >= 1 ? "Upload complete" : "Uploading full IPS PDF", 148, 588, 18, "700");

  panel(826, 264, 398, 342);
  ctx.fillStyle = COLORS.faint;
  text("What the viewer sees", 858, 306, 16, "700");
  const notes = [
    "A complete IPS PDF is selected.",
    "The file is uploaded into the demo workflow.",
    "The next step parses source text, not typed fields.",
    "The original PDF remains part of the evidence package.",
  ];
  notes.forEach((note, index) => bullet(858, 354 + index * 48, note, COLORS.cyan));
}

function drawPdfPreview(scenario, seconds) {
  panel(56, 254, 1168, 370);
  ctx.fillStyle = COLORS.faint;
  text("Uploaded document", 88, 294, 16, "700");
  drawPdfPage(88, 322, 260, 262, "Page 1", [
    "Sample Full Investment Policy Statement",
    "Portfolio PORT_MVO_900",
    "Portfolio value: $250 million",
    "Target annual return: 5.25%",
    "Risk aversion lambda: 3.5",
  ]);
  drawPdfPage(378, 322, 260, 262, "Page 2", [
    "Allocation Constraints",
    "Single asset class max: 40%",
    "Cash floor: at least 3%",
    "No production waiver without approval",
  ]);
  drawPdfPage(668, 322, 260, 262, "Page 3", [
    "Current Portfolio Analytics",
    "Expected return: 4.72%",
    "Volatility: 8.35%",
    "Sharpe ratio: 0.31",
    "Cash allocation: 1.2%",
  ]);
  drawPdfPage(958, 322, 230, 262, "Page 4", [
    "Governance",
    "Materiality notional: $250M",
    "Production constraint change",
    "Evidence packet required",
  ]);
  ctx.fillStyle = COLORS.green;
  const pulse = 0.65 + 0.35 * Math.sin(seconds * 5);
  ctx.globalAlpha = pulse;
  roundRect(84, 318, 268, 270, 8, false);
  ctx.globalAlpha = 1;
}

function drawExtraction(scenario) {
  panel(56, 254, 520, 370);
  ctx.fillStyle = COLORS.faint;
  text("Extracted from sample_full_ips.pdf", 88, 294, 16, "700");
  scenario.extractedFields.forEach(([key, value, confidence], index) => {
    const y = 334 + index * 34;
    ctx.fillStyle = COLORS.panel3;
    roundRect(88, y - 22, 454, 28, 6, true);
    ctx.fillStyle = COLORS.muted;
    text(key, 104, y - 3, 14, "600");
    ctx.fillStyle = index >= 4 ? COLORS.cyan : COLORS.ink;
    text(value, 386, y - 3, 15, "800");
    ctx.fillStyle = COLORS.green;
    text(confidence, 488, y - 3, 13, "700");
  });

  panel(612, 254, 612, 370);
  ctx.fillStyle = COLORS.faint;
  text("Workflow context patch", 644, 294, 16, "700");
  const rows = [
    ["asset_allocation.target_return", "0.0525"],
    ["asset_allocation.risk_aversion", "3.5"],
    ["asset_allocation.max_single_asset_weight", "0.40"],
    ["asset_allocation.min_cash_weight", "0.03"],
    ["governance.production_constraint_change", "true"],
  ];
  rows.forEach(([key, value], index) => {
    const y = 354 + index * 48;
    ctx.fillStyle = COLORS.panel3;
    roundRect(644, y - 27, 528, 34, 6, true);
    ctx.fillStyle = COLORS.muted;
    text(key, 662, y - 4, 15, "600");
    ctx.fillStyle = COLORS.green;
    text(value, 1074, y - 4, 16, "800");
  });
  pill(644, 570, "Ready for human review", COLORS.panel2, COLORS.green);
}

function drawBeforeAnalytics(scenario) {
  drawAnalyticsBoard("Before Optimization", scenario.before, COLORS.amber, false);
}

function drawWorkflowRun(scenario, seconds) {
  const p = clamp((seconds - 53) / 15, 0, 1);
  panel(56, 254, 500, 370);
  ctx.fillStyle = COLORS.faint;
  text("Plan-driven workflow", 88, 294, 16, "700");
  const steps = [
    "Review extracted IPS constraints",
    "Apply context patch",
    "Run MVO optimizer",
    "Validate target and limits",
    "Generate evidence packet",
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
  panel(596, 254, 628, 370);
  ctx.fillStyle = COLORS.faint;
  text("Optimizer status", 628, 294, 16, "700");
  drawMetric(628, 332, "Solver", "SciPy SLSQP", COLORS.cyan, 250);
  drawMetric(900, 332, "Status", "Optimal", COLORS.green, 250);
  drawMetric(628, 462, "Policy checks", "Ready", COLORS.green, 250);
  drawMetric(900, 462, "Evidence", "Packaged", COLORS.cyan, 250);
}

function drawAfterComparison(scenario) {
  panel(56, 246, 558, 386);
  panel(666, 246, 558, 386);
  drawMiniPortfolio(84, 292, "Before IPS Workflow", scenario.before, COLORS.amber);
  drawMiniPortfolio(694, 292, "After IPS Workflow", scenario.after, COLORS.green);
  panel(272, 580, 736, 78);
  ctx.fillStyle = COLORS.cyan;
  text("The PDF upload changes the decision, not just the documentation", 306, 614, 22, "800");
  ctx.fillStyle = COLORS.ink;
  text("Return +53 bps | Volatility -67 bps | Sharpe +0.12 | Cash floor and concentration limit cleared", 306, 642, 16, "600");
}

function drawAnalyticsBoard(title, data, color, after) {
  panel(56, 254, 1168, 370);
  ctx.fillStyle = color;
  text(title, 88, 306, 28, "800");
  drawMetric(88, 336, "Expected return", data.expectedReturn, color);
  drawMetric(306, 336, "Volatility", data.volatility, color);
  drawMetric(524, 336, "Sharpe", data.sharpe, color);
  drawMetric(742, 336, "Cash", data.cash, color);
  drawMetric(960, 336, "Max weight", data.maxWeight, color);
  drawAllocations(96, 492, 520, data.allocation);
  drawPolicyStatus(706, 492, data.policyStatus, after);
}

function drawMiniPortfolio(x, y, title, data, color) {
  ctx.fillStyle = color;
  text(title, x, y, 22, "800");
  drawMetric(x, y + 26, "Return", data.expectedReturn, color, 154);
  drawMetric(x + 172, y + 26, "Vol", data.volatility, color, 154);
  drawMetric(x + 344, y + 26, "Sharpe", data.sharpe, color, 154);
  drawAllocations(x, y + 168, 468, data.allocation);
  pill(x, y + 288, "Policy status: " + data.policyStatus, COLORS.panel2, data.policyStatus === "Ready" ? COLORS.green : COLORS.red);
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
  text(status, x, y + 50, 42, "800");
  ctx.fillStyle = COLORS.muted;
  wrapText(after ? "IPS constraints are satisfied after the optimizer applies the reviewed PDF-derived limits." : "Current analytics show the cash floor and single asset concentration breaches from the IPS.", x, y + 94, 400, 28, 19, "500", 4);
}

function drawPdfFileCard(x, y, name, size, progress) {
  ctx.fillStyle = COLORS.bg;
  roundRect(x, y, 536, 82, 8, true);
  ctx.strokeStyle = COLORS.line;
  roundRect(x, y, 536, 82, 8, false);
  ctx.fillStyle = COLORS.red;
  roundRect(x + 18, y + 18, 44, 46, 6, true);
  ctx.fillStyle = COLORS.ink;
  text("PDF", x + 25, y + 48, 14, "800");
  ctx.fillStyle = COLORS.ink;
  text(name, x + 78, y + 34, 18, "800");
  ctx.fillStyle = COLORS.muted;
  text("Full IPS document | " + size, x + 78, y + 60, 15, "500");
  ctx.fillStyle = progress > 0.25 ? COLORS.green : COLORS.faint;
  text(progress > 0.25 ? "selected" : "waiting", x + 440, y + 48, 15, "800");
}

function drawPdfPage(x, y, w, h, label, lines) {
  ctx.fillStyle = "#F7FAFA";
  roundRect(x, y, w, h, 6, true);
  ctx.strokeStyle = COLORS.line;
  roundRect(x, y, w, h, 6, false);
  ctx.fillStyle = "#16252C";
  text(label, x + 18, y + 30, 15, "800");
  ctx.fillStyle = "#284148";
  lines.forEach((line, index) => {
    wrapText(line, x + 18, y + 68 + index * 35, w - 36, 18, 12, index === 0 ? "800" : "500", 2);
  });
}

function drawTimeline(phase, progress) {
  const labels = ["Upload", "Preview", "Ingest", "Before", "Optimize", "After"];
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
    text(label, stepX - 34, y + 33, 13, done ? "800" : "500");
  });
  ctx.fillStyle = COLORS.green;
  roundRect(x, y - 34, width * progress, 3, 2, true);
}

function drawFooter(scenario) {
  ctx.fillStyle = COLORS.faint;
  text("Final runtime: " + scenario.durationSeconds + "s | Source PDF: examples/policies/sample_full_ips.pdf", 56, 712, 12, "500");
  text("Generated by scripts/generate_ips_pdf_upload_workflow_video.mjs", 858, 712, 12, "500");
}

function bullet(x, y, value, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x + 7, y - 7, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = COLORS.ink;
  wrapText(value, x + 24, y, 320, 24, 18, "600", 2);
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
