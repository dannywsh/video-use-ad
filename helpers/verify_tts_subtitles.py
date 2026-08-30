"""Validate that a TTS script and an SRT carry the same spoken text."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Normalizes only presentation differences that subtitle rules explicitly allow.
# Input: script or SRT text. Returns: comparable speech text with no punctuation or spacing.
def normalize_spoken_text(text: str) -> str:
    text = re.sub(r"^\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}\s*$", "", text, flags=re.MULTILINE)
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).lower()


# Parses SRT cue bodies, ignoring index and timestamp lines.
# Input: SRT text. Returns: ordered caption bodies.
def srt_caption_bodies(srt: str) -> list[str]:
    bodies: list[str] = []
    current: list[str] = []
    for raw in srt.splitlines():
        line = raw.strip()
        if re.fullmatch(r"\d+", line):
            if current:
                bodies.append("\n".join(current))
                current = []
            continue
        if re.fullmatch(r"\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}", line):
            continue
        if not line:
            if current:
                bodies.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        bodies.append("\n".join(current))
    return bodies


# Fails unless every cue is one visual line and within the character budget.
# Input: SRT text and max normalized characters. Returns: None on success.
def assert_single_line_cues(srt: str, maximum_characters: int) -> None:
    for index, body in enumerate(srt_caption_bodies(srt), 1):
        if "\n" in body:
            raise ValueError(f"cue {index} has more than one line: {body!r}")
        spoken = "".join(char for char in body if char.isalnum())
        if len(spoken) > maximum_characters:
            raise ValueError(
                f"cue {index} exceeds {maximum_characters} characters: {body!r}"
            )


# Verifies exact normalized equality and returns a focused mismatch preview.
# Input: final TTS script text and SRT text. Returns: None on success; raises ValueError on mismatch.
def assert_script_matches_srt(script: str, srt: str) -> None:
    expected = normalize_spoken_text(script)
    actual = normalize_spoken_text(srt)
    if expected != actual:
        limit = 120
        raise ValueError(
            "TTS script and SRT text differ after allowed punctuation/spacing normalization.\n"
            f"script: {expected[:limit]}\n"
            f"srt:    {actual[:limit]}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fail unless the final TTS script and SRT text are exactly equivalent."
    )
    parser.add_argument("script", type=Path, help="Final text sent to TTS")
    parser.add_argument("srt", type=Path, help="Subtitle file aligned to that final audio")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=14,
        help="Maximum normalized characters per cue; ad burns use 14",
    )
    args = parser.parse_args()
    srt_text = args.srt.read_text(encoding="utf-8")
    try:
        assert_script_matches_srt(args.script.read_text(encoding="utf-8"), srt_text)
        assert_single_line_cues(srt_text, args.max_chars)
    except ValueError as exc:
        sys.exit(f"subtitle validation failed: {exc}")
    print("subtitle validation passed: final TTS script matches SRT text and stays one line")


if __name__ == "__main__":
    main()
