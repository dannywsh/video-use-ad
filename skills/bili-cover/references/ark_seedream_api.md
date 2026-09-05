# Ark Seedream image API (ark-seedream)

Backend ID: `ark-seedream`. Script: `skills/bili-cover/scripts/ark_seedream_generate.js` (Node.js 18+).

Cover work is usually one 16:9 still (`sequential=false`). The HTTP/CLI surface below is the full Seedream Agent Plan image API; keep using it when the user asks for i2i or a coherent set.

## Credentials and env

Lookup (same as parent TTS): skill-root `.env` → cwd `.env` → process env. Only `ARK_SEEDREAM_*` names; do not scan `ANTHROPIC_AUTH_TOKEN` or a generic `ARK_API_KEY`.

| Variable | Default |
|----------|---------|
| `ARK_SEEDREAM_API_KEY` | required, must start with `ark-` |
| `ARK_SEEDREAM_MODEL` | `doubao-seedream-5.0-lite` |
| `ARK_SEEDREAM_API_BASE_URL` | `https://ark.cn-beijing.volces.com/api/plan/v3` |
| `ARK_SEEDREAM_SAVE_PATH` | cwd (overridden by `--save-dir`) |
| `ARK_SEEDREAM_TIMEOUT_MS` | `120000` |

`--api-key ark-xxx` overrides for this process only. Keys are never written to OpenClaw / Hermes / Claude settings.

## HTTP

All modes (text-to-image, image-to-image, coherent set) use one endpoint:

```http
POST {ARK_SEEDREAM_API_BASE_URL}/images/generations
Content-Type: application/json
Authorization: Bearer ark-xxx
```

Default URL: `https://ark.cn-beijing.volces.com/api/plan/v3/images/generations`

### Body

```json
{
  "model": "doubao-seedream-5.0-lite",
  "prompt": "一只可爱的小猫",
  "sequential_image_generation": "disabled",
  "response_format": "url",
  "size": "2k",
  "stream": false,
  "watermark": false,
  "output_format": "jpeg"
}
```

| Field | Values | Notes |
|-------|--------|--------|
| `model` | string | `ARK_SEEDREAM_MODEL` |
| `prompt` | string | required, max 3000 chars |
| `sequential_image_generation` | `auto` / `disabled` | `auto` when `--sequential true` |
| `response_format` | `url` | script downloads URLs |
| `size` | `2K` / `3K` / `WIDTHxHEIGHT` | cover: `1920x1080` or `2K` plus 16:9 lock in prompt |
| `stream` | boolean | on when sequential |
| `watermark` | boolean | default false |
| `output_format` | `jpeg` / `png` | CLI `--response_format` |
| `tools` | `[{ "type": "web_search" }]` | when `--enable_web_search true` |
| `image` | string or array | i2i only |
| `reference_strength` | 0–1 | optional |

**`--count` is not sent as `num_images` / `max_images`.** The API infers set size from prompt wording such as `生成4张一组的连贯插画`. `--count` is for Agent prompt construction, local validation, progress, and metadata only. Sending `sequential_image_generation_options.max_images` causes HTTP 400.

### Reference images (`image`)

CLI `--reference_images` accepts a JSON array string or comma-separated HTTP URLs. Local files must be converted by the Agent to data URIs first.

Supported values:

- HTTP/HTTPS URL
- Base64 data URI: `data:image/png;base64,...` (png / jpeg / webp / bmp / tiff / gif)

Rules:

- 1 reference → `image` is a **string**
- 2–14 references → `image` is an **array**
- Per file ≤ 10 MB; suggested resolution ≥ 1024×1024
- References + generated images ≤ 15

If `--reference_images` is set and `--mode` is omitted, the script sets `mode=image-to-image`.

## Sequential prompt rule (required)

`sequential=true` alone is not enough. The `prompt` must contain:

1. A phrase like `生成X张一组的连贯插画/漫画/图片`
2. Concrete content for each frame
3. Style-consistency language (`统一画风`, `保持风格一致`, `相同角色`)

Wrong: `prompt: "春夏秋冬"` + `sequential=true`.  
Right: `prompt: "生成4张一组的连贯插画：春天的樱花、夏天的海滩、秋天的红叶、冬天的雪景，统一画风，保持风格一致"` + `sequential=true` + `count=4`.

## CLI

```bash
node skills/bili-cover/scripts/ark_seedream_generate.js \
  --prompt "一只可爱的小猫" \
  --size "2K" \
  --mode "text-to-image" \
  --watermark false \
  --optimize true \
  --response_format "jpeg" \
  --save-dir "/path/to/edit"
```

Coherent set + stream:

```bash
node skills/bili-cover/scripts/ark_seedream_generate.js \
  --prompt "生成4张一组的连贯插画：同一地点的春夏秋冬，统一画风，保持风格一致" \
  --sequential true \
  --count 4 \
  --stream true \
  --save-dir "/path/to/edit"
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--prompt` | — | required |
| `--mode` | `text-to-image` | `text-to-image` / `image-to-image` |
| `--size` | `2K` | `2K` / `3K` / `1920x1080` |
| `--sequential` | false | coherent set |
| `--count` | 4 | 1–15, metadata/progress only |
| `--reference_images` | — | JSON array or comma-separated URLs / data URIs |
| `--reference_strength` | 0.7 | 0–1 |
| `--watermark` | false | |
| `--optimize` | true | append quality/style phrases |
| `--stream` | auto | true when sequential |
| `--enable_web_search` | false | or auto if prompt has 实时/新闻/赛事… |
| `--response_format` | jpeg | `png` / `jpeg` |
| `--save-dir` | cwd | local save directory (no Desktop fallback) |
| `--api-key` | from env | this process only |

stderr = progress. stdout = JSON:

```json
{
  "success": true,
  "images": [
    {
      "url": "https://...",
      "local_path": "/path/to/edit/seedream_123_1.jpg",
      "download_success": true
    }
  ],
  "metadata": {
    "generation_time": 12.5,
    "size": "2k",
    "mode": "text-to-image",
    "image_count": 1,
    "save_dir": "/path/to/edit"
  }
}
```

Parse stdout; show local paths to the user. Cover delivery still copies/renames the first JPEG to `<videos_dir>/edit/cover.jpg`.
