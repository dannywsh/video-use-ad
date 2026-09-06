---
name: bili-cover
description: >
  Generate one 16:9 Bilibili cover with on-canvas artistic type, then center-crop
  cover-4x3.jpg from that same file. Do not generate a second 4:3 image.
  Backends: native, gcp-gemini, ark-seedream.
  Triggers: B站封面, 封面图, cover image, bili-cover.
---

# Bili Cover

Only the cover stills. Video, TTS, and upload stay in the parent skill.

Write `<videos_dir>/edit/cover.jpg` (16:9) and `<videos_dir>/edit/cover-4x3.jpg` (center crop of that file). Never write into the `video-use/` repo or the Desktop.

## Do

- Generate **one** 16:9 image. Crop 4:3 from it. biliup uses `--cover` + `--cover43`.
- Prefer a real product/character still as the foreground so it stays recognizable.
- Keep the product as the primary subject and make it **fully visible from edge to edge**. The artistic title may sit directly in front of, to the left, to the right, or above the product; choose the position that gives the clearest composition. The title may visually connect to the product through matching color, contour, or glow, but it must never cover the product's face, body, silhouette, packaging, or any key selling point.
- Model paints all type (glyphs, stroke, shadow, layout) in the same call.
- Confirmed copy only: main title (usually 4–10 chars) and optional subtitle (6–14). High-contrast stylized type.
- Clean, low-density background. One focus.
- Backend order (user-named backend wins): **`native`** → **`gcp-gemini`** → **`ark-seedream`**. Fall through on missing keys, errors, or a result that fails the redo bar below. Aliases: Gemini/Google/Vertex → `gcp-gemini`; Seedream/豆包/方舟 → `ark-seedream`. Do not start at Seedream unless named. Grok: `image_gen` / `image_edit`. Codex: `$imagegen` built-in `image_gen` (not Codex `scripts/image_gen.py`).
- After a usable 16:9 `cover.jpg`, crop:

```bash
python skills/bili-cover/scripts/crop_cover43.py \
  --input "<videos_dir>/edit/cover.jpg" \
  --output "<videos_dir>/edit/cover-4x3.jpg"
```

- Credentials: same lookup as parent TTS (`~/.config/video-use/.env` → leftover skill-root `.env` → cwd `.env` → env). Never print a key. Ask only after lookup fails. `GCP_GEMINI_IMAGE_API_KEY` (model default `gemini-3.1-flash-lite-image`, size `1K`); `ARK_SEEDREAM_API_KEY` (model default `doubao-seedream-5.0-lite`). Optional overrides in `.env.example`.

## Don't

- Do not generate a second 4:3 image, Seedream `sequential` twins, or img2img restyle “to match.”
- Do not add/fix/replace type afterward (FFmpeg, PIL, Photoshop, Canva, …). Crop/resize of the generated pixels is allowed.
- Do not pin the title to the far left/right of the 16:9 canvas as a separate card, and do not let it push the product out of the safe crop.
- Do not paint 云逛、口播、混剪、资讯、宣传片、广告、配方、提示词、BGM、字幕、封面 onto the image (parent §对外文本禁词). The **generation prompt may use 封面**.
- Do not deliver a watermark, logo, extra sentence, English, or a deformed unrecognizable product.

## Redo only if

Look at **`cover-4x3.jpg`** (or the centered 4:3 of `cover.jpg`). Ship if the product and the artistic title are both there and readable. **Do not** redo because type is partly covered, a stroke/glow crosses the 4:3 edge, layout is imperfect, or a glyph is a bit ugly.

Redo only when:

- Canvas is not 16:9 enough for `crop_cover43.py` (script exits), or there is no image.
- 4:3 crop cuts off, hides, or materially obscures any part of the product, or the product is the wrong item vs the reference.
- 4:3 crop has no readable artistic title (missing, cut off so it cannot be read, or clearly a different phrase than the confirmed copy).

Cap redos. If it is close, ship and say what is imperfect.

## Prompt template

Fill every placeholder. Deliver the filled prompt, not this blank.

```text
生成一张 B站视频封面。**输出必须是 16:9 宽屏（例如 1920×1080），不要生成 4:3、方形或竖图。** 投稿会从正中裁出 4:3，所以商品必须完整、无遮挡地放在画面中心安全区内：商品的脸部、身体、外轮廓、包装和关键卖点全部清晰可见。标题可以根据画面效果放在商品正前方、左侧、右侧或上方，但必须与商品保持清晰的视觉关系，不能遮挡商品，也不能把商品挤出 4:3 正中裁切区域。

主题：<视频主题/产品名>
参考素材：<产品图/角色图>。保留真实外观、颜色、材质和辨识度，不添加无关主体。

构图：商品在前景、偏中、够大且完整可见；标题在商品正前方、左侧、右侧或上方择一布局，和商品形成一个整体但不覆盖商品。背景用干净的 <纯色/柔和渐变/少量光晕>，低信息密度。

文字：只出现以下内容，逐字准确，由图像模型一次画完（含艺术字、描边、阴影、排版），生成后不得再加字：
“<主标题，4–10字>”
“<可选副标题，6–14字>”
醒目、立体、和商品一个色调；缩略图里也能认出标题，同时商品的完整轮廓仍然清楚。

风格：精致商业图，焦点明确，色彩饱满但不刺眼。
限制：无水印、无 Logo、无英文、无乱码、无多余句子、无畸形主体、无杂乱背景。
```

## Backends

**native:** filled prompt + reference stills → save `cover.jpg` → crop.

**gcp-gemini:** lock `aspectRatio=16:9`. HTTP: `references/gcp_gemini_image_api.md`.

```bash
python skills/bili-cover/scripts/gcp_gemini_image.py \
  --prompt "<filled template>" \
  --output "<videos_dir>/edit/cover.jpg" \
  --reference-image "<product.jpg>"
```

**ark-seedream:** one image, `sequential=false`, prefer `1920x1080` or `2K`. Product stills → `--mode image-to-image`. CLI fields: `references/ark_seedream_api.md`. Then rename the JPEG to `cover.jpg` if needed, then crop.

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

## Delivery

`B站封面：<cover.jpg>`

`B站封面4:3：<cover-4x3.jpg>`

`封面提示词：<filled prompt actually used>`
