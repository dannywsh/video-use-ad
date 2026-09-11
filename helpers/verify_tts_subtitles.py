"""Validate that a TTS script and an SRT carry the same spoken text."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Marks a caption may break after. A break anywhere else cuts a phrase in half.
BREAK_PUNCTUATION = "。！？；，、!?…,"
# Sentence-final marks always end a cue, so they stay in the break set above and
# additionally force the cue to close.
SENTENCE_PUNCTUATION = "。！？；!?…"


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


def spoken_length(text: str) -> int:
    """Count the spoken characters of a caption or script fragment."""
    return len("".join(char for char in text if char.isalnum()))


def allowed_break_offsets(script: str, maximum_characters: int) -> set[int]:
    """List the cue starts that are legitimate for this script.

    Input: approved script and the per-line character budget. Returns: the set of
    spoken-character offsets a cue may begin at. Every clause boundary qualifies;
    inside a clause, a break is tolerated only when that clause alone exceeds the
    budget, so a caption never breaks where a clause boundary was available.
    """
    offsets = {0}
    count = 0
    clause_start = 0

    def close_clause(end: int) -> None:
        if end - clause_start > maximum_characters:
            offsets.update(range(clause_start + 1, end))
        offsets.add(end)

    for char in script:
        if char.isalnum():
            count += 1
        elif char in BREAK_PUNCTUATION or char == "\n":
            close_clause(count)
            clause_start = count
    close_clause(count)
    return offsets


# Fails unless every cue is one visual line and within the character budget.
# Input: SRT text and max normalized characters. Returns: None on success.
def assert_single_line_cues(srt: str, maximum_characters: int) -> None:
    for index, body in enumerate(srt_caption_bodies(srt), 1):
        if "\n" in body:
            raise ValueError(f"cue {index} has more than one line: {body!r}")
        if spoken_length(body) > maximum_characters:
            raise ValueError(
                f"cue {index} exceeds {maximum_characters} characters: {body!r}"
            )


# Fails when a cue breaks where a clause boundary was available.
# Input: approved script, SRT text and the per-line budget. Returns: cue count.
def assert_breaks_land_on_clauses(script: str, srt: str, maximum_characters: int) -> int:
    offsets = allowed_break_offsets(script, maximum_characters)
    cursor = 0
    bodies = srt_caption_bodies(srt)
    for index, body in enumerate(bodies, 1):
        cursor += spoken_length(body)
        if cursor not in offsets:
            raise ValueError(
                f"cue {index} breaks inside a phrase although a clause boundary was available: {body!r}"
            )
    return len(bodies)


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


# Reports the cue length spread so an operator can sanity-check pacing.
# Input: SRT text. Returns: a one-line summary.
def caption_summary(srt: str) -> str:
    lengths = [spoken_length(body) for body in srt_caption_bodies(srt)]
    if not lengths:
        return "no cues"
    return (
        f"{len(lengths)} cues, {min(lengths)}-{max(lengths)} chars"
        f" (mean {sum(lengths) / len(lengths):.1f})"
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
        default=18,
        help="Maximum normalized characters per cue; ad burns use 18",
    )
    args = parser.parse_args()
    script_text = args.script.read_text(encoding="utf-8").strip()
    srt_text = args.srt.read_text(encoding="utf-8")
    try:
        assert_script_matches_srt(script_text, srt_text)
        assert_single_line_cues(srt_text, args.max_chars)
        cue_count = assert_breaks_land_on_clauses(script_text, srt_text, args.max_chars)
    except ValueError as exc:
        sys.exit(f"subtitle validation failed: {exc}")
    print(
        f"subtitle validation passed: {cue_count} cues, one line each, "
        f"every break on a clause boundary, text matches the final TTS script"
    )
    print(f"  pacing: {caption_summary(srt_text)}")


if __name__ == "__main__":
    main()
