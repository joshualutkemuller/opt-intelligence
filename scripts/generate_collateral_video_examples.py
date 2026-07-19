"""Generate collateral-focused MP4 presentation examples.

Run from the repository root:
    .venv/bin/python scripts/generate_collateral_video_examples.py
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "video_examples" / "collateral"
TMP_DIR = REPO_ROOT / "tmp" / "video" / "collateral"
WIDTH = 1280
HEIGHT = 720
FPS = 8

COLORS = {
    "bg": "#071014",
    "bg2": "#0B171D",
    "panel": "#101B21",
    "panel2": "#16252C",
    "panel3": "#1C2C33",
    "ink": "#F1F5F4",
    "muted": "#9CB2B4",
    "faint": "#678184",
    "line": "#2E454B",
    "red": "#F07178",
    "blue": "#7AA2F7",
    "green": "#89D185",
    "amber": "#E9C46A",
    "cyan": "#5FD4CF",
}


@dataclass(frozen=True)
class Scene:
    start: int
    headline: str
    support: str
    left_title: str
    left_rows: list[str]
    right_title: str
    right_rows: list[str]
    chart_title: str = ""
    bars: list[tuple[str, float, str]] | None = None
    chat: list[tuple[str, str]] | None = None


@dataclass(frozen=True)
class Scenario:
    filename: str
    title: str
    subtitle: str
    duration: int
    source_seconds: int
    accent: str
    secondary: str
    domain: str
    workflow: str
    audience: str
    request: str
    metrics: list[tuple[str, str]]
    timeline: list[str]
    scenes: list[Scene]


SCENARIOS = [
    Scenario(
        filename="collateral-schedule-ingestion-stress-example.mp4",
        title="Collateral Schedule Ingestion",
        subtitle="Haircuts, concentration limits, and eligibility mapped into stress inputs",
        duration=82,
        source_seconds=103,
        accent=COLORS["blue"],
        secondary=COLORS["amber"],
        domain="Collateral Management",
        workflow="Schedule to Optimized Coverage",
        audience="Collateral operations, treasury risk, secured financing, and governance",
        request=(
            "Ingest the collateral schedule, apply stress haircuts, and optimize "
            "coverage without breaching concentration limits."
        ),
        metrics=[
            ("Schedule clauses", "14"),
            ("Haircut shock", "+8 pts"),
            ("Blocked issues", "0"),
        ],
        timeline=[
            "Upload schedule",
            "Extract limits",
            "Validate preflight",
            "Optimize coverage",
            "Export evidence",
        ],
        scenes=[
            Scene(
                0,
                "The demo begins with a real collateral control artifact",
                (
                    "A collateral schedule is uploaded and interpreted into structured "
                    "model inputs before any optimizer is allowed to run."
                ),
                "Uploaded schedule",
                [
                    "US Treasury haircut: 2% base, 6% stress",
                    "Agency MBS haircut: 5% base, 12% stress",
                    "Equity collateral haircut: 20% stress",
                    "Single asset class cap: 55% per counterparty",
                ],
                "Agent interpretation",
                [
                    "Maps haircut table to limit source",
                    "Reads counterparty eligibility rows",
                    "Detects concentration cap and stress mode",
                    "Creates reviewed context patch",
                ],
                chat=[
                    ("User", "Use this updated collateral schedule for today's stress run."),
                    ("Assistant", "I found haircut, eligibility, and concentration rules."),
                ],
            ),
            Scene(
                16,
                "Preflight validation turns the document into governed inputs",
                (
                    "The platform separates extracted facts from deterministic validation, "
                    "so the model only runs after required data and controls are present."
                ),
                "Preflight checks",
                [
                    "Eligible inventory present: 20 assets",
                    "Margin obligations present: 3 calls",
                    "Haircuts are between 0% and 100%",
                    "Every obligation has eligible classes",
                ],
                "Production adapter config",
                [
                    "Objective: minimize funding cost",
                    "Constraints: inventory, coverage, eligibility",
                    "Limit source: collateral schedule",
                    "Execution: production adapter",
                ],
                "Control extraction coverage",
                [
                    ("Haircuts", 0.96, COLORS["blue"]),
                    ("Eligibility", 0.90, COLORS["green"]),
                    ("Concentration", 0.84, COLORS["amber"]),
                    ("Evidence", 0.92, COLORS["cyan"]),
                ],
            ),
            Scene(
                34,
                "The optimizer reallocates scarce collateral under stress",
                (
                    "The stress schedule changes the cost of coverage and makes "
                    "concentration limits visible as active model controls."
                ),
                "Before stress",
                [
                    "Available HQLA: $318M",
                    "Post-haircut coverage: $112M",
                    "Cash and Treasuries: 58% of posted pool",
                    "No concentration breach",
                ],
                "After optimization",
                [
                    "Post-haircut coverage: $121M",
                    "Funding cost improves vs naive baseline",
                    "Government bond concentration is active",
                    "Equity collateral avoided where possible",
                ],
                "Before / after liquidity profile",
                [
                    ("Before HQLA", 0.62, COLORS["faint"]),
                    ("After HQLA", 0.78, COLORS["blue"]),
                    ("Before cash", 0.36, COLORS["faint"]),
                    ("After cash", 0.48, COLORS["amber"]),
                ],
            ),
            Scene(
                54,
                "HQLA and capital-tier exposure are reviewer language",
                (
                    "Treasury and risk teams see HQLA mix, haircut-adjusted coverage, "
                    "and limit pressure, not just solver objective value."
                ),
                "Fed HQLA tier exposure",
                [
                    "Level 1: Treasuries and cash increase",
                    "Level 2A: agency exposure stays below cap",
                    "Level 2B/equity: reduced in stress",
                    "Non-HQLA: retained but not prioritized",
                ],
                "Risk review",
                [
                    "Concentration limit: active but satisfied",
                    "Eligibility: no ineligible posting",
                    "Coverage: all obligations covered",
                    "Audit status: ready for review",
                ],
                "HQLA tier mix after optimization",
                [
                    ("Level 1", 0.68, COLORS["green"]),
                    ("Level 2A", 0.22, COLORS["blue"]),
                    ("Level 2B", 0.08, COLORS["amber"]),
                    ("Non-HQLA", 0.02, COLORS["red"]),
                ],
            ),
            Scene(
                70,
                "The closeout is an evidence package",
                (
                    "The presenter can show the source schedule, extracted rules, "
                    "preflight report, optimizer result, and reviewer evidence together."
                ),
                "Evidence packet",
                [
                    "Source schedule and extracted clauses",
                    "Production model config",
                    "Data snapshot and fingerprint",
                    "Before/after liquidity and HQLA exposure",
                ],
                "Presenter takeaway",
                [
                    "Policy documents become model constraints",
                    "Agent chat guides the review",
                    "Optimization stays deterministic",
                    "Governance is visible before action",
                ],
            ),
        ],
    ),
    Scenario(
        filename="collateral-liquidity-hqla-orchestration-example.mp4",
        title="Collateral Stress Orchestration",
        subtitle="A cross-step collateral and liquidity workflow under counterparty stress",
        duration=88,
        source_seconds=110,
        accent=COLORS["green"],
        secondary=COLORS["cyan"],
        domain="Enterprise Liquidity",
        workflow="Collateral Pressure to Liquidity Response",
        audience="Treasury, liquidity risk, collateral desk, and executive stakeholders",
        request=(
            "A counterparty raises margin calls; optimize collateral posting and show "
            "the liquidity reserve response."
        ),
        metrics=[
            ("Margin call shock", "+65%"),
            ("HQLA retained", "$241M"),
            ("Approval tier", "Tier 4"),
        ],
        timeline=[
            "Chat intake",
            "Plan workflow",
            "Run collateral",
            "Adjust liquidity",
            "Govern review",
        ],
        scenes=[
            Scene(
                0,
                "The business request starts in chat, not in a terminal",
                (
                    "A user describes margin stress in plain English. The agent turns it "
                    "into a sequenced workflow with collateral first and liquidity second."
                ),
                "User request",
                [
                    "Counterparty A raised IM by 65%",
                    "Preserve daily liquidity buffer",
                    "Avoid overusing Level 1 HQLA",
                    "Show before and after exposure",
                ],
                "Agent plan",
                [
                    "Run collateral pressure optimization",
                    "Apply dependency effect to liquidity reserve",
                    "Surface governance tier and evidence",
                    "Prepare presenter review",
                ],
                chat=[
                    ("User", "We have a margin shock. What collateral should we post?"),
                    ("Assistant", "I will optimize coverage, then update liquidity."),
                ],
            ),
            Scene(
                18,
                "The workflow shows orchestration instead of one isolated solve",
                (
                    "Collateral pressure feeds downstream liquidity planning, so the final "
                    "recommendation reflects the whole stress chain."
                ),
                "Step 1: collateral",
                [
                    "Minimize funding cost of posted collateral",
                    "Cover all haircut-adjusted obligations",
                    "Enforce schedule concentration caps",
                    "Retain scarce HQLA where possible",
                ],
                "Step 2: liquidity",
                [
                    "Raise daily liquidity floor",
                    "Increase weekly liquidity target",
                    "Preserve cash reserve after posting",
                    "Explain dependency changes",
                ],
                "Workflow progress",
                [
                    ("Chat intake", 1.00, COLORS["green"]),
                    ("Collateral solve", 0.86, COLORS["blue"]),
                    ("Dependency update", 0.72, COLORS["amber"]),
                    ("Liquidity review", 0.58, COLORS["cyan"]),
                ],
            ),
            Scene(
                38,
                "Before and after analytics make the stress understandable",
                (
                    "The output connects optimizer decisions to liquidity profile, HQLA "
                    "retention, funding cost, and operational readiness."
                ),
                "Before optimization",
                [
                    "Naive posting consumes Level 1 first",
                    "Daily cash buffer falls to 22%",
                    "Agency and corporate collateral underused",
                    "Counterparty concentration near breach",
                ],
                "After optimization",
                [
                    "Level 1 retained for liquidity buffer",
                    "Daily cash buffer restored to 31%",
                    "Coverage met using lower-cost assets",
                    "Concentration limit satisfied",
                ],
                "Liquidity profile",
                [
                    ("Before daily", 0.44, COLORS["red"]),
                    ("After daily", 0.62, COLORS["green"]),
                    ("Before weekly", 0.58, COLORS["amber"]),
                    ("After weekly", 0.74, COLORS["cyan"]),
                ],
            ),
            Scene(
                58,
                "Fed HQLA tier exposure is visible before the decision",
                (
                    "The committee sees how the recommendation changes the quality of "
                    "the collateral pool, not only the solver objective."
                ),
                "HQLA exposure retained",
                [
                    "Level 1 retained: $241M",
                    "Level 2A deployed selectively",
                    "Level 2B capped by haircut schedule",
                    "Non-HQLA excluded from critical calls",
                ],
                "Model evidence",
                [
                    "Production adapter: collateral allocation",
                    "Data snapshot: stress schedule",
                    "Fingerprint: reproducible run",
                    "Validation: no blocking violations",
                ],
                "Capital tier exposure",
                [
                    ("Level 1", 0.70, COLORS["green"]),
                    ("Level 2A", 0.24, COLORS["blue"]),
                    ("Level 2B", 0.10, COLORS["amber"]),
                    ("Non-HQLA", 0.04, COLORS["red"]),
                ],
            ),
            Scene(
                74,
                "The final screen is built for a nontechnical decision maker",
                (
                    "The presenter can tell the whole story: what happened, how the plan "
                    "ran, what changed, and what evidence supports it."
                ),
                "Governance review",
                [
                    "Execution mode: recommendation",
                    "Materiality: elevated under stress",
                    "Approval tier: Tier 4 review",
                    "Export: JSON, PDF, CSV, Excel evidence",
                ],
                "Why it stands out",
                [
                    "Agent-guided collateral workflow",
                    "Document-derived risk controls",
                    "Before/after liquidity analytics",
                    "HQLA and capital-tier language",
                ],
            ),
        ],
    ),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg = _ffmpeg_path()
    for scenario in SCENARIOS:
        frame_dir = TMP_DIR / scenario.filename.replace(".mp4", "")
        if frame_dir.exists():
            shutil.rmtree(frame_dir)
        frame_dir.mkdir(parents=True)
        _render_frames(scenario, frame_dir)
        _encode_mp4(ffmpeg, frame_dir, OUT_DIR / scenario.filename)
        shutil.rmtree(frame_dir)
        size_mb = (OUT_DIR / scenario.filename).stat().st_size / (1024 * 1024)
        print(f"Wrote {(OUT_DIR / scenario.filename).relative_to(REPO_ROOT)} ({size_mb:.1f} MB)")


def _render_frames(scenario: Scenario, frame_dir: Path) -> None:
    total_frames = scenario.duration * FPS
    for index in range(total_frames):
        seconds = index / FPS
        progress = index / max(total_frames - 1, 1)
        frame = _draw_frame(scenario, seconds, progress)
        frame.save(frame_dir / f"frame_{index:04d}.png")


def _draw_frame(scenario: Scenario, seconds: float, progress: float) -> Image.Image:
    scene = _scene_at(scenario.scenes, seconds)
    scene_index = scenario.scenes.index(scene)
    scene_progress = _scene_progress(scenario.scenes, scene, seconds)
    image = Image.new("RGB", (WIDTH, HEIGHT), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    _background(draw, scenario, progress)
    _top_bar(draw, scenario)
    _hero(draw, scenario, scene, scene_progress)
    _metrics(draw, scenario)
    _request_panel(draw, scenario, scene_progress)
    _main_panels(draw, scenario, scene, scene_progress)
    _timeline(draw, scenario, scene_index, progress)
    _footer(draw, scenario)
    return image


def _background(draw: ImageDraw.ImageDraw, scenario: Scenario, progress: float) -> None:
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=COLORS["bg"])
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=COLORS["bg2"])
    for x in range(-160 + int((progress * 280) % 140), WIDTH + 160, 140):
        draw.line((x, 84, x - 250, HEIGHT), fill="#14272E", width=1)
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=scenario.accent, width=1)


def _top_bar(draw: ImageDraw.ImageDraw, scenario: Scenario) -> None:
    draw.rectangle((0, 0, WIDTH, 84), fill="#0D1A20")
    _round(draw, (56, 20, 108, 64), 10, scenario.accent)
    draw.text((71, 27), "DI", font=_font(24, "bold"), fill=COLORS["bg"])
    draw.text((128, 18), "Decision Intelligence", font=_font(24, "bold"), fill=COLORS["ink"])
    draw.text((128, 45), scenario.domain, font=_font(16, "medium"), fill=COLORS["muted"])
    _pill(draw, (970, 24), "collateral POC", scenario.accent)
    _pill(draw, (1110, 24), "MP4 example", COLORS["muted"])


def _hero(
    draw: ImageDraw.ImageDraw,
    scenario: Scenario,
    scene: Scene,
    scene_progress: float,
) -> None:
    draw.text((56, 103), scenario.workflow, font=_font(18, "bold"), fill=COLORS["muted"])
    _wrap(draw, scene.headline, (56, 145), 770, 2, 38, COLORS["ink"], "bold")
    _wrap(draw, scene.support, (58, 246), 770, 3, 20, COLORS["muted"], "regular")
    _panel(draw, (910, 112, 1224, 262))
    draw.text((934, 133), "Presentation audience", font=_font(17, "bold"), fill=COLORS["faint"])
    _wrap(draw, scenario.audience, (934, 170), 264, 3, 18, COLORS["ink"], "medium")
    _round(draw, (56, 323, 56 + int(740 * scene_progress), 327), 2, scenario.accent)


def _metrics(draw: ImageDraw.ImageDraw, scenario: Scenario) -> None:
    for idx, (label, value) in enumerate(scenario.metrics):
        x = 56 + idx * 250
        _panel(draw, (x, 358, x + 226, 442))
        draw.text((x + 20, 377), label, font=_font(15, "bold"), fill=COLORS["muted"])
        color = scenario.accent if idx == 0 else scenario.secondary if idx == 1 else COLORS["amber"]
        draw.text((x + 20, 401), value, font=_font(30, "bold"), fill=color)


def _request_panel(draw: ImageDraw.ImageDraw, scenario: Scenario, scene_progress: float) -> None:
    _panel(draw, (830, 308, 1224, 442))
    draw.text((854, 329), "Current prompt", font=_font(16, "bold"), fill=COLORS["faint"])
    _wrap(draw, scenario.request, (854, 362), 342, 3, 19, COLORS["ink"], "medium")
    _round(draw, (854, 432, 854 + int(320 * _ease(scene_progress)), 436), 2, scenario.secondary)


def _main_panels(
    draw: ImageDraw.ImageDraw,
    scenario: Scenario,
    scene: Scene,
    scene_progress: float,
) -> None:
    y = 470
    left_w = 420 if scene.chat else 520
    _panel(draw, (56, y, 56 + left_w, y + 166))
    _panel(draw, (56 + left_w + 24, y, 56 + 2 * left_w + 24, y + 166))
    _list_panel(draw, (56, y), left_w, scene.left_title, scene.left_rows, scenario.accent)
    _list_panel(
        draw,
        (56 + left_w + 24, y),
        left_w,
        scene.right_title,
        scene.right_rows,
        scenario.secondary,
    )
    _panel(draw, (920, y, 1224, y + 166))
    if scene.chat:
        draw.text((944, y + 18), "Agent chat", font=_font(15, "bold"), fill=COLORS["faint"])
        line_y = y + 54
        for speaker, message in scene.chat:
            color = COLORS["amber"] if speaker == "User" else scenario.accent
            draw.text((944, line_y), speaker, font=_font(13, "bold"), fill=color)
            _wrap(draw, message, (944, line_y + 18), 254, 2, 13, COLORS["ink"], "medium")
            line_y += 56
    else:
        draw.text((944, y + 18), scene.chart_title, font=_font(15, "bold"), fill=COLORS["faint"])
        _bars(draw, (944, y + 58), 244, scene.bars or [], scene_progress)


def _list_panel(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    width: int,
    title: str,
    rows: list[str],
    accent: str,
) -> None:
    x, y = xy
    _round(draw, (x + 20, y + 22, x + 25, y + 46), 3, accent)
    draw.text((x + 36, y + 20), title, font=_font(18, "bold"), fill=COLORS["ink"])
    for idx, row in enumerate(rows[:4]):
        row_y = y + 66 + idx * 24
        _round(draw, (x + 22, row_y - 8, x + 29, row_y - 1), 4, COLORS["line"])
        _wrap(draw, row, (x + 42, row_y - 14), width - 68, 1, 14, COLORS["muted"], "medium")


def _bars(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    width: int,
    bars: list[tuple[str, float, str]],
    scene_progress: float,
) -> None:
    x, y = xy
    for idx, (label, value, color) in enumerate(bars):
        row_y = y + idx * 26
        draw.text((x, row_y - 2), label, font=_font(12, "bold"), fill=COLORS["muted"])
        _round(draw, (x + 106, row_y, x + width, row_y + 12), 6, COLORS["panel3"])
        fill_width = int((width - 106) * value * _ease(scene_progress))
        _round(draw, (x + 106, row_y, x + 106 + fill_width, row_y + 12), 6, color)


def _timeline(
    draw: ImageDraw.ImageDraw,
    scenario: Scenario,
    active_stage: int,
    progress: float,
) -> None:
    x, y, width = 56, 660, 1168
    draw.line((x + 20, y, x + width - 20, y), fill=COLORS["line"], width=2)
    count = len(scenario.timeline)
    for idx, label in enumerate(scenario.timeline):
        step_x = x + int((width - 40) * (idx / (count - 1))) + 20
        complete = idx <= active_stage
        color = scenario.accent if complete else COLORS["panel3"]
        draw.ellipse((step_x - 12, y - 12, step_x + 12, y + 12), fill=color)
        draw.text(
            (step_x - 58, y + 24),
            label,
            font=_font(13, "bold" if complete else "medium"),
            fill=COLORS["ink"] if complete else COLORS["faint"],
        )
    _round(draw, (x, y - 34, x + int(width * progress), y - 31), 2, scenario.secondary)


def _footer(draw: ImageDraw.ImageDraw, scenario: Scenario) -> None:
    draw.text(
        (56, 700),
        f"Runtime: {scenario.duration}s from a {scenario.source_seconds}s story arc",
        font=_font(12, "medium"),
        fill=COLORS["faint"],
    )
    draw.text(
        (812, 700),
        "Generated locally from scripts/generate_collateral_video_examples.py",
        font=_font(12, "medium"),
        fill=COLORS["faint"],
    )


def _scene_at(scenes: list[Scene], seconds: float) -> Scene:
    selected = scenes[0]
    for scene in scenes:
        if seconds >= scene.start:
            selected = scene
    return selected


def _scene_progress(scenes: list[Scene], scene: Scene, seconds: float) -> float:
    idx = scenes.index(scene)
    end = scenes[idx + 1].start if idx + 1 < len(scenes) else scene.start + 12
    return max(0.0, min((seconds - scene.start) / max(end - scene.start, 1), 1.0))


def _panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    _round(draw, box, 8, COLORS["panel"])
    draw.rounded_rectangle(box, radius=8, outline=COLORS["line"], width=1)


def _pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: str) -> None:
    x, y = xy
    font = _font(14, "bold")
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0] + 26
    _round(draw, (x, y, x + width, y + 32), 16, COLORS["panel2"])
    draw.text((x + 13, y + 7), text, font=font, fill=color)


def _round(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: str,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    width: int,
    max_lines: int,
    size: int,
    fill: str,
    weight: str,
) -> None:
    x, y = xy
    font = _font(size, weight)
    chars = max(14, int(width / max(size * 0.52, 1)))
    lines: list[str] = []
    for line in wrap(text, width=chars):
        lines.append(line)
        if len(lines) >= max_lines:
            break
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += int(size * 1.35)


def _font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _ease(value: float) -> float:
    value = max(0.0, min(value, 1.0))
    return 1 - (1 - value) ** 3


def _ffmpeg_path() -> str:
    bundled = REPO_ROOT / "frontend" / "app" / "node_modules" / "@ffmpeg-installer"
    for path in bundled.glob("*/ffmpeg"):
        return str(path)
    fallback = shutil.which("ffmpeg")
    if fallback:
        return fallback
    raise RuntimeError("No FFmpeg binary found. Run npm install in frontend/app first.")


def _encode_mp4(ffmpeg: str, frame_dir: Path, output: Path) -> None:
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(frame_dir / "frame_%04d.png"),
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
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError(f"FFmpeg failed for {output.name}")


if __name__ == "__main__":
    main()
