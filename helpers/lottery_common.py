"""赏视频共用的路径与原图质量检查。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid

from PIL import Image, ImageOps

# 功能：限制会话输出位置；输入：目标路径；返回：位于 edit 下的绝对路径。
def edit_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if "edit" not in resolved.parts or Path(__file__).resolve().parents[1] in resolved.parents:
        raise ValueError("会话输出必须位于素材目录的 edit 下，不能写入技能工程")
    return resolved


# 功能：准备任务临时目录；输入：edit 根目录；返回：目录绝对路径。
def prepare_edit(path: Path) -> Path:
    root = edit_path(path)
    if root.name != "edit":
        raise ValueError("--edit-dir 必须指向素材目录下的 edit 根目录")
    tmp = root / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    for key in ("TMPDIR", "TMP", "TEMP"):
        os.environ[key] = str(tmp)
    return root


# 功能：读取清晰主体，不裁掉实体；输入：原图；返回：RGBA 主体与原图质量字段。
def read_subject(path: Path) -> tuple[Image.Image, dict]:
    with Image.open(path) as source:
        fmt = source.format
        oriented = ImageOps.exif_transpose(source)
        size = oriented.size
        rgba = oriented.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError(f"图片完全透明：{path}")
        # 只去掉 alpha=0 的透明边缘；白底、文字及其他不透明内容全部保留。
        subject = rgba.crop(bbox)
    return subject, {
        "format": fmt, "source_size": list(size), "subject_bbox": list(bbox),
        "subject_size": list(subject.size), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


# 功能：以最坏运动位置评估清晰度；输入：图、赏类型、显示区域、模板；返回：尺寸与倍率报告。
def assess_image(path: Path, kind: str, box: tuple[int, int], config: dict) -> dict:
    subject, info = read_subject(path)
    width, height = subject.size
    cap = config["ichiban_image_max_width"] if kind == "ichiban" else box[0]
    available_w = min(box[0], cap)
    available_h = box[1] - 2 * config["motion_pixels"]
    if min(available_w, available_h) <= 0:
        raise ValueError("图片显示区域不足以保留运动余量")
    requested = min(available_w / width, available_h / height)
    scale = min(1.0, requested)
    displayed = [max(1, int(width * scale)), max(1, int(height * scale))]
    return {
        **info, "display_box": list(box), "display_size": displayed,
        "requested_scale": round(requested, 4), "max_upscale": 1.0,
        "actual_scale": round(scale, 4), "usable": True,
        "action": "缩小展示，禁止放大" if requested > 1 else "原图像素足够",
    }


# 功能：写入 UTF-8 JSON；输入：路径与可序列化内容；返回：无。
def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}-{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
