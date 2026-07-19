"""Generate operational optimizer MP4 storyboard examples.

Run from the repository root:
    .venv/bin/python scripts/generate_operational_optimizer_video_examples.py
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.production_optimizers import (
    CashMovementProductionAdapter,
    MarginCallWorkflowProductionAdapter,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "video_examples" / "operations"
TMP_DIR = REPO_ROOT / "tmp" / "video" / "operations_storyboard"
WIDTH = 1280
HEIGHT = 720
FPS = 10
SOURCE_SECONDS = 96
PLAYBACK_SPEED = 1.5
SECONDS = round(SOURCE_SECONDS / PLAYBACK_SPEED)

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
    workflow_label: str
    accent: str
    chat: list[tuple[str, str]] | None = None
    bars: list[tuple[str, float, str]] | None = None
    title_card: str | None = None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    frames_dir = TMP_DIR / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    cash_result = _run_cash_movement()
    margin_result = _run_margin_workflow()
    scenes = _build_scenes(cash_result, margin_result)

    total_frames = SECONDS * FPS
    for frame_idx in range(total_frames):
        second = min((frame_idx / FPS) * PLAYBACK_SPEED, SOURCE_SECONDS)
        scene = _scene_at(scenes, second)
        image = _draw_frame(scene, cash_result, margin_result, second / SOURCE_SECONDS)
        image.save(frames_dir / f"frame_{frame_idx:05d}.png")

    _encode_mp4(
        frames_dir,
        OUT_DIR / "treasury-margin-operations-storyboard-demo.mp4",
    )
    shutil.rmtree(TMP_DIR, ignore_errors=True)


def _run_cash_movement():
    request = OptimizationRequest(
        domain="treasury_operations",
        portfolio_id="PORT_TREASURY_OPS",
        objective=Objective(
            name="minimize_cash_movement_cost",
            direction=ObjectiveDirection.MINIMIZE,
            metric="transfer_cost",
        ),
        context={
            "data_snapshot_id": "SNAP_CASHMOVE_VIDEO",
            "cutoff_hour": 15,
            "cash_balances": [
                {
                    "account_id": "SRC_1",
                    "entity": "Broker Dealer",
                    "currency": "USD",
                    "available_cash": 150_000_000,
                    "minimum_buffer": 20_000_000,
                },
                {
                    "account_id": "SRC_2",
                    "entity": "Bank Entity",
                    "currency": "USD",
                    "available_cash": 80_000_000,
                    "minimum_buffer": 15_000_000,
                },
            ],
            "funding_requirements": [
                {
                    "requirement_id": "PAY_A",
                    "target_account_id": "CLEARING_A",
                    "currency": "USD",
                    "required_cash": 90_000_000,
                    "cutoff_hour": 15,
                },
                {
                    "requirement_id": "PAY_B",
                    "target_account_id": "SETTLEMENT_B",
                    "currency": "USD",
                    "required_cash": 65_000_000,
                    "cutoff_hour": 16,
                },
            ],
            "payment_rails": [
                {
                    "rail_id": "FEDWIRE",
                    "currency": "USD",
                    "fee_bps": 0.15,
                    "fixed_fee": 35,
                    "cutoff_hour": 17,
                    "max_transfer": 250_000_000,
                },
                {
                    "rail_id": "CHIPS",
                    "currency": "USD",
                    "fee_bps": 0.08,
                    "fixed_fee": 20,
                    "cutoff_hour": 16,
                    "max_transfer": 125_000_000,
                },
            ],
        },
    )
    return CashMovementProductionAdapter().run(request)


def _run_margin_workflow():
    request = OptimizationRequest(
        domain="margin_operations",
        portfolio_id="PORT_MARGIN_OPS",
        objective=Objective(
            name="minimize_sla_breach_risk",
            direction=ObjectiveDirection.MINIMIZE,
            metric="residual_risk",
        ),
        context={
            "data_snapshot_id": "SNAP_MARGIN_VIDEO",
            "team_capacity_minutes": 150,
            "materiality_threshold": 25_000_000,
            "margin_call_queue": [
                {
                    "call_id": "MC_A",
                    "counterparty": "Dealer A",
                    "amount": 40_000_000,
                    "due_in_hours": 2,
                    "dispute_probability": 0.20,
                    "ops_minutes": 80,
                    "risk_tier": "high",
                },
                {
                    "call_id": "MC_B",
                    "counterparty": "CCP B",
                    "amount": 70_000_000,
                    "due_in_hours": 1,
                    "dispute_probability": 0.05,
                    "ops_minutes": 70,
                    "risk_tier": "critical",
                },
                {
                    "call_id": "MC_C",
                    "counterparty": "Dealer C",
                    "amount": 15_000_000,
                    "due_in_hours": 8,
                    "dispute_probability": 0.60,
                    "ops_minutes": 90,
                    "risk_tier": "medium",
                },
            ],
        },
    )
    return MarginCallWorkflowProductionAdapter().run(request)


def _build_scenes(cash_result, margin_result) -> list[Scene]:
    total_moved = cash_result.domain_attachments["total_moved_cash"]
    transfer_count = cash_result.domain_attachments["transfer_count"]
    cash_savings = cash_result.baseline_value - cash_result.objective_value
    assigned = margin_result.domain_attachments["assigned_calls"]
    deferred = margin_result.domain_attachments["deferred_calls"]
    assigned_amount = margin_result.domain_attachments["assigned_amount"]
    total_queue = margin_result.domain_attachments["total_queue_amount"]
    capacity_used = margin_result.domain_attachments["capacity_used"]
    return [
        Scene(
            0,
            1,
            "Operational Optimization Extends The Platform Beyond Portfolios",
            (
                "This storyboard combines two new production adapters: treasury "
                "cash movement and margin-call workflow prioritization."
            ),
            "Frame operational decisions as optimizer workflows",
            "New Production Adapters",
            [
                "production.treasury.cash_movement",
                "production.margin_call.workflow",
                "Same adapter lifecycle as portfolio models",
                "Preflight, solve, normalize, evidence",
            ],
            "Why It Matters",
            [
                "Treasury and operations teams get decision support",
                "Controls and evidence are built into the workflow",
                "Firm engines can replace the scaffold later",
                "The UI can surface operational recommendations",
            ],
            "Operations storyboard",
            COLORS["cyan"],
            title_card="Operational Optimizer Walkthrough",
        ),
        Scene(
            9,
            2,
            "Example #1: Treasury Cash Movement",
            "The user asks how to fund clearing and settlement needs before cutoffs.",
            "Collect cash balances, funding needs, rails, buffers, and cutoffs",
            "Business Request",
            [
                "Move cash for clearing and settlement",
                "Protect minimum buffers by source account",
                "Use open payment rails before cutoff",
                "Minimize transfer cost and late-funding risk",
            ],
            "Adapter Contract",
            [
                "validate_inputs(): check balances and rails",
                "build_problem(): normalize requirements",
                "solve(): route cash over feasible rails",
                "serialize_evidence(): retain snapshot and fingerprint",
            ],
            "Treasury Cash Movement",
            COLORS["cyan"],
            chat=[
                ("User", "We need to fund clearing and settlement today."),
                ("Assistant", "I will route cash through open rails and preserve buffers."),
            ],
        ),
        Scene(
            22,
            3,
            "The Optimizer Routes Cash Through Feasible Rails",
            (
                "The scaffold uses deterministic least-cost routing today and "
                "can later be swapped for LP, MILP, payment-hub, or vendor logic."
            ),
            "Allocate funding from source accounts to target requirements",
            "Inputs",
            [
                "SRC_1 available: $150M / buffer: $20M",
                "SRC_2 available: $80M / buffer: $15M",
                "PAY_A requirement: $90M",
                "PAY_B requirement: $65M",
                "Rails: CHIPS and FEDWIRE",
            ],
            "Run Output",
            [
                f"Status: {cash_result.status}",
                f"Cash moved: {_money(total_moved)}",
                f"Transfers created: {transfer_count}",
                f"Estimated cost saved: {_money(cash_savings)}",
                f"Binding check: {cash_result.binding_constraints[0]}",
            ],
            "Treasury Cash Movement",
            COLORS["cyan"],
            bars=[
                ("Funding satisfied", 1.0, COLORS["green"]),
                ("Source buffer retained", 0.86, COLORS["cyan"]),
                ("Rail cutoff coverage", 0.92, COLORS["blue"]),
                ("Cost efficiency", 0.74, COLORS["amber"]),
            ],
        ),
        Scene(
            36,
            4,
            "Cash Movement Ends With Reviewer-Ready Evidence",
            (
                "The output is not only a payment list; it carries lineage, "
                "model config, input snapshot, and normalized result sections."
            ),
            "Package transfer recommendations and reproducibility metadata",
            "Recommended Transfers",
            _transfer_rows(cash_result),
            "Evidence Captured",
            [
                "Model version and config version",
                "Data snapshot ID: SNAP_CASHMOVE_VIDEO",
                "Solver method: least_cost_cutoff_feasible",
                "Request, preflight, native solution, normalized result",
            ],
            "Treasury Cash Movement",
            COLORS["cyan"],
        ),
        Scene(
            47,
            5,
            "Example #2: Margin Call Workflow",
            "The second workflow prioritizes an operations queue when capacity is scarce.",
            "Score margin calls by exposure, SLA urgency, dispute risk, and risk tier",
            "Queue Pressure",
            [
                "Three calls arrive in the work window",
                "One CCP call is due in one hour",
                "One dealer call is material and high risk",
                "Team capacity is limited to 150 minutes",
            ],
            "Optimization Goal",
            [
                "Minimize residual queue risk",
                "Use available team capacity first",
                "Escalate material and disputed calls",
                "Defer lower priority work with evidence",
            ],
            "Margin Call Workflow",
            COLORS["amber"],
            title_card="Example #2: Margin Call Workflow",
        ),
        Scene(
            58,
            6,
            "The Adapter Turns A Work Queue Into A Prioritized Plan",
            (
                "The workflow makes operational triage explicit and repeatable "
                "instead of relying on manual queue sorting."
            ),
            "Assign calls that fit capacity and reduce the most risk",
            "Priority Inputs",
            [
                "Amount vs. materiality threshold",
                "Hours until SLA breach",
                "Dispute probability",
                "Counterparty risk tier",
                "Expected ops minutes",
            ],
            "Run Output",
            [
                f"Status: {margin_result.status}",
                f"Assigned amount: {_money(assigned_amount)}",
                f"Queue amount: {_money(total_queue)}",
                f"Capacity used: {capacity_used:.0f} minutes",
                f"Deferred calls: {len(deferred)}",
            ],
            "Margin Call Workflow",
            COLORS["amber"],
            bars=[
                ("Queue materiality", 1.0, COLORS["green"]),
                ("SLA urgency", 0.88, COLORS["red"]),
                ("Capacity used", capacity_used / 150, COLORS["amber"]),
                ("Risk reduced", 0.78, COLORS["blue"]),
            ],
        ),
        Scene(
            72,
            7,
            "The Recommendation Explains What To Process First",
            (
                "A manager sees exactly which calls are assigned, which are "
                "deferred, and why the capacity constraint is binding."
            ),
            "Review assigned work, deferred queue, and recommended actions",
            "Assigned Calls",
            _assigned_rows(assigned),
            "Deferred / Binding Context",
            _deferred_rows(deferred)
            + [
                f"Binding check: {margin_result.binding_constraints[0]}",
                "Evidence supports escalation or deferral",
            ],
            "Margin Call Workflow",
            COLORS["amber"],
            chat=[
                ("Ops Lead", "Why did the CCP call come first?"),
                ("Assistant", "It is material, critical tier, and due inside one hour."),
            ],
        ),
        Scene(
            84,
            8,
            "The Pattern Is Pluggable For Production Operations",
            (
                "Both workflows share the same adapter surface and can later "
                "point to firm systems, services, or solver engines."
            ),
            "Show a reusable production integration pattern",
            "Common Contract",
            [
                "validate_inputs()",
                "build_problem()",
                "solve()",
                "explain_outputs()",
                "serialize_evidence()",
            ],
            "Production Implication",
            [
                "In-process Python today",
                "Subprocess, REST, gRPC, batch, or containers later",
                "Normalized result contract for UI and API",
                "Governance/versioning ready from day one",
            ],
            "Operational platform extension",
            COLORS["green"],
        ),
    ]


def _draw_frame(scene: Scene, cash_result, margin_result, progress: float) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    fonts = _fonts()
    _background(draw, scene.accent, progress)
    _header(draw, fonts, scene)
    _workflow_metrics(draw, fonts, cash_result, margin_result)
    if scene.title_card:
        _title_card(draw, fonts, scene)
    _panel(draw, 36, 138, 584, 346, scene.left_title, scene.left_rows, fonts)
    right_rows = scene.right_rows[:3] if scene.bars else scene.right_rows
    _panel(draw, 660, 138, 584, 346, scene.right_title, right_rows, fonts)
    if scene.chat:
        _chat(draw, fonts, scene.chat, scene.accent)
    if scene.bars:
        _bars(draw, fonts, scene.bars)
    _caption(draw, fonts, scene, progress)
    _timeline(draw, fonts, scene.stage)
    return image


def _background(draw: ImageDraw.ImageDraw, accent: str, progress: float) -> None:
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=COLORS["bg"])
    draw.rectangle((0, 0, WIDTH, 82), fill="#071216")
    for x in range(-100, WIDTH + 140, 36):
        drift = int((progress * 120) % 36)
        draw.line((x + drift, 82, x + 210 + drift, HEIGHT), fill="#0A171B", width=1)
    draw.rounded_rectangle((36, 92, 1244, 98), radius=3, fill=accent)


def _header(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    scene: Scene,
) -> None:
    draw.rounded_rectangle((36, 22, 72, 58), radius=5, fill=scene.accent)
    draw.text((47, 32), "DI", fill=COLORS["bg"], font=fonts["small_bold"])
    draw.text((88, 20), "Decision Intelligence", fill=COLORS["ink"], font=fonts["label"])
    draw.text((88, 43), scene.workflow_label, fill=COLORS["muted"], font=fonts["small"])
    draw.rounded_rectangle(
        (946, 24, 1244, 56), radius=5, outline=COLORS["line"], fill=COLORS["panel"]
    )
    draw.text(
        (964, 33),
        "video_examples/operations",
        fill=scene.accent,
        font=fonts["small_bold"],
    )


def _workflow_metrics(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    cash,
    margin,
) -> None:
    metrics = [
        ("Cash moved", _money(cash.domain_attachments["total_moved_cash"])),
        ("Transfer count", str(cash.domain_attachments["transfer_count"])),
        ("Assigned margin", _money(margin.domain_attachments["assigned_amount"])),
        ("Capacity used", f"{margin.domain_attachments['capacity_used']:.0f} min"),
    ]
    x = 36
    for label, value in metrics:
        draw.rounded_rectangle(
            (x, 500, x + 286, 550), radius=8, fill=COLORS["panel"], outline=COLORS["line"]
        )
        draw.text((x + 16, 510), label, fill=COLORS["muted"], font=fonts["small_bold"])
        draw.text((x + 16, 530), value, fill=COLORS["ink"], font=fonts["metric"])
        x += 306


def _title_card(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    scene: Scene,
) -> None:
    draw.rounded_rectangle(
        (372, 24, 908, 56), radius=8, fill="#071116", outline=scene.accent, width=2
    )
    text_w = draw.textlength(scene.title_card or "", font=fonts["small_bold"])
    draw.text(
        ((WIDTH - text_w) / 2, 34),
        scene.title_card or "",
        fill=scene.accent,
        font=fonts["small_bold"],
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
    for row in rows[:7]:
        draw.rounded_rectangle((x + 18, yy, x + w - 18, yy + 34), radius=5, fill=COLORS["panel2"])
        _wrapped(draw, row, x + 32, yy + 8, w - 72, fonts["small"], COLORS["ink"], 1)
        yy += 42


def _caption(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    scene: Scene,
    progress: float,
) -> None:
    x, y, w, h = 36, 570, 1208, 126
    draw.rounded_rectangle(
        (x, y, x + w, y + h), radius=8, fill="#071116", outline=scene.accent, width=2
    )
    draw.text(
        (x + 18, y + 10),
        f"STAGE {scene.stage} OF 8",
        fill=scene.accent,
        font=fonts["small_bold"],
    )
    draw.text(
        (x + 960, y + 10),
        "PRODUCTION OPTIMIZER STORYBOARD",
        fill=scene.accent,
        font=fonts["small_bold"],
    )
    draw.text((x + 18, y + 32), scene.title, fill=COLORS["ink"], font=fonts["title"])
    _wrapped(draw, scene.caption, x + 18, y + 62, 1060, fonts["body"], COLORS["ink"], 1)
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
        fill=scene.accent,
    )


def _chat(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    chat: list[tuple[str, str]],
    accent: str,
) -> None:
    x, y = 80, 332
    for speaker, text in chat:
        color = COLORS["cyan"] if speaker in {"User", "Ops Lead"} else COLORS["green"]
        draw.rounded_rectangle((x, y, x + 498, y + 58), radius=8, fill="#0B1B1F", outline=color)
        draw.text(
            (x + 14, y + 10),
            speaker,
            fill=accent if speaker == "Assistant" else color,
            font=fonts["small_bold"],
        )
        _wrapped(draw, text, x + 96, y + 10, 380, fonts["small"], COLORS["ink"], 2)
        y += 68


def _bars(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    bars: list[tuple[str, float, str]],
) -> None:
    x, y = 704, 306
    for label, value, color in bars[:4]:
        draw.text((x, y), label, fill=COLORS["muted"], font=fonts["small_bold"])
        draw.rounded_rectangle((x, y + 22, x + 458, y + 38), radius=8, fill=COLORS["panel3"])
        draw.rounded_rectangle((x, y + 22, x + int(458 * value), y + 38), radius=8, fill=color)
        draw.text((x + 472, y + 18), _pct(value), fill=COLORS["ink"], font=fonts["small"])
        y += 48


def _timeline(
    draw: ImageDraw.ImageDraw,
    fonts: dict[str, ImageFont.ImageFont],
    active: int,
) -> None:
    labels = [
        "Overview",
        "Cash Ask",
        "Cash Solve",
        "Cash Proof",
        "Margin Ask",
        "Queue",
        "Actions",
        "Pattern",
    ]
    x, y = 126, 104
    for index, label in enumerate(labels, start=1):
        color = COLORS["green"] if index <= active else COLORS["faint"]
        draw.ellipse((x, y, x + 18, y + 18), fill=color)
        text_w = draw.textlength(label, font=fonts["small"])
        draw.text((x + 9 - text_w / 2, y + 24), label, fill=COLORS["muted"], font=fonts["small"])
        if index < len(labels):
            draw.line((x + 22, y + 9, x + 120, y + 9), fill=color, width=3)
        x += 130


def _transfer_rows(result) -> list[str]:
    rows = []
    for allocation in result.allocations[:4]:
        metadata = allocation.get("metadata", allocation)
        rows.append(
            f"{metadata['requirement_id']}: {_money(metadata['amount'])} "
            f"via {metadata['rail_id']} from {metadata['from_account_id']}"
        )
    return rows


def _assigned_rows(calls: list[dict]) -> list[str]:
    return [
        (
            f"{row['assigned_order']}. {row['call_id']} {row['counterparty']}: "
            f"{_money(row['amount'])}, {row['recommended_action']}"
        )
        for row in calls
    ]


def _deferred_rows(calls: list[dict]) -> list[str]:
    if not calls:
        return ["No deferred calls"]
    return [
        (
            f"{row['call_id']} {row['counterparty']}: {_money(row['amount'])}, "
            f"{row['recommended_action']}"
        )
        for row in calls
    ]


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
