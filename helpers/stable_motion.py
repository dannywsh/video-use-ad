"""Render stable still-image motion clips for product-video timelines."""

from __future__ import annotations

import argparse
import math
import subprocess
import tempfile
from pathlib import Path


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


def make_blurred_background(source: Path, output: Path, width: int, height: int) -> None:
    """Create one static blurred background image.

    Input: source image, destination PNG and target canvas size. Returns: None after writing PNG.
    """
    filters = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},boxblur=20:5,eq=brightness=-0.16:saturation=0.85"
    )
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-vf", filters, "-frames:v", "1", str(output)])


def render_push(source: Path, output: Path, duration: float, fps: int, width: int, height: int, crf: int, supersample: int) -> None:
    """Render a centre push-in without per-frame foreground scaling or positioning.

    Input: source image and video parameters. Returns: None after writing an H.264 MP4.
    """
    render_width, render_height = even(width * supersample), even(height * supersample)
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


def render_scroll(source: Path, output: Path, duration: float, fps: int, width: int, height: int, crf: int, supersample: int) -> None:
    """Render a top-to-bottom detail-image scroll using one static foreground scale.

    Input: source image and video parameters. Returns: None after writing an H.264 MP4.
    """
    source_width, source_height = image_dimensions(source)
    render_width, render_height = even(width * supersample), even(height * supersample)
    foreground_width = even(render_width * 0.92)
    foreground_height = even(source_height * foreground_width / source_width)
    if foreground_height <= render_height:
        render_push(source, output, duration, fps, width, height, crf, supersample)
        return
    frames = max(2, round(duration * fps))
    travel = foreground_height - render_height
    with tempfile.TemporaryDirectory(prefix="stable-motion-") as temp_dir:
        background = Path(temp_dir) / "background.png"
        make_blurred_background(source, background, render_width, render_height)
        filter_complex = (
            f"[1:v]format=rgba,scale={foreground_width}:{foreground_height}[fg];"
            f"[0:v][fg]overlay=x=(W-w)/2:y='-{travel}*n/{frames - 1}':eval=frame,"
            f"scale={width}:{height}:flags=lanczos,format=yuv420p"
        )
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-i", str(background),
            "-loop", "1", "-framerate", str(fps), "-i", str(source), "-t", f"{duration:.6f}",
            "-filter_complex", filter_complex, "-r", str(fps), "-an", "-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-movflags", "+faststart", str(output),
        ])


def main() -> None:
    """Parse CLI options and render one motion-stable product still clip.

    Input: command-line image/video settings. Returns: None after validating and rendering output.
    """
    parser = argparse.ArgumentParser(description="Render a motion-stable product still with FFmpeg.")
    parser.add_argument("source", type=Path, help="Input product/detail image")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output MP4")
    parser.add_argument("--mode", choices=("push", "scroll"), default="push", help="Centre push-in or vertical detail scroll")
    parser.add_argument("--duration", type=float, required=True, help="Clip duration in seconds")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--crf", type=int, default=17)
    parser.add_argument("--supersample", type=int, default=2, help="Render scale before Lanczos downsampling (default: 2)")
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error(f"source does not exist: {args.source}")
    if args.duration <= 0 or args.fps <= 0 or args.width <= 0 or args.height <= 0 or args.supersample < 1:
        parser.error("duration, fps, width, height and supersample must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    renderer = render_push if args.mode == "push" else render_scroll
    renderer(args.source, args.output, args.duration, args.fps, args.width, args.height, args.crf, args.supersample)
    print(f"stable motion → {args.output} ({args.mode}, {args.duration:.2f}s)")


if __name__ == "__main__":
    main()
