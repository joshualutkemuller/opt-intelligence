"""Generate an end-to-end collateral schedule ingestion MP4 demo.

Shows the full flow: register counterparty → create agreement → upload
schedule (CSV / XLSX / PDF) → inspect entries → run optimizer → view
allocation result.

Run from the repository root:
    python scripts/generate_collateral_ingestion_demo_video.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap as _tw

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "video_examples" / "collateral"
TMP_DIR = REPO_ROOT / "tmp" / "video" / "collateral_ingestion_demo"
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
    "purple": "#BB9AF7",
}

ACCENT = COLORS["blue"]
SECONDARY = COLORS["cyan"]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Step:
    """One screen shown during a scene — an API call or code block."""
    label: str
    lines: list[str]
    color: str = COLORS["blue"]


@dataclass
class Scene:
    start: int           # seconds into the video
    headline: str
    support: str
    # left info panel
    left_title: str
    left_rows: list[str]
    # right info panel
    right_title: str
    right_rows: list[str]
    # optional: code / API panel (replaces bar chart)
    step: Step | None = None
    # optional: horizontal bars
    bars: list[tuple[str, float, str]] | None = None


# ---------------------------------------------------------------------------
# Full scenario definition
# ---------------------------------------------------------------------------

SCENES: list[Scene] = [
    # ── 0s  Introduction ──────────────────────────────────────────────────
    Scene(
        start=0,
        headline="Collateral schedule ingestion — end to end",
        support=(
            "From a raw eligibility document to an optimized allocation in five steps: "
            "counterparty, agreement, schedule upload, inspection, and LP solve."
        ),
        left_title="What this demo covers",
        left_rows=[
            "Step 1 — Register counterparty + margin agreement",
            "Step 2 — Upload schedule (CSV, XLSX, or PDF)",
            "Step 3 — LLM extracts haircuts and eligibility",
            "Step 4 — Inspect entries and version history",
        ],
        right_title="End-state capabilities",
        right_rows=[
            "Step 5 — Run collateral LP optimizer",
            "Minimize funding cost across all obligations",
            "Full audit trail: superseded_at on old entries",
            "Multi-counterparty support via agreement_id",
        ],
        step=Step(
            label="Architecture overview",
            lines=[
                "collateral_schedule  ← standalone package",
                "  parse_schedule()   CSV / XLSX → entries",
                "  parse_pdf_with_llm() PDF → LLM → entries",
                "  CollateralDatabase  SQLite version store",
                "",
                "CollateralOptimizer  ← LP solver layer",
                "  load_collateral()  reads from DB via",
                "  agreement_id       threaded through context",
            ],
            color=COLORS["purple"],
        ),
    ),

    # ── 14s  Step 1 — Register counterparty ───────────────────────────────
    Scene(
        start=14,
        headline="Step 1 — Register a counterparty and margin agreement",
        support=(
            "Every schedule belongs to a counterparty. One counterparty can hold "
            "multiple agreements — one per margin type (VM, IM, REPO, CCP_IM …)."
        ),
        left_title="Register counterparty",
        left_rows=[
            "POST /api/collateral/counterparties",
            "name: Goldman Sachs",
            "lei:  784F5XWPLTWKTBV3E584",
            "→ id: cp_abc123",
        ],
        right_title="Create margin agreement",
        right_rows=[
            "POST /api/collateral/agreements",
            "counterparty_id: cp_abc123",
            "margin_type: VM  (variation margin)",
            "→ id: agr_xyz",
        ],
        step=Step(
            label="API request — create counterparty",
            lines=[
                'curl -X POST /api/collateral/counterparties \\',
                '  -d \'{"name": "Goldman Sachs",',
                '       "lei": "784F5XWPLTWKTBV3E584",',
                '       "jurisdiction": "US"}\'',
                "",
                '# Response',
                '{"id": "cp_abc123",',
                ' "name": "Goldman Sachs",',
                ' "created_at": "2026-07-22T10:00:00Z"}',
            ],
            color=COLORS["cyan"],
        ),
    ),

    # ── 28s  Step 2 — Upload CSV schedule ─────────────────────────────────
    Scene(
        start=28,
        headline="Step 2 — Upload a collateral schedule (CSV path)",
        support=(
            "CSV and XLSX schedules are parsed deterministically — no LLM required. "
            "The parser accepts many column-name aliases for every field."
        ),
        left_title="Accepted CSV aliases",
        left_rows=[
            "asset_class  ← Asset Class, Collateral Type",
            "haircut_pct  ← Haircut (%), HC, HC (%)",
            "eligible     ← Eligible, Accepted, Permitted",
            "isin         ← ISIN, CUSIP, Security ID",
        ],
        right_title="Ingest response",
        right_rows=[
            "entries_inserted: 34",
            "replaced: true  (old entries superseded)",
            "eligible_count: 28",
            "avg_haircut_pct: 14.3 %",
        ],
        step=Step(
            label="API request — ingest CSV",
            lines=[
                'curl -X POST /api/collateral/agreements/agr_xyz/ingest \\',
                '  -d \'{"csv_content":',
                '       "Asset Class,Haircut (%),Eligible\\n',
                '        GOVT,2.0,Yes\\n',
                '        CORP,5.0,Yes\\n',
                '        EQUITY,,No",',
                '       "replace": true}\'',
                "",
                '# → {"entries_inserted": 34, "replaced": true}',
            ],
            color=COLORS["green"],
        ),
    ),

    # ── 42s  Step 3 — PDF upload + LLM extraction ─────────────────────────
    Scene(
        start=42,
        headline="Step 3 — PDF upload with LLM extraction",
        support=(
            "For PDF schedules the API calls parse_pdf_with_llm(). "
            "PyMuPDF extracts text and tables; the LLM maps them to structured entries. "
            "Set use_llm: false to fall back to text-heuristic parsing."
        ),
        left_title="LLM extraction pipeline",
        left_rows=[
            "PyMuPDF → [page N text] + [page N table M]",
            "Table-aware chunk splitter → section context",
            "LLM prompt → JSON entries (haircut, class, …)",
            "Post-extraction validator → haircut range check",
        ],
        right_title="Auto-correction rules",
        right_rows=[
            "Values > 50% on eligible entries → inverted",
            "(Fed schedules use % of market value)",
            "notes field tagged [auto-corrected]",
            "isin_invalid flag on malformed ISINs",
        ],
        step=Step(
            label="API request — ingest PDF with LLM",
            lines=[
                'curl -X POST /api/collateral/agreements/agr_xyz/ingest \\',
                '  -d "{\\"pdf_base64\\": \\"$(base64 -w0 schedule.pdf)\\",',
                '        \\"filename\\": \\"schedule.pdf\\",',
                '        \\"use_llm\\": true}"',
                "",
                '# config/llm.yaml → provider: anthropic',
                '# or set ANTHROPIC_API_KEY / OPENAI_API_KEY',
                "",
                '# → {"entries_inserted": 44, "replaced": true}',
            ],
            color=COLORS["amber"],
        ),
    ),

    # ── 56s  Step 4 — Inspect entries ─────────────────────────────────────
    Scene(
        start=56,
        headline="Step 4 — Inspect entries and version history",
        support=(
            "Every ingest stamps the old entries with superseded_at, preserving full "
            "version history. Filter by asset class or eligible-only for a focused view."
        ),
        left_title="GET schedule endpoint",
        left_rows=[
            "GET /agreements/agr_xyz/schedule",
            "?eligible_only=true",
            "?asset_class=GOVT",
            "Returns id, haircut_pct, max_maturity_years …",
        ],
        right_title="Version audit trail",
        right_rows=[
            "GET /agreements/agr_xyz/history",
            "schedule_version 1 → superseded_at stamped",
            "schedule_version 2 → live (superseded_at null)",
            "No data deleted — full lineage preserved",
        ],
        bars=[
            ("GOVT eligible", 0.96, COLORS["green"]),
            ("CORP eligible", 0.82, COLORS["blue"]),
            ("AGENCY eligible", 0.88, COLORS["cyan"]),
            ("EQUITY eligible", 0.12, COLORS["red"]),
        ],
    ),

    # ── 70s  Step 5 — Run optimizer ───────────────────────────────────────
    Scene(
        start=70,
        headline="Step 5 — Run the collateral LP optimizer",
        support=(
            "Pass agreement_id in the request and the optimizer automatically loads "
            "live eligibility rules from the database. No data_source wiring needed."
        ),
        left_title="LP problem formulation",
        left_rows=[
            "Minimize: Σ funding_cost_bps × MV × allocation",
            "Subject to: inventory limits per asset",
            "Coverage: obligation met after haircut",
            "Eligibility: only eligible asset classes posted",
        ],
        right_title="Optimizer result",
        right_rows=[
            "Total funding cost: 42.3 bps",
            "All 3 obligations covered",
            "Concentration limits: satisfied",
            "HQLA Level 1 (Treasuries): 68% of pool",
        ],
        step=Step(
            label="API request — run optimizer",
            lines=[
                'curl -X POST /api/optimizations/run \\',
                '  -d \'{"domain": "collateral",',
                '       "portfolio_id": "PORT_001",',
                '       "objective_metric": "funding_cost",',
                '       "agreement_id": "agr_xyz"}\'',
                "",
                '# Python equivalent:',
                'CollateralOptimizer().solve(',
                '  optimizer.prepare_problem(request))',
            ],
            color=COLORS["blue"],
        ),
    ),

    # ── 84s  Result + closeout ─────────────────────────────────────────────
    Scene(
        start=84,
        headline="End-to-end result — allocation and evidence",
        support=(
            "The optimizer returns an allocation table: per-asset fractions posted "
            "against each obligation. Funding cost, coverage, and HQLA tier mix "
            "are ready for reviewer export."
        ),
        left_title="Allocation output",
        left_rows=[
            "US Treasury 5Y: 42% → Goldman VM obligation",
            "Agency MBS: 23% → Goldman VM obligation",
            "Corporate BBB: 11% → Goldman VM obligation",
            "Equity: 0%   → ineligible under agreement",
        ],
        right_title="Governance summary",
        right_rows=[
            "Source: live CollateralDatabase (agr_xyz)",
            "Objective: funding_cost minimized",
            "Constraints: inventory, coverage, eligibility",
            "Export: JSON / PDF / CSV evidence packet",
        ],
        bars=[
            ("Treasuries", 0.68, COLORS["green"]),
            ("Agency MBS", 0.22, COLORS["blue"]),
            ("Corp credit", 0.08, COLORS["amber"]),
            ("Equity", 0.02, COLORS["red"]),
        ],
    ),
]

TIMELINE_LABELS = [
    "Counterparty",
    "Agreement",
    "Upload",
    "Inspect",
    "Optimize",
    "Result",
]

METRICS = [
    ("Entries ingested", "34"),
    ("Avg haircut", "14.3%"),
    ("Funding cost", "42.3 bps"),
]

REQUEST_TEXT = (
    "Register Goldman Sachs, upload the Q3 collateral schedule, "
    "inspect entries, then optimize coverage at minimum funding cost."
)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def main() -> None:
    import imageio
    import numpy as np

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    out_path = OUT_DIR / "collateral-schedule-ingestion-end-to-end-demo.mp4"
    duration = SCENES[-1].start + 14
    total_frames = duration * FPS

    print(f"Rendering {total_frames} frames ({duration}s) …")
    writer = imageio.get_writer(
        str(out_path),
        fps=30,
        codec="libx264",
        quality=8,
        macro_block_size=None,
        output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    for index in range(total_frames):
        seconds = index / FPS
        progress = index / max(total_frames - 1, 1)
        frame = _draw_frame(seconds, progress)
        # Each source frame holds for (30/FPS) display frames
        arr = np.array(frame)
        hold = 30 // FPS
        for _ in range(hold):
            writer.append_data(arr)
    writer.close()

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Wrote {out_path.relative_to(REPO_ROOT)} ({size_mb:.1f} MB)")


def _draw_frame(seconds: float, progress: float) -> Image.Image:
    scene = _scene_at(seconds)
    scene_idx = SCENES.index(scene)
    scene_progress = _scene_progress(scene, seconds)

    img = Image.new("RGB", (WIDTH, HEIGHT), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    _bg(draw, progress)
    _top_bar(draw)
    _hero(draw, scene, scene_progress)
    _metrics_row(draw)
    _request_panel(draw, scene_progress)
    _main_panels(draw, scene, scene_progress)
    _timeline(draw, scene_idx, progress)
    _footer(draw, seconds)
    return img


# ── Background ───────────────────────────────────────────────────────────────

def _bg(draw: ImageDraw.ImageDraw, progress: float) -> None:
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=COLORS["bg2"])
    for x in range(-160 + int((progress * 280) % 140), WIDTH + 160, 140):
        draw.line((x, 84, x - 250, HEIGHT), fill="#14272E", width=1)
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=ACCENT, width=1)


# ── Top bar ───────────────────────────────────────────────────────────────────

def _top_bar(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((0, 0, WIDTH, 84), fill="#0D1A20")
    _round(draw, (56, 20, 108, 64), 10, ACCENT)
    draw.text((71, 27), "DI", font=_font(24, "bold"), fill=COLORS["bg"])
    draw.text((128, 18), "Decision Intelligence", font=_font(24, "bold"), fill=COLORS["ink"])
    draw.text((128, 45), "Collateral Management", font=_font(16, "medium"), fill=COLORS["muted"])
    _pill(draw, (924, 24), "collateral schedule", ACCENT)
    _pill(draw, (1092, 24), "end-to-end demo", COLORS["muted"])


# ── Hero ─────────────────────────────────────────────────────────────────────

def _hero(draw: ImageDraw.ImageDraw, scene: Scene, scene_progress: float) -> None:
    draw.text((56, 103), "Schedule Ingestion → LP Allocation", font=_font(18, "bold"), fill=COLORS["muted"])
    _wrap(draw, scene.headline, (56, 145), 770, 2, 38, COLORS["ink"], "bold")
    _wrap(draw, scene.support, (58, 246), 770, 3, 20, COLORS["muted"], "regular")
    _panel(draw, (910, 112, 1224, 262))
    draw.text((934, 133), "Presentation audience", font=_font(17, "bold"), fill=COLORS["faint"])
    audience = "Collateral ops, treasury risk, secured financing, and governance teams"
    _wrap(draw, audience, (934, 170), 264, 3, 18, COLORS["ink"], "medium")
    _round(draw, (56, 323, 56 + int(740 * scene_progress), 327), 2, ACCENT)


# ── Metrics ───────────────────────────────────────────────────────────────────

def _metrics_row(draw: ImageDraw.ImageDraw) -> None:
    for idx, (label, value) in enumerate(METRICS):
        x = 56 + idx * 250
        _panel(draw, (x, 358, x + 226, 442))
        draw.text((x + 20, 377), label, font=_font(15, "bold"), fill=COLORS["muted"])
        color = ACCENT if idx == 0 else SECONDARY if idx == 1 else COLORS["amber"]
        draw.text((x + 20, 401), value, font=_font(30, "bold"), fill=color)


# ── Request panel ─────────────────────────────────────────────────────────────

def _request_panel(draw: ImageDraw.ImageDraw, scene_progress: float) -> None:
    _panel(draw, (830, 308, 1224, 442))
    draw.text((854, 329), "Current prompt", font=_font(16, "bold"), fill=COLORS["faint"])
    _wrap(draw, REQUEST_TEXT, (854, 362), 342, 3, 19, COLORS["ink"], "medium")
    _round(draw, (854, 438, 854 + int(320 * _ease(scene_progress)), 440), 2, SECONDARY)


# ── Main panels ───────────────────────────────────────────────────────────────

def _main_panels(draw: ImageDraw.ImageDraw, scene: Scene, scene_progress: float) -> None:
    y = 470
    has_step = scene.step is not None
    left_w = 420 if has_step else 520

    _panel(draw, (56, y, 56 + left_w, y + 166))
    _panel(draw, (56 + left_w + 24, y, 56 + 2 * left_w + 24, y + 166))
    _list_panel(draw, (56, y), left_w, scene.left_title, scene.left_rows, ACCENT)
    _list_panel(draw, (56 + left_w + 24, y), left_w, scene.right_title, scene.right_rows, SECONDARY)

    _panel(draw, (920, y, 1224, y + 166))
    if scene.step:
        step = scene.step
        draw.text((944, y + 14), step.label, font=_font(14, "bold"), fill=COLORS["faint"])
        visible = max(1, int(len(step.lines) * _ease(scene_progress)))
        for i, line in enumerate(step.lines[:visible]):
            color = step.color if line and not line.startswith("#") else COLORS["faint"]
            if line.startswith("#"):
                color = COLORS["faint"]
            draw.text((944, y + 38 + i * 16), line[:36], font=_font(12, "medium"), fill=color)
    elif scene.bars:
        draw.text((944, y + 14), "Eligible asset classes", font=_font(14, "bold"), fill=COLORS["faint"])
        _bars(draw, (944, y + 52), 244, scene.bars, scene_progress)


# ── List panel helper ─────────────────────────────────────────────────────────

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


# ── Bars helper ───────────────────────────────────────────────────────────────

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
        fill_w = int((width - 106) * value * _ease(scene_progress))
        _round(draw, (x + 106, row_y, x + 106 + fill_w, row_y + 12), 6, color)


# ── Timeline ─────────────────────────────────────────────────────────────────

def _timeline(draw: ImageDraw.ImageDraw, active_stage: int, progress: float) -> None:
    x, y, width = 56, 660, 1168
    draw.line((x + 20, y, x + width - 20, y), fill=COLORS["line"], width=2)
    count = len(TIMELINE_LABELS)
    for idx, label in enumerate(TIMELINE_LABELS):
        step_x = x + int((width - 40) * (idx / (count - 1))) + 20
        complete = idx <= active_stage
        color = ACCENT if complete else COLORS["panel3"]
        draw.ellipse((step_x - 12, y - 12, step_x + 12, y + 12), fill=color)
        draw.text(
            (step_x - 52, y + 24),
            label,
            font=_font(13, "bold" if complete else "medium"),
            fill=COLORS["ink"] if complete else COLORS["faint"],
        )
    _round(draw, (x, y - 34, x + int(width * progress), y - 31), 2, SECONDARY)


# ── Footer ────────────────────────────────────────────────────────────────────

def _footer(draw: ImageDraw.ImageDraw, seconds: float) -> None:
    draw.text(
        (56, 700),
        f"t={seconds:.1f}s — collateral schedule ingestion end-to-end demo",
        font=_font(12, "medium"),
        fill=COLORS["faint"],
    )
    draw.text(
        (760, 700),
        "Generated by scripts/generate_collateral_ingestion_demo_video.py",
        font=_font(12, "medium"),
        fill=COLORS["faint"],
    )


# ── Primitives ────────────────────────────────────────────────────────────────

def _scene_at(seconds: float) -> Scene:
    selected = SCENES[0]
    for scene in SCENES:
        if seconds >= scene.start:
            selected = scene
    return selected


def _scene_progress(scene: Scene, seconds: float) -> float:
    idx = SCENES.index(scene)
    end = SCENES[idx + 1].start if idx + 1 < len(SCENES) else scene.start + 12
    return max(0.0, min((seconds - scene.start) / max(end - scene.start, 1), 1.0))


def _panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    _round(draw, box, 8, COLORS["panel"])
    draw.rounded_rectangle(box, radius=8, outline=COLORS["line"], width=1)


def _pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: str) -> None:
    x, y = xy
    font = _font(14, "bold")
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0] + 26
    _round(draw, (x, y, x + w, y + 32), 16, COLORS["panel2"])
    draw.text((x + 13, y + 7), text, font=font, fill=color)


def _round(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str) -> None:
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
    for line in _tw(text, width=chars):
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
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
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




if __name__ == "__main__":
    main()
