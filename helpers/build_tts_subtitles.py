"""Build final-audio-aligned SRT captions without adopting ASR wording."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


def normalized_characters(text: str) -> str:
    """Keep only spoken letters and digits for script-to-ASR alignment.

    Input: source script or ASR text. Returns: a punctuation-free comparison string.
    """
    return "".join(char.lower() for char in text if char.isalnum())


def srt_timestamp(seconds: float) -> str:
    """Convert a floating-point timestamp to HH:MM:SS,mmm SRT form."""
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def split_overlong_caption(text: str, maximum_characters: int) -> list[str]:
    """Hard-split one caption so no piece exceeds the single-line character budget.

    Input: caption text and max normalized characters. Returns: one or more pieces.
    """
    if maximum_characters < 1:
        raise ValueError("maximum_characters must be >= 1")
    if len(normalized_characters(text)) <= maximum_characters:
        return [text] if normalized_characters(text) else []
    pieces: list[str] = []
    current = ""
    current_count = 0
    for char in text:
        extra = len(normalized_characters(char))
        if current and current_count + extra > maximum_characters:
            pieces.append(current)
            current = char
            current_count = extra
        else:
            current += char
            current_count += extra
    if current:
        pieces.append(current)
    return [piece for piece in pieces if normalized_characters(piece)]


def split_caption_text(script: str, maximum_characters: int) -> list[str]:
    """Split a script into single-line semantic captions without dropping text.

    Input: approved script and maximum normalized characters per caption.
    Returns: ordered source-text chunks; punctuation remains until final SRT formatting.
    """
    clauses = [part for part in re.split(r"(?<=[。！？；，、])", script) if part]
    chunks: list[str] = []
    current = ""
    for clause in clauses:
        candidate = current + clause
        current_ends_sentence = current.rstrip().endswith(("。", "！", "？", "；"))
        if current and (current_ends_sentence or len(normalized_characters(candidate)) > maximum_characters):
            chunks.extend(split_overlong_caption(current, maximum_characters))
            current = clause
        else:
            current = candidate
    if current:
        chunks.extend(split_overlong_caption(current, maximum_characters))
    return [chunk for chunk in chunks if normalized_characters(chunk)]


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


def build_srt(script: str, words: list[dict], maximum_characters: int) -> str:
    """Create a verbatim-script SRT using ASR timestamps only.

    Input: final TTS script, word-level ASR words and caption length limit.
    Returns: complete UTF-8 SRT content with one semantic line per cue.
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
    chunks = split_caption_text(script, maximum_characters)
    cursor = 0
    lines: list[str] = []
    for number, chunk in enumerate(chunks, 1):
        normalized = normalized_characters(chunk)
        start_source = cursor
        end_source = cursor + len(normalized) - 1
        start_asr = mapping[start_source]
        end_asr = mapping[end_source]
        start_word = spoken_words[asr_char_to_word[start_asr]]
        end_word = spoken_words[asr_char_to_word[end_asr]]
        caption = re.sub(r"[^\w\s]", " ", chunk)
        caption = re.sub(r"\s+", " ", caption).strip()
        caption = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", caption)
        if "\n" in caption:
            raise ValueError("caption cue contains a line break; ad subtitles must stay one line")
        if len(normalized_characters(caption)) > maximum_characters:
            raise ValueError("caption cue exceeds the single-line character budget")
        lines.extend(
            [
                str(number),
                f"{srt_timestamp(float(start_word['start']))} --> {srt_timestamp(float(end_word['end']))}",
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
        default=32,
        help="Maximum normalized characters per single-line cue; ad burns must use 14",
    )
    args = parser.parse_args()
    script = args.script.read_text(encoding="utf-8").strip()
    transcript = json.loads(args.transcript.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_srt(script, transcript.get("words", []), args.max_chars), encoding="utf-8")
    print(f"master SRT → {args.output} (verbatim final TTS script)")


if __name__ == "__main__":
    main()
