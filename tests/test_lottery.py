from pathlib import Path
import json
import io
import sys
import shutil
import copy
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]))

from helpers import lottery_cards as cards
from helpers import lottery_common as common
from helpers import lottery_templates as templates
from helpers import lottery_scene as scene
from helpers import lottery_remotion as remotion
from helpers import lottery_goods as goods
from helpers.ad_subtitles import ad_force_style


# 功能：创建可核验的最小奖池；输入：图片路径；返回：含真实哈希的测试清单。
def sample_goods(path: Path) -> dict:
    config = templates.load_template().config
    return {"kind": "magic", "item_id": "1", "name": "角色系列", "ready_for_render": True, "issues": [],
            "prizes": [{"id": "magic:1", "sub_sku_ids": ["1"], "tier": "超神款", "name": "完整商品名称",
                        "image_path": str(path), "reference_price": None,
                        "image_quality": common.assess_image(path, "magic", (880, 920), config)}]}


class SourceTests(unittest.TestCase):
    def test_numeric_id_needs_kind_and_url_kind_must_agree(self):
        with self.assertRaises(ValueError):
            goods.parse_source("12345")
        url = "https://mall.bilibili.com/neul-next/index.html?page=ichiban_detail&itemsId=12345"
        self.assertEqual(goods.parse_source(url)[0:2], ("12345", "ichiban"))
        with self.assertRaises(ValueError):
            goods.parse_source(url, "magic")
        with self.assertRaises(ValueError):
            goods.parse_source(url + "&itemsId=2")

    def test_api_error_and_null_data_fail(self):
        for payload in [{"code": 81100001, "message": "商品不存在"}, {"code": 0, "data": None}]:
            session = Mock()
            session.request.return_value.json.return_value = payload
            with self.assertRaises(RuntimeError):
                goods.request_json(session, "GET", goods.MAGIC_INFO, {"itemsId": 1})

    def test_failed_refresh_cannot_leave_previous_manifest_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "edit"
            manifest = root / "lottery" / "1" / "goods.json"
            common.write_json(manifest, {"ready_for_render": True, "prizes": ["old"]})
            with patch.object(goods, "request_json", side_effect=RuntimeError("接口错误")):
                with self.assertRaises(RuntimeError):
                    goods.collect_goods("1", "magic", root)
            current = json.loads(manifest.read_text())
            self.assertFalse(current["ready_for_render"])
            self.assertTrue(current["issues"])


