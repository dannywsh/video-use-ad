---
name: bili-cover
description: >
  Create Bilibili covers from a product reference image or a supplied official convention poster.
  Deliver one 16:9 cover and crop its 4:3 companion using an inspected continuous crop center.
  Defaults to the built-in image generation tool; falls back to a user-specified generation method when no built-in tool is available, or stops and reports the exact failure reason.
  Official posters skip image generation.
  Triggers: B站封面, 封面图, cover image, bili-cover.
---

# Bili Cover

Only the cover stills. Video, TTS and upload stay in the parent skill.

`<skill_root>` 是父 `video-use` 根目录的绝对路径；`<edit>` 是父 skill 已解析的 `<videos_dir>/edit`。从本文件定位父根目录：向上两层，那里包含主 `SKILL.md` 和 `helpers/`。脚本路径从该根目录解析，不从参考文件目录或当前工作目录推导。执行会话继承父入口的 `TMPDIR`、`TMP`、`TEMP`，所有输出位于 `<edit>`。

## Modes

沿用父 skill 已确认的模式、素材和文字，不重新分类。单独调用时，根据用户目标及实际参考图选择模式；信息不足时确认所需素材。

- **product**：读取 [商品封面要求与提示词](references/product.md)。默认使用内置生图工具（若当前环境无内置生图工具，则使用用户指定的生图方式），结合实物参考图与填好的提示词生成 **一张** 16:9（保存至 `<edit>/cover.jpg`），再从它裁出 4:3。按正常浏览和缩略图的人眼观感验收，轻微脸部、比例及服装细节差异允许；首张合格就采用。若无法生成图片（无内置生图工具且用户未指定生图方式、调用报错／被拒绝、缺少必要配置，或重试达上限仍不合格），立即停止流程并告知用户具体原因。
- **poster**：读取 [官方海报要求](references/poster.md)。使用供应的官方宣传图，不调用生图。仅为交付比例进行确定性的缩放／裁切，保留原有画面和文字。

## Shared output and crop

Write `<edit>/cover.jpg` (16:9) and `<edit>/cover-4x3.jpg` (4:3 crop of that file). Never write into the skill repository or the Desktop. biliup still uses `--cover` + `--cover43`.

Do not generate a second 4:3 image or an img2img restyle to match.

- After a usable 16:9 `cover.jpg`, have the LLM inspect the finished composition and output one normalized horizontal crop center (`crop_center_x` in `[0,1]`). In product mode, preserve the product head/face and the most important readable title area; in poster mode, preserve the official main visual and important readable text; choose a continuous center rather than a fixed preset. The 4:3 aspect ratio determines the crop width, so one center point is the only crop parameter.

```bash
python "<skill_root>/skills/bili-cover/scripts/crop_cover43.py" \
  --input "<edit>/cover.jpg" \
  --output "<edit>/cover-4x3.jpg" \
  --crop-center-x 0.60
```

`--crop-center-x` is required. The LLM must provide the value after inspecting the actual cover; do not substitute a fixed preset.

## Product references and generation

仅 `product` 模式调用生图；`poster` 模式跳过本节及生图调用。

- **实物商品必须用实物商品图作为生图参考图**：优先选素材目录中的商品主图或清晰实拍图；重做时继续传入同一组实物参考图。动画截图、角色插画不能代替商品实物图，也不能因生图拒绝或失败就改用动画图、原图直接拼字或本地脚本合成冒充商品封面。
- **生图工具选择优先级（默认内置工具 → 用户指定方式）**：
  1. **默认使用内置生图工具**：优先调用当前运行环境内置的图像生成工具（如 `image_gen` / `generate_image` 等原生生图工具），传入填好的完整提示词与实物商品参考图，锁定 16:9 横屏比例，将生成结果保存为 `<edit>/cover.jpg`。
  2. **无内置工具时使用用户指定方式**：仅当当前环境没有可用的内置生图工具（或用户在提示词中明确指定了特定生图工具／脚本／服务）时，才按用户指定的生图方式执行，同样必须传入同一组实物商品参考图并锁定 16:9 输出。
  3. **无法生成图片时立即停止并报告具体原因**：若当前环境既没有内置生图工具、用户也未指定可用的生图方式，或所选生图方式因接口报错、策略拒绝、缺少凭证／参数、不支持参考图输入而失败，或按验收规则重试达到上限（最多 3 次重做）仍无法生成合格的 16:9 封面，必须**立即停止封面与后续交付／投稿流程**，并向用户明确说明具体失败原因（例如：当前环境无内置生图工具且未提供生图方式、具体接口错误或拒绝原因、哪项验收未通过）。严禁静默跳过封面、用 PIL/FFmpeg 手工贴字或拿未生图的商品原图／动画截图充当商品封面。
- 商品结果只因 [商品验收规则](references/product.md#redo-only-if) 中的明显问题判失败；轻微差异或怀疑被重绘不触发重做。首张合格即结束生成，审阅画面后按选定的连续中心点裁出 `<edit>/cover-4x3.jpg`。

## Delivery

`B站封面：<edit>/cover.jpg`

`B站封面4:3：<edit>/cover-4x3.jpg`

商品模式：`封面提示词：<实际使用的完整提示词>`

官方海报模式：`使用官方宣传图，未调用生图`
