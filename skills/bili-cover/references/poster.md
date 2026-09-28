# Official poster cover

仅 `poster` 模式读取。视频、配音和投稿继续由父 skill 负责；两种比例的交付和连续裁切见 [封面主入口](../SKILL.md)。

## Preparation

For exhibitions, events and other 漫展 material, do **not** call an image-generation backend. Use the supplied official promotional poster as `<edit>/cover.jpg`; only perform deterministic resize/crop if its source dimensions require a 16:9 delivery file. Preserve the poster's original artwork and text. Never stretch the artwork.

官方海报原有的文字、Logo、英文、票价及制作禁词保留。商品生图的艺术字、4–8 字标题、总字数上限、“无 Logo／英文／禁词”等要求不适用于官方原图；不新画艺术字，不重绘，不伪造生图提示词。

## Inspection and delivery

检查实际的 16:9 画面，按官方主视觉和重要可读文字选择连续 `crop_center_x`，再用同一裁切脚本生成 4:3；不得为 4:3 调用生图。检查输出比例、主视觉与文字的实际保留情况。不能因缺少生成艺术字而重做官方图，也不套用商品头脸或商品保真度检查。

交付 `<edit>/cover.jpg` 与 `<edit>/cover-4x3.jpg`，注明“使用官方宣传图，未调用生图”。新写的视频文案、字幕、投稿标题及简介仍执行父 skill 的原有价格与禁词约束，封面原图例外不扩展到这些文本。
