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
- Inspect `cover.jpg` before cropping. Pick the anchor that keeps the product well inside the crop — `left` / `right` when it sits off-centre, `center` when it is genuinely central. The title may run past the 4:3 edge. Pass the choice explicitly:
- Prefer a real product/character still as the foreground so it stays recognizable. Never stretch the product to fit.
- Preserve the reference's real colors, proportions, material, markings, costume details, and product identity. Do not redesign, change the body ratio, add accessories, or invent packaging/details. **Fidelity beats gloss: a flat-looking but proportionally accurate product passes; a glossy product with a re-engineered head/body ratio, ears, or costume structure fails.**
- **Framing serves impact, not completeness.** What matters is that the product is large enough to read instantly. Show it whole when it fits at a size that still reads well. When the product is long — a tall figurine — showing the **main portion** (waist-up, three-quarter or close) is usually the *better* cover rather than a compromise: the subject gets bigger and more immediate, and that is the point. Pick whichever looks stronger. Either way the **head and face** stay inside the frame and unobscured.
- **Leave the layout to the picture.** Two arrangements both ship, and the model picks:
  - *Split* — the title forms a block on one side, the product fills the other, no overlap.
  - *Interlock* — type and product woven through each other, either one over the other.
  The frame is filled with no empty margins.
- Model paints all type (glyphs, stroke, shadow, layout) in the same call.
- Confirmed copy only: main title (usually 4–10 chars) and optional subtitle (6–14). Style the type in the **product's own visual language** — same palette, same material feel, plus small motifs echoing the IP where they fit. High contrast, readable at thumbnail size.
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
- Do not forbid the title from overlapping the product, and do not require it either. Do not add empty margins around the composition.
- Do not sacrifice product fidelity for any layout reason — not to keep the title clear, not to fit a crop, not to satisfy an instruction about who sits in front.
- Do not paint 云逛、口播、混剪、资讯、宣传片、广告、配方、提示词、BGM、字幕、封面 onto the image (parent §对外文本禁词). The **generation prompt may use 封面**.
- Do not deliver a watermark, logo, extra sentence, English, or a deformed unrecognizable product.

## Redo only if

Look at **`cover.jpg`**, then at **`cover-4x3.jpg`** using the selected anchor. Ship if the product reads clearly and faithfully at thumbnail size, and the artistic title is present and readable somewhere in the 4:3.

**Title glyphs clipped by the 4:3 left/right edge are acceptable — do not redo for that.** The 4:3 is a secondary placement. Do not redo because the title and product overlap, a stroke/glow crosses the 4:3 edge, layout is imperfect, or a glyph is a bit ugly.

Redo only when:

- Canvas is not 16:9 enough for `crop_cover43.py` (script exits), or there is no image.
- The product is the wrong item vs the reference, **or its head/body ratio, ears, costume structure or accessory shapes have been visibly re-engineered**, or it is deformed enough to be unrecognizable.
- The product's head or face is cut by the canvas edge, or is completely hidden.
- 4:3 crop loses the product itself, or has no readable artistic title at all (missing, or clearly a different phrase than the confirmed copy).

Cap redos at 3. If it is close, ship and say what is imperfect.

## Prompt template

Fill every placeholder. Deliver the filled prompt, not this blank.

```text
生成一张 B站视频封面。**输出必须是 16:9 宽屏（例如 1920×1080），不要生成 4:3、方形或竖图。**

第一步，先看清参考图：**参考图里的<商品描述>就是最终要出现在封面上的商品照片，你的任务是把这张照片放进取景框，而不是照着它重画一个。** <外观要点，逐条写明要保住的特征：头身比、外形/耳朵、配色、材质质感、服装结构、配件形状与位置、脸部特征>。**禁止手绘化、禁止插画化、禁止重绘；上述外观特征必须与参考图一致。**

主题：<视频主题/产品名>
参考素材：<产品图/角色图>。严格保留真实外观、颜色、比例、材质、纹理、服装、标记和辨识度；不得拉伸、瘦身、改色、换装、添加配件或把商品改造成不同版本，不添加无关主体。

构图：<商品> 是主角，够大、清晰可辨——**取景服务于展示效果，不是追求把商品拍全**。能完整放进画面且够大就完整展示；长商品（比如长手办）取主体部分（半身、三分之二或近景）**效果通常更好**：主体更大、观众一眼就能看清，这是主动选择而不是妥协。头部和脸必须在画面内、不被裁切也不被完全盖死。画面尽量填满，四周不留空边。字与商品可以干净分开（字成块占一侧、商品占满另一侧），也可以互相穿插遮挡，由你按画面效果决定——只要两者在同一个画面里构成一套完整的视觉，而不是商品旁边挂一条无关的横幅。背景用干净的 <纯色/柔和渐变/少量光晕>，和商品同色系，低信息密度。

文字：只出现以下内容，逐字准确，由图像模型一次画完（含艺术字、描边、阴影、排版），生成后不得再加字：
“<主标题，4–10字>”
“<可选副标题，6–14字>”
醒目、立体，和商品同色系同风格（渐变填充、厚描边、投影，可点缀呼应 IP 的小装饰）；缩略图里也能认出标题，同时商品的头部、脸和关键细节仍然清楚。

风格：精致商业图，焦点明确，色彩饱满但不刺眼。
限制：无水印、无 Logo、无英文、无乱码、无多余句子、无畸形主体、无杂乱背景。
```

> The `第一步` paragraph is the one part worth not paraphrasing. Naming the product as *a photo to be placed in the frame rather than redrawn* is what stops the model from re-proportioning it, and the concrete appearance list only works inside that same paragraph.

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
