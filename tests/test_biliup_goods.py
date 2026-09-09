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


def test_write_goods_json_creates_parent_directory(tmp_path: Path):
    output = tmp_path / "edit" / "product_info.json"
    goods = [{"itemId": "1", "goodsName": "示例商品"}]

    assert write_goods_json(goods, str(output)) == output
    assert json.loads(output.read_text(encoding="utf-8")) == goods
