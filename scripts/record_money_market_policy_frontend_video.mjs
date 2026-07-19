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
const outDir = path.join(repoRoot, "video_examples", "money_market");
const tmpDir = path.join(repoRoot, "tmp", "video", "frontend-money-market-policy");
const apiUrl = "http://127.0.0.1:8000";
const uiUrl = "http://127.0.0.1:5173";
const samplePdf = path.join(repoRoot, "examples", "policies", "sample_money_market_policy.pdf");
const outputPath = path.join(outDir, "money-market-pdf-policy-optimization-demo.mp4");
const targetSeconds = 104;

const sleeps = {
  opening: 3500,
  medium: 3500,
  long: 6000,
  run: 8000,
};

const totalStages = 10;

function stage(number, title, body, action) {
  return { number, total: totalStages, title, body, action };
}

async function main() {
  await fs.mkdir(outDir, { recursive: true });
  await fs.rm(tmpDir, { recursive: true, force: true });
  await fs.mkdir(tmpDir, { recursive: true });

  const processes = [];
  try {
    await fs.access(samplePdf);
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
    await caption(
      page,
      stage(
        1,
        "Start In The Live Front-End",
        "This is a real browser capture of the money-market optimizer demo path.",
        "Open the money-market policy workflow lane",
      ),
    );
    await page.waitForTimeout(sleeps.opening);

    await clickByRoleMatch(page, "button", /Load MMF Policy/);
    await ensureMoneyMarketPathLoaded(page);
    await caption(
      page,
      stage(
        2,
        "Load The Money-Market Policy Path",
        "The workflow is scoped to one optimizer: allocate the cash sleeve under policy-derived liquidity and concentration controls.",
        "Select Treasury MMF Policy Optimization",
      ),
    );
    await page.waitForTimeout(sleeps.medium);

    await panelFocus(page, "IPS Ingestion");
    await page.getByLabel("Upload IPS document").setInputFiles(samplePdf);
    await page.getByLabel("Uploaded PDF preview").waitFor({ timeout: 8000 });
    await page.getByLabel("Uploaded PDF preview").scrollIntoViewIfNeeded();
    await page.waitForTimeout(600);
    await panelFocus(page, "IPS Ingestion");
    await caption(
      page,
      stage(
        3,
        "Upload The Portfolio Policy PDF",
        "The source document describes current cash, required daily and weekly liquidity, prime exposure, WAM, and single-fund limits.",
        "Attach sample_money_market_policy.pdf",
      ),
    );
    await page.waitForTimeout(sleeps.medium);

    await clickByRole(page, "button", "Ingest IPS");
    await caption(
      page,
      stage(
        4,
        "Ingest The PDF Into Structured Fields",
        "Auto mode can use local Ollama when available; deterministic validation keeps the extracted controls stable and reviewable.",
        "Extract cash, liquidity floors, WAM, prime cap, single-fund cap, and governance",
      ),
    );
    await page.waitForTimeout(sleeps.long);

    await clickByRole(page, "button", "Apply Fields");
    await caption(
      page,
      stage(
        5,
        "Apply Policy Controls To The Optimizer",
        "The extracted PDF fields become money-market workflow inputs before anything is solved.",
        "Update optimizer controls from document evidence",
      ),
    );
    await page.waitForTimeout(sleeps.medium);

    await panelFocus(page, "Production Adapter");
    await page
      .locator(".production-runtime-toggle")
      .getByRole("button", { name: /^Production$/ })
      .click();
    await caption(
      page,
      stage(
        6,
        "Use The Production Adapter Contract",
        "The run captures model config, data snapshot, solver method, and reproducibility fingerprint for the money-market adapter.",
        "Switch runtime from phase 1 to production",
      ),
    );
    await page.waitForTimeout(sleeps.medium);

    await panelFocus(page, "Ollama Chat");
    await fillTextbox(
      page,
      "Ollama chat input",
      "Explain this money-market PDF policy and what the optimizer will change.",
    );
    if (await ollamaAvailable()) {
      await clickByRole(page, "button", "Ask Ollama");
      await caption(
        page,
        stage(
          7,
          "Discuss The Mandate With The Local LLM",
          "The LLM chat gives a plain-English storyline while the optimizer remains deterministic and auditable.",
          "Ask Ollama to summarize the PDF-derived constraints",
        ),
      );
      await page.waitForTimeout(12000);
    } else {
      await caption(
        page,
        stage(
          7,
          "Local LLM Panel Is Ready",
          "When Ollama is running, this chat explains the policy and output for nontechnical stakeholders.",
          "Continue with deterministic optimizer execution",
        ),
      );
      await page.waitForTimeout(sleeps.medium);
    }

    await panelFocus(page, "Presenter Review");
    await clickByRole(page, "button", "Run Demo");
    await caption(
      page,
      stage(
        8,
        "Run The Money-Market Optimizer",
        "The optimizer maximizes net yield subject to cash budget, liquidity floors, prime cap, WAM limit, and single-fund concentration.",
        "Execute the policy-constrained liquidity allocation",
      ),
    );
    await page.waitForTimeout(sleeps.run);

    await panelFocus(page, "Money-Market Policy Analytics");
    await caption(
      page,
      stage(
        9,
        "Compare Before And After Analytics",
        "The analytics panel shows baseline versus optimized yield, daily and weekly liquidity, WAM, prime exposure, top-fund concentration, and funds used.",
        "Inspect clean post-optimization output",
      ),
    );
    await page.waitForTimeout(sleeps.long);

    await panelFocus(page, "Document-To-Constraint Traceability");
    await caption(
      page,
      stage(
        10,
        "Trace The PDF To Optimizer Controls",
        "Every applied PDF field maps to a validated input, constraint family, and money-market optimizer step.",
        "Review source evidence and control mapping",
      ),
    );
    await page.waitForTimeout(sleeps.long);

    await panelFocus(page, "Evidence Room");
    await caption(
      page,
      stage(
        10,
        "Close With Evidence",
        "The final proof includes document evidence, model and solver metadata, validation checks, governance state, and trace events.",
        "Prepare the run for stakeholder review",
      ),
    );
    await page.waitForTimeout(sleeps.long);

    const elapsed = Date.now() - startedAt;
    const remainingMs = Math.max(0, targetSeconds * 1000 - elapsed);
    if (remainingMs > 0) {
      await caption(
        page,
        stage(
          10,
          "Presentation-Ready Proof",
          "The clip shows PDF upload, LLM-assisted discussion, deterministic ingestion, optimization, analytics, and evidence in one money-market workflow.",
          "End of money-market optimizer demo",
        ),
      );
      await page.waitForTimeout(remainingMs);
    }

    const video = page.video();
    await context.close();
    await browser.close();

    const webmPath = await video.path();
    await convertToMp4(webmPath, outputPath, targetSeconds);
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
        width: min(880px, calc(100vw - 56px));
        min-height: 124px;
        padding: 14px 16px 13px;
        border: 1px solid rgba(0, 200, 240, 0.55);
        background: rgba(6, 14, 24, 0.88);
        color: #f7fbff;
        font: 600 16px/1.35 Inter, ui-sans-serif, system-ui;
        box-shadow: 0 18px 40px rgba(0, 0, 0, 0.34);
        pointer-events: none;
      }
      .recording-caption-kicker {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        color: #5fd4cf;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      .recording-caption-title {
        margin-top: 6px;
        color: #ffffff;
        font-size: 24px;
        font-weight: 850;
        line-height: 1.1;
      }
      .recording-caption-body {
        margin-top: 6px;
        max-width: 820px;
        color: #d7e1ef;
        font-size: 16px;
        font-weight: 650;
        line-height: 1.35;
      }
      .recording-caption-action {
        margin-top: 8px;
        color: #89d185;
        font-size: 13px;
        font-weight: 800;
      }
      .recording-progress {
        margin-top: 10px;
        height: 5px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.15);
        overflow: hidden;
      }
      .recording-progress > span {
        display: block;
        height: 100%;
        width: var(--recording-progress, 0%);
        background: linear-gradient(90deg, #5fd4cf, #89d185);
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

async function caption(page, data) {
  await page.evaluate((value) => {
    const caption = document.querySelector(".recording-caption");
    if (!caption) return;
    caption.textContent = "";

    const kicker = document.createElement("div");
    kicker.className = "recording-caption-kicker";
    const stageLabel = document.createElement("span");
    stageLabel.textContent = `Stage ${value.number} of ${value.total}`;
    const workflowLabel = document.createElement("span");
    workflowLabel.textContent = "Money-Market Policy Optimization";
    kicker.append(stageLabel, workflowLabel);

    const title = document.createElement("div");
    title.className = "recording-caption-title";
    title.textContent = value.title;

    const body = document.createElement("div");
    body.className = "recording-caption-body";
    body.textContent = value.body;

    const action = document.createElement("div");
    action.className = "recording-caption-action";
    action.textContent = `Current action: ${value.action}`;

    const progress = document.createElement("div");
    progress.className = "recording-progress";
    const fill = document.createElement("span");
    fill.style.width = `${Math.min(100, Math.max(0, (value.number / value.total) * 100))}%`;
    progress.append(fill);

    caption.append(kicker, title, body, action, progress);
  }, data);
}

async function panelFocus(page, headingText) {
  const heading = page.getByText(headingText, { exact: true }).first();
  try {
    await heading.scrollIntoViewIfNeeded({ timeout: 8000 });
  } catch {
    return;
  }
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

async function ensureMoneyMarketPathLoaded(page) {
  try {
    await page.getByText("Money-Market Policy Analytics", { exact: true }).first().waitFor({ timeout: 6000 });
    return;
  } catch {
    // The video path button can be off-screen or covered in some captures.
  }
  await clickByRoleMatch(page, "button", /MMF PDF|Load MMF Policy/);
  await page.getByText("Money-Market Policy Analytics", { exact: true }).first().waitFor({ timeout: 12000 });
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

async function convertToMp4(webmPath, mp4Path, durationSeconds) {
  const ffmpeg = await findFfmpeg();
  await new Promise((resolve, reject) => {
    const child = spawn(
      ffmpeg,
      [
        "-y",
        "-fflags",
        "+genpts",
        "-i",
        webmPath,
        "-t",
        String(durationSeconds),
        "-r",
        "25",
        "-vf",
        "setpts=PTS-STARTPTS",
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
    path.join(frontendDir, "node_modules", "@ffmpeg-installer", "darwin-arm64", "ffmpeg"),
    path.join(frontendDir, "node_modules", "@ffmpeg-installer", "darwin-x64", "ffmpeg"),
    "ffmpeg",
  ];
  for (const candidate of candidates) {
    try {
      const child = spawn(candidate, ["-version"], { stdio: "ignore" });
      const ok = await new Promise((resolve) => {
        child.on("error", () => resolve(false));
        child.on("exit", (code) => resolve(code === 0));
      });
      if (ok) return candidate;
    } catch {
      // Try the next candidate.
    }
  }
  throw new Error("Unable to find ffmpeg. Run npm install in frontend/app first.");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
