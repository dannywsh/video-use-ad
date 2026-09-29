---
name: video-use
description: >
  Edit any video by conversation, or produce a Bilibili ACG product or event promo.
  General edits include transcribe, cut, color grade, overlays, subtitles, and AI voiceover
  for talking heads, montages, tutorials, travel, interviews.
  Bilibili promo uses stills, relevant official OP/ED/Trailer when useful, spoken copy,
  Fish Audio clone, single-line Chinese captions, LUFS mix, one title and 16:9 plus 4:3 covers.
  Product copy checks current itemId promotions and places verified offers before a comment goods link.
  Runtime comes from the user prompt, not a skill default.
  Triggers: 剪辑, 宣传广告视频, 商品宣传, ACG 宣传, 产品宣传片, 漫展宣传, event video titles.
  Production-correctness rules are hard; general edits otherwise have artistic freedom.
---

# Video Use

## Principle

1. **LLM reasons from raw transcript + on-demand visuals.** The only derived artifact that earns its keep is a packed phrase-level transcript (`takes_packed.md`). Everything else — filler tagging, retake detection, shot classification, emphasis scoring — you derive at decision time.
2. **Audio is primary, visuals follow.** Cut candidates come from speech boundaries and silence gaps. Drill into visuals only at decision points.
3. **Ask → confirm → execute → iterate → persist.** Never touch the cut until the user has confirmed the strategy in plain English.
4. **Generalize.** Do not assume what kind of video this is. Look at the material, ask the user, then edit.
5. **Artistic freedom is the default.** In the General edit section, specific taste values, presets, fonts, colors, durations, pitch structures and techniques are worked examples, unless explicitly marked as requirements. Bilibili promo production standards remain mandatory. Read them to understand what's possible and why each worked. Then make your own taste calls based on what the material actually is and what the user actually wants. **Follow the Hard Rules and the mandatory requirements of the selected mode.** General-edit taste examples remain adaptable.
6. **Invent freely.** If the material calls for a technique not described here — split-screen, picture-in-picture, lower-third identity cards, reaction cuts, speed ramps, freeze frames, crossfades, match cuts, L-cuts, J-cuts, speed ramps over breath, whatever — build it. The helpers are ffmpeg and PIL. They can do anything the format supports. Do not wait for permission.
7. **Verify your own output before showing it to the user.** If you wouldn't ship it, don't present it.

## Modes

Pick one at session start. Do not blend the two recipes.

