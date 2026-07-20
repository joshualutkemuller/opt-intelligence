"""Compose the two real front-end demos into one presentation MP4.

Run from the repository root:

    .venv/bin/python scripts/generate_combined_frontend_demo_video.py
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = REPO_ROOT / "tmp" / "video" / "combined_frontend_demo"
OUT_DIR = REPO_ROOT / "video_examples" / "combined"
OUTPUT = OUT_DIR / "collateral-and-money-market-frontend-demo.mp4"
COLLATERAL_VIDEO = next(
    (
        REPO_ROOT / "video_examples" / "collateral" / name
        for name in (
            "collateral-hqla-frontend-orchestration-demo.mp4",
            "collateral-hqla-frontend-orchestration-demo.webm",
        )
        if (REPO_ROOT / "video_examples" / "collateral" / name).exists()
    ),
    REPO_ROOT / "video_examples" / "collateral" / "collateral-hqla-frontend-orchestration-demo.mp4",
)
MONEY_MARKET_VIDEO = (
    REPO_ROOT / "video_examples" / "money_market" / "money-market-pdf-policy-optimization-demo.mp4"
)

WIDTH = 1600
HEIGHT = 900
FPS = 25
TITLE_SECONDS = 2

COLORS = {
    "bg": "#030B0F",
    "panel": "#0B1520",
    "panel2": "#0E1C27",
    "line": "#1F3442",
    "cyan": "#27D7E8",
    "teal": "#5FD4CF",
    "green": "#89D185",
    "ink": "#F6FAFF",
    "muted": "#9BAEC0",
    "amber": "#F7B84A",
}


def main() -> None:
    _require_inputs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    TMP_DIR.mkdir(parents=True)

    title_one = _render_title_clip(
        "example_1",
        "Example #1",
        "Collateral Management",
        (
            "Schedule ingestion, LLM-assisted explanation, "
            "HQLA liquidity orchestration, and governance evidence"
        ),
    )
    title_two = _render_title_clip(
        "example_2",
        "Example #2",
        "Money Market Optimization",
        (
            "PDF policy upload, structured ingestion, optimizer execution, "
            "before/after analytics, and evidence review"
        ),
    )

    _compose([title_one, COLLATERAL_VIDEO, title_two, MONEY_MARKET_VIDEO], OUTPUT)
    print(OUTPUT.relative_to(REPO_ROOT))


def _require_inputs() -> None:
    missing = [path for path in [COLLATERAL_VIDEO, MONEY_MARKET_VIDEO] if not path.exists()]
    if missing:
        names = ", ".join(str(path.relative_to(REPO_ROOT)) for path in missing)
        raise FileNotFoundError(f"Missing source video(s): {names}")


def _render_title_clip(key: str, eyebrow: str, title: str, subtitle: str) -> Path:
    frames_dir = TMP_DIR / key
    frames_dir.mkdir(parents=True)
    fonts = _fonts()
    frame_count = TITLE_SECONDS * FPS

    for index in range(frame_count):
        progress = index / max(1, frame_count - 1)
        frame = _draw_title_frame(eyebrow, title, subtitle, progress, fonts)
        frame.save(frames_dir / f"frame_{index:04d}.png")

    output = TMP_DIR / f"{key}.mp4"
    ffmpeg = _ffmpeg()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(frames_dir / "frame_%04d.png"),
            "-r",
            str(FPS),
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
    return output


def _draw_title_frame(
    eyebrow: str,
    title: str,
    subtitle: str,
    progress: float,
    fonts: dict[str, ImageFont.ImageFont],
) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), COLORS["bg"])
    draw = ImageDraw.Draw(image)

    for x in range(-220, WIDTH + 220, 82):
        draw.line((x, 0, x + 260, HEIGHT), fill="#06151D", width=1)
    for y in range(80, HEIGHT, 94):
        draw.line((0, y, WIDTH, y), fill="#071922", width=1)

    accent_x = int(120 + progress * 1020)
    draw.rounded_rectangle((80, 80, WIDTH - 80, HEIGHT - 80), radius=14, fill=COLORS["panel"])
    draw.rounded_rectangle((104, 104, WIDTH - 104, HEIGHT - 104), radius=10, outline=COLORS["line"])
    draw.line((accent_x, 104, accent_x + 170, 104), fill=COLORS["cyan"], width=4)

    draw.rounded_rectangle((128, 126, 176, 174), radius=8, fill=COLORS["cyan"])
    draw.text((143, 141), "DI", fill=COLORS["bg"], font=fonts["small_bold"])
    draw.text((196, 126), "Decision Intelligence", fill=COLORS["ink"], font=fonts["body_bold"])
    draw.text((196, 152), "Optimization demo workspace", fill=COLORS["muted"], font=fonts["small"])

    y = 312
    draw.text((150, y), eyebrow.upper(), fill=COLORS["teal"], font=fonts["eyebrow"])
    draw.text((150, y + 64), title, fill=COLORS["ink"], font=fonts["title"])
    draw.text((154, y + 146), subtitle, fill=COLORS["muted"], font=fonts["subtitle"])

    cards = [
        ("Live front-end", "Browser-recorded UI"),
        ("Document intake", "Policy and schedule evidence"),
        ("Optimizer run", "Traceable analytics output"),
    ]
    card_y = 610
    for idx, (label, note) in enumerate(cards):
        x = 150 + idx * 420
        draw.rounded_rectangle((x, card_y, x + 360, card_y + 116), radius=8, fill=COLORS["panel2"])
        draw.text((x + 22, card_y + 24), label, fill=COLORS["ink"], font=fonts["card"])
        draw.text((x + 22, card_y + 60), note, fill=COLORS["muted"], font=fonts["small"])

    bar_x, bar_y, bar_w = 150, 780, WIDTH - 300
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + 8), radius=5, fill="#223542")
    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + int(bar_w * progress), bar_y + 8),
        radius=5,
        fill=COLORS["green"],
    )

    return image


def _compose(inputs: list[Path], output: Path) -> None:
    ffmpeg = _ffmpeg()
    args = [ffmpeg, "-y"]
    for path in inputs:
        args.extend(["-i", str(path)])
    args.extend(
        [
            "-filter_complex",
            "[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0[v]",
            "-map",
            "[v]",
            "-r",
            str(FPS),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _fonts() -> dict[str, ImageFont.ImageFont]:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
    ]
    font_path = next((path for path in candidates if Path(path).exists()), None)
    if font_path is None:
        return {
            "title": ImageFont.load_default(),
            "subtitle": ImageFont.load_default(),
            "eyebrow": ImageFont.load_default(),
            "body_bold": ImageFont.load_default(),
            "card": ImageFont.load_default(),
            "small": ImageFont.load_default(),
            "small_bold": ImageFont.load_default(),
        }
    return {
        "title": ImageFont.truetype(font_path, 64),
        "subtitle": ImageFont.truetype(font_path, 26),
        "eyebrow": ImageFont.truetype(font_path, 22),
        "body_bold": ImageFont.truetype(font_path, 20),
        "card": ImageFont.truetype(font_path, 24),
        "small": ImageFont.truetype(font_path, 18),
        "small_bold": ImageFont.truetype(font_path, 17),
    }


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
    # Playwright ships its own ffmpeg (stripped build, VP8 only).
    pw_ffmpeg = Path("/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux")
    if pw_ffmpeg.exists():
        return str(pw_ffmpeg)
    binary = shutil.which("ffmpeg")
    if binary:
        return binary
    raise RuntimeError("ffmpeg not found. Run npm install in frontend/app.")


if __name__ == "__main__":
    main()
