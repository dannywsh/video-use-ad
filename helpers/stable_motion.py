"""Render stable still-image motion clips for product-video timelines."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


# 以固定 2× 画布渲染后再下采样，消除慢推镜中的整数像素台阶。
FIXED_SUPERSAMPLE = 2
# 可读匀速：约 5.5 秒滚过一屏。只按这个速度走；镜头更长就停在末帧，更短就裁窗。
DEFAULT_SCROLL_VIEWPORTS_PER_SEC = 0.18
DEFAULT_MAX_VIEWPORTS_PER_SEC = DEFAULT_SCROLL_VIEWPORTS_PER_SEC


def run(command: list[str]) -> None:
    """Run one FFmpeg/FFprobe command.

    Input: complete command argument list. Returns: None after a successful process.
    """
    subprocess.run(command, check=True)


def even(value: float) -> int:
    """Round a size down to the nearest positive even integer.

    Input: a pixel value. Returns: an H.264-compatible even pixel count.
    """
    return max(2, int(math.floor(value / 2) * 2))


def even_coord(value: float) -> int:
    """Round a crop origin down to an even non-negative integer (0 allowed)."""
    return max(0, int(math.floor(value / 2) * 2))


def image_dimensions(path: Path) -> tuple[int, int]:
    """Read the first image/video stream dimensions with FFprobe.

    Input: source media path. Returns: (width, height), or raises on invalid input.
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    try:
        width, height = (int(value) for value in result.stdout.strip().split(","))
    except ValueError as error:
        raise ValueError(f"could not resolve image dimensions for {path}") from error
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid image dimensions for {path}: {width}×{height}")
    return width, height


def parse_region(text: str | None) -> tuple[float, float] | None:
    """Parse a 0–1 vertical band `start,end` of the source image."""
    if not text:
        return None
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        raise ValueError("region must be START,END in 0–1 source-height fractions")
    start, end = float(parts[0]), float(parts[1])
    if not 0.0 <= start < end <= 1.0:
        raise ValueError("region START,END must satisfy 0 <= START < END <= 1")
    return start, end


@dataclass(frozen=True)
class ScrollWindow:
    crop_y: int
    crop_h: int
    source_w: int
    source_h: int
    cropped: bool
    viewport_heights: float
    viewports_per_sec: float
    region: tuple[float, float]
    can_scroll: bool
    scroll_s: float
    hold_s: float


def locked_scroll_pixels_per_sec(
    render_h: int,
    speed: float = DEFAULT_SCROLL_VIEWPORTS_PER_SEC,
) -> float:
    """Canvas pixels per second for every scroll clip. Height and duration do not change this."""
    if render_h <= 0 or speed <= 0:
        return 0.0
    return speed * render_h


def scroll_overlay_y(travel: int, pixels_per_sec: float) -> str:
    """Constant-speed overlay `y`. Motion stops at `-travel` so leftover time holds."""
    if travel < 1 or pixels_per_sec <= 0:
        return "0"
    return f"-min({travel}\\, {pixels_per_sec:.6f}*t)"


def _hold_times(travel: float, render_h: int, duration: float, speed: float) -> tuple[float, float, float]:
    """Return (viewports_per_sec, scroll_s, hold_s) for a constant-speed crawl."""
    if travel <= 1 or speed <= 0 or render_h <= 0:
        return 0.0, 0.0, duration
    pixels_per_sec = speed * render_h
    scroll_s = min(duration, travel / pixels_per_sec)
    hold_s = max(0.0, duration - scroll_s)
    return speed, scroll_s, hold_s


