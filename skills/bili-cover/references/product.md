# Product cover

仅 `product` 模式读取。商品图生成为一张 16:9，连续裁切和后端选择见 [封面主入口](../SKILL.md)。

## Composition and type

- 实物商品封面必须把该商品的实物照片作为生图参考和画面主体，优先用素材中的商品主图；动画或角色插画不能代替实物参考。Never stretch the product to fit.
- 保留商品身份、主要配色、整体比例、材质观感、服装款式和关键配件，不主动改款、换装或添加商品不存在的配件。
- **以人眼正常浏览的观感验收，不要求像素级复刻实拍图。** 定稿前将成图和参考图按相近主体大小并排查看，再检查缩略图。允许轻微脸部、表情、头身比、衣褶、纹理、光影和细小配件轮廓差异，只要一眼仍是同一款商品，整体自然，关键服装和配件可辨。不要放大找微小差异，或仅凭“AI 重画过”的判断否决结果；生成目标仍是尽量贴近实拍。
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
- 构图不能造成明显的商品身份或版本变化；商品一致性按上述人眼验收容差判断。
- Do not paint 云逛、口播、混剪、资讯、宣传片、广告、配方、提示词、BGM、字幕、封面 onto the image (see [广告对外文本禁词](../../../SKILL.md#对外文本禁词硬性)). The **generation prompt may use 封面**.
- Do not deliver a watermark, logo, extra sentence, English, or a deformed unrecognizable product.

## Redo only if

Look at **`cover.jpg`**, then at **`cover-4x3.jpg`** using the inspected continuous crop center. Ship if the product is clearly recognizable as the same item, looks natural at normal viewing and thumbnail size, and the artistic title is present and readable somewhere in the 4:3.

**Title glyphs clipped by the 4:3 left/right edge are acceptable — do not redo for that.** The 4:3 is a secondary placement. Do not redo because the title and product overlap, a stroke/glow crosses the 4:3 edge, layout is imperfect, or a glyph is a bit ugly.

Redo only when:

- Canvas is not 16:9 enough for `crop_cover43.py` (script exits), or there is no image.
- 商品明显是错误角色、错误款式或错误版本；或正常浏览时就能直接看出明显畸形、严重失衡的头身比、错误的主要服装结构、关键配件缺失或错形。轻微脸部、比例、衣褶和轮廓差异不属于重做条件。
- The product's head or face is cut by the canvas edge, or is completely hidden.
- 4:3 crop loses the product itself, or has no readable artistic title at all (missing, or clearly a different phrase than the confirmed copy).

重做总次数最多 3 次，这是上限，不是目标。第一张达到上述标准就采用，不为轻微差异重复生成或切换后端。触发重做前必须指出正常浏览时清楚可见的具体问题；如果需要放大、反复对比才能判断，或只怀疑主体被重绘，按通过处理。临界结果直接交付，必要时简短说明可见的不足。

## Prompt template

Fill every placeholder. Deliver the filled prompt, not this blank.

```text
生成一张 B站视频封面。**输出必须是 16:9 宽屏（例如 1920×1080），不要生成 4:3、方形或竖图。**

第一步，先看清参考图：实物商品必须以该商品的实物照片作为参考和封面主体，不能用动画截图或角色插画代替。优先保留商品照片的外观和实拍质感。<外观要点，简要列出主要配色、整体比例、服装款式和关键配件>。让观众一眼认出同一款商品，整体自然；允许为画面融合调整光影和少量细节，不把商品改成其他角色、款式或版本，不出现明显畸形。

主题：<视频主题/产品名>
参考素材：<实物商品图>。保留主要外观、配色、整体比例、材质观感、服装款式、重要标记和辨识度；不得明显拉伸、瘦身、改色、换装、添加商品配件或把商品改造成不同版本，不添加无关主体。

构图：<商品> 是主角，够大、清晰可辨——**取景服务于展示效果，不是追求把商品拍全**。能完整放进画面且够大就完整展示；长商品（比如长手办）取主体部分（半身、三分之二或近景）**效果通常更好**：主体更大、观众一眼就能看清，这是主动选择而不是妥协。头部和脸必须在画面内、不被裁切也不被完全盖死。画面尽量填满，四周不留空边。字与商品可以干净分开（字成块占一侧、商品占满另一侧），也可以互相穿插遮挡，由你按画面效果决定——只要两者在同一个画面里构成一套完整的视觉，而不是商品旁边挂一条无关的横幅。背景用干净的 <纯色/柔和渐变/少量光晕>，和商品同色系，低信息密度。

文字：只出现以下内容，逐字准确，由图像模型一次画完（含艺术字、描边、阴影、排版），生成后不得再加字。**字数必须短：主标题 4–8 字，副标题 4–8 字（可省略），两行合计不超过 14 字。** 字少字号才能做得大、缩略图才认得出；文案过长先砍字，不要缩小字号：
“<主标题，4–8字>”
“<可选副标题，4–8字>”
醒目、立体，和商品同色系同风格（渐变填充、厚描边、投影，可点缀呼应 IP 的小装饰）；缩略图里也能认出标题，同时商品的头部、脸和关键细节仍然清楚。

风格：精致商业图，焦点明确，色彩饱满但不刺眼。
限制：无水印、无 Logo、无英文、无乱码、无多余句子、无畸形主体、无杂乱背景。
```

> 提示词强调同款商品和自然的实拍观感即可，不堆叠“禁止重绘”“所有细节必须完全一致”等绝对要求。验收使用正常浏览下的人眼容差，不能把提示词中的保留目标变成像素级检查。

## Delivery

除两张封面外，交付实际使用的完整提示词，不交付空模板。
