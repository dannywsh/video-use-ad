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
    args = parser.parse_args()
    try:
        assert_script_matches_srt(
            args.script.read_text(encoding="utf-8"),
            args.srt.read_text(encoding="utf-8"),
        )
    except ValueError as exc:
        sys.exit(f"subtitle validation failed: {exc}")
    print("subtitle validation passed: final TTS script matches SRT text")


if __name__ == "__main__":
    main()