def compute_scroll_window(
    source_w: int,
    source_h: int,
    render_w: int,
    render_h: int,
    duration: float,
    *,
    max_vps: float = DEFAULT_SCROLL_VIEWPORTS_PER_SEC,
    anchor: str = "top",
    region: tuple[float, float] | None = None,
) -> ScrollWindow:
    """Choose a vertical crop that can crawl at a fixed readable speed in `duration`.

    Input: source size, 2× render canvas, shot length, optional 0–1 band and anchor.
    Returns: crop box in source pixels. Too-short bands set can_scroll False (use push).
    Speed is locked: image height and shot duration never change `max_vps`.
    """
    if source_w <= 0 or source_h <= 0 or render_w <= 0 or render_h <= 0 or duration <= 0:
        raise ValueError("sizes and duration must be positive")
    if max_vps <= 0:
        raise ValueError("max viewports per second must be positive")
    if anchor not in {"top", "center", "bottom"}:
        raise ValueError("anchor must be top, center, or bottom")

    y0, y1 = region or (0.0, 1.0)
    band_y = even_coord(source_h * y0)
    band_h = even(source_h * (y1 - y0))
    band_h = max(2, min(band_h, source_h - band_y))
    fg_w = even(render_w * 0.92)
    viewport_src = max(2, even(render_h * source_w / fg_w))
    scaled_band_h = even(band_h * fg_w / source_w)
    full_viewports = max(0.0, (scaled_band_h - render_h) / render_h)
    band_viewports = scaled_band_h / render_h if render_h else 0.0

    if scaled_band_h <= render_h:
        crop_h = min(source_h - band_y, max(band_h, viewport_src))
        return ScrollWindow(
            crop_y=band_y,
            crop_h=crop_h,
            source_w=source_w,
            source_h=source_h,
            cropped=region is not None or crop_h < source_h,
            viewport_heights=band_viewports,
            viewports_per_sec=0.0,
            region=(y0, y1),
            can_scroll=False,
            scroll_s=0.0,
            hold_s=duration,
        )

    max_travel = max_vps * duration * render_h
    full_travel = scaled_band_h - render_h
    if full_travel <= max_travel + 1:
        vps, scroll_s, hold_s = _hold_times(full_travel, render_h, duration, max_vps)
        return ScrollWindow(
            crop_y=band_y,
            crop_h=band_h,
            source_w=source_w,
            source_h=source_h,
            cropped=region is not None,
            viewport_heights=1.0 + full_viewports,
            viewports_per_sec=vps,
            region=(y0, y1),
            can_scroll=full_travel > 1,
            scroll_s=scroll_s,
            hold_s=hold_s,
        )

    target_scaled_h = even(render_h + max_travel)
    crop_h = even(target_scaled_h * source_w / fg_w)
    crop_h = max(viewport_src, min(crop_h, band_h))
    leftover = max(0, band_h - crop_h)
    if anchor == "bottom":
        crop_y = band_y + leftover
    elif anchor == "center":
        crop_y = band_y + leftover // 2
    else:
        crop_y = band_y
    crop_y = max(0, min(even_coord(crop_y), source_h - crop_h))
    crop_h = min(crop_h, source_h - crop_y)
    used_top = crop_y / source_h
    used_bot = (crop_y + crop_h) / source_h
    travel = max(0.0, even(crop_h * fg_w / source_w) - render_h)
    vps, scroll_s, hold_s = _hold_times(travel, render_h, duration, max_vps)
    return ScrollWindow(
        crop_y=crop_y,
        crop_h=crop_h,
        source_w=source_w,
        source_h=source_h,
        cropped=True,
        viewport_heights=1.0 + full_viewports,
        viewports_per_sec=vps,
        region=(used_top, used_bot),
        can_scroll=travel > 1,
        scroll_s=scroll_s,
        hold_s=hold_s,
    )


def make_blurred_background(source: Path, output: Path, width: int, height: int) -> None:
    """Create one static blurred background image.

    Input: source image, destination PNG and target canvas size. Returns: None after writing PNG.
    """
    filters = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},boxblur=20:5,eq=brightness=-0.16:saturation=0.85"
    )
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-vf", filters, "-frames:v", "1", str(output)])


def crop_source(source: Path, output: Path, crop_y: int, crop_h: int, source_w: int) -> None:
    """Write one vertical crop of the source image."""
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vf", f"crop={source_w}:{crop_h}:0:{crop_y}", "-frames:v", "1", str(output),
    ])


def render_push(source: Path, output: Path, duration: float, fps: int, width: int, height: int, crf: int) -> None:
    """Render a centre push-in without per-frame foreground scaling or positioning.

    Input: source image and output video parameters. Returns: None after writing an H.264 MP4 at fixed 2× supersampling.
    """
    render_width, render_height = even(width * FIXED_SUPERSAMPLE), even(height * FIXED_SUPERSAMPLE)
    canvas_width, canvas_height = even(render_width * 1.2), even(render_height * 1.2)
    frames = max(2, round(duration * fps))
    with tempfile.TemporaryDirectory(prefix="stable-motion-") as temp_dir:
        temp = Path(temp_dir)
        base = temp / "base.png"
        base_filter = (
            f"[0:v]split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={canvas_width}:{canvas_height}:force_original_aspect_ratio=increase,"
            f"crop={canvas_width}:{canvas_height},boxblur=20:5,eq=brightness=-0.16:saturation=0.85[bg];"
            f"[fgsrc]format=rgba,scale={even(canvas_width * 0.88)}:{even(canvas_height * 0.88)}:"
            f"force_original_aspect_ratio=decrease,pad={canvas_width}:{canvas_height}:(ow-iw)/2:(oh-ih)/2:color=black@0[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=rgba"
        )
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-filter_complex", base_filter, "-frames:v", "1", str(base)])
        zoom_step = 0.045 / max(1, frames - 1)
        zoom_filter = (
            f"zoompan=z='min(1+{zoom_step:.10f}*on,1.045)':"
            "x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:"
            f"s={render_width}x{render_height}:fps={fps},scale={width}:{height}:flags=lanczos,format=yuv420p"
        )
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-i", str(base),
            "-t", f"{duration:.6f}", "-vf", zoom_filter, "-an", "-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-movflags", "+faststart", str(output),
        ])


