---
name: bili-cover
description: >
  Generate one 16:9 Bilibili cover image with on-canvas text, a 4:3 center safe zone,
  and the filled prompt used for that image. Backends: native image gen, Google Cloud
  Gemini (gcp-gemini), then Volcengine Ark Seedream (ark-seedream).
  Triggers: B站封面, 封面图, cover image, bili-cover.
---

# Bili Cover

This nested skill **only** generates the Bilibili cover still. Video editing, TTS, and upload stay in the parent `video-use` skill.

Write the file to `<videos_dir>/edit/cover.jpg`. Never write into the `video-use/` repo or the Desktop.

## Backend order

User names a backend → use that. Otherwise, fixed:

1. **`native`** — runtime image gen. Grok: `image_gen` / `image_edit`. Codex: `$imagegen` built-in `image_gen` (do not default to Codex `scripts/image_gen.py`).
2. **`gcp-gemini`** — `python skills/bili-cover/scripts/gcp_gemini_image.py`. Model `gemini-3.1-flash-lite-image`. Needs `GCP_GEMINI_IMAGE_API_KEY`. Interface: `references/gcp_gemini_image_api.md`.
3. **`ark-seedream`** — `node skills/bili-cover/scripts/ark_seedream_generate.js`. Model `doubao-seedream-5.0-lite`. Needs `ARK_SEEDREAM_API_KEY`. Interface: `references/ark_seedream_api.md`.

Fall to the next backend when the current one is missing, errors, or cannot meet this spec (reference images, locked 16:9, on-canvas text). Do not start at Seedream unless the user named Seedream / 豆包 / 方舟.

Named aliases: Gemini / Google / Vertex → `gcp-gemini`. Seedream / 豆包画图 / 方舟画图 → `ark-seedream`.

## Credentials

Same lookup as parent TTS: user-config `.env` (`~/.config/video-use/.env` on all platforms, Windows `%USERPROFILE%\.config\video-use\.env`; survives `npx skills update`) → leftover `<skill_root>/.env` → `<cwd>/.env` → exported env. Never print a key or its prefix. Write new keys to the user config file, not the skill install directory.

| Variable | Role |
|----------|------|
| `GCP_GEMINI_IMAGE_API_KEY` | Vertex publisher API key (`?key=`) |
| `GCP_GEMINI_IMAGE_MODEL` | default `gemini-3.1-flash-lite-image` |
| `GCP_GEMINI_IMAGE_API_ENDPOINT` | default `aiplatform.googleapis.com` |
| `GCP_GEMINI_IMAGE_SIZE` | default `1K` |
| `ARK_SEEDREAM_API_KEY` | Ark Bearer `ark-xxx` |
| `ARK_SEEDREAM_MODEL` | default `doubao-seedream-5.0-lite` |
| `ARK_SEEDREAM_API_BASE_URL` | default `https://ark.cn-beijing.volces.com/api/plan/v3` |

Ask the user for a key only after this lookup fails.

## Cover spec

Final delivery is **1** cover image and **1** filled prompt actually used. Canvas is **16:9 landscape**. Prefer a real product still or user-supplied character image as the foreground so appearance, color, material, and details stay recognizable. Bilibili uses the 16:9 original and a 4:3 crop, so product, titles, and key details must sit in the centered 4:3 safe zone.

- **Canvas vs safe zone:** 16:9 is the output canvas. 4:3 is only the inner centered safe rectangle, never the output ratio. The prompt must first lock “final canvas 16:9 widescreen only; no 4:3, square, or portrait,” then describe the safe zone. After generation, verify with `sips -g pixelWidth -g pixelHeight <cover>` (or equivalent) that the aspect ratio is within ±1% of 16:9. Fail → regenerate with “fix canvas to 16:9, keep safe-zone composition.” Do not deliver or upload a failed canvas.
- **On-canvas text:** All glyphs, stylized type, stroke, shadow, and layout must be produced by the image model in the same call. **Forbidden** to add, replace, repair, or composite text afterward with FFmpeg, PIL, Photoshop, Canva, or anything else. Format or resize that does not change pixels of the artwork is allowed. If confirmed copy is not spelled correctly, regenerate; never caption afterward.
- **4:3 safe zone:** On the 16:9 canvas, a horizontally centered, full-height 4:3 rectangle (~75% of width; ~12.5% each side is cropped in 4:3). Product, faces, packaging, main title, subtitle, and selling points must sit fully inside it. The left/right margins may only hold croppable empty background or very light atmosphere — no text or product silhouette.
- **Composition:** Product is the subject, in the foreground, ~45%–60% of the **4:3 safe zone**, large and layered. The title is not a sticker; it should pick up the product’s color, contour, packaging, glow, or scene. Place the title near the product, still inside the safe zone. Do not cover the face/body/selling point, and do not pin type or product to the 16:9 left/right edges.
- **Background:** Clean, low information density. Prefer flat color / soft gradient / a little glow or texture. No stacked stages, dense ornaments, particle storms, extra props, or unrelated objects. Product + title must be the first read in both 16:9 and 4:3 thumbs.
- **Copy on the image:** Only the confirmed main title (usually 4–10 characters, product name or in-circle nickname) and optional subtitle (6–14 characters), spelled exactly, all inside the 4:3 safe zone. High-contrast stylized type with dark stroke or shadow so it stays readable in the web thumbnail.
- **Style:** Match the product; light ACG atmosphere (stars, soft glow, comic texture) is fine. One clear focus; saturated but not noisy.
- **Limits:** no watermark, logo, English, mojibake, extra text, extra subjects, or deformed product.

