"""Mix ACG product-ad narration and BGM to the required separate loudness targets."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path


VOICE_TARGET_I = -13.0
VOICE_TARGET_TP = -1.5
BGM_TARGET_I = -27.0
BGM_TARGET_TP = -3.0


# Runs one loudnorm measurement pass and returns the values required by pass two.
# Input: audio path and target loudness settings. Returns: parsed FFmpeg measurement data.
def measure_loudness(audio_path: Path, target_i: float, target_tp: float) -> dict[str, str]:
    command = [
        "ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(audio_path),
        "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA=7:print_format=json",
        "-vn", "-f", "null", "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    start, end = result.stderr.rfind("{"), result.stderr.rfind("}")
    if result.returncode != 0 or start < 0 or end <= start:
        raise RuntimeError(f"loudnorm measurement failed for {audio_path}: {result.stderr[-800:]}")
    data = json.loads(result.stderr[start : end + 1])
    required = {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"}
    if not required.issubset(data):
        raise RuntimeError(f"loudnorm returned incomplete measurements for {audio_path}")
    return data


# Applies exact two-pass loudness normalization to one audio stream.
# Input: source path, destination WAV and integrated/peak targets. Returns: None after writing WAV.
def normalize_audio(source: Path, output: Path, target_i: float, target_tp: float) -> None:
    measurement = measure_loudness(source, target_i, target_tp)
    filter_string = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA=7"
        f":measured_I={measurement['input_i']}"
        f":measured_TP={measurement['input_tp']}"
        f":measured_LRA={measurement['input_lra']}"
        f":measured_thresh={measurement['input_thresh']}"
        f":offset={measurement['target_offset']}:linear=true"
    )
    command = [
        "ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(source),
        "-af", filter_string, "-ar", "48000", "-c:a", "pcm_s16le", str(output),
    ]
    subprocess.run(command, check=True)


# Reads the selected media stream duration, falling back to its container when unavailable.
# Input: media path and FFprobe stream selector. Returns: finite positive seconds or raises ValueError.
def media_duration_seconds(media_path: Path, stream_selector: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", stream_selector,
            "-show_entries", "stream=duration:format=duration", "-of", "json", str(media_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise ValueError(f"input has no {stream_selector} stream: {media_path}")
    for value in (streams[0].get("duration"), data.get("format", {}).get("duration")):
        try:
            duration = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(duration) and duration > 0:
            return duration
    raise ValueError(f"input has no finite positive duration: {media_path}")


# Reads the visual programme length rather than the length of a potentially longer old audio track.
# Input: video path. Returns: finite positive video-stream duration in seconds.
def video_duration_seconds(video_path: Path) -> float:
    return media_duration_seconds(video_path, "v:0")


# Rejects a mix that would cut the final narration, allowing only one sample of probe rounding.
# Input: narration path and programme duration in seconds. Returns: None or raises ValueError.
def validate_narration_duration(voice: Path, duration: float) -> None:
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("visual programme duration must be finite and positive")
    voice_duration = media_duration_seconds(voice, "a:0")
    if voice_duration > duration + 1 / 48000:
        raise ValueError(
            f"narration ({voice_duration:.6f}s) exceeds visual programme ({duration:.6f}s); "
            "refusing to truncate narration. Use --keep-duration for visual transitions, "
            "or rebuild the picture, narration and subtitles together to fit the intended duration."
        )


# Creates a duration-matched BGM WAV before normalization.
# Input: source BGM, programme duration and output path. Returns: None after writing WAV.
def loop_and_trim_bgm(source: Path, duration: float, output: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-stream_loop", "-1",
            "-i", str(source), "-t", f"{duration:.3f}", "-c:a", "pcm_s16le", str(output),
        ],
        check=True,
    )


# Mixes normalized narration and BGM with fixed gain and only prescribed fades.
# Input: visual video, normalized voice/BGM WAVs, duration and output video. Returns: None.
def mix_tracks(video: Path, voice: Path, bgm: Path, duration: float, output: Path) -> None:
    validate_narration_duration(voice, duration)
    bgm_fade_start = max(0.0, duration - 1.1)
    filter_complex = (
        "[1:a]aformat=channel_layouts=stereo,afade=t=in:st=0:d=0.05[voice];"
        f"[2:a]aformat=channel_layouts=stereo,afade=t=in:st=0:d=0.5,afade=t=out:st={bgm_fade_start:.3f}:d=1.1[bgm];"
        "[voice][bgm]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
        "alimiter=limit=0.95:latency=true[a]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(video),
            "-i", str(voice), "-i", str(bgm), "-filter_complex", filter_complex,
            "-map", "0:v:0", "-map", "[a]", "-t", f"{duration:.6f}",
            "-c:v", "copy", "-c:a", "aac", "-ac", "2", "-b:a", "192k", "-movflags", "+faststart",
            str(output),
        ],
        check=True,
    )


# Checks the CLI inputs before normalization, then produces a narration-preserving promo mix.
# Input: process command-line arguments. Returns: None; invalid timing exits before writing output.
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mix ACG-ad narration at -13 LUFS with BGM at -27 LUFS."
    )
    parser.add_argument("video", type=Path, help="Visual programme before subtitle burn-in")
    parser.add_argument("voiceover", type=Path, help="Final cloned narration WAV")
    parser.add_argument("bgm", type=Path, help="BGM source, looped to programme length")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Mixed video output path")
    args = parser.parse_args()
    for path in (args.video, args.voiceover, args.bgm):
        if not path.exists():
            parser.error(f"input does not exist: {path}")
    try:
        duration = video_duration_seconds(args.video)
        validate_narration_duration(args.voiceover, duration)
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="video-use-ad-mix-") as temp_dir:
        temp = Path(temp_dir)
        bgm_trimmed = temp / "bgm_trimmed.wav"
        voice_normalized = temp / "voice_-13lufs.wav"
        bgm_normalized = temp / "bgm_-27lufs.wav"
        loop_and_trim_bgm(args.bgm, duration, bgm_trimmed)
        normalize_audio(args.voiceover, voice_normalized, VOICE_TARGET_I, VOICE_TARGET_TP)
        normalize_audio(bgm_trimmed, bgm_normalized, BGM_TARGET_I, BGM_TARGET_TP)
        mix_tracks(args.video, voice_normalized, bgm_normalized, duration, args.output)
    print(f"mixed ad audio → {args.output} ({duration:.2f}s)")


if __name__ == "__main__":
    main()
