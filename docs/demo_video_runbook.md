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

Open `http://127.0.0.1:5173/` and show:

1. Workflow selector and demo presets.
2. Editable workflow inputs.
3. Validation/readiness panels.
4. Workflow result timeline and export package.

Select **Institutional CSV Liquidity Stress** in the preset selector when you
want the browser to mirror the video story with file-backed inputs.

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
- Cross-step dependency effects are printed with before/after values.
- Aggregate validation summarizes whether the recommendation is ready, needs
  review, or is blocked.
- The explanation report gives key drivers and next actions.

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
| 10 | Explanation and next actions | Recommendation is explainable and auditable |

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
