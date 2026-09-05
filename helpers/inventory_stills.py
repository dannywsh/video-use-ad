"""Inventory stills and extract on-camera windows from tall infographics.

Classification is the agent's job after looking at the original (and overview).
This helper does not auto-slice by viewport height, color gaps, or OCR.
It measures stills, draws a y-tick overview for tall images, and crops
full-width windows the agent already chose. Crops pad both ends by default
so a slightly short y estimate does not clip titles, goods, or gift items.

Usage:
    python helpers/inventory_stills.py <素材文件夹> --overview-dir <edit>/verify/overview
    python helpers/inventory_stills.py --crop --source <图> --out <裁图> --y0 430 --y1 760
    python helpers/inventory_stills.py --crop --folder <素材> --out-dir <edit>/verify/stills \\
        --window 01_title.jpg,image1.jpeg,430,760
    python helpers/inventory_stills.py --suggest-role "<可见标题>"
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
CANVAS_W = 1920
CANVAS_H = 1080
# True long infographics (detail pages, info posters), not 3:4 KV or square product shots.
TALL_ASPECT = 2.0
OVERVIEW_WIDTH = 360
OVERVIEW_TICK = 200
OVERVIEW_JPEG_QUALITY = 85
CROP_JPEG_QUALITY = 90
# Prefer extra adjacent pixels over clipping the target module.
CROP_PAD_PX = 80

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
PRODUCT_RE = re.compile(
    r"周边一览|周边礼包|礼包套票|套票包含|套票|周边|商品详情|商品|"
    r"卖点|产品参数|规格"
)
HERO_RE = re.compile(r"主视觉|KV")


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


def region_from_pixels(y0: int, y1: int, source_h: int) -> list[float]:
    """Map a full-width crop to `stable_motion.py --region START,END`."""
    if source_h <= 0:
        raise ValueError("source height must be positive")
    if y1 <= y0:
        raise ValueError(f"y1 must be > y0, got y0={y0} y1={y1}")
    return [round(y0 / source_h, 4), round(y1 / source_h, 4)]


def parse_window(spec: str) -> tuple[str, str, int, int]:
    """Parse `name,source,y0,y1`. Source may contain commas; split from the right."""
    text = (spec or "").strip()
    if text.count(",") < 3:
        raise ValueError(
            f"window must be name,source,y0,y1 (got {spec!r})"
        )
    name, rest = text.split(",", 1)
    source, y0s, y1s = rest.rsplit(",", 2)
    name = name.strip()
    source = source.strip()
    if not name or not source:
        raise ValueError(f"window name and source are required (got {spec!r})")
    return name, source, int(y0s), int(y1s)


def suggest_role(visible_text: str) -> str:
    """Map headings already read from a still (or its crops) to a stock role.

    Does not look at pixels. Admin/legal titles win unless a guest or product
    heading is also present — then the agent must keep those windows and drop
    the rest. Guest headings are for event posters; product headings cover
    generic detail pages as well as merch.
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


def export_overview(
    source: Path,
    dest: Path,
    *,
    width: int = OVERVIEW_WIDTH,
    tick: int = OVERVIEW_TICK,
) -> dict:
    """Write a skinny JPEG with original-pixel y ticks for picking crop windows."""
    if width < 1:
        raise ValueError("overview width must be positive")
    if tick < 1:
        raise ValueError("tick must be positive")
    with Image.open(source) as image:
        rgb = _as_rgb(image)
        source_w, source_h = rgb.size
        height = max(1, int(round(source_h * width / source_w)))
        preview = rgb.resize((width, height), Image.Resampling.BOX)
    draw = ImageDraw.Draw(preview)
    scale = width / source_w
    y = 0
    while y < source_h:
        py = int(y * scale)
        draw.line([(0, py), (width, py)], fill=(235, 70, 70), width=1)
        label_bottom = min(height - 1, py + 14)
        draw.rectangle([0, py, 54, label_bottom], fill=(235, 70, 70))
        draw.text((2, py + 1), str(y), fill=(255, 255, 255))
        y += tick
    dest.parent.mkdir(parents=True, exist_ok=True)
    preview.save(dest, format="JPEG", quality=OVERVIEW_JPEG_QUALITY, optimize=True)
    return {
        "file": str(dest),
        "width": preview.width,
        "height": preview.height,
        "tick": tick,
        "source_width": source_w,
        "source_height": source_h,
    }


def crop_window(
    source: Path,
    dest: Path,
    y0: int,
    y1: int,
    *,
    pad: int = CROP_PAD_PX,
) -> dict:
    """Crop a full-width on-camera window. Does not downscale.

    `pad` expands both ends (clamped to the image) so inexact y ticks are
    less likely to clip the module. Extra adjacent content is intended.
    """
    if y1 <= y0:
        raise ValueError(f"y1 must be > y0, got y0={y0} y1={y1}")
    if pad < 0:
        raise ValueError("pad must be >= 0")
    with Image.open(source) as image:
        rgb = _as_rgb(image)
        width, height = rgb.size
        y0c = max(0, min(int(y0) - pad, height - 1))
        y1c = max(y0c + 1, min(int(y1) + pad, height))
        crop = rgb.crop((0, y0c, width, y1c))
        dest.parent.mkdir(parents=True, exist_ok=True)
        crop.save(dest, format="JPEG", quality=CROP_JPEG_QUALITY, optimize=True)
    return {
        "file": str(dest),
        "source": str(source),
        "name": dest.name,
        "y0": y0c,
        "y1": y1c,
        "requested_y0": int(y0),
        "requested_y1": int(y1),
        "pad": pad,
        "width": crop.width,
        "height": crop.height,
        "region": region_from_pixels(y0c, y1c, height),
    }


