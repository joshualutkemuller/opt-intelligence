"""
Generate a presentation-ready video example for the demo folder.

The script builds a deterministic animated GIF from real local optimizer output.
On macOS, it also attempts to convert the GIF to an MP4 with avconvert.

Run from the repository root:
    .venv/bin/python scripts/generate_presentation_video_example.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

OUT_DIR = REPO_ROOT / "video_examples"
GIF_PATH = OUT_DIR / "governed-mvo-presentation-example.gif"
MP4_PATH = OUT_DIR / "governed-mvo-presentation-example.mp4"
WIDTH = 1280
HEIGHT = 720
FRAME_DURATION_MS = 1800

COLORS = {
    "bg": "#071014",
    "panel": "#101B21",
    "panel_2": "#16252C",
    "ink": "#F1F5F4",
    "muted": "#9CB2B4",
    "line": "#2E454B",
    "cyan": "#62D4D0",
    "green": "#89D185",
    "amber": "#E9C46A",
    "blue": "#7AA2F7",
    "red": "#F07178",
}


@dataclass(frozen=True)
class DemoResult:
    expected_return: float
    volatility: float
    sharpe: float
    validation: str
    recommendation: str
    top_allocations: list[tuple[str, float]]
    explanation: str


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = _run_mvo_demo()
    frames = _build_frames(result)
    frames[0].save(
        GIF_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=True,
    )
    converted = _convert_to_mp4()
    print(f"Wrote {GIF_PATH.relative_to(REPO_ROOT)}")
    if converted:
        print(f"Wrote {MP4_PATH.relative_to(REPO_ROOT)}")
    else:
        print(
            "Skipped MP4 conversion because avconvert was unavailable "
            "or rejected the GIF source."
        )


def _run_mvo_demo() -> DemoResult:
    from decision_intelligence.governance import ApprovalPolicy, ApprovalStore, GovernanceController
    from decision_intelligence.governance.audit import AuditLog
    from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
    from decision_intelligence.optimizers import (
        AssetAllocationMVOOptimizer,
        CollateralOptimizer,
        FinancingOptimizer,
        MoneyMarketOptimizer,
    )
    from decision_intelligence.workflows import (
        SequentialWorkflowRunner,
        build_portfolio_rebalance_mvo_workflow,
    )

    audit = AuditLog()
    registry = OptimizerRegistry()
    registry.register(AssetAllocationMVOOptimizer())
    registry.register(CollateralOptimizer())
    registry.register(MoneyMarketOptimizer())
    registry.register(FinancingOptimizer())
    governance = GovernanceController(ApprovalPolicy(), ApprovalStore(), audit)
    orchestrator = OptimizationOrchestrator(registry, audit, governance)

    plan = build_portfolio_rebalance_mvo_workflow(
        portfolio_id="PORT_MVO_PRESENTATION",
        seed=42,
        context={
            "asset_allocation": {
                "portfolio_notional": 250_000_000,
                "target_return": 0.05,
                "risk_aversion": 3.0,
                "max_single_asset_weight": 0.45,
                "min_cash_weight": 0.02,
            }
        },
    )
    workflow_result = SequentialWorkflowRunner(orchestrator).run(plan)
    step_result = workflow_result.step_results[0].result
    metadata = step_result.solver_metadata
    validation = (
        workflow_result.validation_summary.get("aggregate_recommendation")
        if workflow_result.validation_summary
        else "ready"
    )
    explanation = (
        workflow_result.explanation_report.summary
        if workflow_result.explanation_report
        else step_result.explanation
    )
    top_allocations = sorted(
        [
            (allocation.label, allocation.allocated_fraction)
            for allocation in step_result.allocations
            if allocation.allocated_fraction > 0.0001
        ],
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    return DemoResult(
        expected_return=float(metadata.get("expected_return", 0.0)),
        volatility=float(metadata.get("volatility", 0.0)),
        sharpe=float(metadata.get("sharpe", 0.0)),
        validation=str(validation or "ready"),
        recommendation=workflow_result.status,
        top_allocations=top_allocations,
        explanation=explanation,
    )


def _build_frames(result: DemoResult) -> list[Image.Image]:
    return [
        _opening_frame(),
        _workflow_frame(),
        _optimizer_frame(result),
        _allocation_frame(result),
        _governance_frame(result),
        _closing_frame(result),
    ]


def _opening_frame() -> Image.Image:
    image, draw = _base_frame("Decision Intelligence", "Presentation example")
    _headline(draw, "Governed MVO Rebalance")
    _body(
        draw,
        [
            "A portfolio manager asks for a multi-asset rebalance.",
            "The platform turns that request into a deterministic optimization workflow.",
            "The result is explainable, governed, and ready to export for review.",
        ],
        y=270,
    )
    _pill(draw, (72, 600), "Asset Allocation")
    _pill(draw, (270, 600), "Mean-Variance")
    _pill(draw, (474, 600), "Governance")
    _footer(draw, "Use this as a short alternate clip after the liquidity-stress demo.")
    return image


def _workflow_frame() -> Image.Image:
    image, draw = _base_frame("Workflow", "Nontechnical demo path")
    steps = [
        ("1", "Choose Balanced MVO Rebalance", "Starts from a portfolio-construction preset."),
        (
            "2",
            "Review target return and guardrails",
            "Risk aversion, cash floor, and concentration limits are explicit.",
        ),
        (
            "3",
            "Run deterministic optimizer",
            "SciPy SLSQP solves the constrained quadratic program.",
        ),
        ("4", "Export evidence", "The same result can be shared as JSON or PDF proof."),
    ]
    y = 145
    for number, title, detail in steps:
        _step(draw, number, title, detail, y)
        y += 112
    _footer(draw, "Presenter line: this is a workflow surface, not a spreadsheet macro.")
    return image


def _optimizer_frame(result: DemoResult) -> Image.Image:
    image, draw = _base_frame("Optimizer Output", "Real deterministic run")
    _metric(draw, (72, 170), "Expected return", f"{result.expected_return:.2%}", COLORS["green"])
    _metric(draw, (430, 170), "Volatility", f"{result.volatility:.2%}", COLORS["amber"])
    _metric(draw, (788, 170), "Sharpe", f"{result.sharpe:.2f}", COLORS["cyan"])
    _callout(
        draw,
        "Objective",
        "Maximize expected return minus risk_aversion x variance, subject to long-only, "
        "target-return, cash-floor, and concentration constraints.",
        y=420,
    )
    _footer(draw, "The numbers on this frame come from the local optimizer, not a static mock.")
    return image


def _allocation_frame(result: DemoResult) -> Image.Image:
    image, draw = _base_frame("Recommended Allocation", "Top optimized weights")
    max_weight = max((weight for _, weight in result.top_allocations), default=1.0)
    y = 160
    for index, (label, weight) in enumerate(result.top_allocations, start=1):
        bar_width = int(650 * weight / max_weight)
        color = [COLORS["cyan"], COLORS["green"], COLORS["blue"], COLORS["amber"], COLORS["muted"]][
            index - 1
        ]
        draw.text((82, y), label, font=_font(30, "medium"), fill=COLORS["ink"])
        draw.rounded_rectangle((82, y + 44, 82 + bar_width, y + 76), radius=8, fill=color)
        draw.text((790, y + 38), f"{weight:.1%}", font=_font(32, "bold"), fill=COLORS["ink"])
        y += 95
    _footer(draw, "Presenter line: explain the tradeoff, then point to the evidence export.")
    return image


def _governance_frame(result: DemoResult) -> Image.Image:
    image, draw = _base_frame("Governance Review", "Controls before action")
    left = (72, 170, 588, 510)
    right = (692, 170, 1208, 510)
    _panel(draw, left, "Validation", result.validation.title(), COLORS["green"])
    _panel(draw, right, "Workflow status", result.recommendation.title(), COLORS["cyan"])
    _callout(
        draw,
        "Controls",
        "Execution mode, materiality, PnL impact, and production constraint changes determine "
        "whether a recommendation can run, needs review, or requires approval.",
        y=555,
    )
    return image


def _closing_frame(result: DemoResult) -> Image.Image:
    image, draw = _base_frame("Presentation Close", "What the audience should remember")
    _body(
        draw,
        [
            "One interface collects business intent, runs real optimization, "
            "and explains the recommendation.",
            "The same architecture supports liquidity, collateral, financing, "
            "and asset allocation workflows.",
            "Every demo path can produce reviewable evidence instead of an opaque answer.",
        ],
        y=170,
    )
    _callout(draw, "Example summary", result.explanation, y=465)
    _footer(draw, "Generated locally by scripts/generate_presentation_video_example.py")
    return image


def _base_frame(kicker: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=COLORS["bg"])
    draw.rectangle((0, 0, WIDTH, 92), fill="#0D1A20")
    draw.text((72, 28), "DI", font=_font(34, "bold"), fill=COLORS["cyan"])
    draw.text((132, 31), kicker, font=_font(28, "medium"), fill=COLORS["ink"])
    draw.text((72, 104), subtitle, font=_font(28), fill=COLORS["muted"])
    draw.line((72, 138, 1208, 138), fill=COLORS["line"], width=2)
    return image, draw


def _headline(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.text((72, 170), text, font=_font(68, "bold"), fill=COLORS["ink"])


def _body(draw: ImageDraw.ImageDraw, lines: list[str], y: int) -> None:
    for line in lines:
        wrapped = wrap(line, width=72)
        for wrapped_line in wrapped:
            draw.text((86, y), wrapped_line, font=_font(34), fill=COLORS["ink"])
            y += 48
        y += 18


def _pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str) -> None:
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=_font(24, "medium"))
    width = bbox[2] - bbox[0] + 42
    draw.rounded_rectangle((x, y, x + width, y + 48), radius=24, fill=COLORS["panel_2"])
    draw.text((x + 21, y + 11), text, font=_font(24, "medium"), fill=COLORS["cyan"])


def _step(draw: ImageDraw.ImageDraw, number: str, title: str, detail: str, y: int) -> None:
    draw.ellipse((72, y, 128, y + 56), fill=COLORS["cyan"])
    draw.text((91, y + 10), number, font=_font(26, "bold"), fill=COLORS["bg"])
    draw.text((158, y), title, font=_font(32, "bold"), fill=COLORS["ink"])
    draw.text((158, y + 44), detail, font=_font(25), fill=COLORS["muted"])


def _metric(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    label: str,
    value: str,
    color: str,
) -> None:
    x, y = xy
    draw.rounded_rectangle((x, y, x + 320, y + 185), radius=14, fill=COLORS["panel"])
    draw.text((x + 28, y + 28), label, font=_font(26), fill=COLORS["muted"])
    draw.text((x + 28, y + 82), value, font=_font(54, "bold"), fill=color)


def _panel(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
    title: str,
    value: str,
    color: str,
) -> None:
    draw.rounded_rectangle(bounds, radius=16, fill=COLORS["panel"])
    x1, y1, _, _ = bounds
    draw.text((x1 + 34, y1 + 38), title, font=_font(30), fill=COLORS["muted"])
    draw.text((x1 + 34, y1 + 112), value, font=_font(56, "bold"), fill=color)


def _callout(draw: ImageDraw.ImageDraw, title: str, text: str, y: int) -> None:
    draw.rounded_rectangle((72, y, 1208, y + 110), radius=14, fill=COLORS["panel"])
    draw.text((102, y + 22), title, font=_font(26, "bold"), fill=COLORS["cyan"])
    draw.text(
        (102, y + 58),
        "\n".join(wrap(text, width=94)[:2]),
        font=_font(22),
        fill=COLORS["ink"],
    )


def _footer(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.text((72, 672), text, font=_font(20), fill=COLORS["muted"])


def _font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = {
        "regular": [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ],
        "medium": [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ],
        "bold": [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
        ],
    }
    for path in candidates[weight]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _convert_to_mp4() -> bool:
    avconvert = shutil.which("avconvert")
    if not avconvert:
        return False
    command = [
        avconvert,
        "--source",
        str(GIF_PATH),
        "--preset",
        "Preset1280x720",
        "--output",
        str(MP4_PATH),
        "--replace",
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        return False
    return MP4_PATH.exists()


if __name__ == "__main__":
    main()