class CollectorScriptTests(unittest.TestCase):
    def test_magic_script_collects_pool_activities_originals_and_quality(self):
        pool = {"code": 0, "data": {"itemsId": 1, "name": "测试奖池", "price": "10", "subSkuList": [
            {"subSkuId": 11, "subSkuItemsId": 99, "name": "角色甲", "imageUrl": "//i0.hdslb.com/original.png", "type": 3, "subSkuPrice": "100"},
            {"subSkuId": 12, "subSkuItemsId": 99, "name": "角色乙", "imageUrl": "//i0.hdslb.com/original.png", "type": 3}],
            "drawSliceInfo": {"probabilityInfos": [{"type": 3, "probabilityTag": "超神款"}]}}}
        activity = {"code": 0, "data": {"activity": {"inActivity": True}, "demogorgonItems": {"demogorgonSubSkuIdList": [11]}}}
        session = Mock(headers={})
        responses = [Mock(), Mock(), Mock()]
        for response, payload in zip(responses, [pool, {"code": 0, "data": {}}, activity]):
            response.json.return_value = payload
        session.request.side_effect = responses
        image = io.BytesIO()
        Image.new("RGBA", (900, 900), (255, 0, 0, 255)).save(image, format="PNG")
        with tempfile.TemporaryDirectory() as directory, patch.object(goods.requests, "Session", return_value=session), patch.object(goods.requests, "get", return_value=Mock(content=image.getvalue())) as download:
            manifest_path = goods.collect_goods("1", "magic", Path(directory) / "edit")
            manifest = json.loads(manifest_path.read_text())
            self.assertTrue(manifest["ready_for_render"])
            self.assertEqual([p["tier"] for p in manifest["prizes"]], ["魔王款", "超神款"])
            self.assertEqual(manifest["draw_price"]["source_field"], "price")
            self.assertEqual(manifest["prizes"][0]["reference_price"]["source_field"], "subSkuPrice")
            self.assertIsNone(manifest["prizes"][1]["reference_price"])
            self.assertEqual(len(list((manifest_path.parent / "raw").glob("*.json"))), 3)
            self.assertEqual(json.loads((manifest_path.parent / "raw/goods.json").read_text()), pool)
            self.assertTrue(all(Path(p["image_path"]).is_file() for p in manifest["prizes"]))
            self.assertEqual(json.loads((manifest_path.parent / "image_quality.json").read_text())[0]["source_size"], [900, 900])
            self.assertTrue(all(call.args[0] == 'https://i0.hdslb.com/original.png' for call in download.call_args_list))
        self.assertEqual([(call.args[0], call.args[1]) for call in session.request.call_args_list], [
            ("GET", goods.ORIGIN + goods.MAGIC_INFO), ("GET", goods.ORIGIN + goods.MAGIC_ACTIVITY), ("POST", goods.ORIGIN + goods.MAGIC_DEMOGORGON)])
        self.assertEqual(session.request.call_args_list[2].kwargs["json"], {"itemsId": 1})
        self.assertEqual(session.headers["User-Agent"], goods.MOBILE_UA)

    def test_ichiban_script_posts_required_payload_and_retains_last_and_sold_out(self):
        payload = {"code": 0, "data": {"itemsId": 2, "name": "测试一番赏", "price": "78", "boxId": 1, "skuBoxGroupList": [
            {"groupId": 1, "groupName": "LAST赏", "img": "//i0.hdslb.com/original.jpg", "stock": 1,
             "originOdds": "购买最后一张获得", "skuBoxGroupDetailDTOList": [{"subSkuId": 21}]},
            {"groupId": 2, "groupName": "A赏", "img": "//i0.hdslb.com/original.jpg", "stock": 0,
             "skuBoxGroupDetailDTOList": [{"subSkuId": 22}]}]}}
        session = Mock(headers={})
        session.request.return_value.json.return_value = payload
        image = io.BytesIO()
        Image.new("RGB", (800, 800), "white").save(image, format="JPEG")
        with tempfile.TemporaryDirectory() as directory, patch.object(goods.requests, "Session", return_value=session), patch.object(goods.requests, "get", return_value=Mock(content=image.getvalue())):
            path = goods.collect_goods("2", "ichiban", Path(directory) / "edit")
            manifest = json.loads(path.read_text())
            self.assertTrue(manifest["ready_for_render"])
            self.assertEqual([p["tier"] for p in manifest["prizes"]], ["Last赏", "A赏"])
            self.assertEqual(manifest["prizes"][0]["acquisition_condition"], "购买最后一张获得")
            self.assertEqual(manifest["prizes"][1]["stock"], 0)
            self.assertTrue(all(p["reference_price"] is None for p in manifest["prizes"]))
        session.request.assert_called_once_with("POST", goods.ORIGIN + goods.ICHIBAN_INFO, timeout=30,
                                                json={"itemsId": 2, "boxId": 0, "skuId": "", "switchType": 1})

    def test_cli_incomplete_data_returns_nonzero_until_issues_are_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "goods.json"
            for ready, issues, expected in [(False, ["奖级缺失"], 2), (True, ["活动奖缺失"], 2), (True, [], 0)]:
                common.write_json(path, {"ready_for_render": ready, "issues": issues})
                with self.subTest(ready=ready, issues=issues), patch.object(sys, "argv", ["lottery_goods.py", "1", "--kind", "magic", "--edit-dir", str(Path(directory) / "edit")]), patch.object(goods, "collect_goods", return_value=path):
                    self.assertEqual(goods.main(), expected)


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.pool = {"subSkuList": [
            {"subSkuId": 1, "subSkuItemsId": 99, "name": "角色甲", "imageUrl": "//i0.hdslb.com/a.png", "type": 3, "subSkuPrice": "100"},
            {"subSkuId": 2, "subSkuItemsId": 99, "name": "角色乙", "imageUrl": "//i0.hdslb.com/b.png", "type": 3, "subSkuPrice": None}],
            "drawSliceInfo": {"probabilityInfos": [{"type": 3, "probability": "【超神款】：概率为【0.33%】"}]}}

    def test_child_skus_of_same_product_and_missing_price_are_preserved(self):
        prizes, issues = goods.normalize_magic(self.pool, {})
        self.assertFalse(issues)
        self.assertEqual(len(prizes), 2)
        self.assertEqual(prizes[0]["item_id"], prizes[1]["item_id"])
        self.assertNotEqual(prizes[0]["id"], prizes[1]["id"])
        self.assertEqual(prizes[0]["reference_price"]["amount"], "100")
        self.assertIsNone(prizes[1]["reference_price"])

    def test_active_demon_overrides_tier_and_missing_demon_blocks(self):
        activity = {"activity": {"inActivity": True}, "demogorgonItems": {"demogorgonSubSkuIdList": [1, 404]}}
        prizes, issues = goods.normalize_magic(self.pool, activity)
        self.assertEqual(prizes[0]["tier"], "魔王款")
        self.assertTrue(prizes[0]["is_activity_prize"])
        self.assertIn("404", issues[0])
        activity["activity"]["inActivity"] = False
        prizes, issues = goods.normalize_magic(self.pool, activity)
        self.assertFalse(issues)
        self.assertEqual(prizes[0]["tier"], "超神款")

    def test_unknown_type_is_visible_and_requires_verification(self):
        self.pool["subSkuList"][0]["type"] = 42
        prizes, issues = goods.normalize_magic(self.pool, {})
        self.assertEqual(prizes[0]["tier_raw"], 42)
        self.assertTrue(issues)

    def test_last_condition_and_sold_out_tier_are_retained_without_draw_price(self):
        pool = {"itemsId": 1, "boxId": 24, "skuBoxGroupList": [
            {"groupId": 1, "groupName": "LAST赏", "name": "LAST赏", "img": "//i0.hdslb.com/a.jpg", "price": "78", "stock": 1,
             "originOdds": "收到最后一件赏品时附赠，不售卖", "skuBoxGroupDetailDTOList": [{"subSkuId": 10}]},
            {"groupId": 2, "groupName": "A赏", "img": "//i0.hdslb.com/b.jpg", "price": "78", "stock": 0,
             "skuBoxGroupDetailDTOList": [{"subSkuId": 11}, {"subSkuId": 12}]}]}
        prizes = goods.normalize_ichiban(pool)
        self.assertEqual(prizes[0]["tier"], "Last赏")
        self.assertIn("最后", prizes[0]["acquisition_condition"])
        self.assertEqual(prizes[1]["stock"], 0)
        self.assertEqual(prizes[1]["sub_sku_ids"], ["11", "12"])
        self.assertTrue(all(p["reference_price"] is None for p in prizes))


