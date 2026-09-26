import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "helpers" / "render.py"
SPEC = importlib.util.spec_from_file_location("video_use_render_timing", MODULE_PATH)
assert SPEC and SPEC.loader
render = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render)


class MasterSubtitleTimingTests(unittest.TestCase):
    def make_edit_dir(self, root: Path) -> Path:
        edit_dir = root / "edit"
        transcripts = edit_dir / "transcripts"
        transcripts.mkdir(parents=True)
        (transcripts / "first.json").write_text(json.dumps({
            "words": [{"type": "word", "start": 4.5, "end": 4.8, "text": "first"}],
        }))
        (transcripts / "second.json").write_text(json.dumps({
            "words": [{"type": "word", "start": 0.2, "end": 0.5, "text": "second"}],
        }))
        return edit_dir

    def make_edl(self, transition_handles: bool) -> dict:
        return {
            "transition_handles": transition_handles,
            "ranges": [
                {"source": "first", "start": 0, "end": 5},
                {
                    "source": "second",
                    "start": 0,
                    "end": 6,
                    "transition": {"type": "smoothright", "duration": 0.4},
                },
            ],
        }

    def test_handles_keep_dialogue_subtitles_on_authored_cut_timeline(self):
        with tempfile.TemporaryDirectory() as temp:
            edit_dir = self.make_edit_dir(Path(temp))
            output = edit_dir / "kept.srt"
            render.build_master_srt(self.make_edl(True), edit_dir, output)
            self.assertIn("00:00:05,200 --> 00:00:05,500", output.read_text())

    def test_disabling_handles_shifts_subtitles_by_actual_xfade_overlap(self):
        with tempfile.TemporaryDirectory() as temp:
            edit_dir = self.make_edit_dir(Path(temp))
            output = edit_dir / "shortened.srt"
            render.build_master_srt(self.make_edl(False), edit_dir, output)
            self.assertIn("00:00:04,800 --> 00:00:05,100", output.read_text())


if __name__ == "__main__":
    unittest.main()
