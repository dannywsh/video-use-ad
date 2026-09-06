#!/usr/bin/env python3
"""Center-crop a 16:9 Bilibili cover into a 4:3 JPEG.

Do not generate a second 4:3 image. Composition (title placement around a
fully visible product) is the skill's job, not this crop.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

RATIO_16_9 = 16 / 9
RATIO_4_3 = 4 / 3
ASPECT_TOLERANCE = 0.01


def relative_aspect_error(width: int, height: int, target: float) -> float:
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid image size {width}x{height}")
    return abs((width / height) - target) / target


def assert_aspect(
    width: int, height: int, target: float, *, label: str, tolerance: float = ASPECT_TOLERANCE
) -> None:
    error = relative_aspect_error(width, height, target)
    if error > tolerance:
        raise SystemExit(
            f"{label} {width}x{height} aspect error {error:.4f} exceeds {tolerance:.0%} of {target:.6f}"
        )


def center_crop_4x3_box(width: int, height: int) -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) for a centered 4:3 rectangle."""
    crop_w = round(height * RATIO_4_3)
    if crop_w <= width:
        left = (width - crop_w) // 2
        return (left, 0, left + crop_w, height)
    crop_h = round(width / RATIO_4_3)
    top = (height - crop_h) // 2
    return (0, top, width, top + crop_h)


def default_output_path(source: Path) -> Path:
    if source.stem == "cover":
        return source.with_name("cover-4x3.jpg")
    return source.with_name(f"{source.stem}-4x3.jpg")


def crop_cover43(source: Path, output: Path) -> dict:
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        assert_aspect(width, height, RATIO_16_9, label=str(source))
        box = center_crop_4x3_box(width, height)
        cropped = rgb.crop(box)
        crop_w, crop_h = cropped.size
        assert_aspect(crop_w, crop_h, RATIO_4_3, label="4:3 crop")
        output.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(output, format="JPEG", quality=95, optimize=True, subsampling=0)
    return {
        "success": True,
        "input": str(source),
        "output": str(output),
        "source": [width, height],
        "crop": [crop_w, crop_h],
        "box": list(box),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crop a 16:9 Bilibili cover.jpg into a centered 4:3 JPEG."
    )
    parser.add_argument("--input", required=True, help="Verified 16:9 cover.jpg")
    parser.add_argument(
        "--output",
        default=None,
        help="4:3 JPEG path. Default: cover-4x3.jpg next to --input.",
    )
    args = parser.parse_args()
    source = Path(args.input)
    if not source.is_file():
        raise SystemExit(f"missing cover: {source}")
    output = Path(args.output) if args.output else default_output_path(source)
    result = crop_cover43(source, output)
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
