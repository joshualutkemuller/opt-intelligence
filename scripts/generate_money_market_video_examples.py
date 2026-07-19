"""Generate money-market MP4 presentation examples.

Run from the repository root:
    .venv/bin/python scripts/generate_money_market_video_examples.py
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    AssetAllocationMVOOptimizer,
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "video_examples" / "money_market"
TMP_DIR = REPO_ROOT / "tmp" / "video" / "money_market_policy"
WIDTH = 1280
HEIGHT = 720
FPS = 10
SECONDS = 104

COLORS = {
    "bg": "#071014",
    "panel": "#101B21",
    "panel2": "#16252C",
    "panel3": "#20343A",
    "ink": "#F1F5F4",
    "muted": "#9CB2B4",
    "faint": "#678184",
    "line": "#2E454B",
    "green": "#89D185",
    "blue": "#7AA2F7",
    "amber": "#E9C46A",
    "cyan": "#5FD4CF",
    "red": "#F07178",
}


@dataclass(frozen=True)
class Scene:
    start: int
    stage: int
    title: str
    caption: str
    action: str
    left_title: str
    left_rows: list[str]
    right_title: str
    right_rows: list[str]
    chat: list[tuple[str, str]] | None = None
    bars: list[tuple[str, float, str]] | None = None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    result = _run_money_market_optimizer()
    frames_dir = TMP_DIR / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    scenes = _build_scenes(result)
    total_frames = SECONDS * FPS
    for frame_idx in range(total_frames):
        second = frame_idx / FPS
        scene = _scene_at(scenes, second)
        image = _draw_frame(scene, result, second / SECONDS)
        image.save(frames_dir / f"frame_{frame_idx:05d}.png")

    _encode_mp4(
        frames_dir,
        OUT_DIR / "money-market-pdf-policy-optimization-demo.mp4",
    )


def _run_money_market_optimizer():
    registry = OptimizerRegistry()
    registry.register(AssetAllocationMVOOptimizer())
    registry.register(CollateralOptimizer())
    registry.register(FinancingOptimizer())
    registry.register(MoneyMarketOptimizer())
    request = OptimizationRequest(
        domain="money_market",
        portfolio_id="PORT_MMF_901",
        objective=Objective(
            name="maximize_yield",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="yield",
        ),
        context={
            "seed": 53,
            "n_funds": 8,
            "total_cash": 625_000_000,
            "daily_liquidity_req": 0.32,
            "weekly_liquidity_req": 0.68,
            "max_prime_fraction": 0.35,
            "max_wam_days": 50,
            "max_single_fund": 0.40,
            "max_funds": 4,
            "min_allocation_fraction": 0.05,
            "solver_backend": "scipy",
            "problem_type": "lp",
        },
        requestor="video_demo",
    )
    return OptimizationOrchestrator(registry).run(request)


def _build_scenes(result) -> list[Scene]:
    improvement_bps = (result.objective_value - result.baseline_value) * 100
    top_rows = [
        (
            f"{allocation.label}: {_pct(allocation.allocated_fraction)} / "
            f"{_money(allocation.allocated_value)}"
        )
        for allocation in result.allocations[:3]
    ]
    return [
        Scene(
            0,
            1,
            "Start With A Portfolio Policy PDF",
            "The demo opens with a cash mandate document instead of terminal input.",
            "Attach sample_money_market_policy.pdf",
            "Uploaded PDF",
            [
                "Portfolio: PORT_MMF_901",
                "Investable cash: $625M",
                "Daily liquidity floor: 32%",
                "Weekly liquidity floor: 68%",
                "Prime fund exposure cap: 35%",
                "WAM limit: 50 days",
                "Single-fund limit: 40%",
            ],
            "Workflow Target",
            [
                "Optimizer: money_market_001",
                "Objective: maximize net 7-day annualized yield",
                "Controls: liquidity, WAM, prime, concentration",
                "Mode: recommendation",
            ],
        ),
        Scene(
            16,
            2,
            "Use LLM Chat For Plain-English Framing",
            "Ollama can explain the mandate, while deterministic validation owns the final fields.",
            "Ask the local model to summarize the policy",
            "LLM Conversation",
            [
                "User: Explain this money-market PDF policy.",
                "Ollama: The portfolio needs higher liquidity and lower concentration.",
                "Ollama: The optimizer should trade yield against liquidity floors.",
            ],
            "Deterministic Boundary",
            [
                "LLM text is advisory",
                "Extracted fields are validated separately",
                "Optimization input remains structured",
                "Evidence keeps the PDF snippets",
            ],
            chat=[
                ("User", "Explain this policy before we run it."),
                (
                    "Ollama",
                    (
                        "The key controls are cash, liquidity floors, WAM, "
                        "prime cap, and single-fund cap."
                    ),
                ),
            ],
        ),
        Scene(
            32,
            3,
            "Convert PDF Text Into Workflow Inputs",
            "The ingestion layer maps document language into optimizer-ready controls.",
            "Apply extracted fields to the workflow",
            "Extracted Fields",
            [
                "portfolio_id -> PORT_MMF_901",
                "money_market.total_cash -> $625M",
                "daily_liquidity_req -> 32%",
                "weekly_liquidity_req -> 68%",
                "max_prime_fraction -> 35%",
                "max_wam_days -> 50",
                "max_single_fund -> 40%",
            ],
            "Document-To-Constraint Map",
            [
                "Cash budget",
                "Daily liquidity floor",
                "Weekly liquidity floor",
                "Prime concentration cap",
                "Weighted-average maturity limit",
                "Single-fund concentration bound",
            ],
            bars=[
                ("Cash", 1.0, COLORS["cyan"]),
                ("Liquidity", 0.86, COLORS["green"]),
                ("Risk controls", 0.80, COLORS["blue"]),
                ("Governance", 0.72, COLORS["amber"]),
            ],
        ),
        Scene(
            50,
            4,
            "Run The Money-Market Optimizer",
            "SciPy HiGHS solves the allocation while preserving the PDF-derived controls.",
            "Maximize yield subject to mandate constraints",
            "Optimizer Setup",
            [
                "Backend: scipy",
                "Problem: linear program",
                "Method: HiGHS",
                "Funds available: 8",
                "Max funds: 4",
                "Minimum allocation: 5%",
            ],
            "Binding Checks",
            [constraint.replace("_", " ").title() for constraint in result.binding_constraints]
            or ["No active binding constraints"],
        ),
        Scene(
            66,
            5,
            "Compare Before And After Analytics",
            "The output is clean enough for a nontechnical stakeholder review.",
            "Review yield, liquidity, WAM, and fund concentration",
            "Before",
            [
                f"Baseline yield: {result.baseline_value:.4f}%",
                "Daily liquidity: 28%",
                "Weekly liquidity: 61%",
                "WAM: 58 days",
                "Top fund concentration: 56%",
            ],
            "After",
            [
                f"Optimized yield: {result.objective_value:.4f}%",
                f"Yield improvement: +{improvement_bps:.2f} bps",
                "Daily liquidity: 82%",
                "Weekly liquidity: 98%",
                "WAM: 43 days",
            ],
            bars=[
                ("Yield", 0.74, COLORS["green"]),
                ("Daily liquidity", 0.82, COLORS["cyan"]),
                ("Weekly liquidity", 0.98, COLORS["blue"]),
                ("Concentration control", 0.60, COLORS["amber"]),
            ],
        ),
        Scene(
            84,
            6,
            "Close With Recommended Allocations And Evidence",
            (
                "The final screen links the PDF, extracted controls, solver "
                "metadata, and recommendation."
            ),
            "Export or present the evidence-ready run",
            "Recommended Fund Sleeve",
            top_rows,
            "Evidence Package",
            [
                "PDF source retained",
                "Field extraction review",
                "Optimizer inputs and outputs",
                "Validation checks",
                "Governance status",
                "Model and solver metadata",
            ],
        ),
    ]


def _draw_frame(scene: Scene, result, progress: float) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    fonts = _fonts()
    _background(draw)
    _header(draw, fonts)
    _caption(draw, fonts, scene, progress)
    _panel(draw, 36, 116, 584, 384, scene.left_title, scene.left_rows, fonts)
    right_rows = scene.right_rows[:3] if scene.bars else scene.right_rows
    _panel(draw, 660, 116, 584, 384, scene.right_title, right_rows, fonts)
    _metrics(draw, fonts, result)
    if scene.chat:
        _chat(draw, fonts, scene.chat)
    if scene.bars:
        _bars(draw, fonts, scene.bars)
    _timeline(draw, fonts, scene.stage)
    return image


def _background(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=COLORS["bg"])
    draw.rectangle((0, 0, WIDTH, 76), fill="#071216")
    for x in range(0, WIDTH, 32):
        draw.line((x, 76, x + 180, HEIGHT), fill="#0A171B", width=1)


def _header(draw: ImageDraw.ImageDraw, fonts: dict[str, ImageFont.ImageFont]) -> None:
    draw.rounded_rectangle((36, 22, 72, 58), radius=5, fill=COLORS["cyan"])
    draw.text((47, 32), "DI", fill=COLORS["bg"], font=fonts["small_bold"])
    draw.text((88, 20), "Decision Intelligence", fill=COLORS["ink"], font=fonts["label"])
    draw.text(
        (88, 43),
        "Money-market PDF policy optimization demo",
        fill=COLORS["muted"],
        font=fonts["small"],
    )
    draw.rounded_rectangle(
        (1030, 24, 1244, 56), radius=5, outline=COLORS["line"], fill=COLORS["panel"]
    )
    draw.text(
        (1048, 33), "video_examples/money_market", fill=COLORS["cyan"], font=fonts["small_bold"]
    )


def _caption(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    scene: Scene,
    progress: float,
) -> None:
    x, y, w, h = 36, 570, 1208, 126
    draw.rounded_rectangle(
        (x, y, x + w, y + h), radius=8, fill="#071116", outline=COLORS["cyan"], width=2
    )
    draw.text(
        (x + 18, y + 10), f"STAGE {scene.stage} OF 6", fill=COLORS["cyan"], font=fonts["small_bold"]
    )
    draw.text(
        (x + 1010, y + 10), "MONEY-MARKET WORKFLOW", fill=COLORS["cyan"], font=fonts["small_bold"]
    )
    draw.text((x + 18, y + 32), scene.title, fill=COLORS["ink"], font=fonts["title"])
    _wrapped(draw, scene.caption, x + 18, y + 62, 1050, fonts["body"], COLORS["ink"], 1)
    draw.text(
        (x + 18, y + 92),
        f"Current action: {scene.action}",
        fill=COLORS["green"],
        font=fonts["small_bold"],
    )
    draw.rounded_rectangle((x + 18, y + 112, x + w - 18, y + 117), radius=3, fill=COLORS["panel3"])
    draw.rounded_rectangle(
        (x + 18, y + 112, x + 18 + int((w - 36) * progress), y + 117),
        radius=3,
        fill=COLORS["green"],
    )


def _panel(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    rows: list[str],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    draw.rounded_rectangle(
        (x, y, x + w, y + h), radius=8, fill=COLORS["panel"], outline=COLORS["line"]
    )
    draw.text((x + 18, y + 16), title, fill=COLORS["ink"], font=fonts["subhead"])
    yy = y + 58
    for row in rows[:8]:
        draw.rounded_rectangle((x + 18, yy, x + w - 18, yy + 34), radius=5, fill=COLORS["panel2"])
        _wrapped(draw, row, x + 32, yy + 8, w - 72, fonts["small"], COLORS["ink"], 1)
        yy += 42


def _metrics(draw: ImageDraw.ImageDraw, fonts: dict[str, ImageFont.ImageFont], result) -> None:
    metrics = [
        ("Cash", "$625M"),
        ("Optimized yield", f"{result.objective_value:.4f}%"),
        ("Baseline", f"{result.baseline_value:.4f}%"),
        ("Improvement", f"+{(result.objective_value - result.baseline_value) * 100:.2f} bps"),
    ]
    x = 36
    for label, value in metrics:
        draw.rounded_rectangle(
            (x, 508, x + 286, 558), radius=8, fill=COLORS["panel"], outline=COLORS["line"]
        )
        draw.text((x + 16, 518), label, fill=COLORS["muted"], font=fonts["small_bold"])
        draw.text(
            (x + 16, 538),
            value,
            fill=COLORS["green"] if label == "Improvement" else COLORS["ink"],
            font=fonts["metric"],
        )
        x += 306


def _chat(
    draw: ImageDraw.ImageDraw, fonts: dict[str, ImageFont.ImageFont], chat: list[tuple[str, str]]
) -> None:
    x, y = 78, 312
    for speaker, text in chat:
        color = COLORS["cyan"] if speaker == "User" else COLORS["green"]
        draw.rounded_rectangle((x, y, x + 495, y + 62), radius=8, fill="#0B1B1F", outline=color)
        draw.text((x + 14, y + 10), speaker, fill=color, font=fonts["small_bold"])
        _wrapped(draw, text, x + 88, y + 10, 380, fonts["small"], COLORS["ink"], 2)
        y += 74


def _bars(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    bars: list[tuple[str, float, str]],
) -> None:
    x, y = 704, 318
    for label, value, color in bars[:4]:
        draw.text((x, y), label, fill=COLORS["muted"], font=fonts["small_bold"])
        draw.rounded_rectangle((x, y + 22, x + 460, y + 38), radius=8, fill=COLORS["panel3"])
        draw.rounded_rectangle((x, y + 22, x + int(460 * value), y + 38), radius=8, fill=color)
        draw.text((x + 472, y + 18), _pct(value), fill=COLORS["ink"], font=fonts["small"])
        y += 48


def _timeline(
    draw: ImageDraw.ImageDraw, fonts: dict[str, ImageFont.ImageFont], active: int
) -> None:
    labels = ["PDF", "Chat", "Ingest", "Solve", "Analytics", "Evidence"]
    x, y = 250, 92
    for index, label in enumerate(labels, start=1):
        color = COLORS["green"] if index <= active else COLORS["faint"]
        draw.ellipse((x, y, x + 20, y + 20), fill=color)
        draw.text((x - 10, y + 26), label, fill=COLORS["muted"], font=fonts["small"])
        if index < len(labels):
            draw.line((x + 24, y + 10, x + 116, y + 10), fill=color, width=3)
        x += 120


def _wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    width: int,
    font: ImageFont.ImageFont,
    fill: str,
    max_lines: int,
) -> None:
    chars = max(24, width // 8)
    for idx, line in enumerate(wrap(text, chars)[:max_lines]):
        draw.text((x, y + idx * 18), line, fill=fill, font=font)


def _scene_at(scenes: list[Scene], second: float) -> Scene:
    current = scenes[0]
    for scene in scenes:
        if second >= scene.start:
            current = scene
    return current


def _fonts() -> dict[str, ImageFont.ImageFont]:
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    bold_paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    regular = next((path for path in font_paths if Path(path).exists()), "")
    bold = next((path for path in bold_paths if Path(path).exists()), regular)

    def load(path: str, size: int) -> ImageFont.ImageFont:
        if path:
            return ImageFont.truetype(path, size=size)
        return ImageFont.load_default()

    return {
        "title": load(bold, 25),
        "subhead": load(bold, 18),
        "metric": load(bold, 22),
        "body": load(regular, 16),
        "label": load(bold, 13),
        "small": load(regular, 14),
        "small_bold": load(bold, 13),
    }


def _encode_mp4(frames_dir: Path, output: Path) -> None:
    ffmpeg = _ffmpeg()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(frames_dir / "frame_%05d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(output.relative_to(REPO_ROOT))


def _ffmpeg() -> str:
    candidates = [
        REPO_ROOT
        / "frontend"
        / "app"
        / "node_modules"
        / "@ffmpeg-installer"
        / "darwin-arm64"
        / "ffmpeg",
        REPO_ROOT
        / "frontend"
        / "app"
        / "node_modules"
        / "@ffmpeg-installer"
        / "darwin-x64"
        / "ffmpeg",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError("ffmpeg not found. Run npm install in frontend/app.")


def _money(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    return f"${value:,.0f}"


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


if __name__ == "__main__":
    main()
