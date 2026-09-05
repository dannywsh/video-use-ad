"""Join already-extracted clips with optional visual transitions.

Hard cuts stay lossless (`-c copy` concat) when every join is a cut.
Any `xfade` join re-encodes the extracted 1080p segments — not the original
sources — so overlays still land in a later pass (Hard Rule 2).

Usage:
    python helpers/transitions.py a.mp4 b.mp4 c.mp4 -o visual.mp4
    python helpers/transitions.py a.mp4 b.mp4 -o out.mp4 --type fade --duration 0.4
    python helpers/transitions.py a.mp4 b.mp4 c.mp4 -o out.mp4 --joins fade:0.4,cut,fade:0.3
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DURATION = 0.4

# ffmpeg xfade names we document for agents. Unknown names are rejected so a
# typo cannot fail at the end of a long extract.
XFADE_TYPES = frozenset({
    "fade",
    "fadeblack",
    "fadewhite",
    "dissolve",
    "wipeleft",
    "wiperight",
    "wipeup",
    "wipedown",
    "slideleft",
    "slideright",
    "slideup",
    "slidedown",
    "smoothleft",
    "smoothright",
    "smoothup",
    "smoothdown",
    "circleopen",
    "circleclose",
    "zoomin",
    "pixelize",
    "hblur",
    "radial",
})


@dataclass(frozen=True)
class Transition:
    type: str
    duration: float


def parse_transition(value: object, *, default_duration: float = DEFAULT_DURATION) -> Transition | None:
    """Normalize an EDL/CLI transition spec. None / cut / duration<=0 → hard cut."""
    if value is None or value is False:
        return None
    if value is True:
        return Transition("fade", default_duration)
    if isinstance(value, str):
        name = value.strip().lower()
        if name in {"", "cut", "none", "hard"}:
            return None
        if name not in XFADE_TYPES:
            raise ValueError(f"unknown transition type: {value}")
        return Transition(name, default_duration)
    if isinstance(value, dict):
        raw_type = value.get("type", "fade")
        name = str(raw_type).strip().lower()
        if name in {"cut", "none", "hard"}:
            return None
        try:
            duration = float(value.get("duration", default_duration))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid transition duration: {value.get('duration')}") from exc
        if duration <= 0:
            return None
        if name not in XFADE_TYPES:
            raise ValueError(f"unknown transition type: {raw_type}")
        return Transition(name, duration)
    raise ValueError(f"invalid transition spec: {value!r}")


def parse_joins_arg(text: str, n_clips: int) -> list[Transition | None]:
    """Parse `--joins fade:0.4,cut,fade:0.3` into per-clip inbound transitions.

    Index 0 is always a hard cut (no previous clip). Remaining tokens map to
    clips 1..n-1. A single token applies to every inbound join.
    """
    if n_clips < 1:
        return []
    joins: list[Transition | None] = [None]
    if n_clips == 1:
        return joins
    tokens = [part.strip() for part in text.split(",") if part.strip()]
    if len(tokens) == 1:
        tokens = tokens * (n_clips - 1)
    if len(tokens) != n_clips - 1:
        raise ValueError(
            f"--joins needs 1 token or {n_clips - 1} tokens (one per inbound join), got {len(tokens)}"
        )
    for token in tokens:
        if ":" in token:
            name, dur_text = token.split(":", 1)
            joins.append(parse_transition({"type": name, "duration": float(dur_text)}))
        else:
            joins.append(parse_transition(token))
    return joins


def resolve_join_transition(edl: dict, index: int) -> Transition | None:
    """Transition INTO ranges[index]. The first range never has an inbound join."""
    if index <= 0:
        return None
    ranges = edl.get("ranges") or []
    if index >= len(ranges):
        return None
    rng = ranges[index]
    if "transition" in rng:
        return parse_transition(rng["transition"])
    return parse_transition(edl.get("default_transition") or edl.get("transition"))


def edl_join_transitions(edl: dict) -> list[Transition | None]:
    ranges = edl.get("ranges") or []
    return [resolve_join_transition(edl, i) for i in range(len(ranges))]


def output_timeline_offsets(
    ranges: list[dict],
    joins: list[Transition | None],
) -> list[float]:
    """Output-timeline start of each range after xfade overlap is subtracted."""
    offsets: list[float] = []
    cursor = 0.0
    for i, rng in enumerate(ranges):
        duration = float(rng["end"]) - float(rng["start"])
        join = joins[i] if i < len(joins) else None
        if join is not None:
            cursor -= join.duration
        offsets.append(cursor)
        cursor += duration
    return offsets


def clamp_join(join: Transition | None, prev_duration: float, this_duration: float) -> Transition | None:
    """Keep xfade shorter than both clips so each still has exclusive frames."""
    if join is None:
        return None
    cap = min(prev_duration, this_duration) * 0.45
    if cap < 0.05:
        return None
    if join.duration <= cap:
        return join
    return Transition(join.type, round(cap, 3))


def clamp_joins(durations: list[float], joins: list[Transition | None]) -> list[Transition | None]:
    out: list[Transition | None] = list(joins)
    if len(out) < len(durations):
        out.extend([None] * (len(durations) - len(out)))
    out[0] = None
    for i in range(1, len(durations)):
        out[i] = clamp_join(out[i], durations[i - 1], durations[i])
    return out[: len(durations)]


def has_visual_transition(joins: list[Transition | None]) -> bool:
    return any(join is not None for join in joins)


def outbound_handle_seconds(joins: list[Transition | None], n_clips: int) -> list[float]:
    """Extra tail on clip i so an outbound xfade does not steal programme time.

    Clip i is extended by the duration of the join INTO clip i+1. After xfade
    the dissolve starts at the original cut point, so a TTS/SRT timeline
    authored against the hard-cut duration still matches the picture beats.
    """
    extras = [0.0] * n_clips
    for i in range(1, n_clips):
        join = joins[i] if i < len(joins) else None
        if join is not None:
            extras[i - 1] += join.duration
    return extras


def extend_clip_tail(source: Path, extra: float, dest: Path) -> None:
    """Pad a clip by cloning its last frame (and audio, if any) for `extra` seconds."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if extra <= 0:
        raise ValueError("extra tail must be positive")
    extra_text = f"{extra:.6f}"
    if probe_has_audio(source):
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(source),
            "-filter_complex",
            f"[0:v]tpad=stop_mode=clone:stop_duration={extra_text}[v];"
            f"[0:a]apad=pad_dur={extra_text}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(dest),
        ]
    else:
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(source),
            "-vf", f"tpad=stop_mode=clone:stop_duration={extra_text}",
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(dest),
        ]
    subprocess.run(command, check=True)


