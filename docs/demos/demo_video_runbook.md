# Proof-of-Concept Video Runbook

This runbook is tuned for a short presentation video. The goal is to show that
the platform is more than a calculator: it is an agent-guided, deterministic,
auditable optimization workflow.

## Recommended Recording Flow

Use the browser demo for the visual overview, then use the presenter terminal
demo for a crisp proof path.

```bash
make demo-ui
```

Open `http://127.0.0.1:5173/` and use **Presenter Script** as the on-camera
guide:

1. Load the POC path.
2. Review inputs and guardrails.
3. Run the sequential workflow.
4. Export the evidence packet.
5. Close with the architecture summary.

Select **Institutional CSV Liquidity Base Case** first if you want to show a
calmer comparison run. Then switch to **Institutional CSV Liquidity Stress** or
click **Load POC Path** when you want the browser to mirror the primary video
story with tighter file-backed inputs.

After the workflow completes, use **Export Evidence** to download:

- `*-evidence.json`: structured inputs, solver metadata, allocations,
  dependency effects, validation, and raw response.
- `*-evidence.pdf`: compact stakeholder proof packet for review or screen
  share.

Then run the terminal proof:

```bash
make demo-video
```

or directly:

```bash
python examples/run_poc_video_demo.py
```

## Main Story

### 1. Guided Chat Intake

Say:

> I can start with a natural-language treasury request. The agent detects the
> domain, asks for missing constraints, and compiles a strict
> `OptimizationRequest`.

Call out:

- Portfolio and notional are collected interactively.
- Liquidity, WAM, prime concentration, solver backend, and problem type are
  explicit fields.
- MILP-specific `max_funds` and `min_allocation_fraction` are collected before
  execution.

### 2. Solver Choice

Say:

> The math engine is not hard-coded. The same business problem can be routed to
> SciPy LP, SciPy MILP, or CVXPY LP through request context.

Call out:

- `scipy/lp` is the continuous benchmark.
- `scipy/milp` uses binary fund-selection variables.
- `cvxpy/lp` proves that the solver layer is pluggable.

### 3. Executive Workflow

Spend most of the video here.

Say:

> This is the real decision-intelligence concept. Financing stress and
> collateral pressure run first from anonymized CSV inputs. Their results flow
> into the downstream money-market optimizer, which raises liquidity requirements
> before producing the final MILP-selected recommendation.

Call out:

- The workflow has ordered optimizer steps, not one isolated solve.
- The institutional data packet points each optimizer to CSV inputs.
- The base packet gives a calmer comparison case; the stress packet creates
  larger dependency deltas into the final liquidity allocation.
- Cross-step dependency effects are printed with before/after values.
- Aggregate validation summarizes whether the recommendation is ready, needs
  review, or is blocked.
- The explanation report gives key drivers and next actions.
- Export Evidence produces JSON and PDF artifacts for the exact completed run.

## Collateral Management Presentation Clips

Use these when the presentation needs a markets-facing collateral stress story:

- `video_examples/collateral/collateral-schedule-ingestion-stress-example.mp4`
- `video_examples/collateral/collateral-liquidity-hqla-orchestration-example.mp4`

Suggested narration:

> This collateral example starts with the controls that actually govern the
> desk: haircuts, eligibility, and concentration limits from a collateral
> schedule. The agent guides the review, the deterministic optimizer allocates
> scarce collateral under stress, and the output is shown as before/after
> liquidity, HQLA tier exposure, and reviewer-ready evidence.

Call out:

- Haircuts and concentration caps are treated as model inputs, not slide notes.
- Preflight validation blocks missing inventory, obligations, or eligibility.
- The collateral optimizer preserves higher-quality liquidity where possible.
- HQLA and capital-tier exposure make the result legible to treasury and risk.
- Governance and export evidence are visible before the recommendation becomes
  an action.

## Shot List

| Shot | Screen | What to emphasize |
|---|---|---|
| 1 | README or browser home | One-command local demo and repeatable presets |
| 2 | Browser workflow selector | Multiple domains and workflows are already wired |
| 3 | `make demo-video` terminal | Deterministic, camera-ready proof path |
| 4 | Guided chat section | Agent collects missing data, not just text completion |
| 5 | MILP proof panel | True optimization model with selected funds |
| 6 | Solver comparison | Solver backend and problem type are user-selectable |
| 7 | Data packet panel | CSV files backing each optimizer step |
| 8 | Executive workflow timeline | Financing, collateral, money-market chain |
| 9 | Dependency effects table | Upstream stress changes downstream constraints |
| 10 | Export Evidence button | JSON and PDF proof packet from the completed run |
| 11 | Explanation and next actions | Recommendation is explainable and auditable |
| 12 | Collateral schedule clip | Haircuts and concentration limits become optimizer controls |
| 13 | Collateral HQLA clip | Before/after liquidity and HQLA tier exposure under stress |

## Fallback Commands

If the browser is not running smoothly during recording, use these terminal-only
commands:

```bash
python examples/run_poc_video_demo.py
python examples/run_solver_demo.py
di chat
di run money_market --solver scipy --problem-type milp --scenario stress
```

## Success Criteria

- The demo completes without network access or external credentials.
- The institutional CSV data packet is selected for the workflow recording.
- The money-market MILP result is optimal and uses no more than the selected
  fund limit.
- The executive workflow completes all planned steps.
- Dependency effects are visible before the final money-market recommendation.
- Validation and explanation are shown as first-class outputs.
- The evidence JSON/PDF packet exports from the browser after the run.
