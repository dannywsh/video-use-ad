import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from helpers.biliup_goods import fetch_goods, write_goods_json


def test_fetch_goods_calls_biliup_search(tmp_path: Path):
    cookie = tmp_path / "cookies.json"
    cookie.write_text("{}", encoding="utf-8")
    payload = [{"itemId": "13666878", "goodsName": "示例商品", "detail": {"brand": "示例品牌"}}]

    class Completed:
        returncode = 0
        stdout = json.dumps(payload, ensure_ascii=False)
        stderr = ""

    with patch("helpers.biliup_goods._resolve_biliup", return_value="/usr/local/bin/biliup") as resolve, patch(
        "helpers.biliup_goods.subprocess.run", return_value=Completed()
    ) as run:
        assert fetch_goods("13666878", str(cookie), "biliup") == payload

    resolve.assert_called_once_with("biliup")
    assert run.call_args.args[0][-3:] == ["goods", "search", "13666878"]


def test_fetch_goods_ignores_ansi_coloured_log_prefix(tmp_path: Path):
    """biliup 会先往 stdout 打一条带 ANSI 颜色的 INFO 行，再输出 JSON。

    回归用例：剥 ANSI 前，日志里的 "\\x1b[2m" 会被当成 JSON 起始的 "["，
    导致所有 goods search 调用都解析失败。
    """
    cookie = tmp_path / "cookies.json"
    cookie.write_text("{}", encoding="utf-8")
    payload = [{"itemId": "13666269", "goodsName": "示例商品"}]
    log_line = "\x1b[2m2026-09-10 15:43:58\x1b[0m \x1b[32m INFO\x1b[0m \x1b[2mbiliup_cli::uploader\x1b[0m\x1b[2m:\x1b[0m user: 示例UP主\n"

    class Completed:
        returncode = 0
        stdout = log_line + json.dumps(payload, ensure_ascii=False)
        stderr = ""

    with patch("helpers.biliup_goods._resolve_biliup", return_value="/usr/local/bin/biliup"), patch(
        "helpers.biliup_goods.subprocess.run", return_value=Completed()
    ):
        assert fetch_goods("13666269", str(cookie), "biliup") == payload


def test_fetch_goods_rejects_output_without_json(tmp_path: Path):
    cookie = tmp_path / "cookies.json"
    cookie.write_text("{}", encoding="utf-8")

    class Completed:
        returncode = 0
        stdout = "2026-09-10 15:43:58  INFO biliup_cli::uploader: user: 示例UP主\n"
        stderr = ""

    with patch("helpers.biliup_goods._resolve_biliup", return_value="/usr/local/bin/biliup"), patch(
        "helpers.biliup_goods.subprocess.run", return_value=Completed()
    ):
        try:
            fetch_goods("13666269", str(cookie), "biliup")
        except RuntimeError as exc:
            assert "没有返回有效 JSON" in str(exc)
        else:
            raise AssertionError("没有 JSON 时应抛出 RuntimeError")


def test_write_goods_json_creates_parent_directory(tmp_path: Path):
    output = tmp_path / "edit" / "product_info.json"
    goods = [{"itemId": "1", "goodsName": "示例商品"}]

    assert write_goods_json(goods, str(output)) == output
    assert json.loads(output.read_text(encoding="utf-8")) == goods