def prepare_overlap_handles(
    paths: list[Path],
    joins: list[Transition | None],
    work_dir: Path,
) -> list[Path]:
    """Return clip paths with outbound xfade tails added. Unchanged clips are reused."""
    extras = outbound_handle_seconds(joins, len(paths))
    prepared: list[Path] = []
    work_dir.mkdir(parents=True, exist_ok=True)
    for i, path in enumerate(paths):
        extra = extras[i]
        if extra <= 0:
            prepared.append(path)
            continue
        dest = work_dir / f"handle_{i:02d}{path.suffix}"
        print(f"  handle [{i:02d}] +{extra:.2f}s tail → {dest.name}")
        extend_clip_tail(path, extra, dest)
        prepared.append(dest)
    return prepared


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def probe_has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return any(line.strip() for line in out.stdout.splitlines())


def probe_size(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    width, height = (int(part) for part in out.stdout.strip().split(",")[:2])
    return width, height


def build_xfade_filter(
    durations: list[float],
    joins: list[Transition | None],
    has_audio: list[bool],
    width: int,
    height: int,
    fps: str,
    include_audio: bool,
) -> tuple[str, str, str | None]:
    """Build a filter_complex that xfade/concat-joins N already-extracted clips.

    Returns (filter_complex, video_label, audio_label_or_None).
    """
    if len(durations) < 1:
        raise ValueError("need at least one clip")
    joins = clamp_joins(durations, joins)
    parts: list[str] = []
    for i, duration in enumerate(durations):
        parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"setsar=1,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"fps={fps},format=yuv420p,setpts=PTS-STARTPTS[v{i}]"
        )
        if include_audio:
            if has_audio[i]:
                parts.append(
                    f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                    f"aresample=48000,asetpts=PTS-STARTPTS[a{i}]"
                )
            else:
                parts.append(
                    f"anullsrc=channel_layout=stereo:sample_rate=48000:d={duration:.6f}[a{i}]"
                )

    v_cur = "v0"
    a_cur = "a0"
    acc = durations[0]
    for i in range(1, len(durations)):
        join = joins[i]
        if join is not None:
            offset = acc - join.duration
            if offset < 0:
                raise ValueError(
                    f"transition into clip {i} ({join.duration}s) is longer than "
                    f"the timeline so far ({acc}s)"
                )
            parts.append(
                f"[{v_cur}][v{i}]xfade=transition={join.type}:duration={join.duration:.6f}"
                f":offset={offset:.6f}[vx{i}]"
            )
            if include_audio:
                parts.append(
                    f"[{a_cur}][a{i}]acrossfade=d={join.duration:.6f}:c1=tri:c2=tri[ax{i}]"
                )
            acc = acc + durations[i] - join.duration
        else:
            parts.append(f"[{v_cur}][v{i}]concat=n=2:v=1:a=0[vx{i}]")
            if include_audio:
                parts.append(f"[{a_cur}][a{i}]concat=n=2:v=0:a=1[ax{i}]")
            acc += durations[i]
        v_cur = f"vx{i}"
        a_cur = f"ax{i}"
    return ";".join(parts), f"[{v_cur}]", (f"[{a_cur}]" if include_audio else None)


