<p align="center">
  <img src="static/video-use-banner.png" alt="video-use-ad" width="100%">
</p>

# video-use-ad

**对话驱动的视频剪辑工具** — 把原始素材丢进文件夹，和 AI 助手对话，得到 `final.mp4`。适用于口播、混剪、教程、旅行、访谈等任意内容，无需预设或菜单。

本项目基于 [browser-use/video-use](https://github.com/browser-use/video-use) 二次开发，新增了小米 MiMo 与 Fish Audio TTS 配音支持。

## 功能特性

- **自动去除填充词**（`嗯`、`啊`、结巴重复）和镜头间的空白
- **自动调色**每段素材（暖调电影感、中性通透，或自定义 ffmpeg 链）
- **静态商品图动态展示**，支持中心推近、详情长图纵向滚动和宽图横向扫镜
- **商品镜头转场**，可逐个连接选择柔和方向推移、短溶解、淡黑或硬切
- **30ms 音频淡入淡出**，每个剪辑点都不会出现爆音
- **烧录字幕**，普通剪辑默认两词大写分块、可自定义；广告使用固定中文单行样式
- **AI 配音（TTS）**，支持 ElevenLabs、MiMo、Fish Audio 三个 provider；Fish Audio 支持私有可复用的声音克隆
- **生成动画叠加层**，支持 HyperFrames、Remotion、Manim 或 PIL，并行子代理逐个生成
- **渲染输出自检**，在每个剪辑边界自动评估后才展示结果
- **会话记忆持久化**到 `project.md`，下次继续编辑时无缝衔接

## 快速开始

将以下提示词粘贴到 Claude Code、Codex、Hermes、Openclaw 或任何有 shell 权限的 AI 助手中：

```text
Set up https://github.com/dannywsh/video-use-ad for me.

Read install.md first to install this repo, wire up ffmpeg, register the skill with whichever agent you're running under, and set up transcription credentials — ElevenLabs Scribe by default, or Paraformer for Chinese ASR. For AI voiceover, set up the Fish Audio API key (default TTS). Then read SKILL.md for daily usage and follow its routing to the selected workflow and relevant references. Resolve helpers from the main skill root. After install, don't transcribe anything on your own — just tell me it's ready and wait for me to drop footage into a folder.
```

助手会自动完成克隆、依赖安装、技能注册，并在需要时向你询问 API Key：

- **ElevenLabs API Key**（Scribe 默认 ASR / ElevenLabs TTS 时必需）— 词级转写、说话人分离，在 [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys) 获取
- **Paraformer Token**（中文 ASR 可选）— 托管 FunASR Paraformer-large，适合中文口播字幕时间戳；写入 `PARAFORMER_API_TOKEN`，默认地址 `https://paraformer.ow2shit.top`
- **Fish Audio API Key**（默认 TTS / 声音克隆）— 在 [Fish Audio](https://fish.audio) 获取
- **GCP Gemini / Ark Seedream**（B 站封面可选）— `GCP_GEMINI_IMAGE_API_KEY`、`ARK_SEEDREAM_API_KEY`，见 `.env.example`
- **MiMo API Key**（可选）— 仅当明确要求 MiMo 配音时需要，在 [mimo.mi.com](https://mimo.mi.com) 获取

然后进入素材文件夹启动助手：

```bash
cd /path/to/your/videos
claude    # 或 codex、hermes 等
```

在对话中说：

> 把这些素材剪成一个发布视频

助手会清点素材、提出剪辑策略、等你确认，然后在素材目录中生成 `edit/final.mp4`。所有本次任务生成的文件都必须放在 `<videos_dir>/edit/`：包括工程源代码、配置、依赖、缓存、下载素材、中间文件、预览和最终产物；素材目录根部的原始文件保持不变，项目仓库也保持干净。

## 安装 skill（用户）

装的是本仓（`dannywsh/video-use-ad`），不要装上游 `browser-use/video-use`。目录见 [dannywsh/skills](https://github.com/dannywsh/skills)。嵌套的 `skills/bili-cover/` 随本仓一起安装，不必再装独立 Seedream skill。

```bash
npx skills add dannywsh/video-use-ad -g -y
npx skills add dannywsh/biliup -g -y
npx skills update -g -y
```

全局安装后 skill 根目录一般是 `~/.agents/skills/video-use/`（Claude Code 下 `~/.claude/skills/video-use` 会链过去）。密钥写在用户配置目录，不要写进 skill 安装目录：`npx skills update` 会整目录删掉再建。

- 全平台：`~/.config/video-use/.env`（Windows 即 `%USERPROFILE%\.config\video-use\.env`）

本机路径：`python "<skill_root>/helpers/env_file.py" --user-path`。若旧密钥还在 skill 目录 `.env` 里，先跑 `python "<skill_root>/helpers/env_file.py" --migrate`。

之后更新：

```bash
python ~/.agents/skills/video-use/helpers/env_file.py --migrate
npx skills update -g -y
```

## 手动安装

仅当不使用 Skills CLI 时：

```bash
git clone https://github.com/dannywsh/video-use-ad <skill_root>
ln -sfn <skill_root> ~/.claude/skills/video-use     # Claude Code
# ln -sfn <skill_root> ~/.codex/skills/video-use    # Codex

cd <skill_root>
uv sync                         # 或：pip install -e .
brew install ffmpeg             # 必需
brew install yt-dlp             # 可选，用于下载在线素材

mkdir -p ~/.config/video-use
cp .env.example ~/.config/video-use/.env   # 填 FISH_API_KEY，以及 ELEVENLABS_API_KEY 或 PARAFORMER_API_TOKEN
# 封面可选：GCP_GEMINI_IMAGE_API_KEY、ARK_SEEDREAM_API_KEY；MIMO_API_KEY 仅在使用 MiMo 时需要
chmod 600 ~/.config/video-use/.env         # Windows 可省略 chmod
# Windows PowerShell:
# New-Item -ItemType Directory -Force "$env:USERPROFILE\.config\video-use" | Out-Null
# Copy-Item .env.example "$env:USERPROFILE\.config\video-use\.env"
```

## 项目结构

```
video-use-ad/
├── SKILL.md              # 模式选择、关键硬规则与按需读取入口
├── references/           # 共用流程、商品／活动差异及可选工具说明
├── install.md            # 首次安装指引
├── helpers/              # 核心脚本
│   ├── transcribe.py         # ASR：ElevenLabs Scribe 或 Paraformer
│   ├── transcribe_batch.py   # 批量转录
│   ├── pack_transcripts.py   # 打包转录结果为 takes_packed.md
│   ├── timeline_view.py      # 生成胶片+波形+文字标签的可视化图
│   ├── render.py             # EDL 渲染为 final.mp4
│   ├── grade.py              # 渲染输出自检
│   └── tts.py                # AI 配音（ElevenLabs + MiMo + Fish Audio）
├── static/               # 文档图片资源
├── skills/               # 子技能（manim-video、bili-cover）
├── pyproject.toml        # Python 依赖
├── .env.example          # API Key 模板
└── poster.html           # 宣传页
```

这里的 `<skill_root>`、`<videos_dir>`、`<edit>` 均须先按主入口解析为绝对路径。制作会话的临时目录设置见主入口的“临时目录”一节；首次安装与制作会话分开。

## 工作原理

以下说明普通剪辑的转录与视觉检查；商品及漫展任务按广告共用流程先采集商品事实、清点图片，再生成与对齐口播。

AI 从不"看"视频，而是**读**视频 — 通过两层信息获得词级精度的剪辑能力。

<p align="center">
  <img src="static/timeline-view.svg" alt="timeline_view — 胶片+说话人轨道+波形+词标签+静音剪切候选" width="100%">
</p>

**第一层 — 音频转录（始终加载）。** 每个素材调用一次 ASR（默认 ElevenLabs Scribe；中文口播可用 Paraformer），获得词级时间戳。Scribe 还会给出说话人分离和音频事件（`(笑声)`、`(掌声)`、`(叹气)`）。所有素材打包成一个约 12KB 的 `takes_packed.md` — 这是 AI 的主要阅读视图。

```
## C0103  (duration: 43.0s, 8 phrases)
  [002.52-005.36] S0 Ninety percent of what a web agent does is completely wasted.
  [006.08-006.74] S0 We fixed this.
```

**第二层 — 可视化合成图（按需加载）。** `timeline_view.py` 为任意时间段生成胶片+波形+词标签 PNG。仅在决策点调用 — 模糊的停顿、重拍对比、剪辑点合理性检查。

> 朴素方案：30,000 帧 × 1,500 token = **4500 万 token 噪声**。
> video-use-ad：**12KB 文本 + 少量 PNG**。

## 处理流程

```
转录 ──> 打包 ──> AI 推理 ──> EDL ──> 渲染 ──> 自检
                                                  │
                                                  └─ 有问题？修复 + 重新渲染（最多 3 次）
```

自检循环会在渲染输出的每个剪辑边界运行 `timeline_view` — 捕捉画面跳变、音频爆音、字幕遮挡。通过后才展示预览。

## AI 配音（TTS）

`helpers/tts.py` 统一支持三个 provider。**默认 Fish Audio**。仅当用户点名 MiMo 或 ElevenLabs 时才换。使用声音克隆前，请确认你拥有该声音的授权。

### Fish Audio（默认）

```bash
# 从干净的单人参考音频创建私有音色并合成。支持 wav/mp3/m4a/opus，建议每段至少 10 秒。
python "<skill_root>/helpers/tts.py" --provider fish --reference-audio "<videos_dir>/sample.wav" \
  --fish-voice-title "品牌旁白" --text "你好" --output /absolute/path/videos/edit/voiceover/out.mp3

# 后续复用首次执行打印的 Fish voice ID。
python "<skill_root>/helpers/tts.py" --provider fish --fish-voice-id <voice_id> \
  --text "下一段旁白" --output /absolute/path/videos/edit/voiceover/next.mp3

# 进阶调参：JSON 会传给 Fish Audio 的 TTS 请求。
python "<skill_root>/helpers/tts.py" --provider fish --fish-voice-id <voice_id> \
  --extra_params '{"temperature":0.5,"top_p":0.7,"prosody":{"speed":1.1}}' \
  --text "更稳定、略快的旁白" --output /absolute/path/videos/edit/voiceover/tuned.mp3
```

Fish Audio 克隆始终创建为 `private`；其 API Key 置于同一 `.env` 的 `FISH_API_KEY`。`--extra_params` 仅适用于 Fish，接收 JSON 对象；可调整 `temperature`、`top_p`、`repetition_penalty`、`chunk_length`、`latency`、`prosody` 等。`top_k` 会原样透传以兼容服务端扩展，但不在当前公开字段列表中。CLI 会保护文本、声线 ID、输出格式与模型选择，不能通过该参数覆盖。

### ElevenLabs

```bash
python "<skill_root>/helpers/tts.py" --provider elevenlabs --voice <voice_id> --text "你好" --output /absolute/path/videos/edit/voiceover/out.mp3
```

### 小米 MiMo（仅当用户点名时）

```bash
# 预置音色（冰糖、茉莉、苏打、白桦、Mia、Chloe、Milo、Dean 等）
python "<skill_root>/helpers/tts.py" --provider mimo --mimo-model tts --voice 冰糖 --text "你好" --output /absolute/path/videos/edit/voiceover/out.wav

# 文本描述定制音色
python "<skill_root>/helpers/tts.py" --provider mimo --mimo-model voicedesign --style "温柔的女声" --text "你好" --output /absolute/path/videos/edit/voiceover/out.wav

# 音频样本声音克隆（参考音频 ≤10MB，mp3/wav）
python "<skill_root>/helpers/tts.py" --provider mimo --mimo-model voiceclone --reference-audio /absolute/path/sample.wav --text "你好" --output /absolute/path/videos/edit/voiceover/out.wav
```

MiMo API 为 OpenAI 兼容格式，base URL `https://api.xiaomimimo.com/v1`，非流式调用返回 base64 编码的 wav 音频。

## B 站商品宣传片（同一 skill 的硬配方）

`video-use` 一种模式，不是第二个 skill。适合制作商品宣传片——商品主图轮播 + 动漫 OP/ED/Trailer 片段穿插 + ACG 梗口播文案 + Fish Audio 声音克隆配音 + 中文单行小字幕 + 标题封面。成片时长由用户在提示词里给出。

### 示例用法

```text
使用 skill: video-use 任务：制作一个关于「<产品名称>」的宣传广告视频，时长 <时长>。
素材在 <文件夹路径> 文件夹中。参考声音用 <.mp3>，BGM 风格：<风格>。
```

从 [`SKILL.md`](./SKILL.md) 选择模式，广告任务读取 [共用制作流程](references/promo-common.md)，再读取 [商品要求](references/product.md) 或 [活动要求](references/convention.md)。封面由 [bili-cover](skills/bili-cover/SKILL.md) 按对应模式处理：商品生成一张 16:9，查看构图后选择连续 `crop_center_x` 裁出 4:3；漫展直接使用官方宣传图，保留其原有文字、Logo、英文及票价，不调用生图。

数码电子等功能型商品允许以经核实的技术参数为叙事中心，口播、字幕、标题和简介可使用这些参数；普通商品仍保留原有属性限制。具体要求见 [商品类型参考](references/product.md#数码及功能型商品)。

商品标题优先采用“短感受句！核心商品名＋推荐类后缀”，长品牌、厂商和系列名默认省略，让角色名尽早出现。根据品类选用“推荐”“好物推荐”“周边推荐”等一个自然、简短的后缀，例如“冬装温柔感满满！椎名真昼冬服手办推荐”；默认不用“鉴赏”“赏析”，避免重复品类或额外追加一整句情绪文案。商品全名仍用于身份核验；必要版本及用户明确要求的品牌信息按需保留。详见 [商品标题要求](references/promo-common.md#商品标题要求)。

漫展、音乐会、游戏展等活动标题，从“开售、假期出游、阵容、信息整理、具体粉丝钩子”五种切入点中先筛选素材支持、视频实际覆盖的类型，再由模型自行选一种生成，不调用随机选择脚本；不套用商品的强烈感受开头结构。没有可用钩子时采用中性活动标题，最终仍只交付一个标题。适用条件、生成提示词及各活动类型示例见 [活动视频标题](references/convention.md#活动视频标题)。

漫展视频优先采用“开场 → 嘉宾 → 早鸟票优惠／VIP 特典（如有）→ 活动看点”的顺序，活动段末尾接简短点击引导；根据用户指定时长精简或展开，缺少已确认嘉宾或适用福利时跳过该段。优惠与特典须核验目标票种、销售状态及领取条件，票价仍默认仅作后台核验。口播结尾和投稿简介继续引导观众点击评论区链接，商品挂载卡片则称“商品链接”或“点链接”。详见 [漫展视频构成](references/convention.md#漫展视频构成)。

活动选材先看原图的实际栏目，再判断局部是否可上镜，不能因整页字多而排除清楚的头像、作品或实物图片。分镜按内容搭配，并将同套 KV 的横竖版归为同一主视觉组，渲染前核对复用次数、累计时长及可用但未使用的栏目；成片逐镜抽帧复核。素材不足可以有理由地复用，不要求所有图片上镜，也不靠无关画面凑数量。详见 [活动选材与主视觉复用审核](references/convention.md#活动选材与主视觉复用审核)。

### 商品信息采集

宣传片流程的第一步必须调用 biliup 的商品搜索，商品名称、价格、属性、图片和票务信息以返回的 JSON 为准：

```bash
python "<skill_root>/helpers/biliup_goods.py" 13666878 \
  --cookie /absolute/path/cookies.json \
  --output /absolute/path/videos/edit/product_info.json
```

如果 `biliup` 不在 `PATH`，添加 `--biliup-bin /absolute/path/biliup`。`product_info.json` 是当前任务的事实来源；脚本不能从文件名或图片猜测商品卖点。已核实但未生效的优惠可提醒观众先加入购物车，届时符合活动条件再参与，不表述为已经生效或人人可享。

## 设计原则

1. **文本为主，视觉按需。** 不倾倒帧数据，转录是核心界面。
2. **音频优先，画面跟随。** 剪辑点来自语音边界和静音间隙。
3. **询问 → 确认 → 执行 → 自检 → 持久化。** 未经策略确认绝不碰剪辑。
4. **对内容类型零假设。** 先看、先问，再剪辑。
5. **按模式应用规则。** 普通剪辑保留艺术自由，广告规范继续强制；关键硬规则以主入口为准。

从 [`SKILL.md`](./SKILL.md) 按需读取参考文件；普通剪辑详见 [general-edit.md](references/general-edit.md)。辅助脚本始终从技能根目录解析；所有制作进程的临时目录指向素材目录下的 `edit/tmp/`。

### 商品介绍的转场

商品全景切到局部细节时，可用 `smoothright:0.35` 或 `smoothleft:0.35`；不同素材之间可用短交叉溶解 `fade:0.25`；同一镜头的连续角度适合硬切。避免连续重复方向推移，也不要让醒目的效果盖过商品本身。

```bash
python "<skill_root>/helpers/transitions.py" "<edit>/overview.mp4" "<edit>/detail.mp4" "<edit>/display.mp4" \
  -o "<edit>/visual.mp4" --joins smoothright:0.35,fade:0.25 --keep-duration
```

默认保留节目时长：每个出点会补足转场所需的尾帧，转场从原定剪辑点开始，口播和字幕时间不变。只有明确要缩短成片、并同步重做口播与字幕时，才使用 `--no-keep-duration`。

固定整段口播的广告字幕始终对齐最终口播音频，不按画面转场重叠提前。`mix_ad_audio.py` 会在混音前检查实际视频流是否足够容纳完整口播，过短时失败并提示修正时间窗，避免静默截掉末句；限幅器启用延迟补偿。普通剪辑的声音随片段移动，两种转场模式均可使用，但字幕生成须采用与拼接一致的 `transition_handles` 设置，详见 [时间轴说明](references/edl.md)。

相关回归测试：`tests/test_render_subtitle_timing.py`、`tests/test_transitions.py`、`tests/test_mix_ad_audio.py`。最后一项包含实际混音测试，验证语音起点、末尾保留及过短画面的拒绝行为，需要本地 FFmpeg/FFprobe。

## 许可证

MIT
