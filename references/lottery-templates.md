# 赏视频模板扩展

本页用于开发模板；日常采集与制作见[赏视频流程](lottery.md)。默认模板为 `default`，无效模板或场景与工程身份不一致时阻塞，不回退。

## 模板与素材

| ID | 风格 | 背景 |
|---|---|---|
| `default` | 霓虹赏品舞台 | 前端渐变、轨道与光效 |
| `anime-fantasy` | 星樱幻想 | 简约樱花 PNG、底部猫猫头，中央留白突出商品 |

- 背景支持 PNG/JPEG/WebP、SVG 或前端绘制；模板静态资源放在各自 `public/`，直接复用。背景只承担氛围，商品使用接口原图，奖级、名称和价格为独立前景。
- `anime-fantasy` 的背景与文字固定，只有商品轻微运动；樱花在顶部边角，猫猫头在字幕下方，商品区与字幕区保持干净。

## 文件职责

- `assets/lottery/video.json`：共用画布、图片上限及字幕安全区；采集不绑定视觉模板。
- `assets/lottery/shared/`：共用依赖、Composition、字体、场景校验及居中文字组件。
- `assets/lottery/templates/<id>/`：`template.json` 定义身份、入口、配色与布局；TSX 组件负责呈现，`public/` 保存背景等资源。
- `helpers/lottery_templates.py`：发现与校验；`lottery_scene.py`：选品和真实素材绑定；`lottery_remotion.py`：工程、字体及渲染校验；`lottery_cards.py`：CLI 编排。

## 新增模板

1. 在 `assets/lottery/templates/` 新建目录，可复制 `default`。清单 `version:1`，`id` 与目录名一致，以小写字母开头，仅小写字母、数字、连字符，最多 64 字符。
2. 更新 `name`、`description` 和 `entrypoint`；入口为目录内 TSX，导出 `PrizeStage: React.FC<SceneProps>`。从 `../../schema` 引入类型，从 `../../text` 复用 `FONT`、`fitLines`、`CenteredText`，不重复加载字体。
3. `background/ink/muted/tier_colors/extra_tier_colors` 使用六位 HEX。`motion_pixels` 为 0–12；运动使用 `scene.motionPixels`，入场缩放不得超过 1。未知档位由场景模块稳定分配颜色。
4. `layouts` 提供 `"1"` 至 `"4"`，各含对应数量的区域；每区有 `image/name/price`，格式 `[x,y,width,height]`。左右留 72px，内容下沿不超过 y=1620，图像区域高度大于两倍运动余量。
5. 静态资源用 `staticFile('templates/<id>/<资源>')` 及 Remotion 图像组件加载；共用依赖集中在 `shared/package.json`。模板不存任务商品图、字体、视频、`node_modules` 或采集记录。
6. 用真实商品验证单卡、合并卡、长名称、缺价和首中尾帧，检查居中、主体完整与字幕空间。布局校验不能替代视觉检查。

```text
python "<skill_root>/helpers/lottery_cards.py" --list-templates
python "<skill_root>/helpers/lottery_cards.py" "<edit>/lottery/<itemsId>/goods.json" --prize-id "<奖品ID>" --duration <镜头秒数> --template <模板ID> --preview-only -o "<edit>/clips_visual/prize-01.mp4"
```

目录自动发现，无需改中央注册表；helper 生成 `SelectedTemplate.ts`，所有模板共用 `PrizeCard` Composition，工程隔离在 `<edit>/remotion/lottery/<id>/`。

## 场景与工程约束

- `SceneProps` 由 `shared/src/schema.ts` 定义：模板、主题、奖级、时长及真实奖品。模板仅呈现已核验的图片、尺寸和价格；`price:null` 隐藏价格，不请求奖池或生成替代商品。
- 渲染按模板区域复核有效像素及运动余量，保留图片哈希；固定 1080×1920、30fps，每卡最多 4 件同档奖品，一番赏宽度上限 800px。
- 重跑更新 helper 生成且未被编辑的文件，保留用户修改；过期文件仅在哈希仍匹配时清理。浏览器可复用同任务、同 Remotion 版本和平台的缓存。
- `src/scene.json` 为本次 Studio 数据；镜头产物及报告见[渲染流程](lottery.md#模板与渲染)。任务中的局部样式修改不会自动更新技能模板。
- 回归：`python -m unittest discover -s "<skill_root>/tests" -p test_lottery.py`；运行工程内执行 `npm run check`。前端契约验证：`node "<skill_root>/tests/check_lottery_frontend.cjs" "<运行工程>" "<props.json>" ...`。
