"""发现并校验赏视频模板；模板数据与共用视频规格分开管理。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re

ASSETS_ROOT = Path(__file__).resolve().parents[1] / "assets" / "lottery"
DEFAULT_TEMPLATE = "default"
TEMPLATE_ID = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")


@dataclass(frozen=True)
class LotteryTemplate:
    id: str
    directory: Path
    config: dict


# 功能：读取共用视频与原图规格；输入：资源根目录；返回：与模板无关的规格配置。
def load_video_spec(assets_root: Path = ASSETS_ROOT) -> dict:
    spec = json.loads((assets_root / "video.json").read_text(encoding="utf-8"))
    if (spec["width"], spec["height"], spec["fps"]) != (1080, 1920, 30):
        raise ValueError("赏视频必须为 1080×1920、30fps")
    if (spec["ichiban_image_max_width"], spec["subtitle_safe_top"], spec["horizontal_margin"]) != (800, 1620, 72):
        raise ValueError("原图上限或字幕安全区与共用视频契约不一致")
    return spec


# 功能：验证矩形内容区域；输入：矩形及共用规格；返回：无，越界时阻塞。
def validate_box(box: object, spec: dict) -> None:
    if not isinstance(box, list) or len(box) != 4 or any(
        isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in box
    ):
        raise ValueError("模板区域必须为四个有限数值 [x,y,width,height]")
    x, y, width, height = box
    margin = spec["horizontal_margin"]
    if x < margin or y < 0 or width <= 0 or height <= 0 or x + width > spec["width"] - margin or y + height > spec["subtitle_safe_top"]:
        raise ValueError("模板区域超出画布边缘或侵入字幕安全区")


# 功能：校验模板清单、入口与布局；输入：目录、模板 ID、共用规格；返回：完整配置。
def validate_template(directory: Path, identity: str, spec: dict) -> dict:
    manifest = json.loads((directory / "template.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or manifest.get("id") != identity or not manifest.get("name"):
        raise ValueError(f"模板清单版本、ID 或名称无效：{identity}")
    # 共用画布与质量限制不能被某个模板覆盖。
    if set(manifest) & (set(spec) - {"motion_pixels"}):
        raise ValueError("模板不能覆盖共用视频与原图规格")
    entry = manifest.get("entrypoint")
    if not isinstance(entry, str) or Path(entry).suffix != ".tsx" or ".." in Path(entry).parts:
        raise ValueError("模板入口必须为目录内的 TSX 文件")
    target = (directory / entry).resolve()
    if directory.resolve() not in target.parents or not target.is_file():
        raise ValueError("模板入口不存在或超出模板目录")
    motion = manifest.get("motion_pixels")
    if isinstance(motion, bool) or not isinstance(motion, (int, float)) or not math.isfinite(motion) or not 0 <= motion <= 12:
        raise ValueError("商品运动余量必须在 0–12 像素之间")
    for key in ("background", "ink", "muted"):
        if not isinstance(manifest.get(key), str) or not COLOR.fullmatch(manifest[key]):
            raise ValueError(f"模板颜色无效：{key}")
    colors = manifest.get("tier_colors")
    extras = manifest.get("extra_tier_colors")
    if not isinstance(colors, dict) or not isinstance(extras, list) or not extras or any(
        not isinstance(color, str) or not COLOR.fullmatch(color) for color in [*colors.values(), *extras]
    ) or any(not name for name in colors):
        raise ValueError("模板奖级配色必须为有效色表")
    layouts = manifest.get("layouts")
    if not isinstance(layouts, dict) or set(layouts) != {"1", "2", "3", "4"}:
        raise ValueError("模板必须提供 1–4 件商品的布局")
    for count, regions in layouts.items():
        if not isinstance(regions, list) or len(regions) != int(count):
            raise ValueError("模板布局区域数量与商品数不一致")
        for region in regions:
            if not isinstance(region, dict) or set(region) != {"image", "name", "price"}:
                raise ValueError("每个商品须有 image/name/price 区域")
            for box in region.values():
                validate_box(box, spec)
            if region["image"][3] <= 2 * motion:
                raise ValueError("图片区域不足以保留模板运动余量")
    return {**spec, **manifest}


# 功能：加载指定模板且不静默回退；输入：模板 ID、资源根目录；返回：模板定义。
def load_template(identity: str = DEFAULT_TEMPLATE, assets_root: Path = ASSETS_ROOT) -> LotteryTemplate:
    if not isinstance(identity, str) or not TEMPLATE_ID.fullmatch(identity):
        raise ValueError("模板 ID 只允许小写字母、数字及连字符，且以字母开头")
    directory = assets_root / "templates" / identity
    if not (directory / "template.json").is_file():
        raise ValueError(f"模板不存在：{identity}；用 --list-templates 查看可用模板")
    return LotteryTemplate(identity, directory, validate_template(directory, identity, load_video_spec(assets_root)))


# 功能：发现已安装模板；输入：资源根目录；返回：按 ID 排序且已校验的模板列表。
def list_templates(assets_root: Path = ASSETS_ROOT) -> list[LotteryTemplate]:
    return [load_template(path.parent.name, assets_root)
            for path in sorted((assets_root / "templates").glob("*/template.json"))]
