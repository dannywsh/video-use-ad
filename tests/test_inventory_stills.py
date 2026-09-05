import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1] / "helpers"))
import inventory_stills as I  # noqa: E402


class BandPlanTests(unittest.TestCase):
    def test_poster_is_not_tall(self):
        self.assertFalse(I.is_tall(1000, 1333))
        self.assertEqual(I.plan_bands(1000, 1333), [])

    def test_long_infographic_covers_top_and_bottom(self):
        bands = I.plan_bands(1000, 3266)
        self.assertGreaterEqual(len(bands), 3)
        self.assertEqual(bands[0][0], 0)
        last_y, last_h, _, end = bands[-1]
        self.assertEqual(last_y + last_h, 3266)
        self.assertAlmostEqual(end, 1.0, places=3)
        self.assertLess(bands[0][2], bands[1][2])

    def test_region_fractions_match_pixels(self):
        height = 4000
        for y, h, start, end in I.plan_bands(800, height):
            self.assertEqual(start, y / height)
            self.assertEqual(end, (y + h) / height)


class RoleTests(unittest.TestCase):
    def test_entry_notice_is_dropped(self):
        self.assertEqual(
            I.suggest_role("观众购票及入场须知 退票规则 交通路线指南"),
            I.ROLE_ADMIN_DROP,
        )

    def test_guest_poster_is_kept_for_cast(self):
        self.assertEqual(
            I.suggest_role("页眉 日期 专场嘉宾 签售会 舞台活动"),
            I.ROLE_CAST_OR_SCHEDULE,
        )

    def test_bundle_is_product(self):
        self.assertEqual(
            I.suggest_role("周边礼包套票 套票包含 周边一览"),
            I.ROLE_PRODUCT,
        )

    def test_guest_heading_beats_admin_footer(self):
        self.assertEqual(
            I.suggest_role("专场嘉宾 入场须知"),
            I.ROLE_CAST_OR_SCHEDULE,
        )

    def test_empty_needs_review(self):
        self.assertEqual(I.suggest_role("   "), I.ROLE_NEEDS_REVIEW)


class InventoryCliTests(unittest.TestCase):
    def test_exports_bands_for_tall_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "raw"
            bands_dir = Path(tmp) / "bands"
            folder.mkdir()
            Image.new("RGB", (400, 1200), (20, 40, 80)).save(folder / "tall.png")
            Image.new("RGB", (800, 800), (200, 100, 50)).save(folder / "square.jpg")
            helper = Path(__file__).parents[1] / "helpers" / "inventory_stills.py"
            result = subprocess.run(
                [sys.executable, str(helper), str(folder), "--bands-dir", str(bands_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            by_name = {item["name"]: item for item in payload["stills"]}
            self.assertTrue(by_name["tall.png"]["tall"])
            self.assertGreaterEqual(len(by_name["tall.png"]["bands"]), 2)
            self.assertTrue((bands_dir / "tall_band_00.jpg").is_file())
            self.assertFalse(by_name["square.jpg"]["tall"])
            self.assertEqual(by_name["square.jpg"]["bands"], [])


if __name__ == "__main__":
    unittest.main()
