"""Build final-audio-aligned SRT captions without adopting ASR wording."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


# Sentence-final marks: a caption must break here and the mark is not shown.
SENTENCE_PUNCTUATION = "。！？；!?…"
# Clause marks: the preferred break point. When a whole sentence fits on one line
# anyway, the mark survives on screen as a single space, so the viewer still sees
# where the narrator paused.
CLAUSE_PUNCTUATION = "，、,"
# Decorative marks that never appear on screen.
ERASED_PUNCTUATION = SENTENCE_PUNCTUATION + "「」『』（）()【】[]《》\"'"

HARD_BREAK = frozenset(SENTENCE_PUNCTUATION)
SOFT_BREAK = frozenset(CLAUSE_PUNCTUATION)


def normalized_characters(text: str) -> str:
    """Keep only spoken letters and digits for script-to-ASR alignment.

    Input: source script or ASR text. Returns: a punctuation-free comparison string.
    """
    return "".join(char.lower() for char in text if char.isalnum())


def format_caption_text(chunk: str) -> str:
    """Turn a script chunk into one on-screen caption line.

    Input: a source-text chunk that may still contain punctuation.
    Returns: caption text where sentence-final and decorative marks are dropped,
    clause marks become a single visible space, and quantity marks such as 1/7
    and 2.0 stay untouched.
    """
    caption = re.sub("[" + re.escape(ERASED_PUNCTUATION) + "]+", "", chunk)
    caption = re.sub("[" + re.escape(CLAUSE_PUNCTUATION) + "]+", " ", caption)
    return re.sub(r"\s+", " ", caption).strip()


def script_segments(script: str) -> list[tuple[str, bool]]:
    """Split the approved script at every clause boundary without losing text.

    Input: approved script. Returns: ordered (segment, is_sentence_end) pairs.
    Caption breaks may only land on these boundaries, so each cue stays a whole
    clause instead of being cut mid-phrase by a running character count.
    """
    segments: list[tuple[str, bool]] = []
    buffer = ""
    for char in script:
        if char == "\r":
            continue
        if char == "\n":
            if normalized_characters(buffer):
                segments.append((buffer, True))
                buffer = ""
            continue
        buffer += char
        if char in HARD_BREAK:
            segments.append((buffer, True))
            buffer = ""
        elif char in SOFT_BREAK:
            segments.append((buffer, False))
            buffer = ""
    if normalized_characters(buffer):
        segments.append((buffer, False))
    return segments


def segment_length(segments: list[tuple[str, bool]]) -> int:
    """Count the spoken characters carried by a list of segments."""
    return sum(len(normalized_characters(text)) for text, _ in segments)


def even_out_groups(
    groups: list[list[tuple[str, bool]]],
    maximum_characters: int,
    minimum_characters: int,
) -> list[list[tuple[str, bool]]]:
    """Push a trailing clause forward when it would strand a stub caption.

    Input: greedily packed groups and the per-line budget. Returns: the same
    clauses regrouped so neighbouring lines are less lopsided. Only clause marks
    move; a sentence-final mark never leaves the line it closes.
    """
    index = 0
    while index < len(groups) - 1:
        current, following = groups[index], groups[index + 1]
        if segment_length(following) >= minimum_characters or len(current) == 1:
            index += 1
            continue
        last = current[-1]
        last_length = len(normalized_characters(last[0]))
        moved = segment_length(current) - last_length
        after = segment_length(following) + last_length
        if (
            last[1]
            or moved < minimum_characters
            or after < minimum_characters
            or after > maximum_characters
        ):
            index += 1
            continue
        groups[index] = current[:-1]
        groups[index + 1] = [last] + following
        index += 1
    return groups


def group_segments(
    segments: list[tuple[str, bool]],
    maximum_characters: int,
    minimum_characters: int,
) -> list[list[tuple[str, bool]]]:
    """Pack segments into caption lines without ever exceeding the budget.

    Input: script segments plus the per-line budget. Returns: one segment list
    per caption line, greedily filled and then evened out.
    """
    groups: list[list[tuple[str, bool]]] = []
    current: list[tuple[str, bool]] = []
    for segment, is_sentence_end in segments:
        length = segment_length(current) + len(normalized_characters(segment))
        if current and length > maximum_characters:
            groups.append(current)
            current = []
        current.append((segment, is_sentence_end))
        if is_sentence_end:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return even_out_groups(groups, maximum_characters, minimum_characters)


def safe_break_positions(text: str) -> list[int]:
    """Locate indexes where a line may be cut without slicing a word in half.

    Input: caption text. Returns: ascending indexes, each the start of the next
    piece, marking Latin/CJK and space boundaries.
    """
    positions: list[int] = []
    for index in range(1, len(text)):
        before, after = text[index - 1], text[index]
        if before.isspace() != after.isspace():
            positions.append(index)
            continue
        if not before.isalnum() or not after.isalnum():
            continue
        before_cjk = "\u4e00" <= before <= "\u9fff"
        after_cjk = "\u4e00" <= after <= "\u9fff"
        if before_cjk != after_cjk:
            positions.append(index)
    return positions


def split_overlong_caption(text: str, maximum_characters: int) -> list[str]:
    """Hard-split one caption so no piece exceeds the single-line budget.

    Input: caption text and max normalized characters. Returns: one or more
    pieces, cut at a Latin/CJK or space boundary whenever one fits inside the
    budget, so an unpunctuated clause still breaks somewhere readable.
    """
    if maximum_characters < 1:
        raise ValueError("maximum_characters must be >= 1")
    if len(normalized_characters(text)) <= maximum_characters:
        return [text] if normalized_characters(text) else []

    safe = safe_break_positions(text)
    pieces: list[str] = []
    start = 0
    while len(normalized_characters(text[start:])) > maximum_characters:
        limit = start
        count = 0
        for index in range(start, len(text)):
            count += len(normalized_characters(text[index]))
            if count > maximum_characters:
                break
            limit = index + 1
        candidate = max((position for position in safe if start < position <= limit), default=None)
        cut = candidate if candidate is not None else limit
        pieces.append(text[start:cut].strip())
        start = cut
    pieces.append(text[start:].strip())
    return [piece for piece in pieces if normalized_characters(piece)]


def build_caption_chunks(
    script: str, maximum_characters: int, minimum_characters: int
) -> list[str]:
    """Turn the approved script into on-screen caption chunks.

    Input: approved script and the per-line budget. Returns: ordered chunks whose
    breaks sit on clause or sentence boundaries, falling back to a mid-clause cut
    only for a single clause longer than the budget.
    """
    if minimum_characters > maximum_characters:
        raise ValueError("minimum_characters must not exceed maximum_characters")
    chunks: list[str] = []
    for group in group_segments(script_segments(script), maximum_characters, minimum_characters):
        chunks.extend(
            split_overlong_caption("".join(text for text, _ in group), maximum_characters)
        )
    return chunks


def split_caption_text(
    script: str, maximum_characters: int, minimum_characters: int = 1
) -> list[str]:
    """Split a script into single-line semantic captions without dropping text.

    Input: approved script and the per-line character budget.
    Returns: ordered source-text chunks; punctuation remains until final SRT
    formatting.
    """
    return build_caption_chunks(script, maximum_characters, minimum_characters)


def source_to_asr_positions(source: str, words: list[dict]) -> tuple[str, list[int]]:
    """Map every normalized source character to an ASR character position.

    Input: final TTS script plus word-level ASR data. Returns: normalized source text
    and a same-length list of aligned ASR character indexes. Non-verbatim ASR errors
    (for example, brand-name recognition) are interpolated only for timing.
    """
    source_normalized = normalized_characters(source)
    asr_normalized = "".join(normalized_characters(word.get("text", "")) for word in words)
    matcher = difflib.SequenceMatcher(None, source_normalized, asr_normalized, autojunk=False)
    mapping = [-1] * len(source_normalized)
    for tag, source_start, source_end, asr_start, _asr_end in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(source_end - source_start):
                mapping[source_start + offset] = asr_start + offset

    anchors = [index for index, value in enumerate(mapping) if value >= 0]
    if not anchors:
        raise ValueError("ASR has no text that can be aligned to the final TTS script")
    for index, value in enumerate(mapping):
        if value >= 0:
            continue
        left = max((anchor for anchor in anchors if anchor < index), default=None)
        right = min((anchor for anchor in anchors if anchor > index), default=None)
        if left is None:
            mapping[index] = mapping[right]  # type: ignore[index]
        elif right is None:
            mapping[index] = mapping[left]
        else:
            fraction = (index - left) / (right - left)
            mapping[index] = round(mapping[left] + fraction * (mapping[right] - mapping[left]))
    return source_normalized, mapping


def srt_timestamp(seconds: float) -> str:
    """Convert a floating-point timestamp to HH:MM:SS,mmm SRT form."""
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def build_srt(
    script: str,
    words: list[dict],
    maximum_characters: int,
    minimum_characters: int = 1,
) -> str:
    """Create a verbatim-script SRT using ASR timestamps only.

    Input: final TTS script, word-level ASR words and caption length limits.
    Returns: complete UTF-8 SRT content with one semantic line per cue, never with
    two cues on screen at the same time.
    """
    spoken_words = [
        word
        for word in words
        if word.get("type") == "word" and normalized_characters(word.get("text", ""))
    ]
    asr_char_to_word: list[int] = []
    for word_index, word in enumerate(spoken_words):
        asr_char_to_word.extend([word_index] * len(normalized_characters(word["text"])))
    source_normalized, mapping = source_to_asr_positions(script, spoken_words)
    chunks = build_caption_chunks(script, maximum_characters, minimum_characters)
    cursor = 0
    previous_end = 0.0
    lines: list[str] = []
    for number, chunk in enumerate(chunks, 1):
        normalized = normalized_characters(chunk)
        start_source = cursor
        end_source = cursor + len(normalized) - 1
        start_asr = mapping[start_source]
        end_asr = mapping[end_source]
        start_index = asr_char_to_word[start_asr]
        end_index = asr_char_to_word[end_asr]
        # An unmatched run of source characters (a brand name the ASR renders as
        # unrelated syllables) is timed by interpolating between its neighbours.
        # That interpolation can land back inside the previous cue, which would
        # draw two captions on top of each other; walk forward to the first word
        # that actually starts after it instead.
        while (
            start_index < end_index
            and float(spoken_words[start_index]["start"]) < previous_end - 1e-3
        ):
            start_index += 1
        start_word = spoken_words[start_index]
        end_word = spoken_words[end_index]
        start_time = max(float(start_word["start"]), previous_end)
        end_time = max(float(end_word["end"]), start_time + 0.2)
        previous_end = end_time
        caption = format_caption_text(chunk)
        if "\n" in caption:
            raise ValueError("caption cue contains a line break; ad subtitles must stay one line")
        if len(normalized_characters(caption)) > maximum_characters:
            raise ValueError("caption cue exceeds the single-line character budget")
        lines.extend(
            [
                str(number),
                f"{srt_timestamp(start_time)} --> {srt_timestamp(end_time)}",
                caption,
                "",
            ]
        )
        cursor += len(normalized)
    if cursor != len(source_normalized):
        raise ValueError("caption splitting did not preserve the complete final TTS script")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build verbatim TTS subtitles, using ASR only for word-level timing."
    )
    parser.add_argument("script", type=Path, help="Exact final text sent to TTS")
    parser.add_argument("transcript", type=Path, help="Word-level ASR JSON of that final audio")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output SRT path")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=18,
        help="Maximum normalized characters per single-line cue; ad burns must use 18",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=8,
        help="Preferred minimum characters per cue; a shorter stub is merged forward",
    )
    args = parser.parse_args()
    script = args.script.read_text(encoding="utf-8").strip()
    transcript = json.loads(args.transcript.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        build_srt(script, transcript.get("words", []), args.max_chars, args.min_chars),
        encoding="utf-8",
    )
    print(f"master SRT → {args.output} (verbatim final TTS script)")


if __name__ == "__main__":
    main()
