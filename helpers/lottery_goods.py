"""只读采集魔力赏／一番赏奖品、活动身份及原图质量。"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import io
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlparse

import requests
from PIL import Image

try:
    from .lottery_common import assess_image, prepare_edit, write_json
    from .lottery_templates import load_video_spec
except ImportError:
    from lottery_common import assess_image, prepare_edit, write_json
    from lottery_templates import load_video_spec

ORIGIN = "https://mall.bilibili.com"
MAGIC_INFO = "/magic-c-search/blind_box/info"
MAGIC_ACTIVITY = "/magic-c-search/blind_box/queryItemsActivity"
MAGIC_DEMOGORGON = "/mall-dayu/demogorgon/activity_info"
ICHIBAN_INFO = "/mall-ichiban-kuji/items/info"
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")


# 功能：验证商品来源和赏类型；输入：URL/ID、可选类型；返回：ID、类型、原始来源。
def parse_source(source: str, kind: str | None = None) -> tuple[str, str, str]:
    if kind not in {None, "magic", "ichiban"}:
        raise ValueError("赏类型只允许 magic 或 ichiban")
    if re.fullmatch(r"[1-9]\d*", source):
        if kind is None:
            raise ValueError("纯数字商品 ID 必须同时指定 --kind magic|ichiban")
        return source, kind, source
    url = urlparse(source)
    if url.scheme != "https" or url.hostname != "mall.bilibili.com":
        raise ValueError("必须提供会员购 HTTPS 赏商品链接")
    query = parse_qs(url.query)
    ids, pages = query.get("itemsId", []), query.get("page", [])
    if len(ids) != 1 or not re.fullmatch(r"[1-9]\d*", ids[0]) or len(pages) != 1:
        raise ValueError("赏链接必须含唯一、有效的 itemsId 和 page")
    inferred = {"magic-detail_detail": "magic", "ichiban_detail": "ichiban"}.get(pages[0])
    if inferred is None or (kind and kind != inferred):
        raise ValueError("赏链接页面类型不支持或与 --kind 不一致")
    return ids[0], inferred, source


# 功能：发起一个只读商品请求；输入：HTTP 客户端、方法、接口与参数；返回：完整成功响应。
def request_json(session: requests.Session, method: str, endpoint: str, params: dict) -> dict:
    response = session.request(method, ORIGIN + endpoint, timeout=30,
                               **({"params": params} if method == "GET" else {"json": params}))
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{endpoint} 没有返回 JSON") from exc
    if not isinstance(payload, dict) or str(payload.get("code")) != "0":
        message = payload.get("message", "无有效错误信息") if isinstance(payload, dict) else "无效响应"
        raise RuntimeError(f"{endpoint} 采集失败：{message}")
    if not isinstance(payload.get("data"), dict):
        raise RuntimeError(f"{endpoint} 商品/活动数据缺失")
    return payload


# 功能：解析已核实金额；输入：元字符串、原始字段与来源接口；返回：参考价对象或 None。
def reference_price(value: object, field: str, endpoint: str) -> dict | None:
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    return {"amount": format(amount, "f"), "currency": "CNY", "unit": "元",
            "source_field": field, "source_endpoint": endpoint}


# 功能：标准化图片地址；输入：原接口地址；返回：HTTPS 原图地址。
def image_url(value: object) -> str:
    url = str(value or "")
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or not parsed.hostname.endswith(".hdslb.com"):
        raise ValueError(f"奖品图片地址无效：{url}")
    # 使用响应原始地址，不拼接缩略参数，也不根据文件扩展名推断格式。
    return url.replace("http://", "https://", 1)


# 功能：从接口概率说明识别实际档位名称；输入：奖池 data；返回：type→名称映射。
def magic_tier_names(data: dict) -> dict[str, str]:
    names = {}
    for item in (data.get("drawSliceInfo") or {}).get("probabilityInfos") or []:
        text = item.get("probability", "")
        match = re.search(r"【([^】]+)】", text)
        label = item.get("probabilityTag") or (match.group(1) if match else None)
        if label:
            names[str(item["type"])] = label
    return names


# 功能：标准化魔力赏商品并标记活动奖；输入：奖池和魔王活动响应；返回：完整奖品列表与待核实事项。
def normalize_magic(data: dict, activity: dict) -> tuple[list[dict], list[str]]:
    tiers = magic_tier_names(data)
    demon = activity.get("demogorgonItems") or {}
    active = bool((activity.get("activity") or {}).get("inActivity"))
    demon_ids = {str(x) for x in demon.get("demogorgonSubSkuIdList") or []} if active else set()
    prizes, issues, seen = [], [], set()
    for index, item in enumerate(data.get("subSkuList") or []):
        sku = str(item.get("subSkuId") or "")
        if not sku.isdigit() or not item.get("name"):
            raise ValueError("魔力赏子商品缺少 SKU 或名称")
        if sku in seen:
            raise ValueError(f"奖池重复子 SKU：{sku}")
        seen.add(sku)
        raw_tier = item.get("type")
        label = item.get("typeName") or tiers.get(str(raw_tier))
        is_demon = sku in demon_ids
        if is_demon:
            label = "魔王款"
        if not label:
            label = f"档位 {raw_tier}"
            issues.append(f"接口未提供子 SKU {sku} 的档位 {raw_tier} 名称，需补齐接口数据；不能猜测奖级")
        prizes.append({
            "id": f"magic:{sku}", "sub_sku_ids": [sku], "item_id": str(item.get("subSkuItemsId") or ""),
            "name": item["name"], "tier": label, "tier_raw": raw_tier, "order": index,
            "image_url": image_url(item.get("imageUrl")),
            "reference_price": reference_price(item.get("subSkuPrice"), "subSkuPrice", MAGIC_INFO),
            "source_endpoint": MAGIC_INFO, "is_activity_prize": is_demon,
            "tier_source": MAGIC_DEMOGORGON if is_demon else MAGIC_INFO,
            "delivery": item.get("presaleDeliveryTimeStr"),
        })
    missing = demon_ids - seen
    if missing:
        # 活动引用的 SKU 缺少对应图片/名称，必须补采，不能悄悄略过。
        issues.append("活动奖 SKU 不在奖池中，需补采真实商品信息：" + ", ".join(sorted(missing)))
    return prizes, issues


# 功能：标准化一番赏所有档位；输入：奖池 data；返回：含售罄档位及 Last 条件的列表。
def normalize_ichiban(data: dict) -> list[dict]:
    prizes = []
    for index, group in enumerate(data.get("skuBoxGroupList") or []):
        raw = str(group.get("groupName") or group.get("name") or "")
        if not raw or group.get("groupId") is None:
            raise ValueError("一番赏缺少档位名称或 groupId")
        tier = "Last赏" if raw.lower() == "last赏" else raw
        children = group.get("skuBoxGroupDetailDTOList") or []
        ids = [str(x["subSkuId"]) for x in children if x.get("subSkuId") is not None]
        if not ids:
            raise ValueError(f"{raw} 缺少子 SKU 身份")
        prizes.append({
            "id": f"ichiban:{group['groupId']}", "sub_sku_ids": ids, "item_id": str(data["itemsId"]),
            "name": group.get("name") or raw, "tier": tier, "tier_raw": raw, "order": index,
            "image_url": image_url(group.get("img")), "reference_price": None,
            "source_endpoint": ICHIBAN_INFO, "is_activity_prize": False,
            "stock": group.get("stock"), "initial_stock": group.get("boxGroupStock"),
            "acquisition_condition": group.get("originOdds") if tier == "Last赏" else None,
            "box_id": data.get("boxId"),
        })
    return prizes


# 功能：下载一个原图并评估显示尺寸；输入：奖品、输出目录、类型和模板；返回：补充本地路径/质量的奖品。
def download_prize(prize: dict, folder: Path, kind: str, config: dict) -> dict:
    response = requests.get(prize["image_url"], headers={"User-Agent": MOBILE_UA, "Referer": ORIGIN + "/"}, timeout=30)
    response.raise_for_status()
    with Image.open(io.BytesIO(response.content)) as image:
        image.load()
        extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "GIF": ".gif"}.get(image.format)
    if extension is None:
        raise ValueError(f"奖品原图格式不支持：{prize['id']}")
    path = folder / (prize["id"].replace(":", "-") + extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return {**prize, "image_path": str(path),
            "image_quality": assess_image(path, kind, tuple(config["image_box"]), config)}


# 功能：采集完整赏商品；输入：来源、类型、edit 目录；返回：最终商品清单路径。
def collect_goods(source: str, kind: str | None, edit_dir: Path) -> Path:
    item_id, resolved_kind, original_source = parse_source(source, kind)
    root = prepare_edit(edit_dir) / "lottery" / item_id
    root.mkdir(parents=True, exist_ok=True)
    # 新采集失败时不能留下上次的 ready 清单让下游误当本次事实。
    write_json(root / "goods.json", {"item_id": item_id, "kind": resolved_kind,
                                    "ready_for_render": False, "issues": ["采集尚未完成"]})
    session = requests.Session()
    session.headers.update({"User-Agent": MOBILE_UA, "Referer": ORIGIN + "/"})
    endpoint = MAGIC_INFO if resolved_kind == "magic" else ICHIBAN_INFO
    params = ({"itemsId": int(item_id), "afterDraw": "false"} if resolved_kind == "magic" else
              {"itemsId": int(item_id), "boxId": 0, "skuId": "", "switchType": 1})
    raw = request_json(session, "GET" if resolved_kind == "magic" else "POST", endpoint, params)
    write_json(root / "raw" / "goods.json", raw)
    data = raw["data"]
    if str(data.get("itemsId")) != item_id:
        raise ValueError("接口商品 ID 与输入商品不一致")
    issues = []
    if resolved_kind == "magic":
        bubble = request_json(session, "GET", MAGIC_ACTIVITY, {"itemsId": int(item_id), "afterDraw": "false"})
        activity = request_json(session, "POST", MAGIC_DEMOGORGON, {"itemsId": int(item_id)})
        write_json(root / "raw" / "activity.json", bubble)
        write_json(root / "raw" / "demogorgon.json", activity)
        prizes, issues = normalize_magic(data, activity["data"])
    else:
        prizes = normalize_ichiban(data)
    if not prizes:
        raise ValueError("奖池没有可用奖品")
    config = load_video_spec()
    with ThreadPoolExecutor(max_workers=4) as executor:
        prizes = list(executor.map(lambda prize: download_prize(prize, root / "images", resolved_kind, config), prizes))
    manifest = {"item_id": item_id, "kind": resolved_kind, "name": data.get("name"),
                "source": original_source, "source_endpoint": endpoint,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "draw_price": reference_price(data.get("price"), "price", endpoint),
                "box_id": data.get("boxId"), "prizes": prizes, "issues": issues,
                "ready_for_render": not issues, "probability_display": False}
    output = root / "goods.json"
    write_json(output, manifest)
    write_json(root / "image_quality.json", [{"id": p["id"], "name": p["name"], **p["image_quality"]} for p in prizes])
    if issues:
        print("待核实：" + "；".join(issues), file=sys.stderr)
    return output


# 功能：解析命令行并采集；输入：CLI 参数；返回：0 完整、1 失败、2 已采集但待补全。
def main() -> int:
    parser = argparse.ArgumentParser(description="通过接口采集魔力赏/一番赏奖品与原图质量，无需打开商品页面")
    parser.add_argument("source", help="赏链接或商品 ID")
    parser.add_argument("--kind", choices=["magic", "ichiban"])
    parser.add_argument("--edit-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = collect_goods(args.source, args.kind, args.edit_dir)
        manifest = json.loads(output.read_text(encoding="utf-8"))
        if not manifest.get("ready_for_render") or manifest.get("issues"):
            print(f"采集信息不完整，查看清单 issues 并补齐接口数据：{output}", file=sys.stderr)
            return 2
        print(f"已采集：{output}")
        return 0
    except (ValueError, RuntimeError, OSError, requests.RequestException) as exc:
        print(f"采集失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
