---
name: video-use
description: >
  Edit existing videos by conversation or produce Bilibili product and event promos.
  Use for 剪辑, 宣传广告视频, 商品宣传, ACG 宣传, 产品宣传片, 漫展宣传 and event video titles.
  Supports transcription, cutting, grading, animation, voiceover, subtitles, titles and covers.
  Select the relevant workflow and references; promo runtime comes from the user.
---

# Video Use

## Principle

1. **LLM reasons from raw transcript + on-demand visuals.** The only derived artifact that earns its keep is a packed phrase-level transcript (`takes_packed.md`). Everything else — filler tagging, retake detection, shot classification, emphasis scoring — you derive at decision time.
2. **Audio is primary, visuals follow.** Cut candidates come from speech boundaries and silence gaps. Drill into visuals only at decision points.
3. **Ask → confirm → execute → iterate → persist.** Never touch the cut until the user has confirmed the strategy in plain English.
4. **Generalize.** Do not assume what kind of video this is. Look at the material, ask the user, then edit.
5. **Artistic freedom is the default.** In general-edit references, specific taste values, presets, fonts, colors, durations, pitch structures and techniques are worked examples, unless explicitly marked as requirements. Bilibili promo production standards remain mandatory. Read them to understand what's possible and why each worked. Then make your own taste calls based on what the material actually is and what the user actually wants. **Follow the Hard Rules and the mandatory requirements of the selected mode.** General-edit taste examples remain adaptable.
6. **Invent freely.** If the material calls for a technique not described here — split-screen, picture-in-picture, lower-third identity cards, reaction cuts, speed ramps, freeze frames, crossfades, match cuts, L-cuts, J-cuts, speed ramps over breath, whatever — build it. The helpers are ffmpeg and PIL. They can do anything the format supports. Do not wait for permission.
7. **Verify your own output before showing it to the user.** If you wouldn't ship it, don't present it.

## Modes and reference routing

Pick one mode at session start. Do not blend the general-edit recipe and the locked promo recipe.

- **General edit** (default): existing footage such as talking heads, interviews, tutorials, travel and montages. Read [general-edit.md](references/general-edit.md). Artistic freedom applies to taste, subject to the Hard Rules.
- **Bilibili promo**: 宣传广告视频、广告视频、云逛视频、ACG 宣传、商品宣传视频、产品宣传片，或静图配克隆声音的 B站商品视频。Read [promo-common.md](references/promo-common.md), then exactly the applicable type reference:
  - 普通商品、手办及数码等功能型商品：[product.md](references/product.md)。
  - 漫展、游戏展、展览、音乐会等活动：[convention.md](references/convention.md)。活动标题由模型从素材支持的五种切入点中自行选一种，不套用商品的强烈感受开头要求。

结合用户目标、商品详情和实际素材选择类型；`detail.kind` 的 `mall` / `ticket` 是数据来源类型，不能单独代替业务分类。若仍不明确且会影响制作，先向用户确认。广告时长只从用户提示词读取，缺失时追问；普通商品依原有规则优先叙事与外观，不默认列规格或售价；数码电子等功能型商品允许以经核实的技术参数为叙事中心，详见商品类型参考文件。

执行前读取 [环境与工具说明](references/tools.md)，仅核对本次会用到的环境与凭证，不重复首次安装。

| 需要执行的操作 | 按需读取 |
|---|---|
| TTS 或声音克隆 | [voiceover.md](references/voiceover.md) |
| 动画槽位 | [animations.md](references/animations.md)；Manim 槽位另读 [Manim 子 skill](skills/manim-video/SKILL.md) |
| EDL 渲染或转场时间轴 | [edl.md](references/edl.md) |
| B站封面 | [封面子 skill](skills/bili-cover/SKILL.md)，传递已确定的 `product` / `poster` 模式、参考素材及已确认文字 |
| 用户明确要求投稿 | [publishing.md](references/publishing.md)，完成投稿闸门后才执行 |

不默认加载全部参考文件。普通剪辑的示例字幕与混音不替代广告的固定实现。所有辅助脚本从主技能根目录解析，不从当前参考文件所在目录解析。

## Hard Rules (production correctness — non-negotiable)

These are the things where deviation produces silent failures or broken output. They are not taste, they are correctness. Memorize them.

1. **Subtitles are applied LAST in the filter chain**, after every overlay. Otherwise overlays hide captions. Silent failure.
2. **Per-segment extract, then join.** Hard-cut joins use lossless `-c copy` concat. Visual transitions use `xfade` on the *already-extracted* 1080p segments (`<skill_root>/helpers/transitions.py`). Never pull original sources into one giant filtergraph with overlays — that double-encodes.
3. **30ms audio fades at every hard-cut boundary** (`afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03}:d=0.03`). Otherwise audible pops at every cut. `xfade` joins use `acrossfade` of the same duration instead of a hard audio cut.
4. **Overlays use `setpts=PTS-STARTPTS+T/TB`** to shift the overlay's frame 0 to its window start. Otherwise you see the middle of the animation during the overlay window.
5. **Per-source master SRT uses output-timeline offsets**: `output_time = word.start - segment_start + segment_offset`. `segment_offset` follows the selected transition policy: default `--keep-duration` / `transition_handles=true` preserves authored cut offsets; only `--no-keep-duration` / `transition_handles=false` subtracts the actual inbound xfade overlap. Fixed narration/TTS captions stay locked to the final audio; do not subtract visual overlaps from their timestamps. See [EDL timing](references/edl.md). Otherwise captions misalign after segment concat.
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
