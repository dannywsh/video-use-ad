import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "helpers"))
import build_tts_subtitles as B  # noqa: E402
import verify_tts_subtitles as V  # noqa: E402


# Neutral copy on purpose: the fixtures must exercise clause marks, latin runs
# and quantity symbols without borrowing a real brief's script.
SCRIPT = (
    "手冲咖啡其实不难，记住三个数字就行。\n"
    "水温九十二度，粉水比一比十五，先闷蒸三十秒。\n"
    "第一段注水要慢，水流细而稳；第二段可以稍快一些，让粉层翻起来。\n"
    "如果觉得太苦，就把研磨度调粗一点，或者缩短萃取时间，口感会柔和很多。\n"
    "从闷蒸到完成，大约两分半钟。\n"
    "一杯好咖啡，值得花五分钟慢慢等。"
)


def lengths(chunks):
    return [len(B.normalized_characters(chunk)) for chunk in chunks]


def build_srt_text(script, maximum=18, minimum=8):
    lines = []
    for index, chunk in enumerate(B.build_caption_chunks(script, maximum, minimum), 1):
        lines += [str(index), "00:00:00,000 --> 00:00:01,000", B.format_caption_text(chunk), ""]
    return "\n".join(lines)


class ClauseBreakingTests(unittest.TestCase):
    def test_breaks_land_on_clause_boundaries(self):
        offsets = V.allowed_break_offsets(SCRIPT, 18)
        cursor = 0
        for chunk in B.build_caption_chunks(SCRIPT, 18, 8):
            cursor += len(B.normalized_characters(chunk))
            self.assertIn(cursor, offsets, f"break after {cursor} falls inside a phrase")

    def test_no_text_is_dropped(self):
        chunks = B.build_caption_chunks(SCRIPT, 18, 8)
        self.assertEqual(
            "".join(B.normalized_characters(chunk) for chunk in chunks),
            B.normalized_characters(SCRIPT),
        )

    def test_no_cue_exceeds_the_budget(self):
        for chunk in B.build_caption_chunks(SCRIPT, 18, 8):
            self.assertLessEqual(len(B.normalized_characters(chunk)), 18)

    def test_a_short_trailing_clause_is_pulled_forward(self):
        # Greedy packing would give 5+9+4 = 18 then a 5-char stub; the stub is
        # rebalanced to 14 + 9.
        script = "研磨度调粗，水流就快得冲下去了，萃取不足，味道就淡了。"
        self.assertEqual(lengths(B.build_caption_chunks(script, 18, 8)), [14, 9])

    def test_a_sentence_that_fits_stays_on_one_line(self):
        chunks = B.build_caption_chunks("今天天气不错，适合出门散步。", 18, 8)
        self.assertEqual(len(chunks), 1)

    def test_clause_marks_drive_the_break_not_a_character_count(self):
        # 30 characters carrying three clause marks must break on the marks.
        script = "水温偏高，口感会发苦，把研磨度调粗一点就好，或者让水流走得再慢一点。"
        self.assertEqual(lengths(B.build_caption_chunks(script, 18, 8)), [9, 10, 11])

    def test_an_overlong_clause_is_cut_at_the_latin_cjk_boundary(self):
        chunks = B.split_overlong_caption("POUR OVER BREW 慢速手冲咖啡萃取法", 18)
        self.assertEqual(chunks, ["POUR OVER BREW", "慢速手冲咖啡萃取法"])

    def test_minimum_above_maximum_is_rejected(self):
        with self.assertRaises(ValueError):
            B.build_caption_chunks("测试。", 8, 18)


class CaptionFormattingTests(unittest.TestCase):
    def test_clause_marks_become_visible_spaces(self):
        self.assertEqual(B.format_caption_text("研磨度偏细，苦味更明显。"), "研磨度偏细 苦味更明显")

    def test_sentence_marks_are_not_shown(self):
        self.assertEqual(B.format_caption_text("就完成了。"), "就完成了")

    def test_quantity_marks_survive(self):
        self.assertEqual(B.format_caption_text("1/2 杯水，2.5 分钟。"), "1/2 杯水 2.5 分钟")

    def test_latin_cjk_spacing_is_kept(self):
        self.assertEqual(B.format_caption_text("加入 120 毫升热水，搅拌 3 圈。"), "加入 120 毫升热水 搅拌 3 圈")

    def test_commas_leave_a_space_on_screen(self):
        captions = [
            B.format_caption_text(chunk) for chunk in B.build_caption_chunks(SCRIPT, 18, 8)
        ]
        self.assertIn("如果觉得太苦 就把研磨度调粗一点", captions)
        self.assertNotIn("如果觉得太苦就把研磨度调粗一点", "".join(captions))


class CueTimelineTests(unittest.TestCase):
    # "POUR OVER" comes back from ASR as unrelated syllables, so those source
    # characters are timed by interpolation instead of by a matching word.
    SCRIPT = "先看水温。POUR OVER 慢速滤杯，再闻香气。"
    SPOKEN = [
        ("先", 0.2), ("看", 0.2), ("水", 0.2), ("温", 0.2),
        ("摸", 0.2), ("啊", 0.2),
        ("慢", 0.3), ("速", 0.3), ("滤", 0.3), ("杯", 0.3),
        ("再", 0.3), ("闻", 0.3), ("香", 0.3), ("气", 0.3),
    ]

    def words(self):
        out, clock = [], 0.0
        for text, duration in self.SPOKEN:
            out.append({"type": "word", "text": text,
                        "start": round(clock, 3), "end": round(clock + duration, 3)})
            clock += duration
        return out

    def cues(self):
        srt = B.build_srt(self.SCRIPT, self.words(), 18, 8)
        blocks = [block for block in srt.strip().split("\n\n")]
        parsed = []
        for block in blocks:
            _, times, caption = block.split("\n", 2)
            start, end = times.split(" --> ")
            parsed.append((start, end, caption))
        return parsed

    def test_an_interpolated_run_never_pushes_a_cue_backwards(self):
        cues = self.cues()
        self.assertGreater(len(cues), 1)
        for (_, previous_end, _), (start, _, _) in zip(cues, cues[1:]):
            self.assertLessEqual(previous_end, start, "two cues would be on screen at once")

    def test_every_cue_keeps_a_usable_duration(self):
        # SRT timestamps are fixed-width, so lexicographic order is time order.
        for start, end, _ in self.cues():
            self.assertLess(start, end)


class VerifyTests(unittest.TestCase):
    def test_a_break_inside_a_phrase_is_rejected(self):
        script = "水温偏高，口感会发苦，把研磨度调粗一点就好，或者让水流走得再慢一点。"
        srt = "1\n00:00:00,000 --> 00:00:02,000\n水温偏高口感\n\n2\n00:00:02,000 --> 00:00:04,000\n会发苦把研磨度调粗一点就好\n\n"
        with self.assertRaises(ValueError):
            V.assert_breaks_land_on_clauses(script, srt, 18)

    def test_built_cues_pass_verification(self):
        srt = build_srt_text(SCRIPT)
        V.assert_script_matches_srt(SCRIPT, srt)
        V.assert_single_line_cues(srt, 18)
        self.assertEqual(
            V.assert_breaks_land_on_clauses(SCRIPT, srt, 18),
            len(V.srt_caption_bodies(srt)),
        )

    def test_an_overlong_cue_is_rejected(self):
        srt = "1\n00:00:00,000 --> 00:00:02,000\n这条字幕故意写得非常长超过十八个字用来测试\n\n"
        with self.assertRaises(ValueError):
            V.assert_single_line_cues(srt, 18)


if __name__ == "__main__":
    unittest.main()
