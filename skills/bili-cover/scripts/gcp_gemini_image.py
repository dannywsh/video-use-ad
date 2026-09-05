#!/usr/bin/env python3
"""Google Cloud Vertex publisher Gemini image generation (gcp-gemini)."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SKILL_ROOT_ENV = Path(__file__).resolve().parent.parent.parent.parent / ".env"
CWD_ENV = Path.cwd() / ".env"

DEFAULT_ENDPOINT = "aiplatform.googleapis.com"
DEFAULT_MODEL = "gemini-3.1-flash-lite-image"
DEFAULT_IMAGE_SIZE = "1K"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_MIME = "image/jpeg"

ASPECT_RATIOS = {
    "1:1",
    "3:2",
    "2:3",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
    "auto",
}

IMAGE_HARM_CATEGORIES = (
    "HARM_CATEGORY_IMAGE_HATE",
    "HARM_CATEGORY_IMAGE_DANGEROUS_CONTENT",
    "HARM_CATEGORY_IMAGE_HARASSMENT",
    "HARM_CATEGORY_IMAGE_SEXUALLY_EXPLICIT",
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_env_value(name: str, default: str = "") -> str:
    for candidate in (SKILL_ROOT_ENV, CWD_ENV):
        parsed = parse_env_file(candidate)
        value = parsed.get(name, "").strip()
        if value:
            return value
    return os.environ.get(name, "").strip() or default


def load_image_part(path: Path) -> dict:
    data = path.read_bytes()
    mime, _ = mimetypes.guess_type(path.name)
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        suffix = path.suffix.lower()
        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(suffix)
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise SystemExit(f"unsupported reference image type: {path}")
    return {
        "inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(data).decode("ascii"),
        }
    }


def build_request(
    prompt: str,
    reference_images: list[Path] | None = None,
    *,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    image_size: str = DEFAULT_IMAGE_SIZE,
) -> dict:
    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError(
            f"aspectRatio {aspect_ratio!r} is not in {sorted(ASPECT_RATIOS)}"
        )
    parts: list[dict] = [{"text": prompt}]
    for image_path in reference_images or []:
        parts.append(load_image_part(image_path))
    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 1,
            "maxOutputTokens": 32768,
            "responseModalities": ["TEXT", "IMAGE"],
            "topP": 0.95,
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": image_size,
                "imageOutputOptions": {"mimeType": DEFAULT_MIME},
                "personGeneration": "ALLOW_ALL",
            },
            "thinkingConfig": {"thinkingLevel": "MINIMAL"},
        },
        "safetySettings": [
            {"category": category, "threshold": "OFF"}
            for category in IMAGE_HARM_CATEGORIES
        ],
    }


def _iter_json_objects(raw: str):
    text = raw.strip()
    if not text:
        return
    if text.startswith("["):
        payload = json.loads(text)
        if isinstance(payload, list):
            for item in payload:
                yield item
            return
        yield payload
        return
    if text.startswith("{"):
        yield json.loads(text)
        return
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _part_inline(part: dict) -> tuple[str | None, str | None]:
    blob = part.get("inlineData") or part.get("inline_data") or {}
    mime = blob.get("mimeType") or blob.get("mime_type")
    data = blob.get("data")
    if data:
        return mime, data
    return None, None


def parse_stream_images(raw: str) -> list[tuple[str, bytes]]:
    images: list[tuple[str, bytes]] = []
    for chunk in _iter_json_objects(raw):
        candidates = chunk.get("candidates") or []
        for candidate in candidates:
            parts = (candidate.get("content") or {}).get("parts") or []
            for part in parts:
                mime, data = _part_inline(part)
                if data:
                    images.append((mime or DEFAULT_MIME, base64.b64decode(data)))
    return images


def request_url(endpoint: str, model: str, api_key: str) -> str:
    return (
        f"https://{endpoint}/v1/publishers/google/models/"
        f"{model}:streamGenerateContent?key={api_key}"
    )


def generate_gcp_gemini_image(
    prompt: str,
    output: Path,
    reference_images: list[Path] | None = None,
    *,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    image_size: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    timeout: int = 120,
) -> Path:
    key = api_key or load_env_value("GCP_GEMINI_IMAGE_API_KEY")
    if not key:
        raise SystemExit(
            "GCP_GEMINI_IMAGE_API_KEY not found in .env or environment"
        )
    model_id = model or load_env_value("GCP_GEMINI_IMAGE_MODEL", DEFAULT_MODEL)
    host = endpoint or load_env_value(
        "GCP_GEMINI_IMAGE_API_ENDPOINT", DEFAULT_ENDPOINT
    )
    size = image_size or load_env_value("GCP_GEMINI_IMAGE_SIZE", DEFAULT_IMAGE_SIZE)
    body = build_request(
        prompt,
        reference_images,
        aspect_ratio=aspect_ratio,
        image_size=size,
    )
    payload = json.dumps(body).encode("utf-8")
    url = request_url(host, model_id, key)
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"gcp-gemini HTTP {exc.code}: {detail[:2000]}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"gcp-gemini request failed: {exc}") from exc

    images = parse_stream_images(raw)
    if not images:
        raise SystemExit("gcp-gemini returned no image parts")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(images[0][1])
    return output


def _truncate_request_for_print(body: dict) -> dict:
    clone = json.loads(json.dumps(body))
    for part in clone["contents"][0]["parts"]:
        blob = part.get("inline_data")
        if blob and "data" in blob:
            blob["data"] = f"<base64 {len(blob['data'])} chars>"
    return clone


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an image via Vertex publishers Gemini (gcp-gemini)."
    )
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--reference-image",
        action="append",
        default=[],
        dest="reference_images",
        help="Local product/character still. Repeatable.",
    )
    parser.add_argument("--aspect-ratio", default=DEFAULT_ASPECT_RATIO)
    parser.add_argument("--size", default=None, help="imageConfig.imageSize, default 1K")
    parser.add_argument(
        "--print-request",
        action="store_true",
        help="Print the JSON body and exit without calling the API.",
    )
    args = parser.parse_args()
    refs = [Path(p) for p in args.reference_images]
    body = build_request(
        args.prompt,
        refs,
        aspect_ratio=args.aspect_ratio,
        image_size=args.size
        or load_env_value("GCP_GEMINI_IMAGE_SIZE", DEFAULT_IMAGE_SIZE),
    )
    if args.print_request:
        json.dump(_truncate_request_for_print(body), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    path = generate_gcp_gemini_image(
        args.prompt,
        Path(args.output),
        refs,
        aspect_ratio=args.aspect_ratio,
        image_size=args.size,
    )
    print(json.dumps({"success": True, "output": str(path), "backend": "gcp-gemini"}))


if __name__ == "__main__":
    main()
