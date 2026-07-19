#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const require = createRequire(new URL("../frontend/app/package.json", import.meta.url));
const { chromium } = require("playwright");

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const frontendDir = path.join(repoRoot, "frontend", "app");
const outDir = path.join(repoRoot, "video_examples", "collateral");
const tmpDir = path.join(repoRoot, "tmp", "video", "frontend-collateral-hqla");
const apiUrl = "http://127.0.0.1:8000";
const uiUrl = "http://127.0.0.1:5173";
const outputPath = path.join(outDir, "collateral-hqla-frontend-orchestration-demo.mp4");
const targetSeconds = 102;

const sleeps = {
  opening: 4000,
  short: 1800,
  medium: 3500,
  long: 6000,
  run: 8000,
};

async function main() {
  await fs.mkdir(outDir, { recursive: true });
  await fs.rm(tmpDir, { recursive: true, force: true });
  await fs.mkdir(tmpDir, { recursive: true });

  const processes = [];
  try {
    if (!(await urlOk(`${apiUrl}/api/health`))) {
      processes.push(startApi());
      await waitForUrl(`${apiUrl}/api/health`, 30000);
    }
    if (!(await urlOk(uiUrl))) {
      processes.push(startUi());
      await waitForUrl(uiUrl, 30000);
    }

    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1600, height: 900 },
      deviceScaleFactor: 1,
      recordVideo: {
        dir: tmpDir,
        size: { width: 1600, height: 900 },
      },
    });
    const page = await context.newPage();

    await page.goto(uiUrl, { waitUntil: "networkidle" });
    await installRecordingOverlays(page);
    await page.evaluate(() => {
      window.localStorage.removeItem("decision-intelligence.workflowRunHistory.v1");
      window.localStorage.removeItem("decision-intelligence.comparisonSets.v1");
    });
    await page.reload({ waitUntil: "networkidle" });
    await installRecordingOverlays(page);

    const startedAt = Date.now();
    await caption(page, "Collateral HQLA orchestration starts in the live demo UI");
    await page.waitForTimeout(sleeps.opening);

    await clickByRole(page, "button", "Load Collateral HQLA");
    await caption(page, "Load the collateral schedule stress path");
    await page.waitForTimeout(sleeps.medium);

    await panelFocus(page, "Schedule Intake");
    await clickByRole(page, "button", "Ingest Schedule");
    await caption(page, "The schedule is ingested into workflow-ready limits");
    await page.waitForTimeout(sleeps.long);

    await clickByRole(page, "button", "Apply Schedule");
    await caption(page, "Extracted controls are applied to the real workflow inputs");
    await page.waitForTimeout(sleeps.medium);

    await panelFocus(page, "Production Adapter");
    await page
      .locator(".production-runtime-toggle")
      .getByRole("button", { name: /^Production$/ })
      .click();
    await caption(page, "Switch to production adapters for collateral and money-market");
    await page.waitForTimeout(sleeps.medium);

    await panelFocus(page, "Collateral Scenario Comparison");
    await clickByRoleMatch(page, "button", /Severe Haircut/);
    await caption(page, "Compare a severe haircut path before running the workflow");
    await page.waitForTimeout(sleeps.long);

    await clickByRoleMatch(page, "button", /Stress Schedule/);
    await caption(page, "Return to the stress schedule selected for the presentation");
    await page.waitForTimeout(sleeps.medium);

    await panelFocus(page, "Ollama Chat");
    await fillTextbox(
      page,
      "Ollama chat input",
      "Explain how the collateral schedule changes the HQLA and liquidity workflow.",
    );
    if (await ollamaAvailable()) {
      await clickByRole(page, "button", "Ask Ollama");
      await caption(page, "The local LLM explains the schedule impact for nontechnical stakeholders");
      await page.waitForTimeout(12000);
    } else {
      await caption(page, "The local LLM panel is ready when Ollama is available");
      await page.waitForTimeout(sleeps.medium);
    }

    await panelFocus(page, "Presenter Review");
    await clickByRole(page, "button", "Run Demo");
    await caption(page, "Presenter review launches the actual collateral-to-liquidity workflow");
    await page.waitForTimeout(sleeps.run);

    await panelFocus(page, "Sequential Workflow");
    await caption(page, "The workflow completes in dependency order");
    await page.waitForTimeout(sleeps.long);

    await panelFocus(page, "Collateral HQLA Analytics");
    await caption(page, "Before and after analytics show liquidity, HQLA tiers, and allocation stats");
    await page.waitForTimeout(sleeps.long);

    await panelFocus(page, "Document-To-Constraint Traceability");
    await caption(page, "Every applied schedule field maps back to an optimizer constraint");
    await page.waitForTimeout(sleeps.long);

    await panelFocus(page, "Evidence Room");
    await caption(page, "The close is model, solver, governance, trace, and document evidence");
    await page.waitForTimeout(sleeps.long);

    await panelFocus(page, "Governance Review");
    await caption(page, "Governance thresholds stay visible before any action is taken");
    await page.waitForTimeout(sleeps.medium);

    const elapsed = Date.now() - startedAt;
    const remainingMs = Math.max(0, targetSeconds * 1000 - elapsed);
    if (remainingMs > 0) {
      await caption(page, "Presentation-ready proof: chat, ingestion, orchestration, analytics, evidence");
      await page.waitForTimeout(remainingMs);
    }

    const video = page.video();
    await context.close();
    await browser.close();

    const webmPath = await video.path();
    await convertToMp4(webmPath, outputPath);
    const stat = await fs.stat(outputPath);
    console.log(
      `Wrote ${path.relative(repoRoot, outputPath)} (${targetSeconds}s, ${(stat.size / 1024 / 1024).toFixed(2)} MB)`,
    );
  } finally {
    for (const child of processes.reverse()) {
      child.kill("SIGTERM");
    }
  }
}

