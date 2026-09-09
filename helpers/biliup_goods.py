#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 biliup goods search 获取宣传片使用的商品详情 JSON。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_biliup(binary: str) -> str:
    """解析 biliup 可执行文件路径。

    输入：命令名或可执行文件路径。返回：可执行路径；找不到时抛出错误。
    """
    resolved = shutil.which(binary) or (binary if Path(binary).is_file() else None)
    if not resolved:
        raise FileNotFoundError(
            f"找不到 biliup 可执行文件：{binary}。请用 --biliup-bin 指定 Release 二进制路径。"
        )
    return resolved


def fetch_goods(source: str, cookie: str, binary: str) -> list[dict]:
    """调用 biliup goods search 获取商品详情。

    输入：商品 itemId/URL、Cookie 文件路径和 biliup 二进制名。返回：商品结果列表。
    """
    if not cookie:
        raise ValueError("必须提供 --cookie 或 BILIUP_COOKIE，避免使用不确定的登录态。")
    cookie_path = Path(cookie).expanduser()
    if not cookie_path.is_file():
        raise FileNotFoundError(f"Cookie 文件不存在：{cookie_path}")
    command = [
        _resolve_biliup(binary),
        "-u",
        str(cookie_path),
        "goods",
        "search",
        source,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"biliup goods search 失败（退出码 {completed.returncode}）：{detail}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("biliup goods search 没有返回有效 JSON") from exc
    if not isinstance(result, list) or not result:
        raise RuntimeError("biliup goods search 返回空商品列表")
    if not all(isinstance(item, dict) for item in result):
        raise RuntimeError("biliup goods search 返回了非对象商品结果")
    return result


def write_goods_json(goods: list[dict], output: str) -> Path:
    """将商品详情写入当前宣传片的 edit 目录。

    输入：商品结果列表和输出 JSON 路径。返回：规范化后的输出路径。
    """
    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(goods, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    """解析命令行参数并获取商品详情。

    输入：命令行中的商品来源、Cookie、二进制和输出路径。返回：进程退出码。
    """
    parser = argparse.ArgumentParser(description="通过 biliup goods search 获取商品详情")
    parser.add_argument("source", help="会员购 itemId/URL 或票务详情页 URL")
    parser.add_argument("--cookie", default=os.environ.get("BILIUP_COOKIE"), help="Cookie JSON 路径")
    parser.add_argument("--biliup-bin", default=os.environ.get("BILIUP_BIN", "biliup"), help="biliup Release 二进制路径")
    parser.add_argument("--output", required=True, help="输出到 edit/product_info.json")
    args = parser.parse_args()
    try:
        goods = fetch_goods(args.source, args.cookie or "", args.biliup_bin)
        output = write_goods_json(goods, args.output)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    print(f"已写入 {output}（{len(goods)} 个商品结果）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