class ImageAndCardTests(unittest.TestCase):
    def test_transparent_padding_does_not_count_as_subject_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.png"
            image = Image.new("RGBA", (1280, 1280))
            image.paste((255, 0, 0, 255), (400, 400, 700, 700))
            image.save(path)
            quality = common.assess_image(path, "magic", (880, 920), templates.load_template().config)
            self.assertEqual(quality["subject_size"], [300, 300])
            self.assertEqual(quality["display_size"], [300, 300])
            self.assertEqual(quality["actual_scale"], 1)
            self.assertIn("禁止放大", quality["action"])

    def test_actual_format_and_ichiban_width_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jpeg-with-png-extension.png"
            Image.new("RGB", (1280, 1280), "white").save(path, format="JPEG")
            quality = common.assess_image(path, "ichiban", (880, 920), templates.load_template().config)
            self.assertEqual(quality["format"], "JPEG")
            self.assertEqual(quality["display_size"], [800, 800])

    def test_card_hides_missing_price_keeps_name_and_detects_replaced_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "image.png"
            Image.new("RGB", (800, 800), "white").save(path)
            manifest = sample_goods(path)
            props, report = scene.prepare_scene(manifest, manifest["prizes"], root / "public", templates.load_template().config, 2)
            self.assertEqual(props["items"][0]["name"], "完整商品名称")
            self.assertIsNone(props["items"][0]["price"])
            self.assertEqual(report["center_axis"], 540)
            box = props["items"][0]["nameBox"]
            self.assertEqual(box[0] + box[2] / 2, 540)
            Image.new("RGB", (800, 800), "black").save(path)
            with self.assertRaisesRegex(ValueError, "发生变化"):
                scene.prepare_scene(manifest, manifest["prizes"], root / "public", templates.load_template().config, 2)

    def test_grid_regions_leave_space_before_subtitles_and_between_rows(self):
        for count in [2, 3, 4]:
            regions = scene.card_regions(count, templates.load_template().config)
            for region in regions:
                for key in ["image", "name", "price"]:
                    x, y, width, height = region[key]
                    self.assertGreaterEqual(x, 72)
                    self.assertLessEqual(x + width, 1008)
                    self.assertLessEqual(y + height, 1600)
            if count == 3:
                x, _, width, _ = regions[-1]["image"]
                self.assertEqual(x + width / 2, 540)
            if count == 4:
                self.assertGreater(regions[2]["image"][1], regions[0]["price"][1] + regions[0]["price"][3])

    def test_frontend_project_preserves_authored_user_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "edit"
            with patch.object(remotion, "ensure_dependencies"):
                project = remotion.prepare_project(root, templates.load_template())
                component = project / "src/templates/default/PrizeStage.tsx"
                edited = component.read_text() + "\n// 用户调整灯光\n"
                component.write_text(edited)
                remotion.prepare_project(root, templates.load_template())
                self.assertEqual(component.read_text(), edited)

    def test_selection_rejects_foreign_identity_and_mixed_tiers(self):
        manifest = {"kind": "magic", "ready_for_render": True, "prizes": [
            {"id": "1", "tier": "欧皇款", "name": "甲", "sub_sku_ids": [1]},
            {"id": "2", "tier": "普通款", "name": "乙", "sub_sku_ids": [2]}]}
        for ids in [["404"], ["1", "2"], ["1", "1"]]:
            with self.assertRaises(ValueError):
                scene.select_prizes(manifest, ids)

    def test_new_tiers_get_distinct_stable_colors(self):
        prizes = [{"tier": "H赏"}, {"tier": "I赏"}, {"tier": "A赏"}, {"tier": "H赏"}]
        palette = scene.tier_palette(prizes, templates.load_template().config)
        self.assertNotEqual(palette["H赏"], palette["I赏"])
        self.assertEqual(palette, scene.tier_palette(list(reversed(prizes)), templates.load_template().config))

    def test_draw_price_is_rejected_and_fractional_reference_price_preserved(self):
        self.assertIsNone(scene.price_text(None))
        price = goods.reference_price("78", "price", goods.ICHIBAN_INFO)
        with self.assertRaises(ValueError):
            scene.price_text(price)
        self.assertEqual(scene.price_text(goods.reference_price("109.50", "subSkuPrice", goods.MAGIC_INFO)), "参考价 ¥109.5")


