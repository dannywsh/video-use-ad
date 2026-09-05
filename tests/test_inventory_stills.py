import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1] / "helpers"))
import inventory_stills as I  # noqa: E402


class SizeTests(unittest.TestCase):
    def test_poster_is_not_tall(self):
        self.assertFalse(I.is_tall(1000, 1333))

    def test_long_infographic_is_tall(self):
        self.assertTrue(I.is_tall(1000, 3266))


class RegionTests(unittest.TestCase):
    def test_region_fractions_match_pixels(self):
        self.assertEqual(I.region_from_pixels(430, 760, 3266), [0.1317, 0.2327])

    def test_rejects_empty_span(self):
        with self.assertRaises(ValueError):
            I.region_from_pixels(10, 10, 100)


class WindowParseTests(unittest.TestCase):
    def test_parse_window(self):
        name, source, y0, y1 = I.parse_window("01_title.jpg,detail.jpeg,430,760")
        self.assertEqual(name, "01_title.jpg")
        self.assertEqual(source, "detail.jpeg")
        self.assertEqual((y0, y1), (430, 760))

    def test_source_may_contain_commas(self):
        _, source, y0, y1 = I.parse_window("out.jpg,weird,name.jpeg,10,20")
        self.assertEqual(source, "weird,name.jpeg")
        self.assertEqual((y0, y1), (10, 20))


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

    def test_generic_detail_heading_is_product(self):
        self.assertEqual(
            I.suggest_role("商品详情 卖点 产品参数"),
            I.ROLE_PRODUCT,
        )

    def test_guest_heading_beats_admin_footer(self):
        self.assertEqual(
            I.suggest_role("专场嘉宾 入场须知"),
            I.ROLE_CAST_OR_SCHEDULE,
        )

    def test_empty_needs_review(self):
        self.assertEqual(I.suggest_role("   "), I.ROLE_NEEDS_REVIEW)


class OverviewCropTests(unittest.TestCase):
    def test_overview_is_skinny_with_source_height_ticks(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "tall.png"
            Image.new("RGB", (400, 1200), (20, 40, 80)).save(src)
            dest = Path(tmp) / "tall_overview.jpg"
            meta = I.export_overview(src, dest, width=360, tick=200)
            self.assertTrue(dest.is_file())
            self.assertEqual(meta["width"], 360)
            self.assertEqual(meta["height"], 1080)
            self.assertEqual(meta["source_height"], 1200)

    def test_crop_is_full_width_and_not_downscaled(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "tall.png"
            Image.new("RGB", (800, 2000), (30, 80, 40)).save(src)
            dest = Path(tmp) / "unit.jpg"
            meta = I.crop_window(src, dest, 400, 980, pad=0)
            self.assertEqual(meta["width"], 800)
            self.assertEqual(meta["height"], 580)
            self.assertEqual(meta["y0"], 400)
            self.assertEqual(meta["y1"], 980)
            with Image.open(dest) as crop:
                self.assertEqual(crop.size, (800, 580))

    def test_crop_pads_both_ends_so_goods_are_not_clipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "tall.png"
            Image.new("RGB", (800, 2000), (30, 80, 40)).save(src)
            dest = Path(tmp) / "unit.jpg"
            meta = I.crop_window(src, dest, 400, 980, pad=80)
            self.assertEqual(meta["y0"], 320)
            self.assertEqual(meta["y1"], 1060)
            self.assertEqual(meta["requested_y0"], 400)
            self.assertEqual(meta["requested_y1"], 980)
            self.assertEqual(meta["pad"], 80)

    def test_crop_pad_clamps_to_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "tall.png"
            Image.new("RGB", (400, 500), (0, 0, 0)).save(src)
            dest = Path(tmp) / "unit.jpg"
            meta = I.crop_window(src, dest, 10, 480, pad=80)
            self.assertEqual(meta["y0"], 0)
            self.assertEqual(meta["y1"], 500)

    def test_crop_rejects_inverted_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "tall.png"
            Image.new("RGB", (400, 1200), (0, 0, 0)).save(src)
            with self.assertRaises(ValueError):
                I.crop_window(src, Path(tmp) / "bad.jpg", 500, 100)


class InventoryCliTests(unittest.TestCase):
    def test_exports_overview_for_tall_fixture_not_equal_bands(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "raw"
            overview_dir = Path(tmp) / "overview"
            folder.mkdir()
            Image.new("RGB", (400, 1200), (20, 40, 80)).save(folder / "tall.png")
            Image.new("RGB", (800, 800), (200, 100, 50)).save(folder / "square.jpg")
            helper = Path(__file__).parents[1] / "helpers" / "inventory_stills.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(helper),
                    str(folder),
                    "--overview-dir",
                    str(overview_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            by_name = {item["name"]: item for item in payload["stills"]}
            self.assertTrue(by_name["tall.png"]["tall"])
            self.assertIsNotNone(by_name["tall.png"]["overview"])
            self.assertTrue((overview_dir / "tall_overview.jpg").is_file())
            self.assertFalse(list(overview_dir.glob("*_band_*.jpg")))
            self.assertFalse(by_name["square.jpg"]["tall"])
            self.assertIsNone(by_name["square.jpg"]["overview"])

    def test_crop_cli_writes_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "raw"
            out_dir = Path(tmp) / "crops"
            folder.mkdir()
            Image.new("RGB", (400, 1000), (10, 20, 30)).save(folder / "poster.jpeg")
            helper = Path(__file__).parents[1] / "helpers" / "inventory_stills.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(helper),
                    str(folder),
                    "--crop",
                    "--out-dir",
                    str(out_dir),
                    "--window",
                    "01_block.jpg,poster.jpeg,100,400",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            crop = payload["crops"][0]
            self.assertEqual(crop["requested_y0"], 100)
            self.assertEqual(crop["requested_y1"], 400)
            self.assertEqual(crop["y0"], 20)
            self.assertEqual(crop["y1"], 480)
            self.assertEqual(crop["pad"], I.CROP_PAD_PX)
            self.assertTrue((out_dir / "01_block.jpg").is_file())


if __name__ == "__main__":
    unittest.main()
