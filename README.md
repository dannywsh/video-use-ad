<p align="center">
  <img src="static/video-use-banner.png" alt="video-use-ad" width="100%">
</p>

# video-use-ad

**对话驱动的视频剪辑工具** — 把原始素材丢进文件夹，和 AI 助手对话，得到 `final.mp4`。适用于口播、混剪、教程、旅行、访谈等任意内容，无需预设或菜单。

本项目基于 [browser-use/video-use](https://github.com/browser-use/video-use) 二次开发，新增了小米 MiMo TTS 配音支持。

## 功能特性

- **自动去除填充词**（`嗯`、`啊`、结巴重复）和镜头间的空白
- **自动调色**每段素材（暖调电影感、中性通透，或自定义 ffmpeg 链）
- **30ms 音频淡入淡出**，每个剪辑点都不会出现爆音
- **烧录字幕**，默认两词大写分块，完全可自定义
- **AI 配音（TTS）**，支持 ElevenLabs 和小米 MiMo 双 provider，预置音色 / 风格定制 / 声音克隆三种模式
- **生成动画叠加层**，支持 HyperFrames、Remotion、Manim 或 PIL，并行子代理逐个生成
- **渲染输出自检**，在每个剪辑边界自动评估后才展示结果
- **会话记忆持久化**到 `project.md`，下次继续编辑时无缝衔接

## 快速开始

将以下提示词粘贴到 Claude Code、Codex、Hermes、Openclaw 或任何有 shell 权限的 AI 助手中：

```text
Set up https://github.com/dannywsh/video-use-ad for me.

Read install.md first to install this repo, wire up ffmpeg, register the skill with whichever agent you're running under, and set up the ElevenLabs API key — ask me to paste it when you need it. Optionally set up the MiMo API key if I want AI voiceover. Then read SKILL.md for daily usage, and always read helpers/ because that's where the editing scripts live. After install, don't transcribe anything on your own — just tell me it's ready and wait for me to drop footage into a folder.
```

助手会自动完成克隆、依赖安装、技能注册，并在需要时向你询问 API Key：

- **ElevenLabs API Key**（必需）— 用于语音转文字（Scribe 转录），在 [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys) 获取
- **MiMo API Key**（可选）— 用于 AI 配音，在 [mimo.mi.com](https://mimo.mi.com) 获取，目前免费

然后进入素材文件夹启动助手：

```bash
cd /path/to/your/videos
claude    # 或 codex、hermes 等
```

在对话中说：

> 把这些素材剪成一个发布视频

助手会清点素材、提出剪辑策略、等你确认，然后在素材旁边生成 `edit/final.mp4`。所有输出都在 `<videos_dir>/edit/` 目录下，项目仓库保持干净。

## 手动安装

```bash
# 1. 克隆到稳定路径并软链接到助手的 skills 目录
git clone https://github.com/dannywsh/video-use-ad ~/Developer/video-use-ad
ln -sfn ~/Developer/video-use-ad ~/.claude/skills/video-use-ad     # Claude Code
# ln -sfn ~/Developer/video-use-ad ~/.codex/skills/video-use-ad    # Codex

# 2. 安装依赖
cd ~/Developer/video-use-ad
uv sync                         # 或：pip install -e .
brew install ffmpeg             # 必需
brew install yt-dlp             # 可选，用于下载在线素材

# 3. 配置 API Key
cp .env.example .env
$EDITOR .env                    # 填入 ELEVENLABS_API_KEY（必需）和 MIMO_API_KEY（可选）
```

## 项目结构

```
video-use-ad/
├── SKILL.md              # 日常使用指南（助手每次会话读取）
├── install.md            # 首次安装指引
├── helpers/              # 核心脚本
│   ├── transcribe.py         # ElevenLabs Scribe 语音转文字
│   ├── transcribe_batch.py   # 批量转录
│   ├── pack_transcripts.py   # 打包转录结果为 takes_packed.md
│   ├── timeline_view.py      # 生成胶片+波形+文字标签的可视化图
│   ├── render.py             # EDL 渲染为 final.mp4
│   ├── grade.py              # 渲染输出自检
│   └── tts.py                # AI 配音（ElevenLabs + MiMo 双 provider）
├── static/               # 文档图片资源
├── skills/               # 子技能（manim-video、video-use-ad 等）
├── pyproject.toml        # Python 依赖
├── .env.example          # API Key 模板
└── poster.html           # 宣传页
```

## 工作原理

AI 从不"看"视频，而是**读**视频 — 通过两层信息获得词级精度的剪辑能力。

<p align="center">
  <img src="static/timeline-view.svg" alt="timeline_view — 胶片+说话人轨道+波形+词标签+静音剪切候选" width="100%">
</p>

**第一层 — 音频转录（始终加载）。** 每个素材调用一次 ElevenLabs Scribe，获得词级时间戳、说话人分离和音频事件（`(笑声)`、`(掌声)`、`(叹气)`）。所有素材打包成一个约 12KB 的 `takes_packed.md` — 这是 AI 的主要阅读视图。

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

`helpers/tts.py` 统一支持两个 provider：

### ElevenLabs（默认）

```bash
python helpers/tts.py --provider elevenlabs --voice <voice_id> --text "你好" --output out.mp3
```

### 小米 MiMo（三种模式）

```bash
# 预置音色（冰糖、茉莉、苏打、白桦、Mia、Chloe、Milo、Dean 等）
python helpers/tts.py --provider mimo --mimo-model tts --voice 冰糖 --text "你好" --output out.wav

# 文本描述定制音色
python helpers/tts.py --provider mimo --mimo-model voicedesign --style "温柔的女声" --text "你好" --output out.wav

# 音频样本声音克隆（参考音频 ≤10MB，mp3/wav）
python helpers/tts.py --provider mimo --mimo-model voiceclone --reference-audio sample.wav --text "你好" --output out.wav
```

MiMo API 为 OpenAI 兼容格式，base URL `https://api.xiaomimimo.com/v1`，非流式调用返回 base64 编码的 wav 音频。

## 广告视频制作（video-use-ad 子技能）

仓库内置 **video-use-ad** 子技能（`skills/video-use-ad/`）：一份 ACG 风格商品宣传广告视频的**固定生产配方**，包装在通用剪辑流程之上。适合制作约 1 分钟的"云逛式"商品宣传片——商品主图轮播 + 动漫 OP/ED/Trailer 片段穿插 + ACG 梗口播文案 + MiMo 声音克隆配音 + 中文单行小字幕。

### 示例用法

把下面的提示词粘贴给 AI 助手（把尖括号内容换成你的实际信息）：

```text
使用 skill: Video Use 任务：制作一个时长一分钟左右关于「<产品名称>」的宣传广告视频，
素材在 <文件夹路径> 文件夹中。参考声音用 <.mp3>，BGM 风格：<风格>。
```

### 它会做什么

- **图片素材**：多用商品主图、少量详情图、避开文字过多的图；高度不足的图等比放大占满画面高度，超高的图缓慢滚动播放
- **视频素材**：从 YouTube 找相关动漫/游戏 OP、ED、Trailer 适当穿插
- **文案**：资讯类云逛口播，多放动漫梗、结合效果图与动漫设定（查 moegirl），纯口语化、不分点、不出现逻辑总结词
- **画面**：1920×1080，高斯模糊背景填充
- **BGM**：必须从 YouTube 或 Bilibili 找相关动漫/游戏 OST，禁止自行生成
- **混音**：人声 -13 LUFS，BGM 低于人声 20dB（约 -27 LUFS）且恒定不闪避，BGM 仅开头 0.5s 淡入、结尾 1.1s 淡出，人声 0.05s 淡入，限幅防削波
- **字幕**：中文单行字幕（Hiragino Sans GB W6，1080p 基准字号 72 / 字距 1 / 四周 3px 描边，无投影，每条最多 24 字），由 `helpers/ad_subtitles.py` 按成片分辨率设置 `PlayResX/Y` 后烧录，禁止自动换行
- **配音**：mimo-v2.5-tts-voiceclone 声音克隆，普通话

完整规格见 [`skills/video-use-ad/SKILL.md`](./skills/video-use-ad/SKILL.md)。

## 设计原则

1. **文本为主，视觉按需。** 不倾倒帧数据，转录是核心界面。
2. **音频优先，画面跟随。** 剪辑点来自语音边界和静音间隙。
3. **询问 → 确认 → 执行 → 自检 → 持久化。** 未经策略确认绝不碰剪辑。
4. **对内容类型零假设。** 先看、先问，再剪辑。
5. **12 条硬规则，其余自由发挥。** 制作正确性不可妥协，品味可以。

完整制作规则和剪辑技巧见 [`SKILL.md`](./SKILL.md)。

## 许可证

MIT
