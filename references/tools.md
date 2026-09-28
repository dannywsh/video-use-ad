# Environment and tools

辅助脚本路径统一以主入口定义的 `<skill_root>` 为基准。执行环境须继承主入口设置的会话临时目录。只读本次需要的工具与凭证说明；需要配音时再读 [voiceover.md](voiceover.md)，需要动画时再读 [animations.md](animations.md)。

## Setup

First-time install lives in [install.md](../install.md) (clone, deps, ffmpeg, skill registration, API keys). Don't re-run it every session; on cold start just verify:

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
- This skill vendors `skills/manim-video/`. Read [Manim 子 skill](../skills/manim-video/SKILL.md) when building a Manim slot.
- This skill vendors `skills/bili-cover/`. When delivering a Bilibili cover, read [封面子 skill](../skills/bili-cover/SKILL.md) (do not improvise the cover recipe here).
- `GCP_GEMINI_IMAGE_API_KEY` resolves from that lookup — required for the `gcp-gemini` cover backend. Optional `GCP_GEMINI_IMAGE_MODEL` / `GCP_GEMINI_IMAGE_API_ENDPOINT` / `GCP_GEMINI_IMAGE_SIZE` override model, host, and `imageSize`.
- `ARK_SEEDREAM_API_KEY` resolves from that lookup — required for the `ark-seedream` cover backend. Optional `ARK_SEEDREAM_MODEL` / `ARK_SEEDREAM_API_BASE_URL` override model and Ark base URL.
- Bilibili product promo is part of this skill (not a nested skill). When that mode is active, follow [广告共用制作流程](promo-common.md). Cover stills follow `skills/bili-cover/`.

Helpers (`<skill_root>/helpers/transcribe.py`, `<skill_root>/helpers/render.py`, etc.) live under the main skill root alongside its SKILL.md. Resolve their paths from `<skill_root>`, not from this reference directory — the skill is typically symlinked at `~/.claude/skills/video-use/` or `~/.codex/skills/video-use/`.

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
- **`inventory_stills.py`** — list stills, draw a y-tick overview for tall infographics, and crop full-width windows the agent already chose. Does **not** auto-slice by 16:9 viewport, color gaps, or OCR. Crops pad both ends by default (prefer extra neighbors over clipped goods). `region` in crop JSON is for `stable_motion.py --region`. See [静图分拣](promo-common.md#静图分拣硬性).
- **`stable_motion.py`** — jitter-free push/scroll/pan of product stills. `--mode scroll` crawls vertically at a fixed 0.18 screens/s. `--mode pan-right` uses a natural wide image at 0.12 screen widths/s; near-16:9 images selected for detail appreciation get a centered 1.18× zoom and a slower 0.04 screen widths/s scan. On 16:9 footage this crops about 7.6% from the top and bottom, so reserve it for detail shots; use `push` for complete product views. Narrower images fall back to `push`. Scroll supports `--anchor top|center|bottom`, `--region 0.12,0.45`, and `--probe`; `pan-right` also supports `--probe` to inspect available travel and zoom. See [广告共用制作流程](promo-common.md).
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
