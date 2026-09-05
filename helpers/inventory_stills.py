"""Inventory stills and slice tall infographics into readable vertical bands.

Classification is the agent's job after looking at the original (and bands).
This helper only measures, slices, and optionally scores already-read headings.

Usage:
    python helpers/inventory_stills.py <素材文件夹> --bands-dir <edit>/verify/stills
    python helpers/inventory_stills.py --suggest-role "<可见标题>"
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
CANVAS_W = 1920
CANVAS_H = 1080
# True long infographics (detail pages, info posters), not 3:4 KV or square product shots.
TALL_ASPECT = 2.0
BAND_VIEWPORT_PAD = 1.15
BAND_OVERLAP = 0.12
MAX_BANDS = 12
BAND_JPEG_QUALITY = 85
BAND_MAX_WIDTH = 1280

ROLE_ADMIN_DROP = "admin_drop"
ROLE_CAST_OR_SCHEDULE = "cast_or_schedule"
ROLE_PRODUCT = "product"
ROLE_HERO = "hero"
ROLE_NEEDS_REVIEW = "needs_review"

ADMIN_TITLE_RE = re.compile(
    r"(购票|入场|观众|退票|换票)?须知|退票|换票规则|禁止携带|实名购票|"
    r"免责声明|交通路线|购票及入场|儿童入场"
)
CAST_RE = re.compile(r"专场嘉宾|嘉宾阵容|嘉宾|签售|舞台活动|舞台|演出信息|活动日程|日程")
PRODUCT_RE = re.compile(r"周边一览|周边礼包|礼包套票|套票包含|套票|周边|商品详情|商品")
HERO_RE = re.compile(r"主视觉|KV|盛典|博览会|动漫游戏展")


def iter_stills(folder: Path) -> list[Path]:
    """List image files in a material folder, skipping nested edit/ output."""
    if not folder.is_dir():
        raise FileNotFoundError(f"not a directory: {folder}")
    stills = [
        path for path in sorted(folder.iterdir())
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    ]
    return stills


def viewport_height(source_w: int, canvas_w: int = CANVAS_W, canvas_h: int = CANVAS_H) -> float:
    """Source pixels that fill one 16:9 canvas when the image is width-fitted."""
    if source_w <= 0:
        raise ValueError("source width must be positive")
    return source_w * canvas_h / canvas_w


def is_tall(source_w: int, source_h: int, *, min_aspect: float = TALL_ASPECT) -> bool:
    """True when the still is a vertical infographic, not a 3:4 poster."""
    if source_w <= 0 or source_h <= 0:
        raise ValueError("sizes must be positive")
    return source_h / source_w >= min_aspect


def plan_bands(
    source_w: int,
    source_h: int,
    *,
    canvas_w: int = CANVAS_W,
    canvas_h: int = CANVAS_H,
    overlap: float = BAND_OVERLAP,
    max_bands: int = MAX_BANDS,
) -> list[tuple[int, int, float, float]]:
    """Return overlapping (y, h, start_frac, end_frac) windows covering a tall still.

    Empty when the image is not a long infographic. Fractions match
    `stable_motion.py --region START,END`.
    """
    if source_w <= 0 or source_h <= 0:
        raise ValueError("sizes must be positive")
    if not 0.0 <= overlap < 1.0:
        raise ValueError("overlap must be in [0, 1)")
    if max_bands < 1:
        raise ValueError("max_bands must be at least 1")
    if not is_tall(source_w, source_h):
        return []

    viewport = viewport_height(source_w, canvas_w, canvas_h)
    band_h = min(source_h, max(2, int(round(viewport * BAND_VIEWPORT_PAD))))
    usable = source_h - band_h
    if usable <= 0:
        return [(0, source_h, 0.0, 1.0)]

    step = max(1, int(round(band_h * (1.0 - overlap))))
    starts = list(range(0, usable + 1, step))
    if starts[-1] != usable:
        starts.append(usable)
    if len(starts) > max_bands:
        starts = [int(round(usable * i / (max_bands - 1))) for i in range(max_bands)]
        starts[-1] = usable

    bands: list[tuple[int, int, float, float]] = []
    seen: set[int] = set()
    for y in starts:
        y = max(0, min(y, usable))
        if y in seen:
            continue
        seen.add(y)
        start_frac = y / source_h
        end_frac = (y + band_h) / source_h
        bands.append((y, band_h, start_frac, end_frac))
    return bands


def suggest_role(visible_text: str) -> str:
    """Map headings already read from a still (or its bands) to a stock role.

    Does not look at pixels. Admin titles win unless a guest/product heading
    is also present — then the agent must keep those bands and drop the rest.
    """
    text = (visible_text or "").strip()
    if not text:
        return ROLE_NEEDS_REVIEW
    has_admin = bool(ADMIN_TITLE_RE.search(text))
    has_cast = bool(CAST_RE.search(text))
    has_product = bool(PRODUCT_RE.search(text))
    has_hero = bool(HERO_RE.search(text))
    if has_admin and not has_cast and not has_product:
        return ROLE_ADMIN_DROP
    if has_cast:
        return ROLE_CAST_OR_SCHEDULE
    if has_product:
        return ROLE_PRODUCT
    if has_admin:
        return ROLE_ADMIN_DROP
    if has_hero:
        return ROLE_HERO
    return ROLE_NEEDS_REVIEW


def _as_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGB", "L"}:
        return image.convert("RGB")
    rgb = Image.new("RGB", image.size, (255, 255, 255))
    if image.mode == "RGBA":
        rgb.paste(image, mask=image.split()[-1])
        return rgb
    return image.convert("RGB")


def export_band(source: Path, dest: Path, y: int, height: int) -> None:
    """Write one JPEG strip from `source`, scaled down for agent viewing."""
    with Image.open(source) as image:
        rgb = _as_rgb(image)
        width, full_h = rgb.size
        y = max(0, min(y, full_h - 1))
        height = max(1, min(height, full_h - y))
        crop = rgb.crop((0, y, width, y + height))
        if crop.width > BAND_MAX_WIDTH:
            new_h = max(1, int(round(crop.height * BAND_MAX_WIDTH / crop.width)))
            crop = crop.resize((BAND_MAX_WIDTH, new_h), Image.Resampling.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        crop.save(dest, format="JPEG", quality=BAND_JPEG_QUALITY, optimize=True)


def inventory_folder(folder: Path, bands_dir: Path | None = None) -> dict:
    """Measure every still and optionally export tall-image preview bands."""
    stills_payload = []
    for source in iter_stills(folder):
        with Image.open(source) as image:
            width, height = image.size
        viewports = height / viewport_height(width)
        tall = is_tall(width, height)
        bands_meta = []
        if tall and bands_dir is not None:
            stem = source.stem
            for index, (y, band_h, start, end) in enumerate(plan_bands(width, height)):
                dest = bands_dir / f"{stem}_band_{index:02d}.jpg"
                export_band(source, dest, y, band_h)
                bands_meta.append({
                    "index": index,
                    "y": y,
                    "h": band_h,
                    "region": [round(start, 4), round(end, 4)],
                    "file": str(dest),
                })
        stills_payload.append({
            "path": str(source),
            "name": source.name,
            "width": width,
            "height": height,
            "aspect": round(height / width, 3),
            "viewports": round(viewports, 2),
            "tall": tall,
            "bands": bands_meta,
        })
    return {
        "folder": str(folder.resolve()),
        "canvas": [CANVAS_W, CANVAS_H],
        "stills": stills_payload,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inventory stills and slice tall infographics into preview bands.",
    )
    parser.add_argument("folder", nargs="?", type=Path, help="Material folder of stills")
    parser.add_argument(
        "--bands-dir",
        type=Path,
        help="Write JPEG preview bands for tall stills (e.g. <videos_dir>/edit/verify/stills)",
    )
    parser.add_argument(
        "--suggest-role",
        metavar="TEXT",
        help="Classify already-read headings; prints a role and exits",
    )
    args = parser.parse_args()
    if args.suggest_role is not None:
        print(suggest_role(args.suggest_role))
        return
    if args.folder is None:
        parser.error("folder is required unless --suggest-role")
    payload = inventory_folder(args.folder, args.bands_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
