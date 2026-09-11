import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "bili-cover" / "scripts" / "crop_cover43.py"
sys.path.insert(0, str(SCRIPT.parent))

import crop_cover43 as C  # noqa: E402


class BoxTests(unittest.TestCase):
    def test_1920x1080_crops_full_height_center(self):
        self.assertEqual(C.crop_4x3_box(1920, 1080, 0.5), (240, 0, 1680, 1080))

    def test_continuous_crop_center_is_not_limited_to_three_anchors(self):
        self.assertEqual(C.crop_4x3_box(1920, 1080, 0.55), (336, 0, 1776, 1080))

    def test_continuous_crop_center_is_bounded_inside_canvas(self):
        self.assertEqual(C.crop_4x3_box(1920, 1080, 0.99), (480, 0, 1920, 1080))
        self.assertEqual(C.crop_4x3_box(1920, 1080, 0.01), (0, 0, 1440, 1080))

    def test_crop_center_outside_unit_range_is_rejected(self):
        for bad in (-0.01, 1.01):
            with self.assertRaises(ValueError):
                C.crop_4x3_box(1920, 1080, bad)

    def test_1376x768_stays_inside_canvas(self):
        left, top, right, bottom = C.crop_4x3_box(1376, 768, 0.5)
        self.assertEqual((top, bottom), (0, 768))
        self.assertEqual(right - left, 1024)
        self.assertGreaterEqual(left, 0)
        self.assertLessEqual(right, 1376)

    def test_default_output_uses_cover43_name(self):
        self.assertEqual(
            C.default_output_path(Path("/tmp/edit/cover.jpg")),
            Path("/tmp/edit/cover-4x3.jpg"),
        )


class CropTests(unittest.TestCase):
    def test_crop_drops_16x9_side_margins(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "cover.png"
            image = Image.new("RGB", (1920, 1080), (255, 0, 0))
            image.paste(Image.new("RGB", (1440, 1080), (0, 255, 0)), (240, 0))
            image.save(source)
            result = C.crop_cover43(source, Path(tmp) / "cover-4x3.jpg", 0.5)
            self.assertEqual(result["crop"], [1440, 1080])
            self.assertEqual(result["box"], [240, 0, 1680, 1080])
            with Image.open(result["output"]) as cropped:
                self.assertEqual(cropped.size, (1440, 1080))
                for xy in ((0, 0), (1439, 1079)):
                    pixel = cropped.getpixel(xy)[:3]
                    self.assertLess(pixel[0], 16)
                    self.assertGreater(pixel[1], 240)
                    self.assertLess(pixel[2], 16)

    def test_rejects_non_16x9(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "cover.jpg"
            Image.new("RGB", (1000, 1000), (10, 10, 10)).save(source, format="JPEG")
            with self.assertRaises(SystemExit):
                C.crop_cover43(source, Path(tmp) / "cover-4x3.jpg", 0.5)

    def test_cli_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "cover.jpg"
            Image.new("RGB", (1920, 1080), (20, 20, 20)).save(source, format="JPEG")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source), "--crop-center-x", "0.5"],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["success"])
            self.assertEqual(Path(payload["output"]).name, "cover-4x3.jpg")
            self.assertTrue(Path(payload["output"]).is_file())

    def test_result_reports_applied_center_after_clamping(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "cover.jpg"
            Image.new("RGB", (1920, 1080), (20, 20, 20)).save(source, format="JPEG")
            result = C.crop_cover43(source, Path(tmp) / "cover-4x3.jpg", 0.99)
            self.assertEqual(result["crop_center_x"], 0.99)
            self.assertEqual(result["box"], [480, 0, 1920, 1080])
            self.assertAlmostEqual(result["applied_center_x"], 0.625, places=3)

    def test_cli_requires_llm_center_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "cover.jpg"
            Image.new("RGB", (1920, 1080), (20, 20, 20)).save(source, format="JPEG")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