class CrossPlatformRuntimeTests(unittest.TestCase):
    def test_browser_reuse_requires_matching_version_and_platform(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project, peer = root / "anime", root / "default"
            manifest = "node_modules/@remotion/cli/package.json"
            common.write_json(project / manifest, {"version": "4.0.534"})
            common.write_json(peer / manifest, {"version": "4.0.534"})
            cache = peer / "node_modules/.remotion/chrome-headless-shell"
            binary = cache / "mac-arm64/chrome-headless-shell-mac-arm64/chrome-headless-shell"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"test browser")
            with patch.object(remotion.sys, "platform", "darwin"), patch.object(remotion.platform, "machine", return_value="arm64"):
                self.assertEqual(remotion.browser_arguments(project), [f"--browser-executable={binary.resolve()}"])
                common.write_json(peer / manifest, {"version": "4.0.535"})
                self.assertEqual(remotion.browser_arguments(project), [])
            common.write_json(peer / manifest, {"version": "4.0.534"})
            with patch.object(remotion.sys, "platform", "win32"):
                self.assertEqual(remotion.browser_arguments(project), [])
                windows = cache / "win64/chrome-headless-shell-win64/chrome-headless-shell.exe"
                windows.parent.mkdir(parents=True)
                windows.write_bytes(b"test browser")
                self.assertEqual(remotion.browser_arguments(project), [f"--browser-executable={windows.resolve()}"])

    def test_windows_font_uses_actual_windows_directory_and_prefers_bold(self):
        with tempfile.TemporaryDirectory() as directory:
            fonts = Path(directory) / "Fonts"
            fonts.mkdir()
            bold = fonts / "msyhbd.ttc"
            regular = fonts / "msyh.ttc"
            bold.touch(); regular.touch()
            with patch.object(remotion.sys, "platform", "win32"), patch.dict(remotion.os.environ, {"WINDIR": directory}):
                self.assertEqual(remotion.resolve_font(None), bold.resolve())
                self.assertEqual(remotion.resolve_font(regular), regular.resolve())
                with self.assertRaises(FileNotFoundError):
                    remotion.resolve_font(fonts / "missing.ttf")

    def test_windows_npm_launcher_invokes_js_with_node_and_preserves_spaced_paths(self):
        with tempfile.TemporaryDirectory(prefix="node runtime ") as directory:
            root = Path(directory)
            npm = root / "npm.cmd"
            node = root / "node.exe"
            npm.touch(); node.touch()
            entry = root / "node_modules/npm/bin/npm-cli.js"
            entry.parent.mkdir(parents=True)
            entry.touch()
            with patch.object(remotion.shutil, "which", side_effect=lambda name: str(node if name == "node" else npm)):
                self.assertEqual(remotion.npm_command(), [str(node), str(entry.resolve())])
                entry.unlink()
                with self.assertRaises(FileNotFoundError):
                    remotion.npm_command()

    def test_posix_npm_executable_does_not_need_a_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            npm = Path(directory) / "npm"
            npm.touch()
            with patch.object(remotion.shutil, "which", return_value=str(npm)):
                self.assertEqual(remotion.npm_command(), [str(npm)])

    def test_remotion_uses_package_entry_instead_of_platform_bin_wrapper(self):
        with tempfile.TemporaryDirectory(prefix="prize project ") as directory:
            project = Path(directory)
            root = project / "node_modules/@remotion/cli"
            root.mkdir(parents=True)
            entry = root / "cli.js"
            entry.touch()
            common.write_json(root / "package.json", {"bin": {"remotion": "cli.js"}})
            with patch.object(remotion.shutil, "which", return_value="node-executable"):
                self.assertEqual(remotion.remotion_command(project), ["node-executable", str(entry.resolve())])
                common.write_json(root / "package.json", {"bin": {"remotion": "../../outside.js"}})
                with self.assertRaises(FileNotFoundError):
                    remotion.remotion_command(project)
            with patch.object(remotion.shutil, "which", return_value=None):
                with self.assertRaises(FileNotFoundError):
                    remotion.node_executable()


