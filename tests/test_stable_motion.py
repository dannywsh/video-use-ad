import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

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

    def test_slightly_tall_image_stays_full_height_without_scroll(self):
        window = S.compute_scroll_window(1000, 700, 3840, 2160, 7.0)

        self.assertFalse(window.can_scroll)
        self.assertEqual(window.crop_h, 700)
        self.assertEqual(window.scroll_s, 0.0)
        self.assertEqual(window.hold_s, 7.0)

    def test_meaningfully_tall_image_still_scrolls(self):
        window = S.compute_scroll_window(1000, 720, 3840, 2160, 7.0)

        self.assertTrue(window.can_scroll)
        self.assertGreater(
            window.viewport_heights - 1,
            S.MIN_SCROLL_TRAVEL_VIEWPORTS,
        )

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


class PanPlanTests(unittest.TestCase):
    def test_wide_image_pans_right_at_locked_speed_then_holds(self):
        plan = S.compute_pan_plan(3000, 1080, 1920, 1080, 12.0)

        self.assertTrue(plan.can_pan)
        self.assertGreater(plan.travel, 0)
        self.assertEqual(plan.viewports_per_sec, S.DEFAULT_PAN_VIEWPORTS_PER_SEC)
        self.assertAlmostEqual(plan.pan_s, plan.travel / (1920 * 0.12))
        self.assertAlmostEqual(plan.hold_s, 12.0 - plan.pan_s)
        self.assertIn(f"min({plan.travel}\\,", S.pan_crop_x(plan.travel, 1920 * 0.12))

    def test_pan_speed_does_not_change_with_duration_or_image_width(self):
        short = S.compute_pan_plan(2600, 1080, 1920, 1080, 2.0)
        long = S.compute_pan_plan(4000, 1080, 1920, 1080, 10.0)

        self.assertEqual(short.viewports_per_sec, long.viewports_per_sec)
        self.assertEqual(
            S.locked_pan_pixels_per_sec(1920),
            S.DEFAULT_PAN_VIEWPORTS_PER_SEC * 1920,
        )

    def test_sixteen_by_nine_detail_image_uses_gentle_zoom_and_slow_pan(self):
        plan = S.compute_pan_plan(1920, 1080, 1920, 1080, 6.0)

        self.assertTrue(plan.can_pan)
        self.assertTrue(plan.detail_zoom)
        self.assertAlmostEqual(plan.zoom_factor, 1.18, places=2)
        self.assertEqual(plan.viewports_per_sec, S.DEFAULT_DETAIL_PAN_VIEWPORTS_PER_SEC)
        self.assertAlmostEqual(plan.pan_s, plan.travel / (1920 * 0.04))

    def test_narrow_image_still_falls_back_to_push(self):
        plan = S.compute_pan_plan(1600, 1080, 1920, 1080, 6.0)

        self.assertFalse(plan.can_pan)
        self.assertEqual(plan.travel, 0)
        self.assertEqual(plan.hold_s, 6.0)

    def test_natural_pan_threshold_is_fifteen_percent_of_output_width(self):
        below = S.compute_pan_plan(2207, 1080, 1920, 1080, 6.0)
        at_threshold = S.compute_pan_plan(2208, 1080, 1920, 1080, 6.0)

        self.assertTrue(below.can_pan)
        self.assertTrue(below.detail_zoom)
        self.assertGreater(below.zoom_factor, 1.0)
        self.assertTrue(at_threshold.can_pan)
        self.assertFalse(at_threshold.detail_zoom)
        self.assertEqual(at_threshold.travel, 288)

    def test_renderer_uses_push_when_pan_space_is_too_short(self):
        with (
            patch.object(S, "image_dimensions", return_value=(1600, 1080)),
            patch.object(S, "render_profile", return_value=S.RenderProfile(1, ("-c:v", "libx264", "-crf"))),
            patch.object(S, "render_push") as render_push,
        ):
            plan = S.render_pan_right(Path("source.jpg"), Path("out.mp4"), 6, 30, 1920, 1080, 17)

        self.assertFalse(plan.can_pan)
        render_push.assert_called_once()

    def test_cli_accepts_pan_right_mode(self):
        helper = Path(__file__).parents[1] / "helpers" / "stable_motion.py"
        result = subprocess.run(
            [sys.executable, str(helper), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("pan-right", result.stdout)

    def test_cli_rejects_unknown_mode(self):
        helper = Path(__file__).parents[1] / "helpers" / "stable_motion.py"
        result = subprocess.run(
            [sys.executable, str(helper), "missing.jpg", "--mode", "sideways", "--duration", "1"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)

    def test_pan_probe_reports_horizontal_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "wide.png"
            Image.new("RGB", (3000, 1080), (50, 60, 70)).save(image)
            helper = Path(__file__).parents[1] / "helpers" / "stable_motion.py"
            result = subprocess.run(
                [
                    sys.executable, str(helper), str(image), "--mode", "pan-right",
                    "--duration", "8", "--width", "320", "--height", "180", "--probe",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["can_pan"])
        self.assertGreater(payload["travel"], 0)
        self.assertEqual(payload["locked_vps"], S.DEFAULT_PAN_VIEWPORTS_PER_SEC)


class RenderProfileTests(unittest.TestCase):
    def test_macos_uses_reduced_supersampling_and_videotoolbox(self):
        profile = S.render_profile("Darwin")

        self.assertEqual(profile.supersample, S.MACOS_SUPERSAMPLE)
        self.assertEqual(
            S.encoder_args(profile, 17),
            ["-c:v", "h264_videotoolbox", "-b:v", S.MACOS_VIDEO_BITRATE],
        )

    def test_non_macos_retains_x264_and_two_times_supersampling(self):
        profile = S.render_profile("Linux")

        self.assertEqual(profile.supersample, S.DEFAULT_SUPERSAMPLE)
        self.assertEqual(
            S.encoder_args(profile, 17),
            ["-c:v", "libx264", "-crf", "17", "-preset", "medium"],
        )

    def test_push_foreground_reaches_viewport_height_at_max_zoom(self):
        self.assertAlmostEqual(S.PUSH_FOREGROUND_SCALE * S.PUSH_MAX_ZOOM, 1.0)


class ProbeCliTests(unittest.TestCase):
    def test_probe_json_on_tall_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "tall.jpg"
            Image.new("RGB", (800, 4000), (20, 40, 80)).save(image, quality=90)
            helper = Path(__file__).parents[1] / "helpers" / "stable_motion.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(helper),
                    str(image),
                    "--mode",
                    "scroll",
                    "--duration",
                    "7",
                    "--probe",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["cropped"])
        self.assertLess(payload["crop_h"], payload["source_h"])
        self.assertAlmostEqual(
            payload["viewports_per_sec"], S.DEFAULT_SCROLL_VIEWPORTS_PER_SEC, places=2
        )
        self.assertAlmostEqual(
            payload["locked_vps"], S.DEFAULT_SCROLL_VIEWPORTS_PER_SEC, places=2
        )
        self.assertLess(payload["hold_s"], 0.2)


if __name__ == "__main__":
    unittest.main()
