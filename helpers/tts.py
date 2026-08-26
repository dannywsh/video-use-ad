"""Generate voiceover audio from text (TTS).

Unified interface for multiple text-to-speech providers:

  - elevenlabs: ElevenLabs text-to-speech (ELEVENLABS_API_KEY)
  - mimo:       Xiaomi MiMo-V2.5-TTS (MIMO_API_KEY)
                Supports preset voices, text-based voice design, and
                audio-sample voice cloning.

Output is a plain audio file (wav/mp3) that can be mixed into a video
with ffmpeg, e.g.:

    ffmpeg -i video.mp4 -i voice.wav -filter_complex \
      "[0:a]volume=0.3[bg];[bg][1:a]amix=inputs=2:duration=longest[a]" \
      -map 0:v -map "[a]" -c:v copy -c:a aac -shortest out.mp4

Usage:
    # ElevenLabs (default)
    python helpers/tts.py "Hello world" -o voice.mp3
    python helpers/tts.py "Hello" -o voice.mp3 --voice-id <elevenlabs_voice_id>

    # MiMo preset voice
    python helpers/tts.py "你好世界" -o voice.wav --provider mimo --voice 冰糖
    python helpers/tts.py "Hey there" -o voice.wav --provider mimo --voice Chloe

    # MiMo with natural-language style instruction
    python helpers/tts.py "太棒了！" -o voice.wav --provider mimo \
        --voice 苏打 --style "用兴奋上扬的语调，语速稍快"

    # MiMo voice design (describe a voice from scratch)
    python helpers/tts.py "欢迎收听" -o voice.wav --provider mimo \
        --mimo-model voicedesign --style "一位温柔的中年女性，嗓音略带沙哑"

    # MiMo voice clone (from an audio sample)
    python helpers/tts.py "这段话用克隆声音" -o voice.wav --provider mimo \
        --mimo-model voiceclone --reference-audio sample.mp3

    # Read text from a file
    python helpers/tts.py --text-file script.txt -o voice.wav --provider mimo
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import wave
from pathlib import Path

import requests


# ---------------------------------------------------------------------------
# API key loading (same .env convention as transcribe.py)
# ---------------------------------------------------------------------------

PROVIDER_ENV_KEYS = {
    "elevenlabs": "ELEVENLABS_API_KEY",
    "mimo": "MIMO_API_KEY",
}


def load_api_key(provider: str) -> str:
    """Load an API key from .env (repo root or cwd) or the environment."""
    env_var = PROVIDER_ENV_KEYS[provider]
    for candidate in (
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
    ):
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == env_var:
                    return v.strip().strip('"').strip("'")
    v = os.environ.get(env_var, "")
    if not v:
        sys.exit(f"{env_var} not found in .env or environment")
    return v


# ---------------------------------------------------------------------------
# ElevenLabs TTS
# ---------------------------------------------------------------------------

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# Rachel — a sensible default; override with --voice-id.
ELEVENLABS_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
ELEVENLABS_DEFAULT_MODEL = "eleven_multilingual_v2"


def synthesize_elevenlabs(
    text: str,
    api_key: str,
    voice_id: str = ELEVENLABS_DEFAULT_VOICE_ID,
    model_id: str = ELEVENLABS_DEFAULT_MODEL,
    output_format: str = "mp3_44100_128",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
) -> bytes:
    """Call ElevenLabs TTS and return raw audio bytes."""
    url = f"{ELEVENLABS_TTS_URL}/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
        },
    }
    resp = requests.post(
        f"{url}?output_format={output_format}",
        headers=headers,
        json=payload,
        timeout=600,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs TTS returned {resp.status_code}: {resp.text[:500]}"
        )
    return resp.content


# ---------------------------------------------------------------------------
# MiMo TTS (OpenAI-compatible chat-completions endpoint with audio output)
# ---------------------------------------------------------------------------

MIMO_TTS_URL = "https://api.xiaomimimo.com/v1/chat/completions"

MIMO_MODELS = {
    "tts": "mimo-v2.5-tts",
    "voicedesign": "mimo-v2.5-tts-voicedesign",
    "voiceclone": "mimo-v2.5-tts-voiceclone",
}

MIMO_DEFAULT_VOICE = "mimo_default"

# Preset voices for the base `mimo-v2.5-tts` model.
MIMO_PRESET_VOICES = [
    "mimo_default",
    "冰糖", "茉莉", "苏打", "白桦",   # Chinese
    "Mia", "Chloe", "Milo", "Dean",    # English
]

_MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


def _encode_reference_audio(path: Path) -> str:
    """Read an audio sample and return a data URI for MiMo voice cloning."""
    suffix = path.suffix.lower()
    mime = _MIME_TYPES.get(suffix)
    if mime is None:
        raise ValueError(
            f"reference audio must be .mp3 or .wav, got {suffix}"
        )
    raw = path.read_bytes()
    # MiMo limits the base64 payload to 10 MB.
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError(
            f"reference audio too large: {len(raw) / 1024 / 1024:.1f} MB "
            "(limit 10 MB before base64)"
        )
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def reference_duration_seconds(path: Path) -> float:
    """Read a reference-audio duration with ffprobe.

    Input: an existing audio path. Returns: its duration in seconds.
    Raises ValueError when the duration cannot be measured.
    """
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise ValueError(f"could not determine reference-audio duration: {path}") from exc


def synthesize_mimo(
    text: str,
    api_key: str,
    model: str = MIMO_MODELS["tts"],
    voice: str = MIMO_DEFAULT_VOICE,
    style_instruction: str | None = None,
    reference_audio: Path | None = None,
    audio_format: str = "wav",
) -> bytes:
    """Call MiMo-V2.5-TTS and return decoded audio bytes.

    model:
      - mimo-v2.5-tts            → preset voices (voice = voice name)
      - mimo-v2.5-tts-voicedesign → voice designed from `style_instruction`
      - mimo-v2.5-tts-voiceclone  → voice cloned from `reference_audio`

    Per the MiMo API:
      - The text to synthesize MUST be in the assistant message.
      - A user message carries optional style/direction; for voicedesign
        it is required and is the voice description.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    user_content = style_instruction or ""
    messages = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": text},
    ]

    # Resolve the `audio.voice` field based on the model.
    if model == MIMO_MODELS["voiceclone"]:
        if reference_audio is None:
            raise ValueError(
                "voiceclone model requires --reference-audio <path>"
            )
        voice_field: str | None = _encode_reference_audio(reference_audio)
    elif model == MIMO_MODELS["voicedesign"]:
        # voicedesign generates the voice from the user-message description;
        # no voice id / sample is passed.
        voice_field = None
    else:
        voice_field = voice

    audio_payload: dict = {"format": audio_format}
    if voice_field:
        audio_payload["voice"] = voice_field

    payload = {
        "model": model,
        "messages": messages,
        "audio": audio_payload,
    }

    resp = requests.post(
        MIMO_TTS_URL,
        headers=headers,
        json=payload,
        timeout=600,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"MiMo TTS returned {resp.status_code}: {resp.text[:500]}"
        )

    data = resp.json()
    try:
        audio_b64 = data["choices"][0]["message"]["audio"]["data"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            f"unexpected MiMo response structure: {json.dumps(data)[:500]}"
        ) from exc
    return base64.b64decode(audio_b64)