function startApi() {
  const python = path.join(repoRoot, ".venv", "bin", "python");
  return spawn(
    python,
    [
      "-m",
      "uvicorn",
      "decision_intelligence.api.app:app",
      "--host",
      "127.0.0.1",
      "--port",
      "8000",
    ],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONPATH: path.join(repoRoot, "src"),
      },
      stdio: "ignore",
    },
  );
}

function startUi() {
  return spawn(
    "npm",
    ["exec", "vite", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
    {
      cwd: frontendDir,
      stdio: "ignore",
    },
  );
}

async function installRecordingOverlays(page) {
  await page.addStyleTag({
    content: `
      .recording-caption {
        position: fixed;
        left: 28px;
        bottom: 24px;
        z-index: 999999;
        max-width: 760px;
        padding: 12px 16px;
        border: 1px solid rgba(0, 200, 240, 0.55);
        background: rgba(6, 14, 24, 0.88);
        color: #f7fbff;
        font: 700 18px/1.35 Inter, ui-sans-serif, system-ui;
        box-shadow: 0 18px 40px rgba(0, 0, 0, 0.34);
        pointer-events: none;
      }
      .recording-focus {
        outline: 2px solid rgba(0, 200, 240, 0.95) !important;
        outline-offset: 4px !important;
        box-shadow: 0 0 0 9999px rgba(3, 7, 12, 0.14), 0 0 30px rgba(0, 200, 240, 0.26) !important;
      }
    `,
  });
  await page.evaluate(() => {
    let caption = document.querySelector(".recording-caption");
    if (!caption) {
      caption = document.createElement("div");
      caption.className = "recording-caption";
      document.body.appendChild(caption);
    }
    caption.textContent = "";
  });
}

async function caption(page, text) {
  await page.evaluate((value) => {
    const caption = document.querySelector(".recording-caption");
    if (caption) caption.textContent = value;
  }, text);
}

async function panelFocus(page, headingText) {
  const heading = page.getByText(headingText, { exact: true }).first();
  await heading.scrollIntoViewIfNeeded();
  await page.waitForTimeout(350);
  await page.evaluate((text) => {
    document
      .querySelectorAll(".recording-focus")
      .forEach((node) => node.classList.remove("recording-focus"));
    const all = Array.from(document.querySelectorAll("h2, .eyebrow, strong, span"));
    const heading = all.find((node) => node.textContent?.trim() === text);
    const panel = heading?.closest(".panel");
    panel?.classList.add("recording-focus");
  }, headingText);
}

async function clickByRole(page, role, name) {
  const locator = page.getByRole(role, { name, exact: true }).first();
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await locator.click();
}

async function clickByRoleMatch(page, role, name) {
  const locator = page.getByRole(role, { name }).first();
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await locator.click();
}

async function fillTextbox(page, label, value) {
  const input = page.getByLabel(label).first();
  await input.scrollIntoViewIfNeeded();
  await input.fill(value);
}

async function ollamaAvailable() {
  try {
    const response = await fetch("http://localhost:11434/api/tags", { signal: AbortSignal.timeout(1200) });
    return response.ok;
  } catch {
    return false;
  }
}

async function urlOk(url) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(1000) });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForUrl(url, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await urlOk(url)) return;
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function convertToMp4(webmPath, mp4Path) {
  const ffmpeg = await findFfmpeg();
  await new Promise((resolve, reject) => {
    const child = spawn(
      ffmpeg,
      [
        "-y",
        "-i",
        webmPath,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        mp4Path,
      ],
      { stdio: "ignore" },
    );
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited with status ${code}`));
    });
  });
}

async function findFfmpeg() {
  const candidates = [
    path.join(
      frontendDir,
      "node_modules",
      "@ffmpeg-installer",
      "darwin-arm64",
      "ffmpeg",
    ),
    path.join(
      frontendDir,
      "node_modules",
      "@ffmpeg-installer",
      "darwin-x64",
      "ffmpeg",
    ),
    "ffmpeg",
  ];
  for (const candidate of candidates) {
    if (candidate === "ffmpeg") return candidate;
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
      // Keep looking for the bundled binary.
    }
  }
  return "ffmpeg";
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
