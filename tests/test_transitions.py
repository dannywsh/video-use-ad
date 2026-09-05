import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "helpers"))
import transitions as T  # noqa: E402


class ParseTransitionTests(unittest.TestCase):
    def test_cut_aliases_are_hard_cuts(self):
        for value in (None, False, "cut", "none", "hard", {"type": "cut"}, {"type": "fade", "duration": 0}):
            with self.subTest(value=value):
                self.assertIsNone(T.parse_transition(value))

    def test_true_defaults_to_fade(self):
        self.assertEqual(T.parse_transition(True), T.Transition("fade", 0.4))

    def test_named_and_dict_forms(self):
        self.assertEqual(T.parse_transition("fadeblack"), T.Transition("fadeblack", 0.4))
        self.assertEqual(
            T.parse_transition({"type": "wipeleft", "duration": 0.5}),
            T.Transition("wipeleft", 0.5),
        )

    def test_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            T.parse_transition("explode")


class JoinResolutionTests(unittest.TestCase):
    def test_first_range_never_has_inbound_join(self):
        edl = {
            "default_transition": {"type": "fade", "duration": 0.4},
            "ranges": [
                {"source": "a", "start": 0, "end": 5, "transition": {"type": "fade", "duration": 0.4}},
                {"source": "b", "start": 0, "end": 4},
            ],
        }
        self.assertIsNone(T.resolve_join_transition(edl, 0))
        self.assertEqual(T.resolve_join_transition(edl, 1), T.Transition("fade", 0.4))

    def test_per_range_overrides_default(self):
        edl = {
            "default_transition": {"type": "fade", "duration": 0.4},
            "ranges": [
                {"source": "a", "start": 0, "end": 5},
                {"source": "b", "start": 0, "end": 4, "transition": "cut"},
                {"source": "c", "start": 0, "end": 3, "transition": {"type": "fadeblack", "duration": 0.3}},
            ],
        }
        joins = T.edl_join_transitions(edl)
        self.assertEqual(joins, [None, None, T.Transition("fadeblack", 0.3)])

    def test_output_offsets_subtract_overlap(self):
        ranges = [
            {"source": "a", "start": 0, "end": 5},
            {"source": "b", "start": 10, "end": 16},
            {"source": "c", "start": 0, "end": 4},
        ]
        joins = [None, T.Transition("fade", 0.4), T.Transition("fade", 0.4)]
        self.assertEqual(
            T.output_timeline_offsets(ranges, joins),
            [0.0, 4.6, 10.2],
        )


class FilterGraphTests(unittest.TestCase):
    def test_xfade_offset_is_previous_duration_minus_overlap(self):
        graph, v_label, a_label = T.build_xfade_filter(
            [5.0, 6.0],
            [None, T.Transition("fade", 0.4)],
            [True, True],
            1920, 1080, "30",
            include_audio=True,
        )
        self.assertIn("xfade=transition=fade:duration=0.400000:offset=4.600000", graph)
        self.assertIn("acrossfade=d=0.400000", graph)
        self.assertEqual(v_label, "[vx1]")
        self.assertEqual(a_label, "[ax1]")

    def test_hard_cut_uses_concat_filter(self):
        graph, _, a_label = T.build_xfade_filter(
            [5.0, 6.0, 4.0],
            [None, T.Transition("fade", 0.4), None],
            [True, False, True],
            1920, 1080, "30",
            include_audio=True,
        )
        self.assertIn("xfade=transition=fade", graph)
        self.assertIn("concat=n=2:v=1:a=0[vx2]", graph)
        self.assertIn("anullsrc=", graph)
        self.assertIsNotNone(a_label)

    def test_silent_output_omits_audio_labels(self):
        graph, v_label, a_label = T.build_xfade_filter(
            [2.0, 2.0],
            [None, T.Transition("fade", 0.4)],
            [False, False],
            1920, 1080, "30",
            include_audio=False,
        )
        self.assertNotIn("acrossfade", graph)
        self.assertNotIn("anullsrc", graph)
        self.assertEqual(v_label, "[vx1]")
        self.assertIsNone(a_label)

    def test_short_clips_clamp_or_drop_transition(self):
        self.assertIsNone(T.clamp_join(T.Transition("fade", 0.4), 0.08, 0.08))
        clamped = T.clamp_join(T.Transition("fade", 2.0), 5.0, 5.0)
        self.assertEqual(clamped, T.Transition("fade", 2.0))
        shortened = T.clamp_join(T.Transition("fade", 3.0), 5.0, 4.0)
        self.assertEqual(shortened, T.Transition("fade", 1.8))

    def test_outbound_handles_restore_hard_cut_duration(self):
        joins = [None, T.Transition("fade", 0.4), T.Transition("fade", 0.4)]
        self.assertEqual(T.outbound_handle_seconds(joins, 3), [0.4, 0.4, 0.0])
        durs = [7.0, 10.0, 10.0]
        extras = T.outbound_handle_seconds(joins, 3)
        padded = [d + e for d, e in zip(durs, extras)]
        acc = padded[0]
        for i in range(1, 3):
            acc = acc + padded[i] - joins[i].duration
        self.assertAlmostEqual(acc, sum(durs))
        self.assertAlmostEqual(padded[0] - joins[1].duration, durs[0])

    def test_parse_joins_arg(self):
        joins = T.parse_joins_arg("fade:0.4,cut,fadeblack:0.5", 4)
        self.assertEqual(
            joins,
            [None, T.Transition("fade", 0.4), None, T.Transition("fadeblack", 0.5)],
        )


if __name__ == "__main__":
    unittest.main()