def split_text_for_mimo(text: str, maximum_characters: int) -> list[str]:
    """Split a long MiMo script at sentence boundaries without omitting text.

    Input: source script and a positive per-request character limit. Returns: ordered
    synthesis chunks. A very long punctuation-free clause falls back to hard splits.
    """
    if maximum_characters <= 0 or len(text) <= maximum_characters:
        return [text]
    clauses = [part for part in re.split(r"(?<=[。！？；.!?])", text) if part]
    chunks: list[str] = []
    current = ""
    for clause in clauses:
        if current and len(current) + len(clause) > maximum_characters:
            chunks.append(current)
            current = clause
        else:
            current += clause
        while len(current) > maximum_characters:
            chunks.append(current[:maximum_characters])
            current = current[maximum_characters:]
    if current:
        chunks.append(current)
    return chunks


def concatenate_wav_chunks(chunks: list[bytes]) -> bytes:
    """Concatenate compatible WAV responses without re-encoding.

    Input: WAV byte payloads returned by MiMo. Returns: one WAV byte payload.
    Raises ValueError if MiMo returns incompatible audio stream parameters.
    """
    if not chunks:
        raise ValueError("cannot concatenate an empty list of WAV chunks")
    output = io.BytesIO()
    with wave.open(io.BytesIO(chunks[0]), "rb") as first:
        params = first.getparams()
        frames = [first.readframes(first.getnframes())]
        format_signature = (
            first.getnchannels(), first.getsampwidth(), first.getframerate(),
            first.getcomptype(), first.getcompname(),
        )
    for chunk in chunks[1:]:
        with wave.open(io.BytesIO(chunk), "rb") as part:
            if (
                part.getnchannels(), part.getsampwidth(), part.getframerate(),
                part.getcomptype(), part.getcompname(),
            ) != format_signature:
                raise ValueError("MiMo returned incompatible WAV parameters between chunks")
            frames.append(part.readframes(part.getnframes()))
    with wave.open(output, "wb") as merged:
        merged.setparams(params)
        for frame_bytes in frames:
            merged.writeframes(frame_bytes)
    return output.getvalue()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate voiceover audio from text (ElevenLabs / MiMo TTS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("text", nargs="?", help="Text to synthesize")
    ap.add_argument("--text-file", type=Path, help="Read text from a file (UTF-8)")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output audio path")

    ap.add_argument(
        "--provider",
        choices=["elevenlabs", "mimo"],
        default="elevenlabs",
        help="TTS provider (default: elevenlabs)",
    )

    # ---- ElevenLabs options ------------------------------------------------
    ap.add_argument(
        "--voice-id",
        default=None,
        help=f"ElevenLabs voice ID (default: {ELEVENLABS_DEFAULT_VOICE_ID})",
    )
    ap.add_argument(
        "--model-id",
        default=None,
        help=f"ElevenLabs model ID (default: {ELEVENLABS_DEFAULT_MODEL})",
    )
    ap.add_argument("--stability", type=float, default=0.5)
    ap.add_argument("--similarity-boost", type=float, default=0.75)
    ap.add_argument("--el-style", type=float, default=0.0, dest="el_style",
                    help="ElevenLabs style exaggeration (0.0-1.0)")

    # ---- MiMo options ------------------------------------------------------
    ap.add_argument(
        "--voice",
        default=None,
        help=(
            "MiMo preset voice name for mimo-v2.5-tts: "
            + ", ".join(MIMO_PRESET_VOICES)
        ),
    )
    ap.add_argument(
        "--mimo-model",
        choices=list(MIMO_MODELS.keys()),
        default="tts",
        help=(
            "MiMo model: tts (preset voices, default), voicedesign "
            "(describe a voice via --style), voiceclone (clone from "
            "--reference-audio)"
        ),
    )
    ap.add_argument(
        "--style-prefix",
        default=None,
        help=(
            "Required style text prepended before --style. Use this when a "
            "workflow has non-negotiable delivery constraints."
        ),
    )
    ap.add_argument(
        "--style",
        default=None,
        help=(
            "MiMo natural-language style instruction / voice description. "
            "For tts/voiceclone it controls delivery style; for voicedesign "
            "it is the voice design prompt (required)."
        ),
    )
    ap.add_argument(
        "--reference-audio",
        type=Path,
        default=None,
        help="Path to a .mp3/.wav sample for MiMo voice cloning (<=10 MB)",
    )
    ap.add_argument(
        "--mimo-max-chars",
        type=int,
        default=0,
        help=(
            "Split long MiMo text at sentence boundaries before synthesis, then "
            "losslessly merge WAV responses. 0 disables splitting (default)."
        ),
    )

    args = ap.parse_args()

    # Resolve text source
    if args.text_file:
        text = args.text_file.read_text(encoding="utf-8").strip()
    elif args.text:
        text = args.text
    else:
        ap.error("provide text as a positional argument or --text-file")
    if not text:
        sys.exit("error: text is empty")

    # A workflow-owned prefix must precede user direction so callers cannot
    # accidentally replace mandatory speech constraints with --style.
    style_instruction = " ".join(
        part.strip() for part in (args.style_prefix, args.style) if part and part.strip()
    ) or None

    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.provider == "elevenlabs":
        api_key = load_api_key("elevenlabs")
        print(f"[elevenlabs] synthesizing {len(text)} chars -> {args.output.name}")
        audio = synthesize_elevenlabs(
            text=text,
            api_key=api_key,
            voice_id=args.voice_id or ELEVENLABS_DEFAULT_VOICE_ID,
            model_id=args.model_id or ELEVENLABS_DEFAULT_MODEL,
            stability=args.stability,
            similarity_boost=args.similarity_boost,
            style=args.el_style,
        )
    else:  # mimo
        api_key = load_api_key("mimo")
        model = MIMO_MODELS[args.mimo_model]
        if args.mimo_model == "voicedesign" and not style_instruction:
            ap.error("--style is required for voicedesign (it is the voice description)")
        if args.mimo_model == "voiceclone" and not args.reference_audio:
            ap.error("--reference-audio is required for voiceclone")
        if args.reference_audio and not args.reference_audio.exists():
            sys.exit(f"reference audio not found: {args.reference_audio}")
        if args.mimo_model == "voiceclone" and args.reference_audio:
            duration = reference_duration_seconds(args.reference_audio)
            if not 3.0 <= duration <= 10.0:
                ap.error(
                    "voiceclone reference audio must be 3–10 seconds; "
                    f"got {duration:.2f}s. Extract a clean sample before synthesis."
                )
        chunks = split_text_for_mimo(text, args.mimo_max_chars)
        if len(chunks) > 1 and args.output.suffix.lower() != ".wav":
            ap.error("--mimo-max-chars requires a .wav output so chunks can be losslessly merged")
        print(f"[mimo:{model}] synthesizing {len(text)} chars in {len(chunks)} chunk(s) -> {args.output.name}")
        audio_chunks = [
            synthesize_mimo(
                text=chunk,
                api_key=api_key,
                model=model,
                voice=args.voice or MIMO_DEFAULT_VOICE,
                style_instruction=style_instruction,
                reference_audio=args.reference_audio,
                audio_format="wav",
            )
            for chunk in chunks
        ]
        audio = concatenate_wav_chunks(audio_chunks) if len(audio_chunks) > 1 else audio_chunks[0]

    args.output.write_bytes(audio)
    size_kb = args.output.stat().st_size / 1024
    print(f"done: {args.output} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
