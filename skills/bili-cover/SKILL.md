---
name: bili-cover
description: >
  Generate one 16:9 Bilibili cover with on-canvas artistic type, then crop
  cover-4x3.jpg from that same file using a subject-aware horizontal anchor.
  Do not generate a second 4:3 image.
  Backends: native, gcp-gemini, ark-seedream.
  Triggers: B站封面, 封面图, cover image, bili-cover.
---

# Bili Cover

Only the cover stills. Video, TTS, and upload stay in the parent skill.

Write `<videos_dir>/edit/cover.jpg` (16:9) and `<videos_dir>/edit/cover-4x3.jpg` (a left, center, or right crop of that file). Never write into the `video-use/` repo or the Desktop.

## Do

- Product mode: generate **one** 16:9 image, then crop 4:3 from it. biliup uses `--cover` + `--cover43`.
- Poster mode: for exhibitions, events, and other 漫展 material, do **not** call an image-generation backend. Use the supplied official promotional poster as `cover.jpg`; only perform deterministic resize/crop if its source dimensions require a 16:9 delivery file. Preserve the poster's original artwork and text.
- Inspect `cover.jpg` before cropping. Choose the crop that keeps the subject and title together: `left` when the safe content is left-weighted, `right` when it is right-weighted, and `center` only when the important content is genuinely central. Pass the choice explicitly:
- Prefer a real product/character still as the foreground so it stays recognizable.
- Keep the product as the primary subject; do not force a long figurine or tall product to show its entire body. A deliberate waist-up, three-quarter, or close crop is allowed when it makes the face, costume, silhouette, and key detail clearer. Never stretch the product to fit.
- Preserve the reference's real colors, proportions, material, markings, costume details, and product identity. Do not redesign, change the body ratio, add accessories, or invent packaging/details. The title may sit directly in front of, to the left, to the right, or above the product, but it must not cover the face, defining silhouette, or key selling point.
- Model paints all type (glyphs, stroke, shadow, layout) in the same call.
- Confirmed copy only: main title (usually 4–10 chars) and optional subtitle (6–14). High-contrast stylized type.
- Clean, low-density background. One focus.
- Backend order (user-named backend wins): **`native`** → **`gcp-gemini`** → **`ark-seedream`**. Fall through on missing keys, errors, or a result that fails the redo bar below. Aliases: Gemini/Google/Vertex → `gcp-gemini`; Seedream/豆包/方舟 → `ark-seedream`. Do not start at Seedream unless named. Grok: `image_gen` / `image_edit`. Codex: `$imagegen` built-in `image_gen` (not Codex `scripts/image_gen.py`).
- After a usable 16:9 `cover.jpg`, crop:

```bash
python skills/bili-cover/scripts/crop_cover43.py \
  --input "<videos_dir>/edit/cover.jpg" \
  --output "<videos_dir>/edit/cover-4x3.jpg" \
  --anchor left  # 根据画面检查结果替换为 center 或 right
```

- Credentials: same lookup as parent TTS (`~/.config/video-use/.env` → leftover skill-root `.env` → cwd `.env` → env). Never print a key. Ask only after lookup fails. `GCP_GEMINI_IMAGE_API_KEY` (model default `gemini-3.1-flash-lite-image`, size `1K`); `ARK_SEEDREAM_API_KEY` (model default `doubao-seedream-5.0-lite`). Optional overrides in `.env.example`.

## Don't

- Do not generate a second 4:3 image, Seedream `sequential` twins, or img2img restyle “to match.”
- Do not use image generation for 漫展/展览宣传图 when an official promotional poster is supplied; use that poster directly.
- Do not add/fix/replace type afterward (FFmpeg, PIL, Photoshop, Canva, …). Crop/resize of the generated pixels is allowed.
- Do not pin the title to the far left/right of the 16:9 canvas as a separate card, and do not let it push the product out of the safe crop.
- Do not paint 云逛、口播、混剪、资讯、宣传片、广告、配方、提示词、BGM、字幕、封面 onto the image (parent §对外文本禁词). The **generation prompt may use 封面**.
- Do not deliver a watermark, logo, extra sentence, English, or a deformed unrecognizable product.

## Redo only if

Look at **`cover-4x3.jpg`** using the selected anchor. Ship if the subject and the artistic title are both there and readable. If the crop loses either one, choose another anchor and recrop before regenerating. **Do not** redo because type is partly covered, a stroke/glow crosses the 4:3 edge, layout is imperfect, or a glyph is a bit ugly.

Redo only when:

- Canvas is not 16:9 enough for `crop_cover43.py` (script exits), or there is no image.
- 4:3 crop cuts off, hides, or materially obscures the defining subject, face, silhouette, or key product detail, or the product is the wrong item vs the reference.
- 4:3 crop has no readable artistic title (missing, cut off so it cannot be read, or clearly a different phrase than the confirmed copy).

Cap redos. If it is close, ship and say what is imperfect.

## Prompt template

Fill every placeholder. Deliver the filled prompt, not this blank.

```text
生成一张 B站视频封面。**输出必须是 16:9 宽屏（例如 1920×1080），不要生成 4:3、方形或竖图。** 4:3 会从这张 16:9 图中按已选的左侧、中央或右侧安全构图裁出；不要假设必须正中。商品主体要在选定安全区内清晰可辨，长手办允许取脸部、上半身或三分之二主体，不必为了“全身”缩得过小。标题可放在商品正前方、左侧、右侧或上方，但不能遮挡脸部、主体轮廓或关键卖点。

主题：<视频主题/产品名>
参考素材：<产品图/角色图>。严格保留真实外观、颜色、比例、材质、纹理、服装、标记和辨识度；不得拉伸、瘦身、改色、换装、添加配件或把商品改造成不同版本，不添加无关主体。

构图：商品主体在前景、够大且位于 <左侧/中央/右侧> 安全区；根据主体占画面的比例选择 4:3 裁剪锚点为 <left/center/right>。长商品采用能看清主体的自然近景，不强行放全身。标题在商品正前方、左侧、右侧或上方择一布局，和商品形成一个整体但不覆盖商品。背景用干净的 <纯色/柔和渐变/少量光晕>，低信息密度。

文字：只出现以下内容，逐字准确，由图像模型一次画完（含艺术字、描边、阴影、排版），生成后不得再加字：
“<主标题，4–10字>”
“<可选副标题，6–14字>”
醒目、立体、和商品一个色调；缩略图里也能认出标题，同时商品主体、脸部和关键细节仍然清楚。

风格：精致商业图，焦点明确，色彩饱满但不刺眼。
限制：无水印、无 Logo、无英文、无乱码、无多余句子、无畸形主体、无杂乱背景。
```

## Backends

**native:** product mode uses the filled prompt + reference stills → save `cover.jpg` → inspect → crop with the selected anchor. Poster mode copies/prepares the supplied official poster and skips generation.

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
