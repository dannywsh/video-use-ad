"""绑定真实奖品、模板布局与价格，生成统一的前端场景数据。"""

from __future__ import annotations

import colorsys
import copy
import hashlib
import math
from pathlib import Path

try:
    from .lottery_common import assess_image, read_subject
    from .lottery_goods import reference_price
except ImportError:
    from lottery_common import assess_image, read_subject
    from lottery_goods import reference_price


# 功能：为奖池建立稳定色表；输入：完整奖品列表和模板；返回：档位→颜色映射。
def tier_palette(prizes: list[dict], config: dict) -> dict[str, str]:
    colors = dict(config["tier_colors"])
    extra = sorted({p["tier"] for p in prizes} - colors.keys())
    for index, name in enumerate(extra):
        if index < len(config["extra_tier_colors"]):
            colors[name] = config["extra_tier_colors"][index]
        else:
            rgb = colorsys.hsv_to_rgb((index * 0.61803398875) % 1, 0.42, 0.95)
            colors[name] = "#" + "".join(f"{round(value * 255):02X}" for value in rgb)
    return colors


# 功能：检查选品身份及档位一致性；输入：采集清单和 ID 列表；返回：按请求顺序排列的奖品。
def select_prizes(goods: dict, ids: list[str]) -> list[dict]:
    if goods.get("kind") not in {"magic", "ichiban"} or not goods.get("ready_for_render") or goods.get("issues"):
        raise ValueError("奖池有未核实字段或活动奖品，补齐后才能渲染")
    if not 1 <= len(ids) <= 4 or len(ids) != len(set(ids)):
        raise ValueError("每张卡必须选择 1–4 个不同奖品，超过 4 个拆成多张卡")
    by_id = {p["id"]: p for p in goods["prizes"]}
    if len(by_id) != len(goods["prizes"]):
        raise ValueError("商品清单奖品 ID 重复")
    if any(identity not in by_id for identity in ids):
        raise ValueError("选择了不属于该商品奖池的奖品 ID")
    prizes = [by_id[identity] for identity in ids]
    if len({p["tier"] for p in prizes}) != 1:
        raise ValueError("合并卡只能包含同一档位的商品")
    for prize in prizes:
        if not prize.get("sub_sku_ids") or not prize.get("name"):
            raise ValueError("奖品缺少子 SKU 身份或商品名称")
    return prizes


# 功能：格式化有来源的奖品参考价；输入：参考价对象；返回：画面文字或 None。
def price_text(price: dict | None) -> str | None:
    if price is None:
        return None
    if not isinstance(price, dict) or price.get("currency") != "CNY" or not price.get("source_field") or not price.get("source_endpoint"):
        raise ValueError("参考价缺少币种或可靠来源")
    if price["source_field"] == "price":
        raise ValueError("单抽价不能作为奖品参考价")
    validated = reference_price(price.get("amount"), price["source_field"], price["source_endpoint"])
    if validated is None:
        raise ValueError("奖品参考价必须为正有限金额")
    amount = validated["amount"]
    if "." in amount:
        amount = amount.rstrip("0").rstrip(".")
    return f"参考价 ¥{amount}"


# 功能：读取所选模板的商品区域；输入：商品数、模板配置；返回：独立的图、名、价区域。
def card_regions(count: int, config: dict) -> list[dict]:
    if not 1 <= count <= 4:
        raise ValueError("一张卡只能放 1–4 件同档位商品")
    return copy.deepcopy(config["layouts"][str(count)])


# 功能：准备前端数据与原图主体；输入：商品清单、选品、public 文件夹、配置；返回：场景 props 和像素报告。
def prepare_scene(goods: dict, prizes: list[dict], public: Path, config: dict, duration: float) -> tuple[dict, dict]:
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("镜头时长必须为正有限数")
    folder = public / "prizes"
    folder.mkdir(parents=True, exist_ok=True)
    scene = {"templateId": config["id"], "motionPixels": config["motion_pixels"],
             "theme": {key: config[key] for key in ("background", "ink", "muted")}, "kind": goods["kind"], "title": str(goods["name"] or "赏品图鉴"), "tier": prizes[0]["tier"],
             "accent": tier_palette(goods["prizes"], config)[prizes[0]["tier"]],
             "durationInFrames": math.ceil(duration * config["fps"]), "items": []}
    images = []
    for prize, region in zip(prizes, card_regions(len(prizes), config)):
        path = Path(prize["image_path"])
        quality = assess_image(path, goods["kind"], tuple(region["image"][2:]), config)
        if quality["sha256"] != prize.get("image_quality", {}).get("sha256"):
            raise ValueError(f"商品图发生变化，重新采集/核验：{prize['id']}")
        subject, _ = read_subject(path)
        identity = hashlib.sha256(prize["id"].encode()).hexdigest()[:16]
        relative = f"prizes/{identity}-{quality['sha256'][:12]}.png"
        subject.save(public / relative)
        price = prize.get("reference_price")
        price_text(price)  # 单抽价、缺币种、缺来源或非法金额不能流入前端。
        if price is not None:
            price = reference_price(price["amount"], price["source_field"], price["source_endpoint"])
            if not math.isfinite(float(price["amount"])):
                raise ValueError("参考价超出前端可安全显示的数值范围")
        scene["items"].append({"id": prize["id"], "name": prize["name"], "tier": prize["tier"], "src": relative,
            "width": quality["display_size"][0], "height": quality["display_size"][1],
            "nativeWidth": subject.width, "nativeHeight": subject.height,
            "transparent": subject.getchannel("A").getextrema()[0] < 255,
            "price": price, "imageBox": region["image"], "nameBox": region["name"], "priceBox": region["price"]})
        images.append({"id": prize["id"], "region": region["image"], **quality})
    return scene, {"tier": scene["tier"], "color": scene["accent"], "images": images, "renderer": "Remotion / React",
                   "subtitle_safe_top": config["subtitle_safe_top"], "center_axis": 540, "template_id": config["id"]}
