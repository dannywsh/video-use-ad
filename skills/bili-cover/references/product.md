# Product cover

仅 `product` 模式读取。商品图生成为一张 16:9，连续裁切和后端选择见 [封面主入口](../SKILL.md)。

## Composition and type

- Product covers must use a real product photo as the reference — never substitute anime or character illustration. Keep facial features, body proportions, main outfit structure, and key accessories; pixel-perfect replication is not required, and slight differences in folds or silhouette are acceptable.
- **Framing serves impact, not completeness.** What matters is that the product is large enough to read instantly. Show it whole when it fits at a size that still reads well. When the product is long — a tall figurine — showing the **main portion** (waist-up, three-quarter or close) is usually the *better* cover rather than a compromise: the subject gets bigger and more immediate, and that is the point. Pick whichever looks stronger. Either way the **head and face** stay inside the frame and unobscured.
- **Leave the layout to the picture.** Two arrangements both ship, and the model picks:
  - *Split* — the title forms a block on one side, the product fills the other, no overlap.
  - *Interlock* — type and product woven through each other, either one over the other.
  The frame is filled with no empty margins.
- Model paints all type (glyphs, stroke, shadow, layout) in the same call.
- Confirmed copy only, and **keep it short**: main title **4–8 chars**, optional subtitle **4–8 chars**, both lines together **at most 14**. Short copy is what buys a large type size — when the copy runs long, cut words rather than shrink the glyphs. Style the type in the **product's own visual language**: same palette, same material feel, plus small motifs echoing the IP where they fit. High contrast, readable at thumbnail size.
- Clean, low-density background. One focus.

## Do not

- Do not add/fix/replace type afterward (FFmpeg, PIL, Photoshop, Canva, …). Crop/resize of the generated pixels is allowed.
- Do not forbid the title from overlapping the product, and do not require it either. Do not add empty margins around the composition.
- Do not compose in a way that clearly changes the product's identity or version; judge product consistency by the human-eye tolerance above.
- Do not paint 云逛、口播、混剪、资讯、宣传片、广告、配方、提示词、BGM、字幕、封面 onto the image (see [广告对外文本禁词](../../../SKILL.md#对外文本禁词硬性)). The **generation prompt may use 封面**.
- Do not deliver a watermark, logo, extra sentence, English, or a deformed unrecognizable product.

## Redo only if

**How to check.** Side-by-side against the product reference photo: inspect **`cover.jpg`**, then **`cover-4x3.jpg`** at the already-verified continuous crop center. Confirm facial features, body proportions, overall proportions, main outfit structure, and key accessories match the product. Slight differences in folds or silhouette are fine. The cover title must exist and be readable in the 4:3.

**Do not redo for.** The 4:3 is a secondary placement. Acceptable without a redo:

- Title glyphs clipped by the 4:3 left/right edge
- Title overlapping the product
- A stroke or glow crossing the 4:3 edge
- Imperfect layout or a slightly ugly glyph
- Slight fold or silhouette differences vs the reference

**Redo only when** any of these is true:

- No image, or canvas is not 16:9 enough for `crop_cover43.py` (script exits)
- Body proportions are badly wrong, or overall proportions do not match the product
- Main outfit structure is wrong, or a key accessory is missing / misshapen
- Face does not match the product
- Head or face is cut by the canvas edge, or completely hidden
- 4:3 crop loses the product itself, or has no readable artistic title (missing, or clearly a different phrase than the confirmed copy)

**Retry policy.** At most 3 redos total. On a hit, switch to the next image backend and keep the same product reference photo. No hit → pass. Still failing after the limit → stop the cover flow and explain why.

## Prompt template

Fill every placeholder. Deliver the filled prompt, not this blank.

```text
生成一张 B站视频封面。**输出必须是 16:9 宽屏（例如 1920×1080），不要生成 4:3、方形或竖图。**

第一步，先看清参考图：实物商品必须使用该商品的实物照片作为参考和封面主体，保留脸部特征、头身比例、主要服装结构和关键配件。衣褶和轮廓允许轻微变化，不要改成其他商品或版本。

主题：<视频主题/产品名>
参考素材：<实物商品图>。保留脸部特征、比例、主要服装结构和关键配件；衣褶和轮廓允许轻微变化，不要更换服装或添加商品原本没有的关键配件。

构图：<商品> 是主角，够大、清晰可辨——**取景服务于展示效果，不是追求把商品拍全**。能完整放进画面且够大就完整展示；长商品（比如长手办）取主体部分（半身、三分之二或近景）**效果通常更好**：主体更大、观众一眼就能看清，这是主动选择而不是妥协。头部和脸必须在画面内、不被裁切也不被完全盖死。画面尽量填满，四周不留空边。字与商品可以干净分开（字成块占一侧、商品占满另一侧），也可以互相穿插遮挡，由你按画面效果决定——只要两者在同一个画面里构成一套完整的视觉，而不是商品旁边挂一条无关的横幅。背景用干净的 <纯色/柔和渐变/少量光晕>，和商品同色系，低信息密度。

文字：只出现以下内容，逐字准确，由图像模型一次画完（含艺术字、描边、阴影、排版），生成后不得再加字。**字数必须短：主标题 4–8 字，副标题 4–8 字（可省略），两行合计不超过 14 字。** 字少字号才能做得大、缩略图才认得出；文案过长先砍字，不要缩小字号：
“<主标题，4–8字>”
“<可选副标题，4–8字>”
醒目、立体，和商品同色系同风格（渐变填充、厚描边、投影，可点缀呼应 IP 的小装饰）；缩略图里也能认出标题，同时商品的头部、脸和关键细节仍然清楚。

风格：精致商业图，焦点明确，色彩饱满但不刺眼。
限制：无水印、无 Logo、无英文、无乱码、无多余句子、无畸形主体、无杂乱背景。
```

> The prompt stresses that face, proportions, main outfit structure, and key accessories match the physical product; slight fold or silhouette differences are allowed — pixel-perfect replication is not required.

## Delivery

Besides the two covers, deliver the filled prompt that was actually used — not this blank template.