def _load_manifest(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        payload = payload.get("crops", [])
    if not isinstance(payload, list):
        raise ValueError("crop manifest must be a list or {\"crops\": [...]}")
    return payload


def _resolve_source(folder: Path | None, source: str | Path) -> Path:
    path = Path(source)
    if path.is_file():
        return path
    if folder is not None:
        nested = folder / path
        if nested.is_file():
            return nested
    raise FileNotFoundError(f"source image not found: {source}")


def inventory_folder(folder: Path, overview_dir: Path | None = None) -> dict:
    """Measure every still and optionally export y-tick overviews for tall ones."""
    stills_payload = []
    for source in iter_stills(folder):
        with Image.open(source) as image:
            width, height = image.size
        viewports = height / viewport_height(width)
        tall = is_tall(width, height)
        overview = None
        if tall and overview_dir is not None:
            dest = overview_dir / f"{source.stem}_overview.jpg"
            overview = export_overview(source, dest)
        stills_payload.append({
            "path": str(source),
            "name": source.name,
            "width": width,
            "height": height,
            "aspect": round(height / width, 3),
            "viewports": round(viewports, 2),
            "tall": tall,
            "overview": overview,
        })
    return {
        "folder": str(folder.resolve()),
        "canvas": [CANVAS_W, CANVAS_H],
        "stills": stills_payload,
    }


def run_crops(
    *,
    folder: Path | None,
    out_dir: Path | None,
    windows: list[str],
    manifest: Path | None,
    source: Path | None,
    out: Path | None,
    y0: int | None,
    y1: int | None,
    pad: int = CROP_PAD_PX,
) -> dict:
    """Crop one or more agent-chosen windows and return JSON-serializable rows."""
    jobs: list[tuple[Path, Path, int, int]] = []

    def add_job(dest_name: str | Path, src: str | Path, top: int, bottom: int) -> None:
        resolved = _resolve_source(folder, src)
        dest_path = Path(dest_name)
        if not dest_path.is_absolute():
            if out_dir is None and out is None:
                raise ValueError("crop output needs --out or --out-dir")
            dest_path = (out_dir or out.parent) / dest_path.name
        jobs.append((resolved, dest_path, top, bottom))

    if source is not None:
        if out is None or y0 is None or y1 is None:
            raise ValueError("single crop needs --source --out --y0 --y1")
        jobs.append((_resolve_source(folder, source), out, y0, y1))
    for spec in windows:
        name, src, top, bottom = parse_window(spec)
        add_job(name, src, top, bottom)
    if manifest is not None:
        for item in _load_manifest(manifest):
            add_job(item["name"], item["source"], int(item["y0"]), int(item["y1"]))
    if not jobs:
        raise ValueError("nothing to crop")

    crops = [
        crop_window(src, dest, top, bottom, pad=pad)
        for src, dest, top, bottom in jobs
    ]
    return {"crops": crops}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory stills and crop agent-chosen windows from tall infographics. "
            "Does not auto-slice by viewport, gaps, or OCR."
        ),
    )
    parser.add_argument("folder", nargs="?", type=Path, help="Material folder of stills")
    parser.add_argument(
        "--overview-dir",
        type=Path,
        help="Write y-tick overview JPEGs for tall stills (e.g. <videos_dir>/edit/verify/overview)",
    )
    parser.add_argument(
        "--suggest-role",
        metavar="TEXT",
        help="Classify already-read headings; prints a role and exits",
    )
    parser.add_argument(
        "--crop",
        action="store_true",
        help="Crop full-width windows (use with --source/--out or --window / --manifest)",
    )
    parser.add_argument("--source", type=Path, help="Source still for a single --crop")
    parser.add_argument("--out", type=Path, help="Output JPEG for a single --crop")
    parser.add_argument("--y0", type=int, help="Top pixel (inclusive) for a single --crop")
    parser.add_argument("--y1", type=int, help="Bottom pixel (exclusive) for a single --crop")
    parser.add_argument("--out-dir", type=Path, help="Directory for --window / --manifest crops")
    parser.add_argument(
        "--window",
        action="append",
        default=[],
        metavar="NAME,SOURCE,Y0,Y1",
        help="Repeatable crop spec; source is a filename under folder or a path",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="JSON list of {name, source, y0, y1}, or {\"crops\": [...]}",
    )
    parser.add_argument(
        "--pad",
        type=int,
        default=CROP_PAD_PX,
        help=(
            "Extra pixels on both ends of each crop (default "
            f"{CROP_PAD_PX}; prefer leftover neighbors over clipped goods)"
        ),
    )
    args = parser.parse_args()
    if args.suggest_role is not None:
        print(suggest_role(args.suggest_role))
        return
    if args.crop:
        try:
            payload = run_crops(
                folder=args.folder,
                out_dir=args.out_dir,
                windows=args.window,
                manifest=args.manifest,
                source=args.source,
                out=args.out,
                y0=args.y0,
                y1=args.y1,
                pad=args.pad,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if args.folder is None:
        parser.error("folder is required unless --suggest-role or --crop")
    payload = inventory_folder(args.folder, args.overview_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
