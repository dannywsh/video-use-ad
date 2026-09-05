import json
import subprocess
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "helpers"))
import stable_motion as S  # noqa: E402


class ScrollWindowTests(unittest.TestCase):
    def test_short_image_cannot_scroll(self):
        window = S.compute_scroll_window(1920, 800, 3840, 2160, 6.0)
        self.assertFalse(window.can_scroll)
        self.assertEqual(window.viewports_per_sec, 0.0)

    def test_tall_image_short_duration_crops_from_top(self):
        window = S.compute_scroll_window(1000, 3266, 3840, 2160, 7.0)
        self.assertTrue(window.cropped)
        self.assertTrue(window.can_scroll)
        self.assertEqual(window.crop_y, 0)
        self.assertLess(window.crop_h, 3266)
        self.assertAlmostEqual(window.viewports_per_sec, S.DEFAULT_SCROLL_VIEWPORTS_PER_SEC, places=4)
        self.assertLess(window.hold_s, 0.15)

    def test_long_duration_keeps_full_image_at_constant_speed(self):
        window = S.compute_scroll_window(1000, 3266, 3840, 2160, 40.0)
        self.assertFalse(window.cropped)
        self.assertEqual(window.crop_y, 0)
        self.assertEqual(window.crop_h, 3266)
        self.assertAlmostEqual(window.viewports_per_sec, S.DEFAULT_SCROLL_VIEWPORTS_PER_SEC, places=4)
        self.assertGreater(window.hold_s, 5.0)

    def test_short_band_does_not_slow_down_to_fill_the_shot(self):
        window = S.compute_scroll_window(1000, 3266, 3840, 2160, 8.0, region=(0.0, 0.22))
        self.assertTrue(window.can_scroll)
        self.assertAlmostEqual(window.viewports_per_sec, S.DEFAULT_SCROLL_VIEWPORTS_PER_SEC, places=4)
        self.assertGreater(window.hold_s, 4.0)
        self.assertLess(window.scroll_s, window.hold_s)

    def test_region_then_anchor_bottom(self):
        window = S.compute_scroll_window(
            1000, 3266, 3840, 2160, 6.0, region=(0.2, 0.9), anchor="bottom",
        )
        self.assertGreater(window.crop_y, 0)
        self.assertAlmostEqual(window.region[1], 0.9, places=2)

    def test_parse_region(self):
        self.assertEqual(S.parse_region("0.12,0.45"), (0.12, 0.45))
        with self.assertRaises(ValueError):
            S.parse_region("0.8,0.2")

    def test_all_heights_and_durations_share_locked_speed(self):
        locked = S.DEFAULT_SCROLL_VIEWPORTS_PER_SEC
        render_h = 2160
        speeds = []
        for width in (800, 1000, 1920):
            for height in (1400, 2000, 3266, 5331, 9000):
                for duration in (3.0, 5.0, 7.0, 15.0):
                    window = S.compute_scroll_window(width, height, 3840, render_h, duration)
                    if not window.can_scroll:
                        continue
                    self.assertAlmostEqual(window.viewports_per_sec, locked, places=5)
                    speeds.append(S.locked_scroll_pixels_per_sec(render_h, window.viewports_per_sec))
        self.assertGreater(len(speeds), 20)
        self.assertEqual(len(set(round(value, 6) for value in speeds)), 1)

    def test_overlay_speed_term_ignores_travel_distance(self):
        pps = S.locked_scroll_pixels_per_sec(2160)
        slow = S.scroll_overlay_y(80, pps)
        long = S.scroll_overlay_y(8000, pps)
        term = f"{pps:.6f}*t"
        self.assertIn(term, slow)
        self.assertIn(term, long)


class ProbeCliTests(unittest.TestCase):
    def test_probe_json_on_real_image_if_present(self):
        image = Path(
            ""
            "tall.jpg"
        )
        if not image.is_file():
            self.skipTest("sample long poster not on this machine")
        helper = Path(__file__).parents[1] / "helpers" / "stable_motion.py"
        result = subprocess.run(
            [sys.executable, str(helper), str(image), "--mode", "scroll", "--duration", "7", "--probe"],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["cropped"])
        self.assertLess(payload["crop_h"], payload["source_h"])
        self.assertAlmostEqual(payload["viewports_per_sec"], S.DEFAULT_SCROLL_VIEWPORTS_PER_SEC, places=2)
        self.assertAlmostEqual(payload["locked_vps"], S.DEFAULT_SCROLL_VIEWPORTS_PER_SEC, places=2)
        self.assertLess(payload["hold_s"], 0.2)


if __name__ == "__main__":
    unittest.main()