class PortraitSubtitleTests(unittest.TestCase):
    def test_explicit_profile_has_correct_geometry_and_default_is_unchanged(self):
        portrait = ad_force_style(1080, 1920, profile="lottery-portrait")
        for token in ["PlayResX=1080", "PlayResY=1920", "FontSize=64", "MarginL=72", "MarginR=72", "MarginV=180"]:
            self.assertIn(token, portrait)
        self.assertIn("FontSize=72", ad_force_style(1920, 1080))
        self.assertIn("FontSize=43", ad_force_style(720, 1280, profile="lottery-portrait"))
        with self.assertRaises(ValueError):
            ad_force_style(1920, 1080, profile="lottery-portrait")


class TemplateRegistryTests(unittest.TestCase):
    def test_omitted_template_is_default_and_unknown_name_never_falls_back(self):
        self.assertEqual(templates.load_template().id, "default")
        for identity in ["missing", "../default", "Default", "default\n"]:
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                templates.load_template(identity)

    def test_new_template_changes_scene_without_touching_shared_code_and_isolates_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "assets"
            shutil.copytree(templates.ASSETS_ROOT, assets)
            alternative = assets / "templates/alternate"
            shutil.copytree(assets / "templates/default", alternative)
            config = json.loads((alternative / "template.json").read_text())
            config.update({"id": "alternate", "name": "测试模板", "motion_pixels": 0})
            config["tier_colors"]["超神款"] = "#00FF99"
            config["layouts"]["1"][0]["image"] = [200, 500, 680, 800]
            common.write_json(alternative / "template.json", config)
            (alternative / "public").mkdir()
            (alternative / "public/background.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            available = templates.list_templates(assets)
            identities = [t.id for t in available]
            self.assertIn("alternate", identities)
            self.assertIn("default", identities)
            self.assertEqual(identities, sorted(identities))
            first, second = templates.load_template("default", assets), templates.load_template("alternate", assets)
            image = root / "image.png"
            Image.new("RGB", (800, 800), "white").save(image)
            manifest = sample_goods(image)
            before, _ = scene.prepare_scene(manifest, manifest["prizes"], root / "a", first.config, 2)
            after, _ = scene.prepare_scene(manifest, manifest["prizes"], root / "b", second.config, 2)
            self.assertEqual(after["templateId"], "alternate")
            self.assertEqual(after["accent"], "#00FF99")
            self.assertEqual(after["items"][0]["imageBox"], [200, 500, 680, 800])
            self.assertNotEqual(before["items"][0]["width"], after["items"][0]["width"])
            with patch.object(remotion, "ensure_dependencies"):
                a = remotion.prepare_project(root / "edit", first, assets)
                edited = a / "src/templates/default/PrizeStage.tsx"
                edited.write_text(edited.read_text() + "\n// 保留我的修改\n")
                authored = edited.read_bytes()
                b = remotion.prepare_project(root / "edit", second, assets)
                remotion.prepare_project(root / "edit", first, assets)
            self.assertNotEqual(a, b)
            self.assertEqual(edited.read_bytes(), authored)
            self.assertIn('templates/alternate/PrizeStage', (b / "src/SelectedTemplate.ts").read_text())
            self.assertFalse((b / "src/templates/default").exists())
            self.assertTrue((b / "public/templates/alternate/background.svg").is_file())
            self.assertFalse((a / "public/templates/alternate").exists())

    def test_invalid_manifest_geometry_entry_and_shared_override_block(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory) / "assets"
            shutil.copytree(templates.ASSETS_ROOT, assets)
            path = assets / "templates/default/template.json"
            original = json.loads(path.read_text())
            invalid = []
            bad = copy.deepcopy(original); bad["layouts"]["1"][0]["price"][1] = 1700; invalid.append(bad)
            bad = copy.deepcopy(original); bad["layouts"]["4"] = []; invalid.append(bad)
            bad = copy.deepcopy(original); bad["entrypoint"] = "../../shared/src/Root.tsx"; invalid.append(bad)
            bad = copy.deepcopy(original); bad["motion_pixels"] = 13; invalid.append(bad)
            bad = copy.deepcopy(original); bad["tier_colors"]["A赏"] = "red"; invalid.append(bad)
            bad = copy.deepcopy(original); bad["width"] = 720; invalid.append(bad)
            for index, manifest in enumerate(invalid):
                with self.subTest(index=index), self.assertRaises(ValueError):
                    common.write_json(path, manifest)
                    templates.load_template("default", assets)

    def test_template_list_does_not_require_goods_or_start_rendering(self):
        with patch.object(sys, "argv", ["lottery_cards.py", "--list-templates"]), patch.object(cards, "render_card") as render:
            self.assertEqual(cards.main(), 0)
            render.assert_not_called()

    def test_cli_uses_default_and_passes_explicit_selection(self):
        arguments = ["lottery_cards.py", "goods.json", "--prize-id", "magic:1", "--duration", "2", "-o", "preview.mp4"]
        for selection in [None, "alternate"]:
            with self.subTest(selection=selection), patch.object(sys, "argv", arguments + (["--template", selection] if selection else [])), patch.object(cards, "render_card") as render:
                self.assertEqual(cards.main(), 0)
                self.assertEqual(render.call_args.args[-1], selection or "default")


if __name__ == "__main__":
    unittest.main()
