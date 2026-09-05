<p align="center">
  <img src="static/video-use-banner.png" alt="video-use-ad" width="100%">
</p>

# video-use-ad

**对话驱动的视频剪辑工具** — 把原始素材丢进文件夹，和 AI 助手对话，得到 `final.mp4`。适用于口播、混剪、教程、旅行、访谈等任意内容，无需预设或菜单。

本项目基于 [browser-use/video-use](https://github.com/browser-use/video-use) 二次开发，新增了小米 MiMo 与 Fish Audio TTS 配音支持。

## 功能特性

- **自动去除填充词**（`嗯`、`啊`、结巴重复）和镜头间的空白
- **自动调色**每段素材（暖调电影感、中性通透，或自定义 ffmpeg 链）
- **30ms 音频淡入淡出**，每个剪辑点都不会出现爆音
- **烧录字幕**，默认两词大写分块，完全可自定义
- **AI 配音（TTS）**，支持 ElevenLabs、MiMo、Fish Audio 三个 provider；Fish Audio 支持私有可复用的声音克隆
- **生成动画叠加层**，支持 HyperFrames、Remotion、Manim 或 PIL，并行子代理逐个生成
- **渲染输出自检**，在每个剪辑边界自动评估后才展示结果
- **会话记忆持久化**到 `project.md`，下次继续编辑时无缝衔接

## 快速开始

将以下提示词粘贴到 Claude Code、Codex、Hermes、Openclaw 或任何有 shell 权限的 AI 助手中：

```text
Set up https://github.com/dannywsh/video-use-ad for me.

Read install.md first to install this repo, wire up ffmpeg, register the skill with whichever agent you're running under, and set up transcription credentials — ElevenLabs Scribe by default, or Paraformer for Chinese ASR. For AI voiceover, set up the Fish Audio API key (default TTS). Then read SKILL.md for daily usage, and always read helpers/ because that's where the editing scripts live. After install, don't transcribe anything on your own — just tell me it's ready and wait for me to drop footage into a folder.
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

助手会清点素材、提出剪辑策略、等你确认，然后在素材旁边生成 `edit/final.mp4`。所有输出都在 `<videos_dir>/edit/` 目录下，项目仓库保持干净。

## 安装 skill（用户）

装的是本仓（`dannywsh/video-use-ad`），不要装上游 `browser-use/video-use`。目录仓见 [dannywsh/skills](https://github.com/dannywsh/skills)。嵌套的 `skills/bili-cover/` 随本仓一起安装，不必再 add 一次。

```bash
npx skills add dannywsh/skills -g -y
npx skills add dannywsh/video-use-ad -g -y
npx skills add dannywsh/biliup -g -y
npx skills update -g -y
```

全局安装后 skill 根目录一般是 `~/.agents/skills/video-use/`（Claude Code 下 `~/.claude/skills/video-use` 会链过去）。密钥写在该目录 `.env`，不要提交。

之后更新：

```bash
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

cp .env.example .env            # 填 FISH_API_KEY，以及 ELEVENLABS_API_KEY 或 PARAFORMER_API_TOKEN
# 封面可选：GCP_GEMINI_IMAGE_API_KEY、ARK_SEEDREAM_API_KEY；MIMO_API_KEY 仅在使用 MiMo 时需要
```

## 项目结构

```
video-use-ad/
├── SKILL.md              # 日常使用指南（助手每次会话读取）
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

## 工作原理

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
python helpers/tts.py --provider fish --reference-audio sample.wav \
  --fish-voice-title "品牌旁白" --text "你好" --output out.mp3

# 后续复用首次执行打印的 Fish voice ID。
python helpers/tts.py --provider fish --fish-voice-id <voice_id> \
  --text "下一段旁白" --output next.mp3

# 进阶调参：JSON 会传给 Fish Audio 的 TTS 请求。
python helpers/tts.py --provider fish --fish-voice-id <voice_id> \
  --extra_params '{"temperature":0.5,"top_p":0.7,"prosody":{"speed":1.1}}' \
  --text "更稳定、略快的旁白" --output tuned.mp3
```

Fish Audio 克隆始终创建为 `private`；其 API Key 置于同一 `.env` 的 `FISH_API_KEY`。`--extra_params` 仅适用于 Fish，接收 JSON 对象；可调整 `temperature`、`top_p`、`repetition_penalty`、`chunk_length`、`latency`、`prosody` 等。`top_k` 会原样透传以兼容服务端扩展，但不在当前公开字段列表中。CLI 会保护文本、声线 ID、输出格式与模型选择，不能通过该参数覆盖。

### ElevenLabs

```bash
python helpers/tts.py --provider elevenlabs --voice <voice_id> --text "你好" --output out.mp3
```

### 小米 MiMo（仅当用户点名时）

```bash
# 预置音色（冰糖、茉莉、苏打、白桦、Mia、Chloe、Milo、Dean 等）
python helpers/tts.py --provider mimo --mimo-model tts --voice 冰糖 --text "你好" --output out.wav

# 文本描述定制音色
python helpers/tts.py --provider mimo --mimo-model voicedesign --style "温柔的女声" --text "你好" --output out.wav

# 音频样本声音克隆（参考音频 ≤10MB，mp3/wav）
python helpers/tts.py --provider mimo --mimo-model voiceclone --reference-audio sample.wav --text "你好" --output out.wav
```

MiMo API 为 OpenAI 兼容格式，base URL `https://api.xiaomimimo.com/v1`，非流式调用返回 base64 编码的 wav 音频。

## B 站商品宣传片（同一 skill 的硬配方）

`video-use` 一种模式，不是第二个 skill。适合制作商品宣传片——商品主图轮播 + 动漫 OP/ED/Trailer 片段穿插 + ACG 梗口播文案 + Fish Audio 声音克隆配音 + 中文单行小字幕 + 标题封面。成片时长由用户在提示词里给出。

### 示例用法

```text
使用 skill: video-use 任务：制作一个关于「<产品名称>」的宣传广告视频，时长 <时长>。
素材在 <文件夹路径> 文件夹中。参考声音用 <.mp3>，BGM 风格：<风格>。
```

完整规格见 [`SKILL.md`](./SKILL.md) 的 **Bilibili product promo** 一节。

## 设计原则

1. **文本为主，视觉按需。** 不倾倒帧数据，转录是核心界面。
2. **音频优先，画面跟随。** 剪辑点来自语音边界和静音间隙。
3. **询问 → 确认 → 执行 → 自检 → 持久化。** 未经策略确认绝不碰剪辑。
4. **对内容类型零假设。** 先看、先问，再剪辑。
5. **12 条硬规则，其余自由发挥。** 制作正确性不可妥协，品味可以。

完整制作规则和剪辑技巧见 [`SKILL.md`](./SKILL.md)。

## 许可证

MIT