def concat_with_transitions(
    paths: list[Path],
    joins: list[Transition | None],
    out_path: Path,
    *,
    width: int | None = None,
    height: int | None = None,
    fps: str = "30",
    include_audio: bool = True,
    preview: bool = False,
    draft: bool = False,
    keep_duration: bool = True,
) -> None:
    """Join extracted clips. Re-encodes when any join is an xfade."""
    if not paths:
        raise ValueError("no clips to join")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joins = clamp_joins([probe_duration(path) for path in paths], joins)
    handle_dir = None
    if keep_duration and has_visual_transition(joins):
        handle_dir = out_path.parent / f"_xfade_handles_{out_path.stem}"
        print("keep-duration: add outbound overlap handles so TTS/SRT stay on the original beats")
        paths = prepare_overlap_handles(paths, joins, handle_dir)
    durations = [probe_duration(path) for path in paths]
    audio_flags = [probe_has_audio(path) for path in paths]
    if width is None or height is None:
        width, height = probe_size(paths[0])

    if not has_visual_transition(joins) and len(paths) >= 1:
        # Caller should use lossless concat for the all-cuts case. Keep a
        # filtergraph path only so the CLI can still join mismatched sizes.
        pass

    filter_complex, v_label, a_label = build_xfade_filter(
        durations, joins, audio_flags, width, height, fps,
        include_audio=include_audio,
    )
    if draft:
        preset, crf = "ultrafast", "28"
    elif preview:
        preset, crf = "medium", "22"
    else:
        preset, crf = "fast", "20"

    inputs: list[str] = []
    for path in paths:
        inputs += ["-i", str(path)]
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", v_label,
    ]
    if a_label is not None:
        cmd += ["-map", a_label]
    else:
        cmd += ["-an"]
    cmd += [
        "-c:v", "libx264", "-preset", preset, "-crf", crf,
        "-pix_fmt", "yuv420p",
    ]
    if a_label is not None:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    cmd += ["-movflags", "+faststart", str(out_path)]

    print(f"xfade-join {len(paths)} clip(s) → {out_path.name}")
    for i, join in enumerate(joins):
        if join is None:
            kind = "cut" if i > 0 else "start"
            print(f"  [{i:02d}] {paths[i].name}  {durations[i]:.2f}s  {kind}")
        else:
            print(f"  [{i:02d}] {paths[i].name}  {durations[i]:.2f}s  {join.type} {join.duration:.2f}s")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def lossless_concat(paths: list[Path], out_path: Path, list_path: Path) -> None:
    """Hard-cut join with the concat demuxer. No re-encode."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_path.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            "-movflags", "+faststart",
            str(out_path),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    list_path.unlink(missing_ok=True)


def join_clips(
    paths: list[Path],
    joins: list[Transition | None],
    out_path: Path,
    *,
    concat_list: Path | None = None,
    width: int | None = None,
    height: int | None = None,
    fps: str = "30",
    include_audio: bool = True,
    preview: bool = False,
    draft: bool = False,
    keep_duration: bool = True,
) -> None:
    """Lossless concat when every join is a cut; otherwise xfade-join."""
    if not has_visual_transition(joins):
        if concat_list is None:
            concat_list = out_path.parent / "_concat.txt"
        print(f"concat → {out_path.name}")
        lossless_concat(paths, out_path, concat_list)
        return
    concat_with_transitions(
        paths, joins, out_path,
        width=width, height=height, fps=fps,
        include_audio=include_audio, preview=preview, draft=draft,
        keep_duration=keep_duration,
    )


def _probe_fps(path: Path) -> str:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=avg_frame_rate,r_frame_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    streams = json.loads(out.stdout).get("streams") or []
    if not streams:
        return "30"
    for field in ("avg_frame_rate", "r_frame_rate"):
        value = streams[0].get(field)
        if value and value != "0/0":
            return str(value)
    return "30"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Join clips with xfade transitions (or lossless concat for hard cuts)."
    )
    ap.add_argument("clips", nargs="+", type=Path, help="Clips in timeline order")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output MP4")
    ap.add_argument(
        "--type",
        default="fade",
        help="Transition applied to every inbound join (default: fade). Use cut for hard cuts.",
    )
    ap.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION,
        help=f"Transition duration in seconds (default: {DEFAULT_DURATION})",
    )
    ap.add_argument(
        "--joins",
        type=str,
        default=None,
        help="Per-inbound-join list, e.g. fade:0.4,cut,fadeblack:0.5",
    )
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--fps", type=str, default=None)
    ap.add_argument(
        "--an",
        action="store_true",
        help="Drop audio (use when a later mix pass replaces the soundtrack).",
    )
    ap.add_argument(
        "--keep-duration",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pad each outgoing clip by the xfade duration so the programme length "
             "and picture beats stay aligned with an already-authored TTS/SRT timeline. "
             "Use --no-keep-duration to let overlaps shorten the output.",
    )
    args = ap.parse_args()

    clips = [path.resolve() for path in args.clips]
    missing = [str(path) for path in clips if not path.exists()]
    if missing:
        sys.exit("clip not found: " + ", ".join(missing))
    if args.joins:
        joins = parse_joins_arg(args.joins, len(clips))
    else:
        inbound = parse_transition({"type": args.type, "duration": args.duration})
        joins = [None] + [inbound] * (len(clips) - 1)

    fps = args.fps or _probe_fps(clips[0])
    join_clips(
        clips, joins, args.output.resolve(),
        width=args.width, height=args.height, fps=fps,
        include_audio=not args.an,
        keep_duration=args.keep_duration,
    )


if __name__ == "__main__":
    main()
