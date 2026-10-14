# 一番赏／魔力赏商品

## 输入与流程

- 用于介绍赏奖池及奖品；普通商品附带抽奖促销仍走普通商品流程。
- 收集赏链接或 ID、素材目录、成片时长、参考声音和 BGM；时长缺失时询问。任务产物统一写入 `<edit>`。
- 采集、选品、竖屏模板和字幕按本文执行；配音、词级对齐、混音、封面及投稿沿用[共用流程](../SKILL.md#bilibili-product-promo-hard-recipe)。
- 命令中的 `python` 使用已安装依赖的解释器，可替换为 `py`、`python3` 或解释器路径，不要求 uv。占位符先替换，路径用带引号的绝对路径。

## 接口采集

运行现有 helper，不打开商品页面、不另写请求脚本。日常制作只读取采集产物；接口变更或采集失败时再检查 helper。

```text
python "<skill_root>/helpers/lottery_goods.py" "<赏商品链接>" --edit-dir "<edit>"
python "<skill_root>/helpers/lottery_goods.py" "<商品ID>" --kind <magic或ichiban> --edit-dir "<edit>"
```

- 纯数字 ID 必须指定 `--kind`。魔力赏保留实际奖级、活动奖及同商品不同 SKU；一番赏保留全部档位、子 SKU、组合图、售罄状态及 Last 条件。
- `<edit>/lottery/<itemsId>/` 保存标准化事实 `goods.json`、原始响应 `raw/`、原图 `images/` 和图质报告 `image_quality.json`。
- 退出码：0 成功，1 请求或数据错误，2 信息不完整。接口失败或 `ready_for_render=false` 时，依据 `issues` 修复 helper 并重新采集，不猜奖级、漏活动奖或手动清空问题。
- 需要促销及挂载信息时，按共用流程调用 `biliup_goods.py` 补充；奖池事实以 `goods.json` 为准。

## 选品与素材

- **选品**：逐档覆盖，重点奖单独介绍，小奖或同系列按档位合并；每卡最多 4 件同档奖品。时长不足时明确取舍，不自行延长。
- **图质**：helper 测量真实格式、尺寸、透明主体范围和哈希，渲染时按模板区域复核。显示尺寸不得超过有效主体像素，一番赏宽度上限 800px；不足时缩小，或换同 SKU 官方高清图，不生成替代商品图。
- **完整性**：只去除全透明留白，保留商品、底座、配件及海报原字。用原图和渲染预览检查，不用页面截图作素材。
- **价格**：有来源的 `reference_price` 默认只放商品卡；魔力赏取接口 `subSkuPrice`。`draw_price` 是单抽价，不能当奖品价值；缺少独立参考价时隐藏价格区。

## 文案

共同顺序：**切入 → 重点奖 → 其他档位 → 查看详情**。以 IP、角色、造型和画面细节带动兴趣，同系列适当合并介绍；按上下文自然过渡，不固定话术、不连续报菜单。默认不讲概率，不承诺必中、保底或回本，不把小奖说成与重点奖等值，也不反复用未抽中催促追加抽取。

- 有可靠 `draw_price` 时，可说明「每次 X 元，有机会获得这款手办」的意思，明确随机机会；不能写成 X 元保证到手。价格缺失时用角色或造型开场。
- 奖级、名称与商品卡一致。售罄档位可展示，但不能说成当前可抽到。
- 收尾简短引导点击评论区链接查看完整奖池及适用规则，不逐条朗读说明书。

### 魔力赏口播结构

- 按共同顺序介绍，使用奖池中的真实奖级，不固定主打欧皇款或虚构档位。
- **魔力升级**可放在其他档位之后：仅在接口确认该奖池支持时介绍，说明适用赏品或资源、积攒对象、可兑换物品及关键条件。从已介绍的赏品自然承接，不固定转场句。
- 升级依据来自 `goods.json`、`raw/` 或 `product_info.json` 的明确规则，不能仅凭活动名称或其他奖池推断。缺规则时补齐 helper 并重新采集，仍无法核实则省略；不能把抽取次数说成兑换资源，或编造「抽几次就能换大奖」「不喜欢都能换」。

### 一番赏口播结构

- 按共同顺序介绍，使用实际 A、B 等档位，不套用魔力赏奖级，不加入升级、积攒或兑换玩法。
- Last 赏结合奖品亮点及 `acquisition_condition` 介绍，不能说成普通随机中奖；条件缺失时只介绍奖品，不推断获得方式。

## 模板与渲染

固定 **1080×1920、30fps**，默认 `default`；`--list-templates` 查看风格，`--template` 选择，模板无效时不回退。

```text
python "<skill_root>/helpers/lottery_cards.py" --list-templates
python "<skill_root>/helpers/lottery_cards.py" "<edit>/lottery/<itemsId>/goods.json" --prize-id "<奖品ID>" --template default --duration <镜头秒数> -o "<edit>/clips_visual/prize-01.mp4"
```

- 奖品 ID 取自本次清单。镜头时长来自最终口播词级对齐，在 `<edit>/lottery_shots.json` 记录 `prize_ids`、`start/end` 和对应口播；重复 `--prize-id` 生成同档合并卡，加 `--preview-only` 审阅 PNG。
- helper 自动准备前端工程及依赖，每镜保存 `preview.png`、`props.json`、`template.json`、`render_report.json`，绑定模板、真实奖品、图质和价源。
- 图片与文字居中，长名称自动换行，主体完整，底部预留字幕区。需 Node.js/npm、FFmpeg/ffprobe；中文字体自动查找，缺失时用 `--font "<字体绝对路径>"` 指定。
- 新增或调整模板时读取[模板扩展](lottery-templates.md)；日常制作复用模板及背景素材。

## 制作与字幕

1. 根据清单和原图完成选品、文案、分镜，按共用流程确认方案。
2. 生成最终口播、词级对齐并按时间窗渲染；转场用 `transitions.py --keep-duration`，画面覆盖完整口播，帧取整误差合计不超过一帧。
3. 混音后最后烧录字幕，逐字取自最终文案和音频。赏字幕使用显式样式：字号 64、左右边距 72、底部边距 180，单行最多 16 字。

```text
python "<skill_root>/helpers/build_tts_subtitles.py" "<最终文案>" "<词级转写JSON>" -o "<edit>/master.srt" --max-chars 16 --min-chars 6
python "<skill_root>/helpers/verify_tts_subtitles.py" "<最终文案>" "<edit>/master.srt" --max-chars 16
python "<skill_root>/helpers/ad_subtitles.py" "<edit>/mixed.mp4" "<edit>/master.srt" -o "<edit>/final.mp4" --profile lottery-portrait
```

## 验收与交付

- 各镜首、中、尾帧：口播、商品、奖级及价格对应，主体完整，文字居中，无溢出或字幕遮挡。
- 核对缺价隐藏、同档合并、Last 条件、售罄状态及升级依据；单抽价不混入参考价，随机机会不写成确定可得。
- 完整解码检查分辨率、帧率、口播不截尾、转场后字幕同步及共用混音响度。
- 交付成片、1 个标题、16:9 封面及同图裁出的 4:3 封面；封面沿用[封面技能](../skills/bili-cover/SKILL.md)，投稿按主技能授权流程执行。