- **General edit** (default). Existing footage: talking heads, interviews, tutorials, travel, montages. Artistic freedom except Hard Rules. Follow [The process](#the-process).
- **Bilibili product promo.** Triggers: 宣传广告视频, 广告视频, 云逛视频, ACG 宣传, 商品宣传视频, 产品宣传片, 漫展宣传, or a Bilibili product/event video from stills + cloned voice. Then [Bilibili product promo](#bilibili-product-promo-hard-recipe) is a **hard recipe** — for product tasks, the narrative centers on the product/character itself, its visual traits, setting, atmosphere, and audience appeal; event tasks follow the applicable event details below. Do not turn ordinary goods into a specification list; technical parameters may be central only for digital/electronic or other function-led products, and price is omitted from outward copy by default. Runtime is whatever the user wrote in the prompt; do not assume a length. Hard Rules still apply. Do not substitute general subtitle/mix taste examples for the locked promo path.

广告任务开始时，除本文外仅读取适用的一份题材细节：普通商品／手办及数码等功能型商品用 [product.md](references/product.md)；漫展、游戏展、展览、音乐会用 [convention.md](references/convention.md)；一番赏／魔力赏商品用 [lottery.md](references/lottery.md)。漫展的段落顺序、活动标题切入点和选材复用审核以活动参考为准；普通商品附带抽奖促销不因此改为一番赏／魔力赏题材。

结合用户目标、商品详情和实际素材分类，不能仅凭 `mall` / `ticket` 判断；若仍不明确且会影响制作，先确认。广告时长只从用户提示词读取，缺失时追问；数码等功能型商品允许经核实的技术参数成为叙事中心。

通用流程、工具、配音、动画、EDL、混音、字幕和投稿检查均在本文，已读且未变化的内容在本会话复用，不逐阶段搜索参考文件。普通剪辑见 [The process](#the-process)，广告见 [执行流程](#执行流程)，时间轴见 [EDL format](#edl-format)；用户明确要求投稿时，两种模式都必须先完成 [B站唯一投稿闸门](#b站唯一投稿闸门)。封面和 Manim 制作时才读取对应子 skill，辅助脚本统一从 `<skill_root>` 解析。

## Hard Rules (production correctness — non-negotiable)

These are the things where deviation produces silent failures or broken output. They are not taste, they are correctness. Memorize them.

1. **Subtitles are applied LAST in the filter chain**, after every overlay. Otherwise overlays hide captions. Silent failure.
2. **Per-segment extract, then join.** Hard-cut joins use lossless `-c copy` concat. Visual transitions use `xfade` on the *already-extracted* 1080p segments (`<skill_root>/helpers/transitions.py`). Never pull original sources into one giant filtergraph with overlays — that double-encodes.
3. **30ms audio fades at every hard-cut boundary** (`afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03}:d=0.03`). Otherwise audible pops at every cut. `xfade` joins use `acrossfade` of the same duration instead of a hard audio cut.
4. **Overlays use `setpts=PTS-STARTPTS+T/TB`** to shift the overlay's frame 0 to its window start. Otherwise you see the middle of the animation during the overlay window.
5. **Per-source master SRT uses output-timeline offsets**: `output_time = word.start - segment_start + segment_offset`. `segment_offset` follows the selected transition policy: default `--keep-duration` / `transition_handles=true` preserves authored cut offsets; only `--no-keep-duration` / `transition_handles=false` subtracts the actual inbound xfade overlap. Fixed narration/TTS captions stay locked to the final audio; do not subtract visual overlaps from their timestamps. See [EDL timing](#edl-format). Otherwise captions misalign after segment concat.
6. **Never cut inside a word.** Snap every cut edge to a word boundary from the word-level transcript.
7. **Pad every cut edge.** Working window: 30–200ms. ASR timestamps drift 50–100ms — padding absorbs the drift. Tighter for fast-paced, looser for cinematic.
8. **Word-level verbatim ASR only.** Never SRT/phrase mode (loses sub-second gap data). Never normalized fillers (loses editorial signal).
9. **Cache transcripts per source.** Never re-transcribe unless the source file itself changed.
10. **Parallel sub-agents for multiple animations.** Never sequential. Spawn N at once via the `Agent` tool; total wall time ≈ slowest one.
11. **Strategy confirmation before execution.** Never touch the cut until the user has approved the plain-English plan.
12. **All generated session files in `<edit>/`.** This includes engineering projects (source code, configs, manifests, lockfiles, local dependencies, scripts, and per-slot working directories), intermediate media, downloaded media, caches, reports, previews, and final deliverables. Never scaffold, render, download, or cache session files in the `video-use/` project directory, the current working directory, or beside the source files outside `<edit>/`.
13. **TTS narration subtitles are verbatim and final-audio aligned.** Generate captions only after the final TTS audio exists. Every spoken word, including brand names, qualifiers, and fillers the user expects, must appear in the subtitles in the same order; split only at natural semantic boundaries and never summarize, paraphrase, or omit text. Derive timestamps from word-level transcription or forced alignment of that exact final audio, then convert them to output-timeline offsets. Never hand-estimate subtitle timings from the script or total runtime.
14. **Inserted third-party footage must carry the intended meaning on screen.** For a game, film, animation, or product promo, every inserted clip must visibly show the relevant character, world, gameplay, product use, or other claim-supporting subject during its usable duration. Do not use platform logos, publisher cards, rating screens, preorder/date cards, title-only frames, black frames, or generic footage as a substitute. Sample the planned in/out frames before editing; discard or trim any clip whose visible content does not directly support the adjacent narration, caption, or product claim.
15. **B站视频只能真实投稿一次。** 一次任务中只允许触发一次视频上传/投稿；超时、网络错误、返回不明确、投稿后抽查发现问题或任何其他原因都不得再次上传同一视频，也不得换投稿方式补投。`show`、列表查询、`ffprobe`、抽帧、预览和其他只读核验不算投稿。
16. **所有投稿校验必须发生在投稿动作之前。** 最终视频、字幕、音频、画面、标题、简介、标签、分区、16:9 封面、4:3 封面及（如有）商品身份/挂载参数，必须在真实投稿前一次性校验并锁定；校验有任何失败、缺失或不确定，投稿动作必须保持未执行。
17. **投稿命令启动后不得因结果不确定而重试。** 只用 `biliup list` / `biliup show <BV/AV>` 等只读命令核实状态；无法确认是否已投稿时，按唯一投稿机会已消耗处理，停止上传并向用户报告。投稿后的抽查只能用于记录结果或决定允许的后置动作，不能触发第二次投稿。
18. **长时渲染不得使用一次性阻塞调用。** 任何预计超过单次工具等待上限的 `ffmpeg`、`stable_motion.py`、`transitions.py`、字幕烧录或混音任务，必须在可持续的 PTY/后台会话中启动，保存会话 ID，分段轮询直到进程自然结束；不得因为一次工具调用返回或等待上限而判断渲染失败。
19. **渲染产物必须原子完成。** 每个长任务先输出到唯一的临时文件或临时目录，只有进程退出码为 0、`ffprobe` 可读、完整解码到 EOF 且时长/分辨率符合预期后，才能改名为正式产物并进入下一步。中断、超时、`moov atom not found`、解码错误或文件大小异常时，必须丢弃该临时产物并从同一输入重新渲染；不得把半成品交给拼接、混音、字幕或投稿流程。
20. **禁止因渲染耗时降级画面实现。** 渲染慢、工具等待到期、单段失败或会话中断时，禁止改用会裁切主体的 `scale=increase+crop`、强制填充、静态截图、缩短镜头、跳过转场或其他改变已确认画面策略的替代方案。应恢复/分段执行原定 helper 或修复执行会话；若原定方案无法完成，停止并报告阻塞原因。
21. **商品主体完整性是阻塞检查。** 完整商品镜头必须保留商品全貌；只有明确作为细节镜头的素材才允许用 `pan-right` 中心放大裁切，且需要让解说中的目标细节在扫镜过程中清楚可见。完整商品镜头的头部、脸、脚、底座及关键配件不得被裁掉。每个商品镜头至少抽查首帧、中帧、尾帧，发现主体或目标细节丢失必须修复后才能继续。

General-edit taste examples are adaptable. Mandatory promo, animation and production requirements retain their stated scope; animation easing does not override the fixed-speed motion of promo stills.

## Directory layout

The skill lives in `video-use/`. User footage lives wherever they put it. All session outputs go into `<edit>/`.

```
<videos_dir>/
├── <source files, untouched>
└── edit/
    ├── project.md               ← memory; appended every session
    ├── takes_packed.md          ← phrase-level transcripts, the LLM's primary reading view
    ├── edl.json                 ← cut decisions
    ├── transcripts/<name>.json  ← cached raw word-level ASR JSON
    ├── animations/slot_<id>/    ← per-animation source + render + reasoning
    ├── clips_graded/            ← per-segment extracts with grade + fades
    ├── voiceover/               ← TTS audio (tts.py output)
    ├── master.srt               ← output-timeline subtitles
    ├── downloads/               ← yt-dlp outputs
    ├── verify/                  ← debug frames / timeline PNGs / still bands
    ├── submission_preflight.md ← 投稿前检查清单、锁定参数和文件 SHA-256
    ├── stills_inventory.md      ← promo stills: on-screen / voice-only facts / unused
    ├── cover.jpg                ← 16:9 Bilibili cover (skills/bili-cover)
    ├── cover-4x3.jpg            ← continuous crop_center_x crop of cover.jpg
    ├── preview.mp4
    └── final.mp4
```

### 工程文件路径契约

`<videos_dir>` 是用户素材所在目录，`<edit>` 永远等于 `<videos_dir>/edit`。会话开始时先解析这两个绝对路径并创建 `<edit>`；后续所有新建路径都必须从 `<edit>` 派生。素材目录中的原始视频、图片、音频和用户已有文件只读，不得为了方便把工程文件写到素材目录根部。

“工程文件”包括但不限于 HyperFrames/Remotion/Manim/PIL 的源代码、HTML/CSS/JS/TS/py 文件、`package.json`、锁文件、配置文件、虚拟环境、`node_modules`、临时文件、渲染脚本和调试日志。按动画槽位放在 `<edit>/animations/slot_<id>/`；普通剪辑中间工程放在 `<edit>/` 下对应的功能目录，例如 `<edit>/clips_visual/`、`<edit>/voiceover/`、`<edit>/verify/`。

所有命令使用绝对输入和输出路径；需要切换工作目录时，只能切换到 `<edit>` 或其子目录。禁止使用裸的 `-o out.mp4`、`--output result.json` 等相对输出路径。EDL、日志和交付说明中的文件引用也必须指向 `<edit>` 下的实际路径。交付前检查素材目录根部没有本次生成的工程文件，若发现误写，先移动到对应的 `<edit>` 子目录并修正引用，再继续渲染。

### 临时目录

开始制作时，在已解析的绝对路径 `<edit>` 下创建 `tmp/`，并在每个制作进程启动前设置 `TMPDIR`、`TMP`、`TEMP`；重开执行会话或启动动画代理时继续传递这些变量。Python 和其他工具的自动清理临时文件也必须落在该目录。辅助脚本保持原样。

macOS / Linux（以下 `<edit>` 必须替换为实际绝对路径）：

```bash
mkdir -p "<edit>/tmp"
export TMPDIR="<edit>/tmp"
export TMP="<edit>/tmp"
export TEMP="<edit>/tmp"
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force "<edit>/tmp" | Out-Null
$env:TMPDIR = "<edit>/tmp"
$env:TMP = "<edit>/tmp"
$env:TEMP = "<edit>/tmp"
```

`<skill_root>` 为包含本 `SKILL.md` 和 `helpers/` 的主技能根目录绝对路径；`<videos_dir>` 为素材目录绝对路径；`<edit>` 为 `<videos_dir>/edit`。本文及参考文件中的命令占位路径必须先解析，再执行。首次安装见 [install.md](install.md)，工程路径约定适用于制作会话。

## Setup

First-time install lives in [install.md](install.md) (clone, deps, ffmpeg, skill registration, API keys). Don't re-run it every session; on cold start just verify:

- **Credential discovery (mandatory before asking the user):** keys live outside the skill install directory because `npx skills update` deletes and recreates it. Canonical file: `~/.config/video-use/.env` on all platforms (Windows: `%USERPROFILE%\.config\video-use\.env`; or `$XDG_CONFIG_HOME/video-use/.env`, or `$VIDEO_USE_ENV`). Print the local path with `python "<skill_root>/helpers/env_file.py" --user-path`. Lookup order matches `<skill_root>/helpers/env_file.py`: user config → leftover `<skill_root>/.env` (copied to user config on first helper run) → `<cwd>/.env` → exported environment variables. Do **not** infer the key file from the current workspace, source-video directory, or a hard-coded example path. If a leftover skill-root `.env` exists, run `python "<skill_root>/helpers/env_file.py" --migrate` before updating.
- Run the check for the relevant key names (`ELEVENLABS_API_KEY`, `MIMO_API_KEY`, `FISH_API_KEY`, `PARAFORMER_API_TOKEN`, `GCP_GEMINI_IMAGE_API_KEY`, `ARK_SEEDREAM_API_KEY`) with the helpers' parsing semantics: strip whitespace around the key name and value, accept quoted values, and treat an empty value as missing. Do not use a strict `^KEY=` regex, because a valid `.env` may contain spaces around `=`. Never print a key or its prefix in tool output.
- `ELEVENLABS_API_KEY` resolves from that lookup — required for Scribe transcription (the default ASR) and ElevenLabs TTS. Ask the user only after the mandatory discovery check fails, then write a supplied key to the user-config `.env` from `--user-path` (never to the skill install directory, never to the user's `<videos_dir>`).
- `PARAFORMER_API_TOKEN` resolves using the same lookup — required only for `--provider paraformer`. Optional `PARAFORMER_API_URL` overrides the default `https://paraformer.ow2shit.top`. Ask the user only after the discovery check fails.
- `FISH_API_KEY` resolves using the same lookup — required for the default Fish Audio TTS / voice cloning. Ask the user only after the discovery check fails.
- `MIMO_API_KEY` resolves using the same lookup — required only when the user explicitly asks for MiMo TTS. If MiMo is not used, leave it unset.
- `ffmpeg` + `ffprobe` on PATH.
- Python deps installed (`uv sync` or `pip install -e .` inside the repo).
- Node.js + npm available if the session needs HyperFrames, Remotion, or the `ark-seedream` cover backend. HyperFrames currently requires Node.js 22+; Seedream needs Node 18+.
- `yt-dlp`, HyperFrames, Remotion, Manim installed only on first use.
- First-use animation setup happens inside the slot directory, never at the video-use repo root. HyperFrames can be invoked with `npx --yes hyperframes ...`; Remotion can be scaffolded with `npx create-video@latest` or installed as a project-local dependency before using its `remotion render` command.
- This skill vendors `skills/manim-video/`. Read [Manim 子 skill](skills/manim-video/SKILL.md) when building a Manim slot.
- This skill vendors `skills/bili-cover/`. When delivering a Bilibili cover, read [封面子 skill](skills/bili-cover/SKILL.md) (do not improvise the cover recipe here).
- `GCP_GEMINI_IMAGE_API_KEY` resolves from that lookup — required for the `gcp-gemini` cover backend. Optional `GCP_GEMINI_IMAGE_MODEL` / `GCP_GEMINI_IMAGE_API_ENDPOINT` / `GCP_GEMINI_IMAGE_SIZE` override model, host, and `imageSize`.
- `ARK_SEEDREAM_API_KEY` resolves from that lookup — required for the `ark-seedream` cover backend. Optional `ARK_SEEDREAM_MODEL` / `ARK_SEEDREAM_API_BASE_URL` override model and Ark base URL.
- Bilibili product promo is part of this skill (not a nested skill). When that mode is active, follow [广告共用制作流程](#bilibili-product-promo-hard-recipe). Cover stills follow `skills/bili-cover/`.

Helpers (`<skill_root>/helpers/transcribe.py`, `<skill_root>/helpers/render.py`, etc.) live under the main skill root alongside its SKILL.md. Resolve their paths from `<skill_root>`, not from the current working directory — the skill is typically symlinked at `~/.claude/skills/video-use/` or `~/.codex/skills/video-use/`.

## Helpers

### 长时渲染执行协议

渲染工具的单次等待上限属于外层执行环境，不是视频任务的时长上限。凡是可能超过该上限的任务，必须采用可持续会话：在 PTY 或后台会话中启动命令，保留会话 ID，使用轮询读取进度和退出码。不要把多个长镜头串进一个普通阻塞调用，也不要用一次调用返回来判断 FFmpeg 是否完成。

每个输出必须遵循以下顺序：

1. 写入唯一临时路径，例如 `<edit>/clips_visual/slot_03.tmp.mp4`，不得直接覆盖正式产物。
2. 会话自然结束后检查退出码。
3. 运行 `ffprobe` 检查容器、音视频流、时长、分辨率和帧率。
4. 运行一次完整解码到 null 输出，确认没有 `Invalid NAL`、`moov atom not found` 或其他解码错误。
5. 仅当上述检查全部通过时，才将临时文件改名为正式路径。

如果会话被中断，必须从原始输入恢复渲染并重新校验。禁止使用裁切、强制拉伸、静态截图、缩短时长或跳过已确认工序来掩盖渲染耗时；禁止把未完成文件交给 `transitions.py`、`mix_ad_audio.py`、字幕烧录或投稿流程。

- **`transcribe.py <video>`** — single-file ASR. `--provider elevenlabs|paraformer` (default elevenlabs). `--num-speakers N` is Scribe-only. `--audio-track N` selects a zero-based audio stream (OBS: 0 = game, 1 = mic); track 0 keeps the existing `{stem}.json` cache name, other tracks write `{stem}.trackN.json`. Refuses to upload a silent track (peak < -60 dBFS). Cached. Writes Scribe-compatible `words` JSON for either provider.
- **`transcribe_batch.py <videos_dir>`** — 4-worker parallel transcription. Same `--provider` and `--audio-track` flags. Use for multi-take.
- **`pack_transcripts.py --edit-dir <dir>`** — `transcripts/*.json` → `takes_packed.md` (phrase-level, break on silence ≥ 0.5s).
- **`timeline_view.py <video> <start> <end>`** — filmstrip + waveform PNG. On-demand visual drill-down. **Not a scan tool** — use it at decision points, not constantly.
- **`render.py <edit>/edl.json -o <edit>/<name>.mp4`** — per-segment extract → join (lossless concat or xfade) → overlays (PTS-shifted) → subtitles LAST. `--preview` for 720p fast. `--build-subtitles` to generate master.srt inline. Default output fps matches the first source (`--fps 30` or `--fps 30000/1001` to force). Portrait detection honors display-matrix rotation so phone footage scaled on the right axis. Pass absolute paths under `<edit>`.
- **`transitions.py <clips...> -o <edit>/<name>.mp4`** — join already-rendered clips with visual transitions. Default `--type fade --duration 0.4`. Per-join: `--joins fade:0.4,cut,fadeblack:0.5`. `--an` when a later mix pass replaces audio (Bilibili promo). Default `--keep-duration` pads each outgoing clip by the xfade so the programme length stays aligned with an already-authored TTS/SRT; `--no-keep-duration` lets overlaps shorten the output. Hard-cut-only runs stay lossless `-c copy`. Pass absolute paths under `<edit>`.
- **`tts.py <text> -o <edit>/voiceover/<name>.mp3`** — text-to-speech for adding voiceover/narration. `--provider fish|mimo|elevenlabs` (default **fish**). Fish Audio creates a reusable private clone from `--reference-audio` or reuses `--fish-voice-id`. MiMo is opt-in for preset voices, voice design, or short-sample cloning. `--style` is MiMo-only. Outputs wav/mp3 ready to mix with ffmpeg; always pass an absolute path under `<edit>/voiceover/`.
- **`grade.py <in> -o <out>`** — ffmpeg filter chain grade. Presets + `--filter '<raw>'` for custom.
- **`bilibili_src.py <cmd>`** — Bilibili stock-source helper (good for ACG/anime/game OST and short clips). `search "<kw>" --n 5` lists candidates (bvid/title/UP主/duration); `check-watermark <BVid>` heuristically detects a burned-in watermark by checking edge detail in all four corners against the center — **run it BEFORE using any Bilibili-sourced VIDEO as stock; a watermark hit means discard that clip** (videos from YouTube/other platforms are NOT subject to this check); `download <BVid> --audio-out/--video-out [--force] [--cookies-from-browser <browser>]` pulls audio (BGM, no watermark concern) or video via yt-dlp. Video formats need a logged-in cookie (see below). This check is heuristic; visually spot-check any borderline or business-critical result.
- **Bilibili cookie acquisition:** pass `--cookies-from-browser <chrome|firefox|edge|safari|brave>`; yt-dlp reads the already-logged-in Bilibili cookie straight from the user's local browser (no manual export). Anonymous downloads are audio-only.
- **`env_file.py`** — dotenv lookup and migrate. Canonical keys: `~/.config/video-use/.env` on all platforms (Windows: `%USERPROFILE%\.config\video-use\.env`). `--user-path` prints the local file; `--migrate` copies a leftover skill-root `.env` there so `npx skills update` cannot wipe keys.
- **`inventory_stills.py`** — list stills, draw a y-tick overview for tall infographics, and crop full-width windows the agent already chose. Does **not** auto-slice by 16:9 viewport, color gaps, or OCR. Crops pad both ends by default (prefer extra neighbors over clipped goods). `region` in crop JSON is for `stable_motion.py --region`. See [静图分拣](#静图分拣硬性).
- **`stable_motion.py`** — jitter-free push/scroll/pan of product stills. `--mode scroll` crawls vertically at a fixed 0.18 screens/s. `--mode pan-right` uses a natural wide image at 0.12 screen widths/s; near-16:9 images selected for detail appreciation get a centered 1.18× zoom and a slower 0.04 screen widths/s scan. On 16:9 footage this crops about 7.6% from the top and bottom, so reserve it for detail shots; use `push` for complete product views. Narrower images fall back to `push`. Scroll supports `--anchor top|center|bottom`, `--region 0.12,0.45`, and `--probe`; `pan-right` also supports `--probe` to inspect available travel and zoom. See [广告共用制作流程](#bilibili-product-promo-hard-recipe).
- **`mix_ad_audio.py`** — locked promo mix (voice -13 LUFS, BGM -27 LUFS), with limiter delay compensation. Rejects narration longer than the actual video stream before mixing; rebuild the visual timing or narration/subtitles together instead of truncating speech. Promo mode only.
- **`build_tts_subtitles.py` / `verify_tts_subtitles.py` / `ad_subtitles.py`** — verbatim single-line Chinese captions for promo TTS. Promo mode only.

**ASR provider choice** (do not default blindly):

- **ElevenLabs Scribe** (`--provider elevenlabs`, default) — word-level timestamps, speaker diarization, filler/audio-event tags. Use for multi-take talking-head inventory, interviews, and any cut that needs speaker changes or `(laughs)` / `(sighs)`. Requires `ELEVENLABS_API_KEY`.
- **Paraformer** (`--provider paraformer`) — hosted FunASR Paraformer-large at `https://paraformer.ow2shit.top`. Chinese-first character timestamps, no diarization, no audio events. Use for Chinese TTS/voiceover subtitle timing, and for Chinese-only sources when speaker IDs and audio events are not needed. Requires `PARAFORMER_API_TOKEN`. Never pass `response_format=srt` into the edit pipeline — the helper converts JSON to word-level `words` entries.

```bash
python "<skill_root>/helpers/transcribe.py" "<edit>/voiceover/narration.wav" --edit-dir "<edit>" --provider paraformer
python "<skill_root>/helpers/transcribe_batch.py" <videos_dir> --provider paraformer
```

For animations, create `<edit>/animations/slot_<id>/` with `Bash` and spawn a sub-agent via the `Agent` tool.

## The process

If this session is **Bilibili product promo**, skip this section and follow [广告共用制作流程](#bilibili-product-promo-hard-recipe) instead.

1. **Inventory.** `ffprobe` every source. `transcribe_batch.py` on the directory. `pack_transcripts.py` to produce `takes_packed.md`. Sample one or two `timeline_view`s for a visual first impression.
2. **Pre-scan for problems.** One pass over `takes_packed.md` to note verbal slips, obvious mis-speaks, or phrasings to avoid. Plain list, feed into the editor brief.
3. **Converse.** Describe what you see in plain English. Ask questions *shaped by the material*. Collect: content type, target length/aspect, aesthetic/brand direction, pacing feel, must-preserve moments, must-cut moments, animation and grade preferences, subtitle needs, voiceover needs. Do not use a fixed checklist — the right questions are different every time.
4. **Propose strategy.** 4–8 sentences: shape, take choices, cut direction, animation plan, grade direction, subtitle style, voiceover plan, length estimate. **Wait for confirmation.**
5. **Execute.** Produce `edl.json` via the editor sub-agent brief. Drill into `timeline_view` at ambiguous moments. Build animations in parallel sub-agents. Generate voiceover with `tts.py` if requested. Apply grade per-segment. Compose via `render.py`.
6. **Preview.** `render.py --preview`.
7. **Self-eval (before showing the user).** Run `timeline_view` on the **rendered output** (not the sources) at every cut boundary (±1.5s window). Check each image for:
   - Visual discontinuity / flash / jump at the cut
   - Waveform spike at the boundary (audio pop that slipped past the 30ms fade)
   - Subtitle hidden behind an overlay (Rule 1 violation)
   - Overlay misaligned or showing wrong frames (Rule 4 violation)

   Also sample: first 2s, last 2s, and 2–3 mid-points — check grade consistency, subtitle readability, overall coherence. Run `ffprobe` on the output to verify duration matches the EDL expectation.

   For every externally inserted game, film, animation, or stock clip, inspect a frame near its start, midpoint, and end. Verify that the intended relevant subject is actually visible and that no logo/card/preorder/title-only frame remains. Treat a failed relevance check as a blocking defect: replace or trim the clip, then re-render.

   If anything fails: fix → re-render → re-eval. **Cap at 3 self-eval passes** — if issues remain after 3, flag them to the user rather than looping forever. Only present the preview once the self-eval passes.
8. **Iterate + persist.** Natural-language feedback, re-plan, re-render. Never re-transcribe. Final render on confirmation. Append to `project.md`.

### B站唯一投稿闸门

仅用户明确要求投稿时执行。制作视频本身不授权投稿、评论或其他发布动作；后置动作需要用户对应授权。广告标题、简介和挂载文案见本文相应章节。

本节适用于任何使用 `biliup` 投稿的成片，且必须在执行真实投稿命令前完成。投稿不是“先发出去再抽查”的流程，而是一次性动作：

1. 封存本次投稿输入到 `<edit>/submission_preflight.md`：最终 `final.mp4`、标题、简介、标签、分区、`cover.jpg`、`cover-4x3.jpg` 及商品参数（如有），并记录最终视频和封面的 SHA-256。封存后不得替换这些文件或修改这些字段。
2. 在投稿前完成并记录全部检查：`ffprobe` 检查文件可读性、容器、音视频流、编码、时长、分辨率和帧率；抽查成片首段、中段、尾段及所有关键切点；活动另按 [主视觉复用审核](references/convention.md#活动选材与主视觉复用审核) 核对每镜代表帧总览和分镜搭配，遗漏可用内容或无理由复用的画面须先修正；确认字幕、音频峰值、画面与文案、外部素材相关性、对外文本禁词、标题/简介/标签和两张封面均通过。简介的真实换行与链接范围也必须在投稿前确认；投稿后的 `show` 回读只能作为结果核验，不能替代投稿前校验。
3. 只有全部结果为通过，才允许执行一次 `biliup upload ...`。执行后即使发现错误，也不得自动修正并再次投稿；停止并向用户说明问题。
4. 命令超时、断网、进程中断或返回不明确时，禁止重跑上传命令。改用只读查询确认是否已生成 BV/AV；仍无法确认时，按已投稿处理，不能为了“确保成功”再投一次。
5. 投稿成功后可执行 `biliup show <BV/AV>` 和本 skill 允许的商品挂载/评论等后置操作，但这些动作永远不能重新上传视频。任何需要换视频文件的修正版都属于新的投稿任务，当前任务不得执行。

若用户只要求制作视频而没有明确要求投稿，完成自检后交付文件即可，不要擅自投稿；若明确要求投稿，必须先完成本闸门再调用 `biliup upload`。

## Cut craft (techniques)

- **Audio-first.** Candidate cuts from word boundaries and silence gaps.
- **Preserve peaks.** Laughs, punchlines, emphasis beats. Extend past punchlines to include reactions — the laugh IS the beat.
- **Speaker handoffs** benefit from air between utterances. Common values: 400–600ms. Less for fast-paced, more for cinematic. Taste call.
- **Audio events as signals.** `(laughs)`, `(sighs)`, `(applause)` mark beats. Extend past them.
- **Silence gaps are cut candidates.** Silences ≥400ms are usually the cleanest. 150–400ms phrase boundaries are usable with a visual check. <150ms is unsafe (mid-phrase).
- **Example cut padding** (the launch video shipped with this): 50ms before the first kept word, 80ms after the last. Tighter for montage energy, looser for documentary. Stay in the 30–200ms working window (Hard Rule 7).
- **Never reason audio and video independently.** Every cut must work on both tracks.

## The packed transcript (primary reading view)

`pack_transcripts.py` reads all `transcripts/*.json` and produces one markdown file where each take is a list of phrase-level lines, each prefixed with its `[start-end]` time range. Phrases break on any silence ≥ 0.5s OR speaker change. This is the artifact the editor sub-agent reads to pick cuts — it gives word-boundary precision from text alone at 1/10 the tokens of raw JSON.

Example line:
```
## C0103  (duration: 43.0s, 8 phrases)
  [002.52-005.36] S0 Ninety percent of what a web agent does is completely wasted.
  [006.08-006.74] S0 We fixed this.
```

## Editor sub-agent brief (for multi-take selection)

When the task is "pick the best take of each beat across many clips," spawn a dedicated sub-agent with a brief shaped like this. The structure is load-bearing; the pitch-shape example is not.

```
You are editing a <type> video. Pick the best take of each beat and
assemble them chronologically by beat, not by source clip order.

INPUTS:
  - takes_packed.md (time-annotated phrase-level transcripts of all takes)
  - Product/narrative context: <2 sentences from the user>
  - Speaker(s): <name, role, delivery style note>
  - Expected structure: <pick an archetype or invent one>
  - Verbal slips to avoid: <list from the pre-scan pass>
  - Target runtime: <seconds>

Common structural archetypes (pick, adapt, or invent):
  - Tech launch / demo:   HOOK → PROBLEM → SOLUTION → BENEFIT → EXAMPLE → CTA
  - Tutorial:             INTRO → SETUP → STEPS → GOTCHAS → RECAP
  - Interview:            (QUESTION → ANSWER → FOLLOWUP) repeat
  - Travel / event:       ARRIVAL → HIGHLIGHTS → QUIET MOMENTS → DEPARTURE
  - Documentary:          THESIS → EVIDENCE → COUNTERPOINT → CONCLUSION
  - Music / performance:  INTRO → VERSE → CHORUS → BRIDGE → OUTRO
  - Or invent your own.

RULES:
  - Start/end times must fall on word boundaries from the transcript.
  - Pad cut boundaries (working window 30–200ms).
  - Prefer silences ≥ 400ms as cut targets.
  - Unavoidable slips are kept if no better take exists. Note them in "reason".
  - If over budget, revise: drop a beat or trim tails. Report total and self-correct.

OUTPUT (JSON array, no prose):
  [{"source": "C0103", "start": 2.42, "end": 6.85, "beat": "HOOK",
    "quote": "...", "reason": "..."}, ...]

Return the final EDL and a one-line total runtime check.
```

## Color grade (when requested)

Your job is to **reason about the image**, not apply a preset. Look at a frame (via `timeline_view`), decide what's wrong, adjust one thing, look again.

Mental model is ASC CDL. Per channel: `out = (in * slope + offset) ** power`, then global saturation. `slope` → highlights, `offset` → shadows, `power` → midtones.

**Example filter chains** (`grade.py` has `--list-presets`; use them as starting points or mix your own):

- **`warm_cinematic`** — retro/technical, subtle teal/orange split, desaturated. Shipped in a real launch video. Safe for talking heads.
- **`neutral_punch`** — minimal corrective: contrast bump + gentle S-curve. No hue shifts.
- **`none`** — straight copy. Default when the user hasn't asked.

For anything else — portraiture, nature, product, music video, documentary — invent your own chain. `grade.py --filter '<raw ffmpeg>'` accepts any filter string.

Hard rules: apply **per-segment during extraction** (not post-concat, which re-encodes twice). Never go aggressive without testing skin tones.

## Subtitles (when requested)

Subtitles have three dimensions worth reasoning about: **chunking** (1/2/3/sentence per line), **case** (UPPER/Title/Natural), and **placement** (margin from bottom). The right combo depends on content.

**Worked styles** — pick, adapt, or invent:

**`bold-overlay`** — short-form tech launch, fast-paced social. 2-word chunks, UPPERCASE, break on punctuation, Helvetica 18 Bold, white-on-outline, `MarginV=35`. `render.py` ships with this as `SUB_FORCE_STYLE`.

```
FontName=Helvetica,FontSize=18,Bold=1,
PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,
BorderStyle=1,Outline=2,Shadow=0,
Alignment=2,MarginV=35
```

**`natural-sentence`** (if you invent this mode) — narrative, documentary, education. 4–7 word chunks, sentence case, break on natural pauses, `MarginV=60–80`, larger font for readability, slightly wider max-width. No shipped force_style — design one if you need it.

Invent a third style if neither fits. Hard rules: subtitles LAST (Rule 1), output-timeline offsets (Rule 5).

## Voiceover / TTS (when requested)

广告任务继续使用整段 TTS、最终音频对齐及固定混音要求，不使用下文普通剪辑混音示例替代它们。

When the user wants AI narration, dubbing, or a synthetic voice added to the edit, use `<skill_root>/helpers/tts.py`. **Default to Fish Audio** (`--provider fish`). Do not use MiMo unless the user names it.

- **Default / 声音克隆 / 参考音频 / 要复用声线:** **Fish Audio**. Create a private reusable voice from `--reference-audio`, then reuse `--fish-voice-id`. Requires `FISH_API_KEY` and either a reference clip (≥10s recommended) or an existing voice ID.
- **They explicitly ask for MiMo**, a named MiMo preset (`冰糖` etc.), MiMo voice design, or a 3–10s MiMo clone: choose **MiMo**.
- **They explicitly ask for ElevenLabs** or a specific ElevenLabs library voice: choose **ElevenLabs**.
- If the prompt names a provider, follow it. Never fall back to MiMo just because the clip is Chinese or short.

Before creating any clone, confirm the user has the right to use the reference speaker's voice. Never publish a cloned model: this helper always creates Fish Audio clones with `visibility=private`.

It supports three providers behind one CLI:

- **Fish Audio** (`--provider fish`, default) — persistent private voice clone. Requires `FISH_API_KEY`. Supply `--reference-audio "<videos_dir>/sample.wav"` (accepts `.wav`, `.mp3`, `.m4a`, `.opus`; clean single-speaker audio of at least 10 seconds is recommended) to create a reusable voice model, or supply its `--fish-voice-id` to reuse one. Default synthesis model: `s2.1-pro-free` (override with `--fish-model`).
- **ElevenLabs** (`--provider elevenlabs`) — wide voice library via `--voice-id`, multilingual, MP3 output. Requires `ELEVENLABS_API_KEY`.
- **MiMo** (`--provider mimo`) — Xiaomi MiMo-V2.5-TTS, Chinese-first, currently free. Opt-in only. Requires `MIMO_API_KEY`. Three modes:
  - **Preset voice** (`--mimo-model tts`, default): `--voice 冰糖` (Chinese female), `茉莉` (Chinese female), `苏打` (Chinese male), `白桦` (Chinese male), `Mia`/`Chloe` (English female), `Milo`/`Dean` (English male), or `mimo_default`.
  - **Voice design** (`--mimo-model voicedesign`): describe a voice in natural language via `--style`, e.g. `"一位温柔的中年女性，嗓音略带沙哑"`. No sample needed; `--style` is required.
  - **Voice clone** (`--mimo-model voiceclone`): pass a 3–10s `.mp3`/`.wav` sample via `--reference-audio "<videos_dir>/sample.mp3"` (≤10 MB); MiMo clones the timbre.

**Fish Audio advanced controls:** use `--extra_params '<JSON object>'` only when the prompt asks for a deliberate output adjustment. The helper forwards supported TTS fields such as `temperature`, `top_p`, `repetition_penalty`, `max_new_tokens`, `chunk_length`, `latency`, `normalize`, `min_chunk_length`, `condition_on_previous_chunks`, `early_stop_threshold`, and `prosody` (with `speed` / `volume`). Example: `--extra_params '{"temperature":0.5,"top_p":0.7,"prosody":{"speed":1.1}}'`. `top_k` is also passed through for API compatibility, but it is not listed in Fish Audio’s current public TTS field reference. The CLI rejects attempts to override `text`, `reference_id`, `references`, `format`, or `model`.

**Style control (MiMo):** `--style` takes a natural-language direction placed in the API's `user` message — e.g. `"用兴奋上扬的语调，语速稍快"` or the full director-mode format (角色/场景/指导). You can also embed audio tags directly in the synthesis text, e.g. `"(慵懒)再让我睡五分钟……"` or `"(东北话)哎呀妈呀，这天儿忒冷了！"`.

**Typical workflow:**

1. Generate the voiceover file into `<edit>/voiceover/`:
   ```bash
   python "<skill_root>/helpers/tts.py" "欢迎来到本期视频" -o "<edit>/voiceover/narration.mp3" \
     --provider fish --reference-audio "<videos_dir>/speaker.wav" --fish-voice-title "品牌旁白"
   # Save the printed voice ID, then reuse it without uploading the sample again:
   python "<skill_root>/helpers/tts.py" "下一段旁白" -o "<edit>/voiceover/next.mp3" \
     --provider fish --fish-voice-id <voice_id>
   # Reduce variation and slightly speed up delivery.
   python "<skill_root>/helpers/tts.py" "更稳定的旁白" -o "<edit>/voiceover/tuned.mp3" \
     --provider fish --fish-voice-id <voice_id> \
     --extra_params '{"temperature":0.5,"top_p":0.7,"prosody":{"speed":1.1}}'
   ```
2. Measure its duration with `ffprobe` if animations need to sync to it.
3. Mix it into the rendered video with ffmpeg — duck the original audio under the voiceover, or replace it entirely:
   ```bash
   # Mix voiceover over original audio (original ducked to 30%)
   ffmpeg -i "<edit>/final.mp4" -i "<edit>/voiceover/narration.mp3" -filter_complex \
     "[0:a]volume=0.3[bg];[bg][1:a]amix=inputs=2:duration=longest:dropout_transition=2[a]" \
     -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -shortest "<edit>/final_voiced.mp4"
   ```
   If the voiceover should start at a specific offset, use `adelay` on the voiceover track before mixing.
4. If the voiceover drives animation timing, generate it **before** building overlays so you can sync reveals to it (see the animation payoff-timing rule).
5. If subtitles are required, transcribe or force-align the **generated final voiceover file** at word level before creating `master.srt`. For Chinese narration, prefer `--provider paraformer`; use Scribe when diarization or non-Chinese timing is required. Use the narration source text only to verify the alignment; do not write a shortened caption version. Compare the rendered SRT text against the narration text before delivery and treat any missing, reordered, or paraphrased spoken content as a blocking defect.

Hard rules: never commit API keys; write them only to the user-config `.env` (`python "<skill_root>/helpers/env_file.py" --user-path`). Generated voiceover files go under `<edit>/voiceover/`, never inside the skill directory.

## Animations (when requested)

Animations match the content and the brand. **Get the palette, font, and visual language from the conversation** — never assume a default. If the user hasn't told you, propose a palette in the strategy phase and wait for confirmation before building anything.

**Tool options:**

Pick the engine per animation slot. Do not default to Remotion just because the animation is web-adjacent.

- **HyperFrames** — Browser-native HTML/CSS/GSAP video compositions: product UI motion, website-to-video or mockup-to-video captures, kinetic typography, landing-page/storyboard promos, data-driven UI states, transparent WebM overlays, and clips that need deterministic frame capture plus HyperFrames lint/validate/render checks. Best when the animation should be authored and verified like a web composition instead of a React component tree.
- **Remotion** — React/CSS compositions with component state, reusable React primitives, or an existing Remotion brand system. Best when the user specifically asks for React/Remotion or when React composition is the simpler authoring model.
- **Manim** — formal diagrams, state machines, equation derivations, graph morphs. Read [Manim 子 skill](skills/manim-video/SKILL.md) and its references for depth.
- **PIL + PNG sequence + ffmpeg** — simple overlay cards: counters, typewriter text, single bar reveals, progressive draws. Fast to iterate, any aesthetic you want. The launch video used this.

For HyperFrames slots, create and enter the absolute directory `<edit>/animations/slot_<id>/`, then scaffold there with `npx --yes hyperframes init . --example blank --non-interactive --skip-skills`. Build the HTML composition, dependencies, checks, and render outputs in that slot only. Run the HyperFrames checks that fit the slot (`lint`, `validate`, and a draft render when practical), then produce the final overlay video with `npx --yes hyperframes render . -o <edit>/animations/slot_<id>/render.mp4` or `--format webm -o <edit>/animations/slot_<id>/render.webm` when alpha is required. Point the EDL overlay `file` at the actual absolute path under `<edit>`.

For Remotion slots, keep the Remotion project isolated inside the same absolute slot directory, scaffold with `npx create-video@latest` or install Remotion locally there, render to `<edit>/animations/slot_<id>/render.mp4` with the project-local `remotion render` command, and verify duration and dimensions with `ffprobe`.

None is mandatory. Invent hybrids if useful (e.g., PIL background with a HyperFrames or Remotion layer on top).

**Duration rules of thumb, context-dependent:**

- **Sync-to-narration explanations.** A viewer needs to parse the content at 1×. Rough floor 3s, typical 5–7s for simple cards, 8–14s for complex diagrams. The launch video shipped at 5–7s per simple card.
- **Beat-synced accents** (music video, fast montage). 0.5–2s is fine — they're visual accents, not information. The "readable at 1×" rule becomes *"recognizable at 1×"*, not *"fully parseable."*
- **Hold the final frame ≥ 1s** before the cut (universal).
- **Over voiceover:** total duration ≥ `narration_length + 1s` (universal).
- **Never parallel-reveal independent elements** — the eye can't track two new things at once. One thing, pause, next thing.

**Animation payoff timing (rule for sync-to-narration):** get the payoff word's timestamp. Start the overlay `reveal_duration` seconds earlier so the landing frame coincides with the spoken payoff word. Without this sync the animation feels disconnected.

**Easing** (animation reveals and draws — never `linear`; promo still scrolling and panning retain their fixed-speed rules):

```python
def ease_out_cubic(t):    return 1 - (1 - t) ** 3
def ease_in_out_cubic(t):
    if t < 0.5: return 4 * t ** 3
    return 1 - (-2 * t + 2) ** 3 / 2
```

`ease_out_cubic` for single reveals (slow landing). `ease_in_out_cubic` for continuous draws.

**Typing text anchor trick:** center on the FULL string's width, not the partial-string width — otherwise text slides left during reveal.

**Example palette** (the launch video — one aesthetic among infinite):
- Background `(10, 10, 10)` near-black
- Accent `#FF5A00` / `(255, 90, 0)` orange
- Labels `(110, 110, 110)` dim gray
- Font: Menlo Bold at `/System/Library/Fonts/Menlo.ttc` (index 1)
- ≤ 2 accent colors, ~40% empty space, minimal chrome
- Result: terminal / retro tech feel

This is one style. If the brand is warm and serif, use that. If it's colorful and playful, use that. If the user handed you a style guide, follow it. If they didn't, propose one and confirm.

**Parallel sub-agent brief** — each animation is one sub-agent spawned via the `Agent` tool. Each prompt is self-contained (sub-agents have no parent context). Include:

1. One-sentence goal: *"Build ONE animation: [spec]. Nothing else."*
2. Absolute output path (`<edit>/animations/slot_<id>/render.mp4`)
3. Exact technical spec: resolution, fps, codec, pix_fmt, CRF, duration
4. Style palette as concrete values (RGB tuples, hex, or reference to a design system)
5. Font path with index
6. Frame-by-frame timeline (what happens when, with easing)
7. Anti-list ("no chrome, no extras, no titles unless specified")
8. Code pattern reference (copy helpers inline, don't import across slots)
9. Deliverable checklist (script, render, verify duration via ffprobe, report)
10. **"Do not ask questions. If anything is ambiguous, pick the most obvious interpretation and proceed."**

同时在代理任务中传递主入口已解析的 `<skill_root>`、`<edit>` 及指向 `<edit>/tmp` 的 `TMPDIR`、`TMP`、`TEMP`，在代理的渲染进程启动前设置，避免自包含任务丢失临时目录约定。

One sub-agent = one file (unique filenames, parallel agents don't overwrite each other).

## Output spec

Match the source unless the user asked for something specific. Common targets: `1920×1080@24` cinematic, `1920×1080@30` screen content, `1080×1920@30` vertical social, `3840×2160@24` 4K cinema, `1080×1080@30` square. `render.py` defaults the scale to 1080p from any source and preserves the first source's frame rate (falls back to 24 only if the rate can't be probed); pass `--fps` to force, or `--filter` / edit the extract command for other targets. Worth asking the user which delivery format matters.

## EDL format

```json
{
  "version": 1,
  "sources": {"C0103": "/abs/path/C0103.MP4", "C0108": "/abs/path/C0108.MP4"},
  "ranges": [
    {"source": "C0103", "start": 2.42, "end": 6.85,
     "beat": "HOOK", "quote": "...", "reason": "Cleanest delivery, stops before slip at 38.46."},
    {"source": "C0108", "start": 14.30, "end": 28.90,
     "beat": "SOLUTION", "quote": "...", "reason": "Only take without the false start."},
    {"source": "BROLL", "start": 3.00, "end": 7.00,
     "beat": "EXAMPLE", "reason": "Inserted footage — dissolve in.",
     "transition": {"type": "fade", "duration": 0.4}}
  ],
  "grade": "warm_cinematic",
  "overlays": [
    {"file": "<edit>/animations/slot_1/render.mp4", "start_in_output": 0.0, "duration": 5.0}
  ],
  "subtitles": "<edit>/master.srt",
  "subtitle_style": "PlayResX=1920,PlayResY=1080,FontName=Hiragino Sans GB,FontSize=72,Bold=1,Spacing=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00201828,BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginL=64,MarginR=64,MarginV=8,WrapStyle=2",
  "total_duration_s": 87.4
}
```

`grade` is a preset name or raw ffmpeg filter. `overlays` are rendered animation clips. `subtitles` is optional and applied LAST. `subtitle_style` is an optional libass `force_style` string; use it when a specialized workflow requires a fixed caption treatment.

**Transitions.** Omitted `transition` on a range is a hard cut, unless `default_transition` (or top-level `transition`) is set. The first range never has an inbound join. `"transition": "cut"` opts one join out of a default dissolve. Types are ffmpeg `xfade` names, including `fade` (cross-dissolve, default), `dissolve`, `fadeblack`, `fadewhite`, `wipeleft` / `wiperight`, `slideleft` / `slideright`, `smoothleft` / `smoothright`, `circleopen`, and `zoomin`. Duration is seconds; keep it under half of either adjacent clip. For product videos, use `smoothleft` / `smoothright` for a restrained move from a full view into detail (0.3–0.4s), a short `fade` cross-dissolve between different source classes (0.2–0.3s), and a hard cut for consecutive angles of the same shot. Use bold effects sparingly. Talking-head / same-camera cuts stay hard-cut. Inserted B-roll, product stills vs OP/ED, or any source-class change should dissolve unless the user asked for jump cuts.

**Per-source dialogue captions.** For general edits whose audio moves with the clips, `build_master_srt` must use the same transition policy as the picture/audio joiner: default `--keep-duration` / `"transition_handles": true` preserves authored segment offsets; `--no-keep-duration` / `"transition_handles": false` subtracts the actual (clamped) overlap. Both modes can keep dialogue captions synchronized when these settings agree.

**Do not shift fixed TTS captions to chase the dissolve.** Promo/TTS subtitles are locked to the final narration audio (Hard Rule 13). Default `--keep-duration` adds the overlap as a freeze/tail on the outgoing clip so each transition starts at the original cut point and the programme retains its authored length. The promo joiner uses `--an`; the separate narration does not move with the visual clips. Shortening the picture does not justify subtracting overlaps from these captions. Only disable handles when you intend to shorten the picture and re-time or regenerate the voiceover and subtitles together.

广告混音前，`mix_ad_audio.py` 检查视频流时长是否覆盖完整口播音轨；画面过短时直接失败，禁止静默裁掉末句。正常情况下继续使用默认保留时长；检查失败时修正画面时间窗，或按已确定的目标时长重做完整口播及其词级对齐字幕。不要只提前字幕；检查本身不自动裁切或改变口播速度。混音限幅器启用延迟补偿，字幕仍沿用最终口播音频的时间戳。

## Memory — `project.md`

Append one section per session at `<edit>/project.md`:

```markdown
## Session N — YYYY-MM-DD

**Strategy:** one paragraph describing the approach
**Decisions:** take choices, cuts, grades, animations + why
**Reasoning log:** one-line rationale for non-obvious decisions
**Outstanding:** deferred items
```

On startup, read `<edit>/project.md` if it exists and summarize the last session in one sentence before asking whether to continue.

## Anti-patterns

Things that consistently fail regardless of style:

- **Hierarchical pre-computed codec formats** with USABILITY / tone tags / shot layers. Over-engineering. Derive from the transcript at decision time.
- **Hand-tuned moment-scoring functions.** The LLM picks better than any heuristic you'll write.
- **Whisper SRT / phrase-level output.** Loses sub-second gap data. Always word-level verbatim JSON (`words` with start/end), whether from Scribe or Paraformer.
- **Running Whisper locally on CPU.** Slow and it normalizes fillers. Use Scribe or Paraformer.
- **Burning subtitles into base before compositing overlays.** Overlays hide them. (Hard Rule 1.)
- **Single-pass filtergraph when you have overlays.** Double re-encodes. Use per-segment extract → concat or xfade-join of extracted clips.
- **Linear animation easing.** Looks robotic. Use cubic easing for authored animation reveals; this does not govern the fixed-speed motion of promo stills.
- **Hard audio cuts at segment boundaries.** Audible pops. (Hard Rule 3.)
- **Hard-cutting between different source classes.** Product stills vs OP/ED/Trailer, or any inserted B-roll against the A-roll, need a dissolve (`fade` 0.3–0.5s) unless the user asked for jump cuts. Same-camera talking-head cuts stay hard-cut.
- **Typing text centered on the partial string.** Text slides left as it grows.
- **Sequential sub-agents for multiple animations.** Always parallel.
- **Editing before confirming the strategy.** Never.
- **Re-transcribing cached sources.** Immutable outputs of immutable inputs.
- **Assuming what kind of video it is.** Look first, ask second, edit last.
- **Dropping the facts with the graphic.** A text-heavy still can stay off-screen. If it holds useful facts, say them in the voiceover (captions follow the voice). Do not show a wall of unreadably small type just because the facts are on it.
- **Racing a whole tall infographic in one short shot.** If it is going on screen, slice by section and pair each window with one spoken beat.

## Bilibili product promo (hard recipe)

The rules here are production standards, not taste. For ordinary goods, product/character setting and visible appeal take priority over product attributes. For ordinary goods, do not mention material, size, specifications, ingredients, or manufacturing details in outward copy unless the user explicitly asks. Digital/electronic and other function-led products may center the narrative on verified technical parameters; see [数码及功能型商品](references/product.md#数码及功能型商品). Include verified promotions applicable to the target SKU from `product_info.json` by default; distinguish active offers from upcoming offers and follow the promotion timing rule below; distinguish coupon thresholds and random rewards from guaranteed direct discounts. The regular shelf price stays out of outward copy unless the user asks. Hard Rules still apply. Credential lookup is [环境检查](#setup). TTS CLI is [Voiceover / TTS](#voiceover--tts-when-requested) (default Fish Audio; strip [对外文本禁词](#对外文本禁词硬性) from `--extra_params`; write files to `<edit>/voiceover/`).

### 对外文本禁词（硬性）

面向观众或平台发布的文本，禁止出现制作配方用语和提示词。适用范围：口播文案、烧录字幕、B站标题、投稿简介、封面画面文字、标签。

禁止出现：云逛、口播、混剪、资讯、宣传片、广告、配方、提示词、BGM、字幕、封面。

官方漫展海报封面保留原有文字，原图中的禁词、票价、Logo 和英文不按商品生图规则清除；新写文本仍遵守本节。

这些词只留在本技能的内部说明里，不得写进任何将要发布或给观众看的句子（含商品封面画面上要画出来的文案；官方海报原有文字按上述例外处理）。送入 TTS 的口播文案同样不得使用上述禁词。发给图像模型的**生成提示词可以用「封面」**等内部用语；禁词约束的是画面文字，不是生图 prompt。

### 内容重心（用户偏好硬规则）

- **普通商品先讲商品/人物，再讲字段**：主叙事必须围绕商品本身或其中的角色展开，优先写外观、姿态、表情、服装、气质、世界观关系和能被画面证明的设定。不要讲材质、尺寸、规格、配料、工艺等商品属性。`product_info.json` 是事实来源，但不是逐项播报清单；事实清单中的字段不必全部进入口播。
- **商品属性与技术参数**：普通商品的口播、烧录字幕、标题、投稿简介和挂载评论默认不写材质、尺寸、规格、配料、工艺及参数清单；用户明确要求时按其要求处理。数码电子等功能型商品允许技术参数成为叙事中心，文案和标题可使用经商品事实核实的功能与参数，具体见 [数码及功能型商品](references/product.md#数码及功能型商品)。
- **促销信息来自实时商品数据**：默认从 `product_info.json` 的 `detail.promotions` 选取已核实、且适用于目标 SKU 的优惠。对外文案不主动写活动开始日期或时间；若活动未开始，不得说成优惠已经生效，可讲已核实的活动亮点，提醒观众先加入购物车、届时符合活动条件再享受优惠，并引导查看链接。优惠券不等同于直接降价或保证到手价，不把资格不明的优惠说成人人可享。
- **文案面向观众**：口播、简介和挂载文案用自然、顺口的表达，避免说明书式罗列、字段堆叠和客服腔。介绍商品或角色，再挑一个已核实的优惠重点，引导观众点击链接；不写“商品页标注”“具体规则以商品页为准”等生硬转述。
- **普通售价默认不出现在对外文本**：除非用户明确要求，商品标价不得写入口播、烧录字幕、标题、投稿简介、商品封面新增文字或标签；官方漫展海报封面允许保留原有票价。用户要求纳入促销时，可写促销券面金额与门槛，但不可据此计算或承诺最终到手价。不要用“低价”“划算”等话术制造购买承诺。
- **结尾引导了解详情**：视频文案或商品简介可自然引导观众点击评论区链接；商品挂载卡片的链接前文案应称“商品链接”或直接说“点链接”，不要说“评论区”。不要在视频里替观众把所有优惠规则讲完。
- **写作自测**：若删掉数字和商品属性后，普通商品的文案反而更像角色/商品介绍，就删掉这些数字和属性；文案应围绕角色/商品与已核实活动展开。

未开始活动的购物车提醒只用于观众文案，不增加自动加车操作；仅在目标商品支持加入购物车时使用该引导。券门槛、资格和目标 SKU 仍须核实，不承诺人人优惠或到手价。

### 输入参数

每次任务开始先收集以下参数，缺失时追问，不猜测：

| 参数 | 占位 | 说明 |
|------|------|------|
| 商品 ID/链接 | `<商品 ID 或 URL>` | 先交给 `biliup goods search`，不凭商品名猜测商品 |
| 成片时长 | `<时长>` | 只从用户提示词读取；缺失时追问，不默认任何时长 |
| 素材文件夹 | `<文件夹路径>` | 商品图片、效果图所在目录 |
| 参考声音 | `<.mp3>` | Fish Audio 声音克隆参考音频（建议 ≥10 秒、干净单人声） |
| BGM 风格 | `<风格>` | 检索关键词（作品名、OST、曲风）；只用于在 YouTube / Bilibili 找现成 BGM，禁止据此生成音乐 |
| TTS 风格提示词 | `<用户提示词>` | 可选；Fish Audio 默认不使用。仅当用户明确要求语速/音量等，才写入 `--extra_params` |

### 执行流程

1. **先采集商品事实和促销**：必须使用 `biliup goods search`，不要先凭商品名或图片文件名写文案。推荐运行：`python "<skill_root>/helpers/biliup_goods.py" <商品 ID 或 URL> --cookie <cookies.json> --output <edit>/product_info.json`。该 helper 只负责调用 biliup 并保存 JSON，不复制商品接口逻辑；需要指定 Release 二进制时加 `--biliup-bin <绝对路径>`。核对返回的 `itemId`、`goodsName`、`detail.kind`、`detail` 和 `detail.promotions`。会员购逐项查看活动有效期、券门槛/资格、活动说明、赠品和 SKU 对应的价格/库存/活动标签；票务按接口实际返回字段处理。只写已核实且适用于目标 SKU 的优惠；区分已生效与未开始的活动，未开始时按下文促销状态规则处理，标价/票价默认仅作后台核验。普通商品的材质等属性不得作为文案卖点；数码及功能型商品按对应类型规则使用经核实的技术参数。商品事实以 JSON 为准，无法从中得到的卖点不得写入文案；事实字段不是必须逐项播报的清单。
2. **清点素材（静图分拣在文案之前）**：`ffprobe` 检查视频素材。静图必须按 [静图分拣](#静图分拣硬性) 跑 `inventory_stills.py`、看每张原图和长图 y 刻度总览，先识别实际栏目与主体，再判断可上镜的局部并裁窗复核，写入 `<edit>/stills_inventory.md`。将 `product_info.json` 的图片/属性与本地素材逐项对照；按栏目记录上镜 / 只取信息 / 弃用，再写口播。同一张图允许不同栏目有不同判定，不能只因整图字多就排除其中的实物、人物或活动画面。活动另做 [素材与主视觉复用审核](references/convention.md#活动选材与主视觉复用审核)。
3. **评估并按相关性分层收集视频素材**：先依据静图分拣结果判断是否需要外部动态画面。检索必须按“**商品本体/具体人物 → 具体作品设定 → 其他相关动漫或游戏**”逐层降级，不得为了方便直接使用泛相关片段：A 先找该商品、该 SKU、该手办或商品官方展示视频；B 找不到合适商品视频，再找商品对应的具体角色官方片段；C 仍不足，再找该角色所属作品的官方 OP / ED / Trailer；D 以上都找不到能服务叙事的镜头，才允许使用其他相关动漫或游戏片段，且必须能解释其与商品氛围的关系。每层内 YouTube 与 Bilibili 平级，相关性高于平台便利。外部动态画面只能承担一个明确任务：建立作品世界观、在角色/设定转换时提供承接，或在连续静态画面后重置节奏；若没有能完成该任务的官方镜头，或它会遮蔽商品细节，就不使用。YouTube 用 `yt-dlp` 检索并下载视频；Bilibili 先用 `python "<skill_root>/helpers/bilibili_src.py" search "<关键词>" --n 5` 找到 BV 号，再运行 `python "<skill_root>/helpers/bilibili_src.py" check-watermark <BVid>`，未命中水印后必须用 `python "<skill_root>/helpers/bilibili_src.py" download <BVid> --video-out <输出路径>` 下载**视频画面**（需要时加 `--cookies-from-browser <browser>`），而非只下载音频。仅当素材来自 Bilibili 时需要该水印检查；YouTube/其他平台来源的视频无需水印检测。若选择视频，记录检索层级、关键词、来源、源时间码、计划插入的口播语义点；成片输出时间窗等「TTS 配音与词级转写」完成后再填，不为凑数量下载或插入。
4. **检索设定**：在 <https://zh.moegirl.org.cn/> 查找产品相关动漫设定与梗，供文案使用；设定只能补充世界观，不能替代 `product_info.json` 的商品事实。
5. **撰写文案**：按 [文案规范](#文案规范口播脚本)起草口播文案。先用 `product_info.json` 的 `detail.summary` 建立角色/商品事实清单，再把 `detail.promotions` 中已核实且适用于目标 SKU 的优惠按实际生效状态自然写进口播；普通商品不写材质、尺寸、规格、配料、工艺等属性，数码及功能型商品可围绕已核实的技术参数组织叙事。漫展依据票务实际字段，按 [漫展视频构成](references/convention.md#漫展视频构成) 安排段落与对应画面，按时长取舍。再将上镜镜头对应保留窗口；密字图里若有相关活动规则，只提炼准确门槛和期限写进口播（字幕随口播），画面改用其他上镜素材。判定为弃用的条目两端都不进。
6. **确认方案**：把文案 + 素材搭配展示给用户，确认后再制作（文案是创作性产物，先确认避免返工）。必须附上静图分拣表（上镜 / 只取信息 / 弃用，含理由）；上镜的长图写出 `--region`。搭配只钉「哪句对哪张图 / 哪一窗」，不要把估出来的秒数当成最终镜头时长。活动必须在 `<edit>/stills_inventory.md` 附分镜搭配及复用审核：每段写实际画面主体、原图／栏目、主视觉组和选择理由，检查可用非主视觉栏目为何没有进入分镜。不同文件的横竖版主视觉不能算作不同内容。若选择了动态视频，标明它服务的口播语义点；输出时间窗等「TTS 配音与词级转写」完成后再填。若未选择，说明商品图如何独立完成节奏。不能只列 BGM 或下载链接。
7. **TTS 配音（画面之前）**：按 [Voiceover / TTS](#voiceover--tts-when-requested) 生成**整段**口播，不要按句多次合成。立刻 `python "<skill_root>/helpers/transcribe.py" <口播音频> --edit-dir <edit> --provider paraformer`。用这份词级转写，把确认方案里的每一句口播映射到时间窗：镜头 `i` 从该句第一个字的 `start` 起，到下一句第一个字的 `start` 止（最后一句到音频结尾）。句间停顿并入当前镜头，使各镜 `--duration` 之和等于口播 `ffprobe` 时长。禁止用手估秒数渲画面。后续字幕复用这份转写缓存，音频未改不得重跑。
8. **合成视频**：按上一步的时间窗渲染画面（`stable_motion.py --duration`、OP/ED 裁切都用该窗）。活动先用真实时间窗更新分镜搭配，汇总同组主视觉的出现次数和累计时长，完成复用审核后再渲染。动态视频仅在其计划的语义点实际进入时间轴，不得作为与口播无关的固定装饰。商品静图与穿插视频之间必须用 `<skill_root>/helpers/transitions.py` 做画面转场，禁止 `-c copy` 硬切拼接。转场默认 `--keep-duration`，画面总长必须仍等于口播时长。
9. **检索并下载 BGM**：按 [混音规范](#混音规范人声为主数值硬性)从 **YouTube 或 Bilibili** 找到与产品/作品相关的现成 OST 或 BGM 并下载音频。禁止用 AI 或本地合成生成 BGM。
10. **混音**：对无字幕的视觉成片运行 `python "<skill_root>/helpers/mix_ad_audio.py" <visual.mp4> <narration.mp3> <bgm.mp3> -o <mixed.mp4>`。该 helper 固定执行人声 -13 LUFS、BGM -27 LUFS、BGM 首尾淡化、无自动闪避与防削波；不得再对 `mixed.mp4` 做整轨 loudnorm。混音前会检查实际视频流时长是否覆盖完整口播，过短时失败，不生成或覆盖混音成片。修正画面时间窗，或按确定的目标时长同步重做口播与字幕，禁止截掉末句。限幅器启用延迟补偿，口播和字幕不按画面转场重叠提前。
11. **烧录字幕**：最后执行，按 [字幕规范](#字幕规范中文单行字幕)。字幕必须烧录到 `mixed.mp4` 上；不得先烧字幕再混音，也不得在烧录后用 `render.py` 的默认整轨 loudnorm 覆盖分轨响度。
12. **自检交付**：检查字幕在最上层、无削波、无爆音、图片与文案匹配；`ffprobe` 对照画面与口播时长（允许转场取整误差，不得差出一整句）。若使用了动态视频，确认每个计划的语义点确实出现对应画面，而不是 BGM 音频或静态封面替代，并抽查首帧、中帧与尾帧。按 [对外文本禁词](#对外文本禁词硬性)检查口播、字幕、标题、简介、封面文字和标签。最终交付是一个不可拆分的套件：`final.mp4`、按 [B站标题交付规范](#b站标题交付规范)生成的 **1 个**标题、以及按 [封面子 skill](skills/bili-cover/SKILL.md) 交付的 **16:9 + 4:3 两张封面**（4:3 从 16:9 以看图后选择的连续 `crop_center_x` 裁出）。商品封面同时交付实际使用的完整提示词；官方漫展海报注明“使用官方宣传图，未调用生图”；任何一项缺失均不得宣告任务完成。

### B站商品挂载文案

- `biliup goods search` 返回的 `detail.promotions` 中有目标 SKU 适用的优惠时，在挂载文案里挑最有吸引力的一点，接一个清楚的点击引导。`--prefix-text` / `--postfix-text` 面向观众，默认短、口语、轻松，不写成规则摘要或客服公告；尽量一条优惠信息加一句点击引导，不粘贴接口 JSON 或券清单。
- `--prefix-text` 默认控制在 **15 字左右**，并且必须包含一个已核实的促销亮点或点击引导；能同时写两者时优先两者。字数是方向，不是硬上限；自然、轻松、直接优先，不要为了卡字数写得生硬。按商品和活动语境灵活写 CTA，避免每条都复用同一句模板。由于文案紧贴商品链接，CTA 称“商品链接”或直接说“点链接”，不要说“评论区”；“评论区”用于视频文案或商品简介。只有用户明确给出硬性字数上限时才严格计数。
- 有优惠券时可突出“还有优惠券”；确有大额优惠时可说“前XX名有大额优惠哦”；确有欧气宝箱活动时可用“欧气宝箱出没中”“去商品链接碰碰运气”等积极表达，不得写成人人必得。优惠券不必主动列使用日期或所有门槛。对外文案不主动写活动开始日期或时间；活动未开始时不说优惠已生效，可提醒观众先加入购物车、届时符合活动条件再享受优惠。CTA 要短、自然、紧扣福利亮点，并灵活变化。
- 不得把优惠券说成人人可领、无门槛直降或保证到手价，也不得保证中奖、编造优惠或使用虚假稀缺。若资格或库存不确定，保持邀请式表达；“大额”等强度词必须有优惠金额等信息支撑。
- 示例（约15字，按实际活动挑选并改写，避免机械复用同一 CTA）：`前80名尾款有优惠哦，点商品链接看看～`；`优惠券也有，商品链接里瞧瞧～`；若确有宝箱活动：`欧气宝箱出没中，去商品链接碰碰运气～`。根据实际 `detail.promotions` 删除没有的优惠项，不照抄示例里的活动类型。
- 多商品挂载时，只把属于所挂商品且已核实的优惠合并成一段易懂文案。

### 静图分拣（硬性）

长图会出现在很多素材里（商品详情、规格分栏、活动海报、KV 等）。先看画面适不适合上镜，再看文字里有没有口播需要的重点。下面的切窗流程对所有长图通用；**哪一类算镜头、哪一类只进口播**，按素材类型用后面的题材约束，不要拿某一次任务的栏目名去套所有图。

#### 长图提取关键信息

目标是找出**能当镜头的栏目**：一段栏目标题，加上它解释的那块画面（产品图、参数卡、卖点图等）。不是把长图切成等高条。禁止用 16:9 视窗等分、颜色空隙、OCR 禁切线自动切片——那些会切断标题与画面，或把密字表切成假镜头。

1. **出总览**：`python "<skill_root>/helpers/inventory_stills.py" "<素材文件夹>" --overview-dir "<edit>/verify/overview"`。`tall: true` 的图写出 `{stem}_overview.jpg`（瘦长缩略，每 200px 标原图 y）。3:4 KV、方图、横图不画总览，直接看原图。
2. **先识别栏目再分拣**：打开每张原图，记录图上可见标题与实际主体；长图对照总览逐栏查看。禁止只凭文件名、缩略图字密程度或图的尺寸决定去留。含多种内容的图分别判定各栏，例如规则文字只取信息，但同图清楚的奖品／周边图片可以评估上镜；人物头像与姓名卡不能误记为纯文字名录。整图不适合直接展示，不等于没有可用局部。
3. **对候选上镜栏目定窗**：在总览上按栏目估 `y0–y1`，裁图复核后才最终判定。一个窗口承接一个完整信息单元（可见标题／名称 + 对应画面）；长栏可选完整一组人物或作品卡片，保留各自名称和主体，不必滚完整页。仍然整宽只裁上下，不自动等分或按 OCR 切片。不要为了凑 16:9 去切。总览估 y 会有误差，**宁可多带一点相邻栏目，也不要把本栏切残**。套装、对比、多件展示要把这一栏里的主体都框进去，不要为了画面干净而裁短。
4. **裁窗并看图补全**：`python "<skill_root>/helpers/inventory_stills.py" --crop --folder "<素材文件夹>" --out-dir "<edit>/verify/stills" --window <name>,<source>,<y0>,<y1>`（可重复 `--window`；默认上下各扩 80px）。必须打开每张裁图：本栏主体（图、关键数字、名称）被切掉就**加大窗口再裁**。边上带进下一栏可以留着，禁止为了「收干净」往里收。JSON 里的 `region` 给 `stable_motion.py --region`。
5. 读到的标题可用 `python "<skill_root>/helpers/inventory_stills.py" --suggest-role "<可见标题>"` 做核对。这是标题用词提示，不是终裁；商品详情以看图为准。
6. 写入 `<edit>/stills_inventory.md` 后再写文案。表格至少包含：文件与栏目、判定、可见标题与主体、用法（上镜写裁图路径和 `--region`，或「不进画面 + 口播要点」，或「两端都不用」）、理由。同图多栏可写多行；不确定内容先回看原图，不能用模糊的“密集说明”代替识别。

| 判定 | 何时 | 处理 |
|------|------|------|
| 上镜 | 画面清楚、好看，观众看得清 | 主视觉用 `--mode push`。长图按栏/标题语义切窗，一句口播对一窗 |
| 只取信息 | 该栏目文字过密、不适合当镜头，但里面有口播需要的重点 | **该栏目不上镜**。把重点写进口播，字幕跟口播走；同图其他栏目仍单独评估 |
| 弃用 | 没有可讲重点，或与主题无关 | 不进画面、不入口播、不进封面 |

纯密字栏目默认按「只取信息」或「弃用」处理，不要为了保留字而把整张密字图滚进成片。混合长图必须先评估其中有可讲画面的栏目；裁窗后仍不可读、不完整或不相关，才排除该栏目。口播时长由用户提示词决定，**不要为了滚完整张长图而拉长 TTS**。先 `--probe` 再渲染。

**题材约束（在通用流程上收紧，不另走一套切法）**

题材约束使用开始时已选的 [普通商品素材](references/product.md#普通商品详情)、[漫展素材](references/convention.md#漫展展览活动长图) 或 [一番赏／魔力赏素材](references/lottery.md#叙事与素材)。通用切窗方法不变，不重复读取其它题材。

### 图片素材规范

- **选图优先级**：商品以本体图为主，尽量多使用主图，少量使用仍清楚可读的详情图。活动以各段内容匹配的主视觉、人物／节目、作品、玩法或实物栏目组织分镜，详见 [活动选材](references/convention.md#活动选材与主视觉复用审核)，不把商品“多使用主图”的偏好套成活动主视觉循环。
- **文字过密**：纯密字栏目默认不上镜；混合图先评估可用的视觉栏目。局部仍无法上镜时，相关重点可以写进口播和字幕，画面换别的合适素材；没有可讲重点或可用画面才整张丢掉。不要把密字图滚进成片充数。
- **画面适配**（每张图进入 1920×1080 画布时）：
  - **带透明通道的抠像图（PNG）必须先铺底**：透明区会被渲染成黑底，`stable_motion.py` 的模糊填充也取不到有效背景，成片会出现大面积黑场。先用 PIL 把图 `alpha_composite` 到一个浅色渐变底（与商品 KV 同色系）并存成不透明 JPG，再送 `--mode push`。
  - 图片高度不足画布高度 → **等比例放大**，占满画面高度（允许裁切左右）。
  - 图片比 16:9 更高：3:4 / 方图主视觉用 `--mode push`；详情/信息长图用 `--mode scroll`。滚动是 **固定 0.18 屏/秒**（约 5.5 秒一屏），与图有多长、镜头有几秒无关：只改变滚多久或裁多长，禁止为某张图改 `--max-viewports-per-sec`。不要用 duration 去「拉满」或「刷完整张」。镜头比内容长就停在末帧；镜头比内容短就从 `--anchor`（默认顶）裁一段可读窗口。口播对中段/底部时用 `--region 0.35,0.7` 或 `--anchor center|bottom`。先 `--probe` 看 JSON 再渲染。
- 文案与上镜画面尽量匹配：讲到哪张上镜的图、哪一段长图，就展示哪一段。只取信息、不上镜的句子，用其他上镜素材垫画面。
- **镜头时长**：`--duration` 必须用 执行流程的「TTS 配音与词级转写」阶段从口播转写算出的时间窗，禁止手估或按图有多长反推。滚动速度仍固定 0.18 屏/秒，不因某句变长而加速刷完整张。

#### 动态图片分镜稳定性

- 商品主图可采用缓慢中心推镜，横向宽图可采用向右扫镜，详情长图可采用缓慢纵向滚动；背景、清晰前景和暗角先各生成一次静态资产，再由同一条视频滤镜链驱动运动。不得为每一帧重新生成背景或前景位图。
- **运动参数必须连续**：推镜缩放以输出帧编号计算同一条连续曲线，并在滤镜中以浮点表达式执行。推镜清晰前景在结束帧应约占满画面高度，不要以明显留白的小图结束。长图只有在等比例缩放后超出一屏高度至少 **15%** 时才滚动；未达到阈值的短长图保持整图、等比例放大到接近满高并走推镜。需要滚动时，滚动必须对时间 `t` **匀速**（固定像素/秒），滚完用 `min()` 停在末帧；禁止用 `n/(frames-1)` 把整段行程摊满镜头时长，那会让短窗口几乎不动、长窗口被拉成不同速度。禁止在逐帧循环中对缩放后的宽高、居中坐标或裁切坐标使用 `int()` / `//` 后再渲染；这会产生“停一帧、跳一像素”的抖动。
- 缩放与滚动不能分别用不同的取整坐标系计算。长图滚动的可用纵向范围必须基于**当前帧**缩放后的图像高度计算；否则缩放变化会使裁切位置不连续。
- 中心推镜推荐用 FFmpeg `zoompan` 的 `on`（输出帧编号）驱动；纵向滚动用 `overlay` 的连续时间表达式，横向扫镜用 `crop` 的连续 x 表达式。模糊背景只用于填补画布边缘，不能替代清晰前景的轻放大来展示细节。该方案避免 Python/PIL 按帧缩放带来的整数舍入抖动，也避免大量 PNG 序列写入造成的性能问题。
- **统一实现**：商品静态图默认使用 `python "<skill_root>/helpers/stable_motion.py" <图片> -o <片段.mp4> --mode push --duration <秒>`。超宽图用 `--mode pan-right` 按自然余量从左扫到右，固定 0.12 屏宽/秒；成片 16:9 时，源图宽高比约 2.05:1 或更宽（例如 3000×1080）即可不裁切扫镜。若素材约为 16:9 且确实是细节图，同一模式会以中心放大约 1.18× 后慢扫（固定 0.04 屏宽/秒）；裁掉的上下边缘各约占原图 7.6%，完整商品主图不要用此策略。更窄图像回退到 `push`。详情/信息长图使用 `--mode scroll`（固定 0.18 屏/秒；过长则裁窗，滚完停住，不要手写更快的 duration 去追完整张）。滚动模式只在开始时缩放前景，再用 `t` 的匀速表达式移动它。它会检测操作系统：**macOS 使用 1.5× 输出画布、Lanczos 下采样和 `h264_videotoolbox` 硬编码**，平衡慢运动稳定性与 M 系列芯片上的渲染时间；其他系统保留 **2× 输出画布和 `libx264` CRF 编码**。禁止退回到逐帧 `scale` 加 `overlay` 的组合。
- **调用示例**：`python "<skill_root>/helpers/stable_motion.py" "<videos_dir>/主图.jpg" -o "<edit>/clips_visual/main.mp4" --mode push --duration 6`；横向赏析：`python "<skill_root>/helpers/stable_motion.py" "<videos_dir>/横图.jpg" -o "<edit>/clips_visual/pan.mp4" --mode pan-right --duration 6`；商详长图：`python "<skill_root>/helpers/stable_motion.py" "<videos_dir>/商详.jpg" -o "<edit>/clips_visual/detail.mp4" --mode scroll --duration 7`；长图对顶部：`... --mode scroll --duration 7 --anchor top`；对中段：`--region 0.28,0.62`。`--probe` 可检查对应模式的移动空间/裁窗计划。
- **自检**：动态图片分镜生成后，逐段以 1× 速度查看首段、中段、末段，并抽取连续 10 帧检查运动方向只前进、不回跳；发现抖动时必须修正运动表达式后重渲染，不得改用静态图规避问题。

### 视频素材规范

- **来源优先级**：先按相关性分层，再在同一层级内选择平台。严格顺序是：**Exact product/SKU 商品视频 → Exact character 具体人物官方视频 → Exact work 具体作品官方 OP / ED / Trailer → Broader related 其他相关动漫/游戏官方片段**。只有前一层找不到合适、能服务口播的镜头时，才能进入下一层；不能因为 YouTube 或 Bilibili 更容易下载，就跳过商品/人物相关检索。所有层级均仅限官方 OP / ED / Trailer 或官方商品/角色展示视频；明确排除玩家二创、同人剪辑、游戏实况、reaction 等任何其他来源类型。YouTube 与 Bilibili 在同一层级内平级。
  - **Bilibili 素材获取**（`<skill_root>/helpers/bilibili_src.py`）：
    - 检索：`python "<skill_root>/helpers/bilibili_src.py" search "<关键词>" --n 5`（返回 bvid / 标题 / UP主 / 时长）。
    - 下载前必先做水印检测（仅 B 站视频）：`python "<skill_root>/helpers/bilibili_src.py" check-watermark <BVid>`，命中即弃用该视频；检测查四角边缘细节（B 站水印常见于右上角），属启发式，重要片段建议肉眼抽检。YouTube/其他平台视频免检。
    - 取素材：`python "<skill_root>/helpers/bilibili_src.py" download <BVid> --video-out ...` 取片段、`--audio-out` 取 BGM（音频无视觉水印，不受水印检测限制）。
    - 视频流 Cookie：命令加 `--cookies-from-browser <chrome|firefox|edge|safari|brave>`，yt-dlp 直接读本机已登录 B 站的浏览器 cookie（无需手动导出）；匿名则仅音频可用。
- **叙事优先**：外部动态画面是可选素材，不是配方要求。优先让商品主图、效果图和详情图承担展示；仅在它能为“世界观建立、角色/设定承接、节奏重置”中的至少一项提供商品图做不到的价值时采用。选择镜头时，以自然口播停顿、角色名/设定词落点、或静态图信息展示结束后的呼吸点作为进入和离开位置；镜头停留以观众看清其功能为准，不设固定数量、时长或总占比。若没有自然落点，宁可不插入。
- **定窗时必须扫完整段，不能只看首末帧**：宣传 PV 常在角色段落之后紧跟一串纯字卡／无人的场景／界面转场。先按 0.5 秒粒度对候选区间抽帧铺成网格，确认区间内**每一帧**都有目标角色，再定入点与出点；首末帧合格不代表中段合格。
- 若使用片段，它必须是真实编码进成片的动态画面，且与相邻商品图在色彩、方向与情绪上连贯；不得以“已下载”“仅作 BGM”或静态首帧替代，也不得为了满足镜头数量而重复同类画面。
- **转场（硬性）**：商品静图与穿插的 OP/ED/Trailer 之间禁止硬切。默认交叉溶解 `fade` **0.4 秒**。先用 `stable_motion.py` / 裁切得到各片段，再：
  ```bash
  python "<skill_root>/helpers/transitions.py" "<edit>/静图1.mp4" "<edit>/穿插.mp4" "<edit>/静图2.mp4" -o "<edit>/clips_visual/visual.mp4" --type fade --duration 0.4 --an
  ```
  `--an` 因为后续 `mix_ad_audio.py` 会替换音轨。默认 `--keep-duration`：交接段片尾补上转场时长的 handle，转场从原剪辑点开始，成片时长仍等于各镜头之和，口播和 `master.srt` **不改时间戳**。商品全景转细节可用 `smoothright:0.35` 或 `smoothleft:0.35`；不同素材类型之间用短交叉溶解 `fade:0.25`；同类静图之间也可用短 `fade:0.25` 或硬切。逐个连接设置示例：`--joins smoothright:0.35,fade:0.25,cut`。只有打算按缩短后的画面重做 TTS 和字幕时才加 `--no-keep-duration`。走 EDL 时在后一段写 `"transition": {"type": "smoothright", "duration": 0.35}`，或设 `"default_transition"`。

### 文案规范（口播脚本）

下文关于商品／角色和作品设定的写法用于商品任务；活动按 [活动要求](references/convention.md) 组织内容，漫展优先采用其中的视频构成。口语化表达、结尾点击引导、促销状态、禁词及字幕时间线要求共同适用。

- **体裁**：商品/角色设定导向的短视频解说——让商品画面、角色气质和作品语境带动叙事，普通商品不写成资讯播报或参数清单；数码及功能型商品可围绕技术参数组织解说。画面跟上镜素材走；密字图里抽出的重点可以只出现在口播和字幕里。
- **风格**：多放动漫梗，引起 ACG 爱好者共鸣；结合素材文件夹中的效果图介绍商品本身；结合动漫设定展开（设定信息查 moegirl）。普通商品优先写设定、外观、动作、服装、表情和氛围；数码电子等功能型产品可重点写有事实支撑的功能卖点和技术参数，并允许以技术参数为叙事中心。口播覆盖 `stills_inventory.md` 里「上镜」和「只取信息」的相关内容，不讲「弃用」条目；普通商品不播报材质等属性，数码及功能型商品依对应类型要求使用技术参数。
- **表达**：必须口语化，只讲这件商品；像朋友分享一个喜欢的角色/造型，句子短而顺，避免说明书式罗列和生硬的“商品页标注”“具体规则以商品页为准”。用具体画面细节带出感受，再用一句简短的点击引导收尾。促销只选最值得说的一点；有券可说“有优惠券”，宝箱/抽奖可说“有机会中/抽到”，但不得写成保证人人可领或必中奖。活动未开始时不写成已经生效，可提醒观众先加入购物车、届时符合活动条件再享受优惠。口播篇幅按用户给出的成片时长写，不自行改成别的长度；**禁止**出现逻辑总结类词语（如"总之""综上所述""最后总结一下"）；**禁止分点列条**。对外用词见 [对外文本禁词](#对外文本禁词硬性)。
- **数字**：促销门槛、优惠金额和作品设定等需要播报的数字使用阿拉伯数字，禁止写成中文数字；普通商品不播报尺寸、规格等商品参数，商品标价默认不写。数码电子等功能型产品可以讲经商品事实支持的功能与技术参数，参数中的数字同样用阿拉伯数字并保留原有量化符号。口语虚词如「一个」「一下」保持汉字。送入 TTS 的文案和烧录字幕都必须保留分数线，禁止把「1/7」改成「17」或「1 7」。

### 视频规格

- 画布：**1920×1080**。
- 背景：**高斯模糊填充**——原图放大铺满并高斯模糊作为背景层，前景叠放适配后的清晰画面。

### 混音规范（人声为主，数值硬性）

| 轨 | 响度目标 | 说明 |
|----|----------|------|
| 口播人声 | **-13 LUFS** | 保持自然清晰的原始响度，不做多余处理 |
| BGM | **-27 LUFS** | 分轨两遍标准化后固定叠加，全程不自动闪避 |

- **BGM 恒定**：不随人声出现、停顿或强弱自动降低；**不使用侧链压缩或自动闪避**（ducking）。
- **淡入淡出**：BGM 仅开头 **0.5 秒**淡入、结尾 **1.1 秒**淡出，避免突兀起止；人声开头 **0.05 秒**淡入。
- **防削波**：最终混音限制峰值（loudnorm / alimiter），避免削波失真。
- **BGM 来源（硬性）**：必须从 **YouTube 或 Bilibili** 检索并下载与产品相关动漫/游戏的现成 OST、OP/ED 音源或官方 BGM。两个来源平级。YouTube 用 `yt-dlp` 搜并抽音频；Bilibili 用 `python "<skill_root>/helpers/bilibili_src.py" search "<作品名 或 风格> OST"` 找到 BV 号后 `download <BVid> --audio-out ...`（音频无视觉水印，无需水印检测）。也可从本次已下载的 YouTube/Bilibili 视频素材中提取音轨，前提是该视频本身来自这两个平台。检索优先用作品名、角色名、官方曲名；`<风格>` 只作辅助关键词。必须记录曲名/来源 URL。
- **禁止自行生成 BGM**：不得用 TTS、Suno、Udio、音乐模型、MIDI、循环素材拼贴或任何本地合成来“做一条 BGM”。找不到相关曲目时换关键词继续搜，不得用生成音乐凑数。
- **执行脚本**：必须使用 `<skill_root>/helpers/mix_ad_audio.py` 完成混音。该脚本先检查原口播长度，分别两遍标准化人声与 BGM，混音前再次检查标准化后的口播，再以 `amix=normalize=0` 固定叠加。`alimiter=limit=0.95:latency=true` 补偿限幅器前瞻延迟。画面必须覆盖口播文件的完整时长（包括尾静音或编码填充），仅容许 48 kHz 的一个采样点探测误差；不足时修正时间窗，不自动截尾、拉伸或加速口播。

### 字幕规范（中文单行字幕）

样式锁在 `<skill_root>/helpers/ad_subtitles.py`，禁止手写或改写 `force_style`。该 helper 会 `ffprobe` 成片宽高，把 `PlayResX/PlayResY` 设成**当前视频的显示分辨率**，再按 `height/1080` 缩放字号、字距、描边和边距。只写 `PlayResY=1080` 会让 libass 用 4:3 的 `PlayResX=1440`，在 1920×1080 上把字横向拉宽，禁止那样烧录。

- **生成脚本（硬性）**：

  ```bash
  python "<skill_root>/helpers/transcribe.py" <最终口播音频> --edit-dir <edit> --provider paraformer
  python "<skill_root>/helpers/build_tts_subtitles.py" <最终送入TTS的文案文件> <最终音频的词级转写JSON> -o <master.srt> --max-chars 18 --min-chars 8
  python "<skill_root>/helpers/verify_tts_subtitles.py" <最终送入TTS的文案文件> <master.srt> --max-chars 18
  python "<skill_root>/helpers/ad_subtitles.py" <mixed.mp4> <master.srt> -o <final.mp4> --primary-colour <ASS颜色>
  ```

  口播转写在「TTS 配音与词级转写」阶段已完成；音频未改则直接复用 `transcripts/` 缓存，禁止重跑。广告流程禁止对 TTS 成片使用 `render.py --build-subtitles`，该路径会采用 ASR 文本。`verify_tts_subtitles.py` 失败即禁止烧录（Hard Rule 13）。
- **锁定样式（1080p 基准，按成片高度缩放）**：Hiragino Sans GB W6，`FontSize=72`，`Spacing=1`，`Outline=3`（四周细描边），`Shadow=0`，`WrapStyle=2`，`MarginV=8`，左右 `MarginL/R=64`。烧录时必须同时带上 `PlayResX=<视频宽>` 和 `PlayResY=<视频高>`；720p / 4K 由 helper 自动缩放，不要手填。Linux 或未安装冬青黑体时，只允许把 `FontName` 换成 `Noto Sans SC`。
- **单行（硬性）**：每条字幕必须只有一行。`--max-chars 18` 按**语义断句**切分：断点只允许落在句读标点（`。！？；` 必断，`，、` 优先断）之后，字幕永远不会在一句话中间被裁断；只有当单个分句自身超过 18 字时，才在拉丁/中文边界或空格处退让硬切。`--min-chars 8` 用于把过短的尾句前移，避免出现「孤字行」。禁止一条里出现换行。烧录用 `WrapStyle=2`，即使文本偏长也不许折成两行。
- **断句验收**：`verify_tts_subtitles.py` 除文本等价、单行、字数上限外，还会校验**每个断点都必须落在分句边界上**（单分句超长导致的硬切除外），并打印行长分布。断点跑偏即失败，禁止烧录。
- **颜色与对比度**：默认白色 `&H00FFFFFF`。若产品有指定高亮色，用 `--primary-colour` 覆盖，必须仍是高亮度浅色；禁止低亮度或接近画面暗部的颜色。抽查首帧、中段、尾帧确认可读。粉色 `&H00FF8FCF` 只是可选强调色，不是默认字幕色。
- **特效**：只用四周细描边；**不使用**底框、投影阴影、弹跳或花哨特效。
- **烧录顺序**：必须在所有画面、转场和叠加层完成后**最后烧录**，确保始终位于最上层不被遮挡（Hard Rule 1）。
- **文字**：字幕文字必须逐字采用最终送入 TTS 的口播文案，且顺序完全一致。标点处理分两类：**句末标点（`。！？；`）与其后的换行直接删除**（那里已经断行）；**句读标点（`，、`）保留为一个可见空格**——即使整句没超行长、没有断行，观众也要能在屏幕上看到念到哪停顿了。**不得**再把中文汉字之间的空格去掉，那会让整句糊成一串。分数线 `/`、小数点、百分号、比例冒号等量化符号必须原样保留（「1/7」不得变成「1 7」）。字距只由 `Spacing=1` 控制。不得根据 ASR 文本改写、纠错、概括、删减或补写字幕。
- 每条字幕时长与文案自然停顿对齐，不手估时间。ASR/强制对齐**只用于取得最终音频的词级时间戳**。

### B站投稿简介规范

投稿简介只写给观众的产品与活动信息。下文的点击引导同样适用于漫展等活动，保留准确活动名称及核心看点，以简短、明确的邀请指向评论区链接；无需照搬视频的段落顺序。用词见 [对外文本禁词](#对外文本禁词硬性)；另不得写入内部制作过程、工具参数、文件路径、凭证或调试日志。

- 除非用户明确要求，简介不放素材来源 URL；需要记录授权或来源时，写入 `<edit>/project.md`。用户明确要求外链时，链接必须独占一行，并在发布后核对平台没有扩大自动链接范围。
- 使用 API 或 CLI 发送简介时，必须传递真实换行符。禁止在单引号参数中写字面量 `\\n`、`\\r\\n` 或其他转义文本。
- 默认写 2–4 行短句，不强求固定结构：保留完整商品名和核心商品介绍，再挑一个确有依据的优惠点，最后用简短、明确的点击引导收尾。商品简介不使用句号，CTA 直接指向评论区链接；避免“商品页标注”“具体规则以商品页为准”等生硬话术、字段堆叠和客服腔。普通商品不要列价格或规格清单；数码电子等功能型产品可写有事实支撑的功能卖点与技术参数，简介可围绕核心参数组织。
- 有券时可只说“还有优惠券”，不用列可用时间或所有门槛；有宝箱/抽奖时可说“有机会中/抽到”，不得承诺人人中奖。对外文案不主动写活动开始日期或时间；活动未开始时不得说优惠已经生效，可提醒观众先加入购物车、届时符合活动条件再享受优惠，并引导观众点击评论区链接查看。用户明确要求保留的文案照做。
- 发送前校验：简介符合 [对外文本禁词](#对外文本禁词硬性)，且不得包含字面量反斜杠转义、文件系统路径、凭证标识，或非用户要求的 URL。
- 每次新投稿或编辑后，必须运行 `biliup show <BV>` 回读 `archive.desc`，精确核对文本、真实换行与链接范围。回读不一致时，停止商品挂载、评论等后续发布动作；修正简介并再次回读通过后才能继续。

### B站标题交付规范

最终视频交付时，必须同时提供 **1 个** 可直接发布的 B站标题；它与封面、成片同为强制交付物。先确认商品或活动的准确名称与已核实简称，不得编造昵称、场景或亲身体验。用词见 [对外文本禁词](#对外文本禁词硬性)。

**按业务类型选择标题规则：** 商品任务采用以下商品标题要求；漫展、游戏展、展览、音乐会等活动采用 [活动视频标题](references/convention.md#活动视频标题)，先筛选素材支持的切入点，再由模型自行选一种生成。以下“强烈感受开头”等商品要求不套用于活动。

#### 商品标题要求

标题生成前确认产品全名与常用圈内昵称，用于核实商品身份；发布标题使用准确、简短的商品称呼，不必照搬商品详情页全名，也不必同时写全名与昵称。不得编造昵称、场景或上手体验。

只写这件商品：品类、外观、IP/角色或一个真实卖点。普通商品不写材质、尺寸、规格等属性；数码及功能型商品可以用经核实的技术参数作为核心卖点。

- 标题开头必须是“具体卖点／产品特质 + 强烈感受”的完整短句，再用感叹号衔接产品名。普通商品优先写角色、设定、外观或气质，不得用价格或参数堆砌标题；数码电子等功能型产品可用经核实的功能卖点或技术参数作为标题核心。优先让卖点本身成为钩子，例如“桌面萌力超标！”“压迫感炸场！”“反差萌拉满！”。禁止使用“救命啊”“谁顶得住”“我破防了”等空泛语气词作为开头。
- 必须露出产品具体名或圈内昵称；只使用本商品自带的 IP、角色或圈层称呼。
- **名称要短，但不能短到认不出出处**：手办标题保留作品/IP 名、角色名，以及区分商品所需的版本和品类；尤其作品名是角色出处时，不得为缩短标题而删掉。优先删厂商、系列和营销赘词；不要缩写或截断作品名、角色名。
- **标题前段就能认出商品**：钩子后写“作品/IP 名＋角色名＋必要版本＋品类＋内容后缀”，删去重复信息即可，不要求照抄商品详情页全名。示例：`neonmax 蔚蓝档案 夜樱绮罗罗 纪念大厅Ver. 1/7手办` → `松弛感满分！《蔚蓝档案》夜樱绮罗罗纪念大厅手办推荐`。
- **商品名后优先加推荐类后缀**：这些视频定位是商品推荐，即使主要展示外观或细节，标题也优先使用“推荐”“好物推荐”“周边推荐”等简短词语，默认不用“鉴赏”“赏析”。根据品类与读起来是否自然选一个，避免“手办手办推荐”“周边周边推荐”等重复；不堆叠后缀，不额外追加一整句情绪文案。没有实际开箱、上手或测试内容时，不写“开箱”“实测”“测评”；不使用“必买”“闭眼入”等购买承诺。
- 用反差或悬念时，必须来自这件商品的外观或用途，不得使用“最”“第一”“100%”等绝对化表述。
- 文风应像真人发布：简洁、口语化、信息具体；不堆砌标签，不使用营销腔和标题党式承诺

#### 共用输出与自检

**标题输出格式：** `B站标题：<单行标题>`。除这 1 个最终标题外，不提供备选列表，用户明确要求评审示例时按其要求提供。商品交付前自检：作品/IP 名、角色/商品名及必要版本是否保留，能否一眼认出商品；是否有可删的厂商、系列或营销赘词；末尾是否有与视频内容相符的简短后缀。删掉商品名、卖点和 IP 后若仍能套到任意商品上，必须重写。活动交付前自检：类型、名称、时间状态与钩子均有事实支持，且视频能够承接标题中的具体承诺；允许缺少可用钩子时使用中性活动标题。

### B站封面交付规范

最终交付必须包含 `<edit>/cover.jpg`（16:9）和 `<edit>/cover-4x3.jpg`（从同一张 16:9 裁出），不得单独生成第二张 4:3。商品任务传递 `product` 模式，官方漫展海报传递 `poster` 模式；封面构图、提示词、保真度、裁切与验收规则仅在 [封面子 skill](skills/bili-cover/SKILL.md) 维护。商品模式交付实际使用的提示词，官方海报模式注明“使用官方宣传图，未调用生图”。投稿参数仍为 biliup `--cover` + `--cover43`。

### 示例

```text
使用 skill: video-use 任务：制作一个关于「明日香」手办的宣传广告视频，时长 <时长>。
素材在 <素材文件夹> 中。参考声音用 <参考音频.mp3>，
BGM 风格：电音。
```
