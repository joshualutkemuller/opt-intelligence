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

const totalStages = 11;

function stage(number, title, body, action) {
  return { number, total: totalStages, title, body, action };
}

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
    await caption(
      page,
      stage(
        1,
        "Start In The Live Front-End",
        "This is a real browser recording of the demo UI, not a rendered storyboard.",
        "Open the collateral HQLA workflow lane",
      ),
    );
    await page.waitForTimeout(sleeps.opening);

    await clickByRoleMatch(page, "button", /Load Collateral HQLA/);
    await ensureCollateralPathLoaded(page);
    await caption(
      page,
      stage(
        2,
        "Load Collateral HQLA Path",
        "The preset represents a stressed collateral book with bilateral CSAs, CCP margin, and exchange margin.",
        "Populate the schedule text and workflow inputs",
      ),
    );
    await page.waitForTimeout(sleeps.medium);

    await panelFocus(page, "Schedule Intake");
    await clickByRole(page, "button", "Ingest Schedule");
    await caption(
      page,
      stage(
        3,
        "Ingest The Collateral Schedule",
        "Auto mode can use local Ollama when available; deterministic extraction and validation produce structured workflow fields.",
        "Extract cash, liquidity floors, WAM, prime cap, obligation scale, and concentration limit",
      ),
    );
    await page.waitForTimeout(sleeps.long);

    await page
      .locator(".policy-review-summary")
      .filter({ hasText: "Collateral Liquidity Review" })
      .first()
      .waitFor({ timeout: 12000 });
    await clickButtonText(page, "Apply Schedule");
    await page.getByRole("button", { name: "Applied", exact: true }).first().waitFor({ timeout: 8000 });
    await caption(
      page,
      stage(
        4,
        "Convert Text Into Optimizer Controls",
        "Haircuts and eligibility are visible in the schedule review; the concentration cap and liquidity limits feed the optimizer request.",
        "Apply extracted fields to the workflow",
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
        5,
        "Use Production Adapter Contracts",
        "The workflow will run the collateral production adapter first and the money-market production adapter second.",
        "Switch runtime from phase 1 to production",
      ),
    );
    await page.waitForTimeout(sleeps.medium);

    await panelFocus(page, "Collateral Scenario Comparison");
    await clickByRoleMatch(page, "button", /Severe Haircut/);
    await caption(
      page,
      stage(
        6,
        "Compare Schedule Stress Paths",
        "The severe haircut case shows how tighter reusable-value and concentration assumptions change liquidity and HQLA outcomes.",
        "Apply the severe haircut scenario",
      ),
    );
    await page.waitForTimeout(sleeps.long);

    await clickByRoleMatch(page, "button", /Stress Schedule/);
    await caption(
      page,
      stage(
        6,
        "Select The Presentation Stress Case",
        "The stress schedule keeps the story realistic: higher margin calls, a 48% asset-class cap, and elevated cash liquidity floors.",
        "Return to the stress schedule",
      ),
    );
    await page.waitForTimeout(sleeps.medium);

    await panelFocus(page, "Ollama Chat");
    await fillTextbox(
      page,
      "Ollama chat input",
      "Explain how the collateral schedule changes the HQLA and liquidity workflow.",
    );
    if (await ollamaAvailable()) {
      await clickByRole(page, "button", "Ask Ollama");
      await caption(
        page,
        stage(
          7,
          "Explain With The Local LLM",
          "The chat can translate the schedule and workflow result into plain English for a nontechnical reviewer.",
          "Ask Ollama for the collateral-liquidity storyline",
        ),
      );
      await page.waitForTimeout(12000);
    } else {
      await caption(
        page,
        stage(
          7,
          "Local LLM Panel Is Ready",
          "When Ollama is running, this panel explains how schedule terms become optimizer inputs and reviewer evidence.",
          "Continue with deterministic workflow execution",
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
        "Run The Orchestrated Workflow",
        "Step 1 posts efficient collateral across bilateral, CCP, and exchange obligations. Step 2 reallocates cash under the resulting liquidity constraints.",
        "Execute collateral optimizer, then money-market optimizer",
      ),
    );
    await page.waitForTimeout(sleeps.run);

    await panelFocus(page, "Sequential Workflow");
    await caption(
      page,
      stage(
        9,
        "Review Sequential Execution",
        "The timeline shows the two optimizers, dependency effects, validation checks, and trace events in execution order.",
        "Confirm collateral ran before money-market allocation",
      ),
    );
    await page.waitForTimeout(sleeps.long);

    await panelFocus(page, "Collateral HQLA Analytics");
    await caption(
      page,
      stage(
        10,
        "Compare Before And After Analytics",
        "The HQLA panel shows the effect of schedule-driven allocation on liquidity profile, tier mix, concentration usage, and reusable collateral.",
        "Inspect post-optimization liquidity and HQLA exposure",
      ),
    );
    await page.waitForTimeout(sleeps.long);

    await panelFocus(page, "Document-To-Constraint Traceability");
    await caption(
      page,
      stage(
        11,
        "Trace Document Text To Constraints",
        "Each applied schedule field is mapped to a validated input, constraint family, and optimizer step for audit review.",
        "Connect evidence snippets to optimizer controls",
      ),
    );
    await page.waitForTimeout(sleeps.long);

    await panelFocus(page, "Evidence Room");
    await caption(
      page,
      stage(
        11,
        "Close With Evidence",
        "The evidence room brings together document extraction, model versions, solver metadata, validation, governance, and workflow trace.",
        "Prepare the run for stakeholder review",
      ),
    );
    await page.waitForTimeout(sleeps.long);

    await panelFocus(page, "Governance Review");
    await caption(
      page,
      stage(
        11,
        "Governance Stays In The Loop",
        "The demo remains a recommendation unless approval tiers, materiality thresholds, and policy-change controls allow further action.",
        "Review approval tier and materiality settings",
      ),
    );
    await page.waitForTimeout(sleeps.medium);

    const elapsed = Date.now() - startedAt;
    const remainingMs = Math.max(0, targetSeconds * 1000 - elapsed);
    if (remainingMs > 0) {
      await caption(
        page,
        stage(
          11,
          "Presentation-Ready Proof",
          "The clip shows schedule ingestion, LLM-assisted explanation, deterministic optimization, HQLA analytics, and governance evidence in one flow.",
          "End of collateral HQLA orchestration demo",
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
    workflowLabel.textContent = "Collateral HQLA Orchestration";
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

async function ensureCollateralPathLoaded(page) {
  try {
    await page.getByText("Schedule Intake", { exact: true }).first().waitFor({ timeout: 6000 });
    return;
  } catch {
    // The video path button can be off-screen or covered in some browser captures.
  }
  await clickByRoleMatch(page, "button", /^Collateral$/);
  await page.getByText("Schedule Intake", { exact: true }).first().waitFor({ timeout: 12000 });
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

async function clickButtonText(page, name) {
  await page.evaluate((buttonName) => {
    const button = Array.from(document.querySelectorAll("button")).find(
      (node) => node.textContent?.trim() === buttonName,
    );
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error(`Button not found: ${buttonName}`);
    }
    button.click();
  }, name);
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
