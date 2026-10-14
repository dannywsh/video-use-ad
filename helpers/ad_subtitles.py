"""Stable ACG-ad subtitle style and burn-in. One line, even outline, unstretched glyphs."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
import uuid

try:
    from .verify_tts_subtitles import assert_single_line_cues
except ImportError:
    from verify_tts_subtitles import assert_single_line_cues


# Design tokens are 1080p pixels. Helpers scale them to the file being burned.
AD_DESIGN_HEIGHT = 1080
AD_FONT_NAME = "Hiragino Sans GB"
AD_FONT_SIZE = 72
AD_BOLD = 1
AD_SPACING = 1
AD_OUTLINE = 3
AD_SHADOW = 0
AD_MARGIN_V = 8
AD_MARGIN_X = 64
AD_WRAP_STYLE = 2
# Measured against a rendered 1080p master (Hiragino Sans GB, FontSize 72,
# Spacing 1): one CJK glyph inks about 59 px and a clause space about 21 px, so
# 18 glyphs span ~55% of the frame width and 24 span ~74%. 24 read as a wall of
# text and left no headroom for the visible spaces clause marks now produce.
AD_MAX_CHARS = 18
AD_DEFAULT_PRIMARY = "&H00FFFFFF"
AD_OUTLINE_COLOUR = "&H00201828"


def _scale(value: float, factor: float, minimum: int = 0) -> int:
    return max(minimum, int(round(value * factor)))


# Reads encoded width/height and display size after sample-aspect-ratio.
# Input: video path. Returns: (pixel_width, pixel_height, display_width, display_height).
def probe_video_size(video: Path) -> tuple[int, int, int, int]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,sample_aspect_ratio",
        "-of",
        "json",
        str(video),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {video}: {result.stderr[-800:]}")
    stream = json.loads(result.stdout)["streams"][0]
    width = int(stream["width"])
    height = int(stream["height"])
    sar = stream.get("sample_aspect_ratio") or "1:1"
    if sar in {"", "0:1", "N/A"}:
        sar = "1:1"
    num_s, den_s = sar.split(":")
    num, den = int(num_s), int(den_s)
    if num <= 0 or den <= 0:
        num, den = 1, 1
    display_width = int(round(width * num / den))
    display_height = height
    return width, height, display_width, display_height


# Builds libass force_style in the video's own pixel canvas.
# Input: display width/height, ASS primary colour and explicit style profile. Returns: force_style string.
def ad_force_style(
    play_res_x: int,
    play_res_y: int,
    primary_colour: str = AD_DEFAULT_PRIMARY,
    profile: str = "product",
) -> str:
    colour = primary_colour.strip()
    if not colour.startswith("&H"):
        raise ValueError("primary colour must be an ASS &HAABBGGRR value")
    if play_res_x < 2 or play_res_y < 2:
        raise ValueError("video resolution is too small for subtitle burn-in")
    if profile not in {"product", "lottery-portrait"}:
        raise ValueError("unknown subtitle profile")
    if profile == "lottery-portrait":
        if play_res_x * 16 != play_res_y * 9:
            raise ValueError("lottery-portrait captions require a 9:16 canvas")
        factor = play_res_x / 1080
        font_size, margin_x, margin_v = 64, 72, 180
    else:
        factor = play_res_y / AD_DESIGN_HEIGHT
        font_size, margin_x, margin_v = AD_FONT_SIZE, AD_MARGIN_X, AD_MARGIN_V
    return (
        f"PlayResX={play_res_x},"
        f"PlayResY={play_res_y},"
        f"FontName={AD_FONT_NAME},"
        f"FontSize={_scale(font_size, factor, 1)},"
        f"Bold={AD_BOLD},"
        f"Spacing={_scale(AD_SPACING, factor)},"
        f"PrimaryColour={colour},"
        f"OutlineColour={AD_OUTLINE_COLOUR},"
        f"BackColour={AD_OUTLINE_COLOUR},"
        f"BorderStyle=1,"
        f"Outline={_scale(AD_OUTLINE, factor, 1)},"
        f"Shadow={AD_SHADOW},"
        f"Alignment=2,"
        f"MarginL={_scale(margin_x, factor)},"
        f"MarginR={_scale(margin_x, factor)},"
        f"MarginV={_scale(margin_v, factor)},"
        f"WrapStyle={AD_WRAP_STYLE}"
    )


# Burns captions onto mixed video with PlayResX/Y matching that file.
# Input: mixed video, SRT, output path, ASS colour and explicit profile. Returns: None after writing MP4.
def burn_ad_subtitles(
    video: Path,
    srt: Path,
    output: Path,
    primary_colour: str = AD_DEFAULT_PRIMARY,
    profile: str = "product",
) -> None:
    if not video.exists():
        raise FileNotFoundError(video)
    if not srt.exists():
        raise FileNotFoundError(srt)
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height, display_width, display_height = probe_video_size(video)
    style = ad_force_style(display_width, display_height, primary_colour, profile).replace("'", r"\'")
    if profile == "lottery-portrait":
        assert_single_line_cues(srt.read_text(encoding="utf-8"), 16)
    temporary = output.with_name(f".{output.stem}-{uuid.uuid4().hex}.partial.mp4")
    subs = str(srt.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    vf = (
        "setsar=1,"
        f"scale={display_width}:{display_height}:flags=lanczos,"
        f"subtitles='{subs}':original_size={display_width}x{display_height}:force_style='{style}'"
    )
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-i",
        str(video),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(temporary),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"subtitle burn-in failed: {result.stderr[-1200:]}")
        if probe_video_size(temporary)[2:] != (display_width, display_height):
            raise RuntimeError("subtitle burn-in changed the display resolution")
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(temporary), "-f", "null", "-"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(
        f"subtitle canvas {display_width}x{display_height} "
        f"(coded {width}x{height}) force_style={ad_force_style(display_width, display_height, primary_colour, profile)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Burn ACG-ad subtitles with PlayResX/Y locked to the video size."
    )
    parser.add_argument("video", type=Path, help="Mixed visual+audio file before captions")
    parser.add_argument("srt", type=Path, help="Verified master.srt")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Final MP4 path")
    parser.add_argument(
        "--profile", choices=["product", "lottery-portrait"], default="product",
        help="Explicit portrait lottery style: 64px font, 72px side and 180px bottom margins at 1080×1920",
    )
    parser.add_argument(
        "--primary-colour",
        default=AD_DEFAULT_PRIMARY,
        help="ASS PrimaryColour, default white &H00FFFFFF",
    )
    args = parser.parse_args()
    burn_ad_subtitles(args.video, args.srt, args.output, args.primary_colour, args.profile)
    print(f"burned subtitles → {args.output}")


if __name__ == "__main__":
    main()
