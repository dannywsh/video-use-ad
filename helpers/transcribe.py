"""Transcribe a video or audio file to word-level JSON.

Providers:
  - elevenlabs (default): ElevenLabs Scribe with diarize + audio events
  - paraformer: hosted FunASR Paraformer-large (Chinese-first, char timestamps)

Extracts mono 16kHz audio via ffmpeg, uploads it, and writes a Scribe-compatible
JSON to <edit_dir>/transcripts/<stem>.json so pack_transcripts.py, render.py,
and build_tts_subtitles.py can consume either provider.

Cached: if the output file already exists, the upload is skipped.

Usage:
    python helpers/transcribe.py <media_path>
    python helpers/transcribe.py <media_path> --provider paraformer
    python helpers/transcribe.py <media_path> --edit-dir /custom/edit
    python helpers/transcribe.py <media_path> --language en
    python helpers/transcribe.py <media_path> --num-speakers 2
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests


SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_PARAFORMER_URL = "https://paraformer.ow2shit.top"
PROVIDERS = ("elevenlabs", "paraformer")


def load_env_value(name: str, default: str = "") -> str:
    """Read one value from skill-root .env, cwd .env, then the process environment."""
    for candidate in (Path(__file__).resolve().parent.parent / ".env", Path.cwd() / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    return os.environ.get(name, default).strip()


def load_api_key(name: str = "ELEVENLABS_API_KEY") -> str:
    """Load a required credential or exit with the variable name."""
    value = load_env_value(name)
    if not value:
        sys.exit(f"{name} not found in .env or environment")
    return value


def extract_audio(video_path: Path, dest: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dest),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def call_scribe(
    audio_path: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
) -> dict:
    data: dict[str, str] = {
        "model_id": "scribe_v1",
        "diarize": "true",
        "tag_audio_events": "true",
        "timestamps_granularity": "word",
    }
    if language:
        data["language_code"] = language
    if num_speakers:
        data["num_speakers"] = str(num_speakers)

    with open(audio_path, "rb") as f:
        resp = requests.post(
            SCRIBE_URL,
            headers={"xi-api-key": api_key},
            files={"file": (audio_path.name, f, "audio/wav")},
            data=data,
            timeout=1800,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Scribe returned {resp.status_code}: {resp.text[:500]}")

    return resp.json()


def _is_spoken_char(char: str) -> bool:
    """True for letters, digits, and CJK unified ideographs (skip punctuation)."""
    return char.isalnum() or "\u4e00" <= char <= "\u9fff"


def _ms_pair_to_seconds(pair: list | tuple) -> tuple[float, float]:
    """Convert a FunASR [start_ms, end_ms] pair into seconds."""
    start_ms, end_ms = float(pair[0]), float(pair[1])
    return start_ms / 1000.0, max(end_ms, start_ms) / 1000.0


def align_text_to_timestamps(text: str, timestamps: list) -> list[dict]:
    """Map spoken characters onto FunASR millisecond timestamps.

    Input: sentence or full transcript text, plus [[start_ms, end_ms], ...].
    Returns: Scribe-shaped word dicts. When counts match (the usual Chinese
    case), mapping is 1:1. Otherwise timestamps are split evenly across chars.
    """
    spoken = [char for char in text if _is_spoken_char(char)]
    if not spoken or not timestamps:
        return []

    words: list[dict] = []
    if len(timestamps) == len(spoken):
        pairs = zip(spoken, timestamps)
    else:
        n_chars = len(spoken)
        n_ts = len(timestamps)
        pairs = []
        for ts_index, ts in enumerate(timestamps):
            start_i = int(ts_index * n_chars / n_ts)
            end_i = int((ts_index + 1) * n_chars / n_ts)
            group = spoken[start_i:end_i]
            if not group:
                continue
            start, end = _ms_pair_to_seconds(ts)
            span = (end - start) / len(group)
            for offset, char in enumerate(group):
                pairs.append((char, [ (start + offset * span) * 1000.0, (start + (offset + 1) * span) * 1000.0 ]))

    for char, ts in pairs:
        start, end = _ms_pair_to_seconds(ts)
        words.append({
            "text": char,
            "start": start,
            "end": end,
            "type": "word",
            "speaker_id": "speaker_0",
        })
    return words


def paraformer_to_scribe(result: dict) -> dict:
    """Normalize FunASR JSON into the word-level shape downstream helpers read.

    Input: `/v1/audio/transcriptions` JSON (`text`, `timestamp`, `sentence_info`).
    Returns: `{text, words, language_code, asr_provider, model, ...}` where each
    word is `{text, start, end, type=word}` with timestamps in seconds.
    """
    words: list[dict] = []
    sentences = result.get("sentence_info") or []
    if sentences:
        for sentence in sentences:
            words.extend(
                align_text_to_timestamps(
                    sentence.get("text") or "",
                    sentence.get("timestamp") or [],
                )
            )
    else:
        words.extend(
            align_text_to_timestamps(
                result.get("text") or "",
                result.get("timestamp") or [],
            )
        )
    return {
        "text": result.get("text") or "",
        "words": words,
        "language_code": "zho",
        "asr_provider": "paraformer",
        "model": result.get("model"),
        "model_revision": result.get("model_revision"),
        "sentence_info": sentences,
    }


def call_paraformer(audio_path: Path, api_token: str, base_url: str) -> dict:
    """POST 16 kHz WAV to the hosted Paraformer OpenAI-compatible endpoint."""
    url = f"{base_url.rstrip('/')}/v1/audio/transcriptions"
    with open(audio_path, "rb") as f:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_token}"},
            files={"file": (audio_path.name, f, "audio/wav")},
            data={"response_format": "json"},
            timeout=1800,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Paraformer returned {resp.status_code}: {resp.text[:500]}")
    payload = resp.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Paraformer returned a non-object JSON payload")
    return paraformer_to_scribe(payload)


def transcribe_one(
    video: Path,
    edit_dir: Path,
    api_key: str | None = None,
    language: str | None = None,
    num_speakers: int | None = None,
    verbose: bool = True,
    provider: str = "elevenlabs",
    paraformer_url: str | None = None,
    paraformer_token: str | None = None,
) -> Path:
    """Transcribe a single video or audio file. Returns path to transcript JSON.

    Cached: returns existing path immediately if the transcript already exists.
    """
    if provider not in PROVIDERS:
        raise ValueError(f"unknown ASR provider: {provider}")

    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcripts_dir / f"{video.stem}.json"

    if out_path.exists():
        if verbose:
            print(f"cached: {out_path.name}")
        return out_path

    if verbose:
        print(f"  extracting audio from {video.name}", flush=True)

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / f"{video.stem}.wav"
        extract_audio(video, audio)
        size_mb = audio.stat().st_size / (1024 * 1024)
        if verbose:
            print(f"  uploading {video.stem}.wav ({size_mb:.1f} MB) via {provider}", flush=True)
        if provider == "paraformer":
            token = paraformer_token or load_api_key("PARAFORMER_API_TOKEN")
            base_url = paraformer_url or load_env_value("PARAFORMER_API_URL", DEFAULT_PARAFORMER_URL)
            payload = call_paraformer(audio, token, base_url)
        else:
            payload = call_scribe(
                audio,
                api_key or load_api_key("ELEVENLABS_API_KEY"),
                language,
                num_speakers,
            )

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    dt = time.time() - t0

    if verbose:
        kb = out_path.stat().st_size / 1024
        print(f"  saved: {out_path.name} ({kb:.1f} KB) in {dt:.1f}s")
        if isinstance(payload, dict) and "words" in payload:
            print(f"    words: {len(payload['words'])}")

    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Transcribe a video with ElevenLabs Scribe or hosted Paraformer"
    )
    ap.add_argument("video", type=Path, help="Path to video or audio file")
    ap.add_argument(
        "--edit-dir",
        type=Path,
        default=None,
        help="Edit output directory (default: <video_parent>/edit)",
    )
    ap.add_argument(
        "--provider",
        choices=PROVIDERS,
        default="elevenlabs",
        help="ASR provider (default: elevenlabs)",
    )
    ap.add_argument(
        "--language",
        type=str,
        default=None,
        help="Optional ISO language code (e.g., 'en'). Scribe only. Omit to auto-detect.",
    )
    ap.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="Optional number of speakers when known. Scribe only.",
    )
    ap.add_argument(
        "--paraformer-url",
        type=str,
        default=None,
        help=f"Paraformer base URL (default: PARAFORMER_API_URL or {DEFAULT_PARAFORMER_URL})",
    )
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.exists():
        sys.exit(f"video not found: {video}")

    if args.provider == "paraformer" and (args.language or args.num_speakers):
        print("note: --language / --num-speakers are ignored for paraformer", file=sys.stderr)

    edit_dir = (args.edit_dir or (video.parent / "edit")).resolve()
    transcribe_one(
        video=video,
        edit_dir=edit_dir,
        language=args.language,
        num_speakers=args.num_speakers,
        provider=args.provider,
        paraformer_url=args.paraformer_url,
    )


if __name__ == "__main__":
    main()
