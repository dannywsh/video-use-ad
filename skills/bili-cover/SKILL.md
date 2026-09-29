---
name: bili-cover
description: >
  Create Bilibili covers from a product reference image or a supplied official convention poster.
  Deliver one 16:9 cover and crop its 4:3 companion using an inspected continuous crop center.
  Product image backends: native, gcp-gemini, ark-seedream. Official posters skip image generation.
  Triggers: B站封面, 封面图, cover image, bili-cover.
---

# Bili Cover

Only the cover stills. Video, TTS and upload stay in the parent skill.

`<skill_root>` 是父 `video-use` 根目录的绝对路径；`<edit>` 是父 skill 已解析的 `<videos_dir>/edit`。从本文件定位父根目录：向上两层，那里包含主 `SKILL.md` 和 `helpers/`。脚本路径从该根目录解析，不从参考文件目录或当前工作目录推导。执行会话继承父入口的 `TMPDIR`、`TMP`、`TEMP`，所有输出位于 `<edit>`。

## Modes

沿用父 skill 已确认的模式、素材和文字，不重新分类。单独调用时，根据用户目标及实际参考图选择模式；信息不足时确认所需素材。

- **product**：读取 [商品封面要求与提示词](references/product.md)。生成 **一张** 16:9，再从它裁出 4:3。按正常浏览和缩略图的人眼观感验收，轻微脸部、比例及服装细节差异允许；首张合格就采用。
- **poster**：读取 [官方海报要求](references/poster.md)。使用供应的官方宣传图，不调用生图。仅为交付比例进行确定性的缩放／裁切，保留原有画面和文字。

## Shared output and crop

Write `<edit>/cover.jpg` (16:9) and `<edit>/cover-4x3.jpg` (4:3 crop of that file). Never write into the skill repository or the Desktop. biliup still uses `--cover` + `--cover43`.

Do not generate a second 4:3 image, Seedream sequential twins or an img2img restyle to match.

- After a usable 16:9 `cover.jpg`, have the LLM inspect the finished composition and output one normalized horizontal crop center (`crop_center_x` in `[0,1]`). In product mode, preserve the product head/face and the most important readable title area; in poster mode, preserve the official main visual and important readable text; choose a continuous center rather than a fixed preset. The 4:3 aspect ratio determines the crop width, so one center point is the only crop parameter.

```bash
python "<skill_root>/skills/bili-cover/scripts/crop_cover43.py" \
  --input "<edit>/cover.jpg" \
  --output "<edit>/cover-4x3.jpg" \
  --crop-center-x 0.60
```

`--crop-center-x` is required. The LLM must provide the value after inspecting the actual cover; do not substitute a fixed preset.

## Product references, backends and credentials

仅 `product` 模式选择生图后端并检查相关凭证；`poster` 模式跳过本节及生图调用。

- **实物商品必须用实物商品图作为生图参考图**：优先选素材目录中的商品主图或清晰实拍图；每次切换后端都继续传入同一组实物参考图。动画截图、角色插画不能代替商品实物图，也不能因某个模型拒绝或失败就改用动画图生成封面。
- Backend order (user-named backend wins): **`native`（ChatGPT）** → **`gcp-gemini`** → **`ark-seedream`**. 当前后端因拒绝、错误、缺少密钥或结果不合格而无法出图时，立即用下一后端和实物参考图重试；不得重复调用已失败后端。用户指定后端时优先使用该后端，失败后仍按顺序尝试其余后端。Aliases: Gemini/Google/Vertex → `gcp-gemini`; Seedream/豆包/方舟 → `ark-seedream`. Do not start at Seedream unless named. Codex: `$imagegen` built-in `image_gen` (not Codex `scripts/image_gen.py`).

- 商品结果只因 [商品验收规则](references/product.md#redo-only-if) 中的明显问题判失败；轻微差异或怀疑被重绘不触发重做或后端切换。首张合格即结束生成。所有后端都无法生成时，停止封面流程并报告原因；不得改用动画图冒充商品封面。

- Credentials: same lookup as parent TTS (`~/.config/video-use/.env` → leftover skill-root `.env` → cwd `.env` → env). Never print a key. Ask only after lookup fails. `GCP_GEMINI_IMAGE_API_KEY` (model default `gemini-3.1-flash-lite-image`, size `1K`); `ARK_SEEDREAM_API_KEY` (model default `doubao-seedream-5.0-lite`). Optional overrides in `.env.example`.

## Backends

**native:** product mode uses the filled prompt + reference stills → save `<edit>/cover.jpg` → inspect → crop with the continuous center. Poster mode copies/prepares the supplied official poster and skips generation.

**gcp-gemini:** lock `aspectRatio=16:9`. HTTP: [gcp-gemini API](references/gcp_gemini_image_api.md).

```bash
python "<skill_root>/skills/bili-cover/scripts/gcp_gemini_image.py" \
  --prompt "<filled template>" \
  --output "<edit>/cover.jpg" \
  --reference-image "<videos_dir>/product.jpg"
```

**ark-seedream:** one image, `sequential=false`, prefer `1920x1080` or `2K`. Product stills → `--mode image-to-image`. CLI fields: [ark-seedream API](references/ark_seedream_api.md). Then rename the JPEG to `cover.jpg` if needed, then crop.

```bash
node "<skill_root>/skills/bili-cover/scripts/ark_seedream_generate.js" \
  --prompt "<filled template>" \
  --size "1920x1080" \
  --mode image-to-image \
  --reference_images '["data:image/jpeg;base64,..."]' \
  --watermark false \
  --optimize true \
  --save-dir "<videos_dir>/edit"
```

## Delivery

`B站封面：<edit>/cover.jpg`

`B站封面4:3：<edit>/cover-4x3.jpg`

商品模式：`封面提示词：<实际使用的完整提示词>`

官方海报模式：`使用官方宣传图，未调用生图`