def render_scroll(
    source: Path,
    output: Path,
    duration: float,
    fps: int,
    width: int,
    height: int,
    crf: int,
    *,
    max_vps: float = DEFAULT_SCROLL_VIEWPORTS_PER_SEC,
    anchor: str = "top",
    region: tuple[float, float] | None = None,
) -> ScrollWindow:
    """Render a top-to-bottom detail-image scroll at a fixed readable speed.

    Input: source image, output video parameters, crawl speed, optional 0–1 band.
    Returns: the crop window actually used. Falls back to push when the band is not tall.
    """
    source_width, source_height = image_dimensions(source)
    render_width, render_height = even(width * FIXED_SUPERSAMPLE), even(height * FIXED_SUPERSAMPLE)
    window = compute_scroll_window(
        source_width, source_height, render_width, render_height, duration,
        max_vps=max_vps, anchor=anchor, region=region,
    )
    with tempfile.TemporaryDirectory(prefix="stable-motion-") as temp_dir:
        cropped = Path(temp_dir) / "crop.png"
        need_crop = window.crop_y > 0 or window.crop_h < source_height
        plate = cropped if need_crop else source
        if need_crop:
            crop_source(source, cropped, window.crop_y, window.crop_h, source_width)
        if not window.can_scroll:
            render_push(plate, output, duration, fps, width, height, crf)
            return window
        crop_w, crop_h = image_dimensions(plate)
        foreground_width = even(render_width * 0.92)
        foreground_height = even(crop_h * foreground_width / crop_w)
        travel = max(1, foreground_height - render_height)
        pixels_per_sec = locked_scroll_pixels_per_sec(render_height, max_vps)
        background = Path(temp_dir) / "background.png"
        make_blurred_background(plate, background, render_width, render_height)
        filter_complex = (
            f"[1:v]format=rgba,scale={foreground_width}:{foreground_height}[fg];"
            f"[0:v][fg]overlay=x=(W-w)/2:y='{scroll_overlay_y(travel, pixels_per_sec)}':eval=frame,"
            f"scale={width}:{height}:flags=lanczos,format=yuv420p"
        )
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-i", str(background),
            "-loop", "1", "-framerate", str(fps), "-i", str(plate), "-t", f"{duration:.6f}",
            "-filter_complex", filter_complex, "-r", str(fps), "-an", "-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-movflags", "+faststart", str(output),
        ])
    return window


def main() -> None:
    """Parse CLI options and render one motion-stable product still clip.

    Input: command-line image/video settings. Returns: None after validating and rendering output.
    """
    parser = argparse.ArgumentParser(description="Render a motion-stable product still with FFmpeg.")
    parser.add_argument("source", type=Path, help="Input product/detail image")
    parser.add_argument("-o", "--output", type=Path, help="Output MP4 (omit with --probe)")
    parser.add_argument("--mode", choices=("push", "scroll"), default="push", help="Centre push-in or vertical detail scroll")
    parser.add_argument("--duration", type=float, required=True, help="Clip duration in seconds")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--crf", type=int, default=17)
    parser.add_argument(
        "--max-viewports-per-sec",
        type=float,
        default=DEFAULT_SCROLL_VIEWPORTS_PER_SEC,
        help="Locked crawl speed for every still (default 0.18 screens/s). "
             "Do not raise this for taller images; duration only changes how long we crawl "
             "or how much we crop. Leftover shot time holds the last frame.",
    )
    parser.add_argument("--anchor", choices=("top", "center", "bottom"), default="top")
    parser.add_argument("--region", default=None, help="Vertical band START,END as 0–1 fractions of the source (e.g. 0.12,0.45)")
    parser.add_argument("--probe", action="store_true", help="Print the scroll crop plan as JSON and exit")
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error(f"source does not exist: {args.source}")
    if args.duration <= 0 or args.fps <= 0 or args.width <= 0 or args.height <= 0:
        parser.error("duration, fps, width and height must be positive")
    region = parse_region(args.region) if args.region else None
    if args.probe or args.mode == "scroll":
        src_w, src_h = image_dimensions(args.source)
        render_w, render_h = even(args.width * FIXED_SUPERSAMPLE), even(args.height * FIXED_SUPERSAMPLE)
        window = compute_scroll_window(
            src_w, src_h, render_w, render_h, args.duration,
            max_vps=args.max_viewports_per_sec, anchor=args.anchor, region=region,
        )
        if args.probe:
            payload = asdict(window)
            payload["region"] = list(window.region)
            payload["locked_vps"] = DEFAULT_SCROLL_VIEWPORTS_PER_SEC
            print(json.dumps(payload, ensure_ascii=False))
            return
    if args.output is None:
        parser.error("--output is required unless --probe")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "push":
        render_push(args.source, args.output, args.duration, args.fps, args.width, args.height, args.crf)
        print(f"stable motion → {args.output} (push, {args.duration:.2f}s)")
        return
    window = render_scroll(
        args.source, args.output, args.duration, args.fps, args.width, args.height, args.crf,
        max_vps=args.max_viewports_per_sec, anchor=args.anchor, region=region,
    )
    print(
        f"stable motion → {args.output} (scroll, {args.duration:.2f}s, "
        f"crop y={window.crop_y} h={window.crop_h}, "
        f"{window.viewports_per_sec:.2f} vp/s, hold {window.hold_s:.2f}s)"
    )


if __name__ == "__main__":
    main()