**Viewer-facing copy vs generation prompt:** Parent §对外文本禁词 applies to **text drawn on the cover** (and spoken/title/description/tags). Do not paint 云逛、口播、混剪、资讯、宣传片、广告、配方、提示词、BGM、字幕、封面 onto the image. The **generation prompt sent to the model may use 封面** and other internal terms.

## Prompt template

Fill every placeholder. Deliver the filled prompt, not this blank template.

```text
生成一张用于 B站视频封面的高点击率图片。**最终输出画布必须是 16:9 宽屏（例如 1920×1080）；禁止生成 4:3、方形或竖图。** B站会把这张 16:9 原图再裁成 4:3；下文的 4:3 只表示画面内部安全区，不表示输出画布比例。商品、文字和关键细节必须全部落在画面正中的 4:3 安全区：水平居中、高度拉满、约占宽度中间 75%；左右各约 12.5% 只能是可裁切的空背景。

主题：<视频主题/产品名>
参考素材：<上传的产品图、角色图或人物图>。必须保留主体的真实外观、颜色、材质、关键细节与辨识度，不添加无关主体。

构图：商品主体位于前景，并完整待在正中 4:3 安全区内，占该安全区约 45%–60%，清晰、大尺寸、有层次；背景采用干净、低信息密度的 <纯色/柔和渐变/极少量光晕>，只衬托商品与标题。商品与标题必须构成一个整体：让商品的色彩、轮廓或少量光效自然承接标题，标题不应像后贴的独立卡片；不得遮挡主体脸部、关键卖点和轮廓；不得把文字或商品轮廓放到左右将被裁掉的区域。

文字：只出现以下文字，必须逐字准确，且全部放在正中 4:3 安全区内：
“<主标题，4–10字>”
“<可选副标题，6–14字>”
文字、艺术字、描边、阴影与排版必须由图像模型在本次生成中直接完成，不得在生成后添加、修复、替换或拼接。文字采用醒目、立体、与整体色调协调的艺术字；主标题在网页缩略图中也清晰可读。高亮文字搭配深色描边或阴影，避免低对比度。

风格：精致商业宣传图，视觉焦点明确，色彩饱满但不刺眼，适合 B站 16:9 与 4:3 两种列表缩略图。
限制：无水印、无 Logo、无英文、无乱码、无多余文字、无夸张畸形主体、无杂乱背景、无密集装饰、无与商品无关的道具、无贴边文字、无贴边主体。
```

## How to call backends

### native

Pass the filled prompt and reference stills to the runtime tool. Then verify 16:9 and copy accuracy.

### gcp-gemini

```bash
python skills/bili-cover/scripts/gcp_gemini_image.py \
  --prompt "<filled template>" \
  --output "<videos_dir>/edit/cover.jpg" \
  --reference-image "<product.jpg>"
```

Locks `imageConfig.aspectRatio=16:9`, `imageSize` from `GCP_GEMINI_IMAGE_SIZE` (default `1K`), JPEG, `personGeneration=ALLOW_ALL`. Full HTTP contract: `references/gcp_gemini_image_api.md`.

### ark-seedream

Cover path is single 16:9 image (`sequential=false`). Prefer pixel size `1920x1080` or `2K` plus the canvas lock in the prompt. Product stills → `--mode image-to-image` with data URI or URL.

```bash
node skills/bili-cover/scripts/ark_seedream_generate.js \
  --prompt "<filled template>" \
  --size "1920x1080" \
  --mode image-to-image \
  --reference_images '["data:image/jpeg;base64,..."]' \
  --watermark false \
  --optimize true \
  --save-dir "<videos_dir>/edit"
```

Then copy the saved JPEG to `<videos_dir>/edit/cover.jpg` if the script used a timestamped name. Do not add text after the fact.

**Seedream CLI parameters** (keep these; do not invent others):

| Parameter | Type | Default | Required | Meaning |
|-----------|------|---------|----------|---------|
| `prompt` | string | — | yes | Image description |
| `mode` | string | `text-to-image` | no | `text-to-image` / `image-to-image` |
| `size` | string | `2K` | no | `2K` / `3K` or `WIDTHxHEIGHT` |
| `sequential` | boolean | `false` | no | Coherent set |
| `count` | integer | `4` | no | Set size when sequential (1–15). **Not sent as an API count field** — the prompt must say `生成X张一组` |
| `reference_images` | array | — | no | Up to 14 HTTP URLs or `data:image/...;base64,...` |
| `reference_strength` | number | `0.7` | no | 0–1 |
| `watermark` | boolean | `false` | no | |
| `optimize` | boolean | `true` | no | Prompt polish |
| `stream` | boolean | auto | no | On when sequential |
| `enable_web_search` | boolean | `false` | no | `tools: [{type:web_search}]` |
| `response_format` | string | `jpeg` | no | `png` / `jpeg` |
| `save-dir` | string | cwd | no | Local directory (no Desktop fallback) |

HTTP body, sequential prompt rules, and limits: `references/ark_seedream_api.md`.

When the user asks for a **coherent set**, the `prompt` itself must include `生成X张一组的连贯插画/漫画/图片`, per-image content, and style-consistency language. `sequential=true` and `count=X` are extra; they do not replace prompt semantics.

## Delivery

`B站封面：<file path or link>`

then

`封面提示词：<the filled prompt actually used>`

Verify 16:9 before declaring done.
