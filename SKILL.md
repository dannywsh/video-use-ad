---
name: video-use
description: >
  Edit any video by conversation, or produce a Bilibili ACG product promo.
  General edits include transcribe, cut, color grade, overlays, subtitles, and AI voiceover
  for talking heads, montages, tutorials, travel, interviews.
  Bilibili promo uses product stills mixed with official OP/ED/Trailer, spoken product copy,
  Fish Audio clone, single-line Chinese captions, LUFS mix, one title and one cover.
  Runtime comes from the user prompt, not a skill default.
  Triggers: 剪辑, 宣传广告视频, 商品宣传, ACG 宣传, 产品宣传片.
  Production-correctness rules are hard; general edits otherwise have artistic freedom.
---

# Video Use

## Principle

1. **LLM reasons from raw transcript + on-demand visuals.** The only derived artifact that earns its keep is a packed phrase-level transcript (`takes_packed.md`). Everything else — filler tagging, retake detection, shot classification, emphasis scoring — you derive at decision time.
2. **Audio is primary, visuals follow.** Cut candidates come from speech boundaries and silence gaps. Drill into visuals only at decision points.
3. **Ask → confirm → execute → iterate → persist.** Never touch the cut until the user has confirmed the strategy in plain English.
4. **Generalize.** Do not assume what kind of video this is. Look at the material, ask the user, then edit.
5. **Artistic freedom is the default.** Every specific value, preset, font, color, duration, pitch structure, and technique in this document is a *worked example* from one proven video — not a mandate. Read them to understand what's possible and why each worked. Then make your own taste calls based on what the material actually is and what the user actually wants. **The only things you MUST do are in the Hard Rules section below.** Everything else is yours.
6. **Invent freely.** If the material calls for a technique not described here — split-screen, picture-in-picture, lower-third identity cards, reaction cuts, speed ramps, freeze frames, crossfades, match cuts, L-cuts, J-cuts, speed ramps over breath, whatever — build it. The helpers are ffmpeg and PIL. They can do anything the format supports. Do not wait for permission.
7. **Verify your own output before showing it to the user.** If you wouldn't ship it, don't present it.

## Modes

Pick one at session start. Do not blend the two recipes.

- **General edit** (default). Existing footage: talking heads, interviews, tutorials, travel, montages. Artistic freedom except Hard Rules. Follow The process.
- **Bilibili product promo.** Triggers: 宣传广告视频, 广告视频, 云逛视频, ACG 宣传, 商品宣传视频, 产品宣传片, or a Bilibili product video from stills + cloned voice. Then §Bilibili product promo is a **hard recipe** — numeric specs are mandatory unless the user overrides. Runtime is whatever the user wrote in the prompt; do not assume a length. Hard Rules still apply. Do not substitute general subtitle/mix taste examples for the locked promo path.

## Hard Rules (production correctness — non-negotiable)

These are the things where deviation produces silent failures or broken output. They are not taste, they are correctness. Memorize them.

1. **Subtitles are applied LAST in the filter chain**, after every overlay. Otherwise overlays hide captions. Silent failure.
2. **Per-segment extract, then join.** Hard-cut joins use lossless `-c copy` concat. Visual transitions use `xfade` on the *already-extracted* 1080p segments (`helpers/transitions.py`). Never pull original sources into one giant filtergraph with overlays — that double-encodes.
3. **30ms audio fades at every hard-cut boundary** (`afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03}:d=0.03`). Otherwise audible pops at every cut. `xfade` joins use `acrossfade` of the same duration instead of a hard audio cut.
4. **Overlays use `setpts=PTS-STARTPTS+T/TB`** to shift the overlay's frame 0 to its window start. Otherwise you see the middle of the animation during the overlay window.
5. **Master SRT uses output-timeline offsets**: `output_time = word.start - segment_start + segment_offset`. `segment_offset` subtracts inbound xfade overlap. Otherwise captions misalign after segment concat.
6. **Never cut inside a word.** Snap every cut edge to a word boundary from the word-level transcript.
7. **Pad every cut edge.** Working window: 30–200ms. ASR timestamps drift 50–100ms — padding absorbs the drift. Tighter for fast-paced, looser for cinematic.
8. **Word-level verbatim ASR only.** Never SRT/phrase mode (loses sub-second gap data). Never normalized fillers (loses editorial signal).
9. **Cache transcripts per source.** Never re-transcribe unless the source file itself changed.
10. **Parallel sub-agents for multiple animations.** Never sequential. Spawn N at once via the `Agent` tool; total wall time ≈ slowest one.
11. **Strategy confirmation before execution.** Never touch the cut until the user has approved the plain-English plan.
12. **All session outputs in `<videos_dir>/edit/`.** Never write inside the `video-use/` project directory.
13. **TTS narration subtitles are verbatim and final-audio aligned.** Generate captions only after the final TTS audio exists. Every spoken word, including brand names, qualifiers, and fillers the user expects, must appear in the subtitles in the same order; split only at natural semantic boundaries and never summarize, paraphrase, or omit text. Derive timestamps from word-level transcription or forced alignment of that exact final audio, then convert them to output-timeline offsets. Never hand-estimate subtitle timings from the script or total runtime.
14. **Inserted third-party footage must carry the intended meaning on screen.** For a game, film, animation, or product promo, every inserted clip must visibly show the relevant character, world, gameplay, product use, or other claim-supporting subject during its usable duration. Do not use platform logos, publisher cards, rating screens, preorder/date cards, title-only frames, black frames, or generic footage as a substitute. Sample the planned in/out frames before editing; discard or trim any clip whose visible content does not directly support the adjacent narration, caption, or product claim.

Everything else in this document is a worked example. Deviate whenever the material calls for it.

## Directory layout

The skill lives in `video-use/`. User footage lives wherever they put it. All session outputs go into `<videos_dir>/edit/`.

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
    ├── stills_inventory.md      ← promo stills: on-screen / voice-only facts / unused
    ├── cover.jpg                ← Bilibili cover from skills/bili-cover
    ├── preview.mp4
    └── final.mp4
```

## Setup

First-time install lives in `install.md` (clone, deps, ffmpeg, skill registration, API keys). Don't re-run it every session; on cold start just verify:

- **Credential discovery (mandatory before asking the user):** keys live outside the skill install directory because `npx skills update` deletes and recreates it. Canonical file: `~/.config/video-use/.env` on all platforms (Windows: `%USERPROFILE%\.config\video-use\.env`; or `$XDG_CONFIG_HOME/video-use/.env`, or `$VIDEO_USE_ENV`). Print the local path with `python helpers/env_file.py --user-path`. Lookup order matches `helpers/env_file.py`: user config → leftover `<skill_root>/.env` (copied to user config on first helper run) → `<cwd>/.env` → exported environment variables. Do **not** infer the key file from the current workspace, source-video directory, or a hard-coded example path. If a leftover skill-root `.env` exists, run `python helpers/env_file.py --migrate` before updating.
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
- This skill vendors `skills/manim-video/`. Read its SKILL.md when building a Manim slot.
- This skill vendors `skills/bili-cover/`. When delivering a Bilibili cover, read `skills/bili-cover/SKILL.md` (do not improvise the cover recipe here).
- `GCP_GEMINI_IMAGE_API_KEY` resolves from that lookup — required for the `gcp-gemini` cover backend. Optional `GCP_GEMINI_IMAGE_MODEL` / `GCP_GEMINI_IMAGE_API_ENDPOINT` / `GCP_GEMINI_IMAGE_SIZE` override model, host, and `imageSize`.
- `ARK_SEEDREAM_API_KEY` resolves from that lookup — required for the `ark-seedream` cover backend. Optional `ARK_SEEDREAM_MODEL` / `ARK_SEEDREAM_API_BASE_URL` override model and Ark base URL.
- Bilibili product promo is part of this skill (not a nested skill). When that mode is active, follow §Bilibili product promo. Cover stills follow `skills/bili-cover/`.

Helpers (`helpers/transcribe.py`, `helpers/render.py`, etc.) live alongside this SKILL.md. Resolve their paths relative to the directory containing this file — the skill is typically symlinked at `~/.claude/skills/video-use/` or `~/.codex/skills/video-use/`.

## Helpers

- **`transcribe.py <video>`** — single-file ASR. `--provider elevenlabs|paraformer` (default elevenlabs). `--num-speakers N` is Scribe-only. `--audio-track N` selects a zero-based audio stream (OBS: 0 = game, 1 = mic); track 0 keeps the existing `{stem}.json` cache name, other tracks write `{stem}.trackN.json`. Refuses to upload a silent track (peak < -60 dBFS). Cached. Writes Scribe-compatible `words` JSON for either provider.
- **`transcribe_batch.py <videos_dir>`** — 4-worker parallel transcription. Same `--provider` and `--audio-track` flags. Use for multi-take.
- **`pack_transcripts.py --edit-dir <dir>`** — `transcripts/*.json` → `takes_packed.md` (phrase-level, break on silence ≥ 0.5s).
- **`timeline_view.py <video> <start> <end>`** — filmstrip + waveform PNG. On-demand visual drill-down. **Not a scan tool** — use it at decision points, not constantly.
- **`render.py <edl.json> -o <out>`** — per-segment extract → join (lossless concat or xfade) → overlays (PTS-shifted) → subtitles LAST. `--preview` for 720p fast. `--build-subtitles` to generate master.srt inline. Default output fps matches the first source (`--fps 30` or `--fps 30000/1001` to force). Portrait detection honors display-matrix rotation so phone footage scaled on the right axis.
- **`transitions.py <clips...> -o <out>`** — join already-rendered clips with visual transitions. Default `--type fade --duration 0.4`. Per-join: `--joins fade:0.4,cut,fadeblack:0.5`. `--an` when a later mix pass replaces audio (Bilibili promo). Default `--keep-duration` pads each outgoing clip by the xfade so the programme length stays aligned with an already-authored TTS/SRT; `--no-keep-duration` lets overlaps shorten the output. Hard-cut-only runs stay lossless `-c copy`.
- **`tts.py <text> -o <out>`** — text-to-speech for adding voiceover/narration. `--provider fish|mimo|elevenlabs` (default **fish**). Fish Audio creates a reusable private clone from `--reference-audio` or reuses `--fish-voice-id`. MiMo is opt-in for preset voices, voice design, or short-sample cloning. `--style` is MiMo-only. Outputs wav/mp3 ready to mix with ffmpeg.
- **`grade.py <in> -o <out>`** — ffmpeg filter chain grade. Presets + `--filter '<raw>'` for custom.
- **`bilibili_src.py <cmd>`** — Bilibili stock-source helper (good for ACG/anime/game OST and short clips). `search "<kw>" --n 5` lists candidates (bvid/title/UP主/duration); `check-watermark <BVid>` heuristically detects a burned-in watermark by checking edge detail in all four corners against the center — **run it BEFORE using any Bilibili-sourced VIDEO as stock; a watermark hit means discard that clip** (videos from YouTube/other platforms are NOT subject to this check); `download <BVid> --audio-out/--video-out [--force] [--cookies-from-browser <browser>]` pulls audio (BGM, no watermark concern) or video via yt-dlp. Video formats need a logged-in cookie (see below). This check is heuristic; visually spot-check any borderline or business-critical result.
- **Bilibili cookie acquisition:** pass `--cookies-from-browser <chrome|firefox|edge|safari|brave>`; yt-dlp reads the already-logged-in Bilibili cookie straight from the user's local browser (no manual export). Anonymous downloads are audio-only.
- **`env_file.py`** — dotenv lookup and migrate. Canonical keys: `~/.config/video-use/.env` on all platforms (Windows: `%USERPROFILE%\.config\video-use\.env`). `--user-path` prints the local file; `--migrate` copies a leftover skill-root `.env` there so `npx skills update` cannot wipe keys.
- **`inventory_stills.py`** — list stills, draw a y-tick overview for tall infographics, and crop full-width windows the agent already chose. Does **not** auto-slice by 16:9 viewport, color gaps, or OCR. Crops pad both ends by default (prefer extra neighbors over clipped goods). `region` in crop JSON is for `stable_motion.py --region`. See §静图分拣.
- **`stable_motion.py`** — jitter-free push/scroll of product stills. `--mode scroll` crawls at a fixed 0.18 screens/s; leftover shot time holds the last frame, and a too-tall still is cropped (`--anchor top|center|bottom`, `--region 0.12,0.45`, `--probe`). See §Bilibili product promo.
- **`mix_ad_audio.py`** — locked promo mix (voice -13 LUFS, BGM -27 LUFS). Promo mode only.
- **`build_tts_subtitles.py` / `verify_tts_subtitles.py` / `ad_subtitles.py`** — verbatim single-line Chinese captions for promo TTS. Promo mode only.

**ASR provider choice** (do not default blindly):

- **ElevenLabs Scribe** (`--provider elevenlabs`, default) — word-level timestamps, speaker diarization, filler/audio-event tags. Use for multi-take talking-head inventory, interviews, and any cut that needs speaker changes or `(laughs)` / `(sighs)`. Requires `ELEVENLABS_API_KEY`.
- **Paraformer** (`--provider paraformer`) — hosted FunASR Paraformer-large at `https://paraformer.ow2shit.top`. Chinese-first character timestamps, no diarization, no audio events. Use for Chinese TTS/voiceover subtitle timing, and for Chinese-only sources when speaker IDs and audio events are not needed. Requires `PARAFORMER_API_TOKEN`. Never pass `response_format=srt` into the edit pipeline — the helper converts JSON to word-level `words` entries.

```bash
python helpers/transcribe.py edit/voiceover/narration.wav --edit-dir edit --provider paraformer
python helpers/transcribe_batch.py <videos_dir> --provider paraformer
```

For animations, create `<edit>/animations/slot_<id>/` with `Bash` and spawn a sub-agent via the `Agent` tool.

## The process

If this session is **Bilibili product promo**, skip this section and follow §Bilibili product promo instead.

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

When the user wants AI narration, dubbing, or a synthetic voice added to the edit, use `helpers/tts.py`. **Default to Fish Audio** (`--provider fish`). Do not use MiMo unless the user names it.

- **Default / 声音克隆 / 参考音频 / 要复用声线:** **Fish Audio**. Create a private reusable voice from `--reference-audio`, then reuse `--fish-voice-id`. Requires `FISH_API_KEY` and either a reference clip (≥10s recommended) or an existing voice ID.
- **They explicitly ask for MiMo**, a named MiMo preset (`冰糖` etc.), MiMo voice design, or a 3–10s MiMo clone: choose **MiMo**.
- **They explicitly ask for ElevenLabs** or a specific ElevenLabs library voice: choose **ElevenLabs**.
- If the prompt names a provider, follow it. Never fall back to MiMo just because the clip is Chinese or short.

Before creating any clone, confirm the user has the right to use the reference speaker's voice. Never publish a cloned model: this helper always creates Fish Audio clones with `visibility=private`.

It supports three providers behind one CLI:

- **Fish Audio** (`--provider fish`, default) — persistent private voice clone. Requires `FISH_API_KEY`. Supply `--reference-audio sample.wav` (accepts `.wav`, `.mp3`, `.m4a`, `.opus`; clean single-speaker audio of at least 10 seconds is recommended) to create a reusable voice model, or supply its `--fish-voice-id` to reuse one. Default synthesis model: `s2.1-pro-free` (override with `--fish-model`).
- **ElevenLabs** (`--provider elevenlabs`) — wide voice library via `--voice-id`, multilingual, MP3 output. Requires `ELEVENLABS_API_KEY`.
- **MiMo** (`--provider mimo`) — Xiaomi MiMo-V2.5-TTS, Chinese-first, currently free. Opt-in only. Requires `MIMO_API_KEY`. Three modes:
  - **Preset voice** (`--mimo-model tts`, default): `--voice 冰糖` (Chinese female), `茉莉` (Chinese female), `苏打` (Chinese male), `白桦` (Chinese male), `Mia`/`Chloe` (English female), `Milo`/`Dean` (English male), or `mimo_default`.
  - **Voice design** (`--mimo-model voicedesign`): describe a voice in natural language via `--style`, e.g. `"一位温柔的中年女性，嗓音略带沙哑"`. No sample needed; `--style` is required.
  - **Voice clone** (`--mimo-model voiceclone`): pass a 3–10s `.mp3`/`.wav` sample via `--reference-audio sample.mp3` (≤10 MB); MiMo clones the timbre.

**Fish Audio advanced controls:** use `--extra_params '<JSON object>'` only when the prompt asks for a deliberate output adjustment. The helper forwards supported TTS fields such as `temperature`, `top_p`, `repetition_penalty`, `max_new_tokens`, `chunk_length`, `latency`, `normalize`, `min_chunk_length`, `condition_on_previous_chunks`, `early_stop_threshold`, and `prosody` (with `speed` / `volume`). Example: `--extra_params '{"temperature":0.5,"top_p":0.7,"prosody":{"speed":1.1}}'`. `top_k` is also passed through for API compatibility, but it is not listed in Fish Audio’s current public TTS field reference. The CLI rejects attempts to override `text`, `reference_id`, `references`, `format`, or `model`.

**Style control (MiMo):** `--style` takes a natural-language direction placed in the API's `user` message — e.g. `"用兴奋上扬的语调，语速稍快"` or the full director-mode format (角色/场景/指导). You can also embed audio tags directly in the synthesis text, e.g. `"(慵懒)再让我睡五分钟……"` or `"(东北话)哎呀妈呀，这天儿忒冷了！"`.

**Typical workflow:**

1. Generate the voiceover file into `<edit>/voiceover/`:
   ```bash
   python helpers/tts.py "欢迎来到本期视频" -o edit/voiceover/narration.mp3 \
     --provider fish --reference-audio speaker.wav --fish-voice-title "品牌旁白"
   # Save the printed voice ID, then reuse it without uploading the sample again:
   python helpers/tts.py "下一段旁白" -o edit/voiceover/next.mp3 \
     --provider fish --fish-voice-id <voice_id>
   # Reduce variation and slightly speed up delivery.
   python helpers/tts.py "更稳定的旁白" -o edit/voiceover/tuned.mp3 \
     --provider fish --fish-voice-id <voice_id> \
     --extra_params '{"temperature":0.5,"top_p":0.7,"prosody":{"speed":1.1}}'
   ```
2. Measure its duration with `ffprobe` if animations need to sync to it.
3. Mix it into the rendered video with ffmpeg — duck the original audio under the voiceover, or replace it entirely:
   ```bash
   # Mix voiceover over original audio (original ducked to 30%)
   ffmpeg -i final.mp4 -i edit/voiceover/narration.mp3 -filter_complex \
     "[0:a]volume=0.3[bg];[bg][1:a]amix=inputs=2:duration=longest:dropout_transition=2[a]" \
     -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -shortest final_voiced.mp4
   ```
   If the voiceover should start at a specific offset, use `adelay` on the voiceover track before mixing.
4. If the voiceover drives animation timing, generate it **before** building overlays so you can sync reveals to it (see the animation payoff-timing rule).
5. If subtitles are required, transcribe or force-align the **generated final voiceover file** at word level before creating `master.srt`. For Chinese narration, prefer `--provider paraformer`; use Scribe when diarization or non-Chinese timing is required. Use the narration source text only to verify the alignment; do not write a shortened caption version. Compare the rendered SRT text against the narration text before delivery and treat any missing, reordered, or paraphrased spoken content as a blocking defect.

Hard rules: never commit API keys; write them only to the user-config `.env` (`python helpers/env_file.py --user-path`). Generated voiceover files go under `<videos_dir>/edit/voiceover/`, never inside the skill directory.

## Animations (when requested)

Animations match the content and the brand. **Get the palette, font, and visual language from the conversation** — never assume a default. If the user hasn't told you, propose a palette in the strategy phase and wait for confirmation before building anything.

**Tool options:**

Pick the engine per animation slot. Do not default to Remotion just because the animation is web-adjacent.

- **HyperFrames** — Browser-native HTML/CSS/GSAP video compositions: product UI motion, website-to-video or mockup-to-video captures, kinetic typography, landing-page/storyboard promos, data-driven UI states, transparent WebM overlays, and clips that need deterministic frame capture plus HyperFrames lint/validate/render checks. Best when the animation should be authored and verified like a web composition instead of a React component tree.
- **Remotion** — React/CSS compositions with component state, reusable React primitives, or an existing Remotion brand system. Best when the user specifically asks for React/Remotion or when React composition is the simpler authoring model.
- **Manim** — formal diagrams, state machines, equation derivations, graph morphs. Read `skills/manim-video/SKILL.md` and its references for depth.
- **PIL + PNG sequence + ffmpeg** — simple overlay cards: counters, typewriter text, single bar reveals, progressive draws. Fast to iterate, any aesthetic you want. The launch video used this.

For HyperFrames slots, scaffold the slot inside `edit/animations/slot_<id>/` with `npx --yes hyperframes init . --example blank --non-interactive --skip-skills`, build the HTML composition there, run the HyperFrames checks that fit the slot (`lint`, `validate`, and a draft render when practical), then produce the final overlay video with `npx --yes hyperframes render . -o render.mp4` or `--format webm -o render.webm` when alpha is required. Point the EDL overlay `file` at the actual rendered path.

For Remotion slots, keep the Remotion project isolated inside the same slot directory, scaffold with `npx create-video@latest` or install Remotion locally there, render the composition to `render.mp4` with the project-local `remotion render` command, and verify duration and dimensions with `ffprobe`.

None is mandatory. Invent hybrids if useful (e.g., PIL background with a HyperFrames or Remotion layer on top).

**Duration rules of thumb, context-dependent:**

- **Sync-to-narration explanations.** A viewer needs to parse the content at 1×. Rough floor 3s, typical 5–7s for simple cards, 8–14s for complex diagrams. The launch video shipped at 5–7s per simple card.
- **Beat-synced accents** (music video, fast montage). 0.5–2s is fine — they're visual accents, not information. The "readable at 1×" rule becomes *"recognizable at 1×"*, not *"fully parseable."*
- **Hold the final frame ≥ 1s** before the cut (universal).
- **Over voiceover:** total duration ≥ `narration_length + 1s` (universal).
- **Never parallel-reveal independent elements** — the eye can't track two new things at once. One thing, pause, next thing.

**Animation payoff timing (rule for sync-to-narration):** get the payoff word's timestamp. Start the overlay `reveal_duration` seconds earlier so the landing frame coincides with the spoken payoff word. Without this sync the animation feels disconnected.

**Easing** (universal — never `linear`, it looks robotic):

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
    {"file": "edit/animations/slot_1/render.mp4", "start_in_output": 0.0, "duration": 5.0}
  ],
  "subtitles": "edit/master.srt",
  "subtitle_style": "PlayResX=1920,PlayResY=1080,FontName=Hiragino Sans GB,FontSize=72,Bold=1,Spacing=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00201828,BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginL=64,MarginR=64,MarginV=8,WrapStyle=2",
  "total_duration_s": 87.4
}
```

`grade` is a preset name or raw ffmpeg filter. `overlays` are rendered animation clips. `subtitles` is optional and applied LAST. `subtitle_style` is an optional libass `force_style` string; use it when a specialized workflow requires a fixed caption treatment.

**Transitions.** Omitted `transition` on a range is a hard cut, unless `default_transition` (or top-level `transition`) is set. The first range never has an inbound join. `"transition": "cut"` opts one join out of a default dissolve. Types are ffmpeg `xfade` names: `fade` (cross-dissolve, default), `fadeblack`, `fadewhite`, `wipeleft` / `wiperight`, `slideleft` / `slideright`. Duration is seconds; keep it under half of either adjacent clip. Talking-head / same-camera cuts stay hard-cut. Inserted B-roll, product stills vs OP/ED, or any source-class change should dissolve unless the user asked for jump cuts.

**Do not shift TTS captions to chase the dissolve.** Promo/TTS subtitles are locked to the final narration audio (Hard Rule 13). Naive xfade shortens the picture by the overlap, so later shots arrive early while the voice stays put. Default `--keep-duration` (EDL `transition_handles`, default true) adds that overlap as a freeze/tail on the outgoing clip so the dissolve *starts* at the original cut point and `total_duration_s` still equals the narration. Only use `--no-keep-duration` / `"transition_handles": false` when you intend to re-time or re-generate the voiceover to the shorter picture.

## Memory — `project.md`

Append one section per session at `<edit>/project.md`:

```markdown
## Session N — YYYY-MM-DD

**Strategy:** one paragraph describing the approach
**Decisions:** take choices, cuts, grades, animations + why
**Reasoning log:** one-line rationale for non-obvious decisions
**Outstanding:** deferred items
```

On startup, read `project.md` if it exists and summarize the last session in one sentence before asking whether to continue.

## Anti-patterns

Things that consistently fail regardless of style:

- **Hierarchical pre-computed codec formats** with USABILITY / tone tags / shot layers. Over-engineering. Derive from the transcript at decision time.
- **Hand-tuned moment-scoring functions.** The LLM picks better than any heuristic you'll write.
- **Whisper SRT / phrase-level output.** Loses sub-second gap data. Always word-level verbatim JSON (`words` with start/end), whether from Scribe or Paraformer.
- **Running Whisper locally on CPU.** Slow and it normalizes fillers. Use Scribe or Paraformer.
- **Burning subtitles into base before compositing overlays.** Overlays hide them. (Hard Rule 1.)
- **Single-pass filtergraph when you have overlays.** Double re-encodes. Use per-segment extract → concat or xfade-join of extracted clips.
- **Linear animation easing.** Looks robotic. Always cubic.
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

Numeric specs here are production standards, not taste. Override only when the user explicitly asks. Hard Rules still apply. Credential lookup is §Setup. TTS CLI is §Voiceover / TTS (default Fish Audio; strip §对外文本禁词 from `--extra_params`; write files to `<videos_dir>/edit/voiceover/`).

### 对外文本禁词（硬性）

面向观众或平台发布的文本，禁止出现制作配方用语和提示词。适用范围：口播文案、烧录字幕、B站标题、投稿简介、封面画面文字、标签。

禁止出现：云逛、口播、混剪、资讯、宣传片、广告、配方、提示词、BGM、字幕、封面。

这些词只留在本技能的内部说明里，不得写进任何将要发布或给观众看的句子（含封面画面上要画出来的文案）。送入 TTS 的口播文案同样不得使用上述禁词。发给图像模型的**生成提示词可以用「封面」**等内部用语；禁词约束的是画面文字，不是生图 prompt。

### 输入参数

每次任务开始先收集以下参数，缺失时追问，不猜测：

| 参数 | 占位 | 说明 |
|------|------|------|
| 产品名称 | `<产品名称>` | 文案与画面围绕的产品 |
| 成片时长 | `<时长>` | 只从用户提示词读取；缺失时追问，不默认任何时长 |
| 素材文件夹 | `<文件夹路径>` | 商品图片、效果图所在目录 |
| 参考声音 | `<.mp3>` | Fish Audio 声音克隆参考音频（建议 ≥10 秒、干净单人声） |
| BGM 风格 | `<风格>` | 检索关键词（作品名、OST、曲风）；只用于在 YouTube / Bilibili 找现成 BGM，禁止据此生成音乐 |
| TTS 风格提示词 | `<用户提示词>` | 可选；Fish Audio 默认不使用。仅当用户明确要求语速/音量等，才写入 `--extra_params` |

### 执行流程

1. **清点素材（静图分拣在文案之前）**：`ffprobe` 检查视频素材。静图必须按 §静图分拣 跑 `inventory_stills.py`、看原图和长图 y 刻度总览、只对上镜栏目裁窗并看裁图、写入 `edit/stills_inventory.md`。先定上镜 / 只取信息 / 弃用，再写口播。文字多的图可以不上镜，但其中的重点信息仍可进口播和字幕。
2. **评估并按需收集视频素材**：先依据静图分拣结果判断是否需要外部动态画面。它只能承担一个明确任务：建立作品世界观、在角色/设定转换时提供承接，或在连续静态画面后重置节奏；若没有能完成该任务的官方镜头，或它会遮蔽商品细节，就不使用。相关动漫、游戏的官方 OP / ED / Trailer 可从 **YouTube 或 Bilibili** 下载，两个来源平级：YouTube 用 `yt-dlp` 检索并下载视频；Bilibili 先用 `python helpers/bilibili_src.py search "<关键词>" --n 5` 找到 BV 号，再运行 `python helpers/bilibili_src.py check-watermark <BVid>`，未命中水印后必须用 `python helpers/bilibili_src.py download <BVid> --video-out <输出路径>` 下载**视频画面**（需要时加 `--cookies-from-browser <browser>`），而非只下载音频。仅当素材来自 Bilibili 时需要该水印检查；YouTube/其他平台来源的视频无需水印检测。若选择视频，记录其来源、源时间码、计划插入的口播语义点；成片输出时间窗等第 6 步转写后再填，不为凑数量下载或插入。
3. **检索设定**：在 <https://zh.moegirl.org.cn/> 查找产品相关动漫设定与梗，供文案使用。
4. **撰写文案**：按 §文案规范 起草口播文案。上镜镜头对应保留窗口；密字图里抽出的重点写进口播（字幕随口播），画面改用其他上镜素材。判定为弃用的条目两端都不进。
5. **确认方案**：把文案 + 素材搭配展示给用户，确认后再制作（文案是创作性产物，先确认避免返工）。必须附上静图分拣表（上镜 / 只取信息 / 弃用，含理由）；上镜的长图写出 `--region`。搭配只钉「哪句对哪张图 / 哪一窗」，不要把估出来的秒数当成最终镜头时长。若选择了动态视频，标明它服务的口播语义点；输出时间窗等 TTS 转写后再填。若未选择，说明商品图如何独立完成节奏。不能只列 BGM 或下载链接。
6. **TTS 配音（画面之前）**：按 §Voiceover / TTS 生成**整段**口播，不要按句多次合成。立刻 `python helpers/transcribe.py <口播音频> --edit-dir <edit> --provider paraformer`。用这份词级转写，把确认方案里的每一句口播映射到时间窗：镜头 `i` 从该句第一个字的 `start` 起，到下一句第一个字的 `start` 止（最后一句到音频结尾）。句间停顿并入当前镜头，使各镜 `--duration` 之和等于口播 `ffprobe` 时长。禁止用手估秒数渲画面。后续字幕复用这份转写缓存，音频未改不得重跑。
7. **合成视频**：按上一步的时间窗渲染画面（`stable_motion.py --duration`、OP/ED 裁切都用该窗）。动态视频仅在其计划的语义点实际进入时间轴，不得作为与口播无关的固定装饰。商品静图与穿插视频之间必须用 `helpers/transitions.py` 做画面转场，禁止 `-c copy` 硬切拼接。转场默认 `--keep-duration`，画面总长必须仍等于口播时长。
8. **检索并下载 BGM**：按 §混音规范 从 **YouTube 或 Bilibili** 找到与产品/作品相关的现成 OST 或 BGM 并下载音频。禁止用 AI 或本地合成生成 BGM。
9. **混音**：对无字幕的视觉成片运行 `python helpers/mix_ad_audio.py <visual.mp4> <narration.mp3> <bgm.mp3> -o <mixed.mp4>`。该 helper 固定执行人声 -13 LUFS、BGM -27 LUFS、BGM 首尾淡化、无自动闪避与防削波；不得再对 `mixed.mp4` 做整轨 loudnorm。混音长度跟画面走，故画面必须先对齐口播，否则人声会被裁切。
10. **烧录字幕**：最后执行，按 §字幕规范。字幕必须烧录到 `mixed.mp4` 上；不得先烧字幕再混音，也不得在烧录后用 `render.py` 的默认整轨 loudnorm 覆盖分轨响度。
11. **自检交付**：检查字幕在最上层、无削波、无爆音、图片与文案匹配；`ffprobe` 对照画面与口播时长（允许转场取整误差，不得差出一整句）。若使用了动态视频，确认每个计划的语义点确实出现对应画面，而不是 BGM 音频或静态封面替代，并抽查首帧、中帧与尾帧。按 §对外文本禁词 检查口播、字幕、标题、简介、封面文字和标签。最终交付是一个不可拆分的三件套：`final.mp4`、按 §B站标题交付规范生成的 **1 个** 标题、以及按 `skills/bili-cover/SKILL.md` 生成的 **1 张** 封面和完整提示词；任何一项缺失均不得宣告任务完成。

### 静图分拣（硬性）

长图会出现在很多素材里（商品详情、规格分栏、活动海报、KV 等）。先看画面适不适合上镜，再看文字里有没有口播需要的重点。下面的切窗流程对所有长图通用；**哪一类算镜头、哪一类只进口播**，按素材类型用后面的题材约束，不要拿某一次任务的栏目名去套所有图。

#### 长图提取关键信息

目标是找出**能当镜头的栏目**：一段栏目标题，加上它解释的那块画面（产品图、参数卡、卖点图等）。不是把长图切成等高条。禁止用 16:9 视窗等分、颜色空隙、OCR 禁切线自动切片——那些会切断标题与画面，或把密字表切成假镜头。

1. **出总览**：`python helpers/inventory_stills.py "<素材文件夹>" --overview-dir "<videos_dir>/edit/verify/overview"`。`tall: true` 的图写出 `{stem}_overview.jpg`（瘦长缩略，每 200px 标原图 y）。3:4 KV、方图、横图不画总览，直接看原图。
2. **整张分拣**：打开每张原图；长图对照总览看栏。禁止只凭文件名决定去留。先定整张是上镜 / 只取信息 / 弃用，再决定要不要往下裁窗。
3. **只对上镜长图定窗**：在总览上按栏目估 `y0–y1`。一窗 = 一个信息单元（标题 + 该栏的完整画面），整宽只裁上下。不要为了凑 16:9 去切。总览估 y 会有误差，**宁可多带一点相邻栏目，也不要把本栏切残**。套装、对比、多件展示要把这一栏里的主体都框进去，不要为了画面干净而裁短。
4. **裁窗并看图补全**：`python helpers/inventory_stills.py --crop --folder "<素材文件夹>" --out-dir "<videos_dir>/edit/verify/stills" --window <name>,<source>,<y0>,<y1>`（可重复 `--window`；默认上下各扩 80px）。必须打开每张裁图：本栏主体（图、关键数字、名称）被切掉就**加大窗口再裁**。边上带进下一栏可以留着，禁止为了「收干净」往里收。JSON 里的 `region` 给 `stable_motion.py --region`。
5. 读到的标题可用 `python helpers/inventory_stills.py --suggest-role "<可见标题>"` 做核对。这是标题用词提示，不是终裁；商品详情以看图为准。
6. 写入 `<videos_dir>/edit/stills_inventory.md` 后再写文案。表格至少包含：文件、判定、可见内容、用法（上镜写裁图路径和 `--region`，或「不进画面 + 口播要点」，或「两端都不用」）。

| 判定 | 何时 | 处理 |
|------|------|------|
| 上镜 | 画面清楚、好看，观众看得清 | 主视觉用 `--mode push`。长图按栏/标题语义切窗，一句口播对一窗 |
| 只取信息 | 文字过密、不适合当镜头，但里面有口播需要的重点 | **图不上镜**。把重点写进口播，字幕跟口播走；该句画面用其他上镜素材顶上 |
| 弃用 | 没有可讲重点，或与主题无关 | 不进画面、不入口播、不进封面 |

密字图默认按「只取信息」或「弃用」处理，不要为了保留字而把整张密字图滚进成片。有可讲画面时才上镜。口播时长由用户提示词决定，**不要为了滚完整张长图而拉长 TTS**。先 `--probe` 再渲染。

**题材约束（在通用流程上收紧，不另走一套切法）**

- **普通商品详情**（手办参数、食品配料、规格表、使用说明等）：上镜优先外观、场景、卖点插图，以及字少、图大的规格块。配料表、营养成分、密集参数、注意事项小字默认「只取信息」——数字可以进口播，不要当镜头硬滚。一窗对应一个卖点或一块仍看得清的规格图，不要把整页说明书裁成一条。
- **漫展 / 展览活动长图**（海报、场贩、票种、嘉宾日程等）：上镜优先主视觉 KV、嘉宾/舞台海报、场贩商品卡、票价、礼包套装；礼包要把每一件实物和价格都框进同一窗。当日版权/IP 密表「只取信息」。购票须知、退票换票、交通路线、展商格子名录默认不上镜（无画面价值则「弃用」）。

### 图片素材规范

- **选图优先级**：商品本体图为主，尽量多使用主图；少量仍清楚可读的详情图。信息长图能看清再切窗上镜；文字过密则不上镜。
- **文字过密**：默认不上镜。先判断里面有没有口播需要的重点——有则写进口播和字幕，画面换别的图；没有可讲重点才整张丢掉。不要把密字图滚进成片充数。
- **画面适配**（每张图进入 1920×1080 画布时）：
  - 图片高度不足画布高度 → **等比例放大**，占满画面高度（允许裁切左右）。
  - 图片比 16:9 更高：3:4 / 方图主视觉用 `--mode push`；详情/信息长图用 `--mode scroll`。滚动是 **固定 0.18 屏/秒**（约 5.5 秒一屏），与图有多长、镜头有几秒无关：只改变滚多久或裁多长，禁止为某张图改 `--max-viewports-per-sec`。不要用 duration 去「拉满」或「刷完整张」。镜头比内容长就停在末帧；镜头比内容短就从 `--anchor`（默认顶）裁一段可读窗口。口播对中段/底部时用 `--region 0.35,0.7` 或 `--anchor center|bottom`。先 `--probe` 看 JSON 再渲染。
- 文案与上镜画面尽量匹配：讲到哪张上镜的图、哪一段长图，就展示哪一段。只取信息、不上镜的句子，用其他上镜素材垫画面。
- **镜头时长**：`--duration` 必须用 §执行流程 第 6 步从口播转写算出的时间窗，禁止手估或按图有多长反推。滚动速度仍固定 0.18 屏/秒，不因某句变长而加速刷完整张。

#### 动态图片分镜稳定性

- 商品主图可采用缓慢中心推镜，详情长图可采用缓慢纵向滚动；背景、清晰前景和暗角先各生成一次静态资产，再由同一条视频滤镜链驱动运动。不得为每一帧重新生成背景或前景位图。
- **运动参数必须连续**：推镜缩放以输出帧编号计算同一条连续曲线，并在滤镜中以浮点表达式执行。长图滚动必须对时间 `t` **匀速**（固定像素/秒），滚完用 `min()` 停在末帧；禁止用 `n/(frames-1)` 把整段行程摊满镜头时长，那会让短窗口几乎不动、长窗口被拉成不同速度。禁止在逐帧循环中对缩放后的宽高、居中坐标或裁切坐标使用 `int()` / `//` 后再渲染；这会产生“停一帧、跳一像素”的抖动。
- 缩放与滚动不能分别用不同的取整坐标系计算。长图滚动的可用纵向范围必须基于**当前帧**缩放后的图像高度计算；否则缩放变化会使裁切位置不连续。
- 推荐用 FFmpeg `zoompan` 的 `on`（输出帧编号）驱动中心推镜，并让透明前景在模糊背景上合成；该方案避免 Python/PIL 按帧缩放带来的整数舍入抖动，也避免大量 PNG 序列写入造成的性能问题。
- **统一实现**：商品静态图必须优先使用 `python helpers/stable_motion.py <图片> -o <片段.mp4> --mode push --duration <秒>`；详情/信息长图使用 `--mode scroll`（固定 0.18 屏/秒；过长则裁窗，滚完停住，不要手写更快的 duration 去追完整张）。该 helper 先只生成一次高分辨率合成画布，再由 `zoompan` 的 `on` 驱动中心推镜；滚动模式只在开始时缩放前景，再用 `t` 的匀速表达式移动它。它**强制固定以 2× 输出画布渲染**并 Lanczos 下采样到交付分辨率，且不接受覆盖该值的参数，避免缓慢运动在 1080p 整数裁切时产生 0/1 像素台阶。禁止退回到逐帧 `scale` 加 `overlay` 的组合。
- **调用示例**：`python helpers/stable_motion.py 主图.jpg -o edit/clips_visual/main.mp4 --mode push --duration 6`；`python helpers/stable_motion.py 商详.jpg -o edit/clips_visual/detail.mp4 --mode scroll --duration 7`；长图对顶部：`... --mode scroll --duration 7 --anchor top`；对中段：`--region 0.28,0.62`。`--probe` 只打印裁窗 JSON。
- **自检**：动态图片分镜生成后，逐段以 1× 速度查看首段、中段、末段，并抽取连续 10 帧检查运动方向只前进、不回跳；发现抖动时必须修正运动表达式后重渲染，不得改用静态图规避问题。

### 视频素材规范

- **来源优先级**：视频素材可来自 **YouTube** 或 **Bilibili** 两个平级来源，均**仅限相关动漫、游戏视频的 OP / ED / Trailer 类型**；**明确排除玩家二创、同人剪辑、游戏实况、reaction 等任何其他来源类型**。两者择一或混用，按素材质量与可用性决定。
  - **Bilibili 素材获取**（`helpers/bilibili_src.py`）：
    - 检索：`python helpers/bilibili_src.py search "<关键词>" --n 5`（返回 bvid / 标题 / UP主 / 时长）。
    - 下载前必先做水印检测（仅 B 站视频）：`python helpers/bilibili_src.py check-watermark <BVid>`，命中即弃用该视频；检测查四角边缘细节（B 站水印常见于右上角），属启发式，重要片段建议肉眼抽检。YouTube/其他平台视频免检。
    - 取素材：`python helpers/bilibili_src.py download <BVid> --video-out ...` 取片段、`--audio-out` 取 BGM（音频无视觉水印，不受水印检测限制）。
    - 视频流 Cookie：命令加 `--cookies-from-browser <chrome|firefox|edge|safari|brave>`，yt-dlp 直接读本机已登录 B 站的浏览器 cookie（无需手动导出）；匿名则仅音频可用。
- **叙事优先**：外部动态画面是可选素材，不是配方要求。优先让商品主图、效果图和详情图承担展示；仅在它能为“世界观建立、角色/设定承接、节奏重置”中的至少一项提供商品图做不到的价值时采用。选择镜头时，以自然口播停顿、角色名/设定词落点、或静态图信息展示结束后的呼吸点作为进入和离开位置；镜头停留以观众看清其功能为准，不设固定数量、时长或总占比。若没有自然落点，宁可不插入。
- 若使用片段，它必须是真实编码进成片的动态画面，且与相邻商品图在色彩、方向与情绪上连贯；不得以“已下载”“仅作 BGM”或静态首帧替代，也不得为了满足镜头数量而重复同类画面。
- **转场（硬性）**：商品静图与穿插的 OP/ED/Trailer 之间禁止硬切。默认交叉溶解 `fade` **0.4 秒**。先用 `stable_motion.py` / 裁切得到各片段，再：
  ```bash
  python helpers/transitions.py 静图1.mp4 穿插.mp4 静图2.mp4 -o edit/clips_visual/visual.mp4 --type fade --duration 0.4 --an
  ```
  `--an` 因为后续 `mix_ad_audio.py` 会替换音轨。默认 `--keep-duration`：交接段片尾补上 0.4 秒 handle，成片时长仍等于各镜头之和，口播和 `master.srt` **不要改时间戳**。只有打算按缩短后的画面重做 TTS 时才加 `--no-keep-duration`。同类静图之间可用更短的 `fade:0.25`，或按用户要求硬切（`--joins fade:0.25,cut,fade:0.4`）。走 EDL 时在后一段写 `"transition": {"type": "fade", "duration": 0.4}`，或设 `"default_transition"`。

### 文案规范（口播脚本）

- **体裁**：资讯类"云逛"口播——滚动播放资讯/商品图片，配合口播解说。画面跟上镜素材走；密字图里抽出的重点可以只出现在口播和字幕里。
- **风格**：多放动漫梗，引起 ACG 爱好者共鸣；结合素材文件夹中的效果图介绍产品；结合动漫设定展开（设定信息查 moegirl）。口播覆盖 `stills_inventory.md` 里「上镜」和「只取信息」的内容，不讲「弃用」条目。
- **表达**：必须口语化，只讲这件商品；口播篇幅按用户给出的成片时长写，不自行改成别的长度；**禁止**出现逻辑总结类词语（如"总之""综上所述""最后总结一下"）；**禁止分点列条**。对外用词见 §对外文本禁词。
- **数字**：金额、数量、尺寸、比例等量化信息一律用阿拉伯数字（如「199元」「2.0」「1/7」），禁止写成中文数字（如「一百九十九元」「二点零」）。口语虚词如「一个」「一下」保持汉字。送入 TTS 的文案和烧录字幕都必须保留分数线，禁止把「1/7」改成「17」或「1 7」。

### 视频规格

- 画布：**1920×1080**。
- 背景：**高斯模糊填充**——原图放大铺满并高斯模糊作为背景层，前景叠放适配后的清晰画面。

### 混音规范（人声为主，数值硬性）

| 轨 | 响度目标 | 说明 |
|----|----------|------|
| 口播人声 | **-13 LUFS** | 保持自然清晰的原始响度，不做多余处理 |
| BGM | 低于人声 **20dB**（约 -27 LUFS） | 固定为人声音量的约 **10%**，全程恒定 |

- **BGM 恒定**：不随人声出现、停顿或强弱自动降低；**不使用侧链压缩或自动闪避**（ducking）。
- **淡入淡出**：BGM 仅开头 **0.5 秒**淡入、结尾 **1.1 秒**淡出，避免突兀起止；人声开头 **0.05 秒**淡入。
- **防削波**：最终混音限制峰值（loudnorm / alimiter），避免削波失真。
- **BGM 来源（硬性）**：必须从 **YouTube 或 Bilibili** 检索并下载与产品相关动漫/游戏的现成 OST、OP/ED 音源或官方 BGM。两个来源平级。YouTube 用 `yt-dlp` 搜并抽音频；Bilibili 用 `python helpers/bilibili_src.py search "<作品名 或 风格> OST"` 找到 BV 号后 `download <BVid> --audio-out ...`（音频无视觉水印，无需水印检测）。也可从本次已下载的 YouTube/Bilibili 视频素材中提取音轨，前提是该视频本身来自这两个平台。检索优先用作品名、角色名、官方曲名；`<风格>` 只作辅助关键词。必须记录曲名/来源 URL。
- **禁止自行生成 BGM**：不得用 TTS、Suno、Udio、音乐模型、MIDI、循环素材拼贴或任何本地合成来“做一条 BGM”。找不到相关曲目时换关键词继续搜，不得用生成音乐凑数。
- **执行脚本**：必须使用 `helpers/mix_ad_audio.py` 完成混音。该脚本先分别两遍标准化人声与 BGM，再以 `amix=normalize=0` 固定叠加，避免 FFmpeg 默认归一化把已达标的人声再次降低。

### 字幕规范（中文单行字幕）

样式锁在 `helpers/ad_subtitles.py`，禁止手写或改写 `force_style`。该 helper 会 `ffprobe` 成片宽高，把 `PlayResX/PlayResY` 设成**当前视频的显示分辨率**，再按 `height/1080` 缩放字号、字距、描边和边距。只写 `PlayResY=1080` 会让 libass 用 4:3 的 `PlayResX=1440`，在 1920×1080 上把字横向拉宽，禁止那样烧录。

- **生成脚本（硬性）**：

  ```bash
  python helpers/transcribe.py <最终口播音频> --edit-dir <edit> --provider paraformer
  python helpers/build_tts_subtitles.py <最终送入TTS的文案文件> <最终音频的词级转写JSON> -o <master.srt> --max-chars 24
  python helpers/verify_tts_subtitles.py <最终送入TTS的文案文件> <master.srt> --max-chars 24
  python helpers/ad_subtitles.py <mixed.mp4> <master.srt> -o <final.mp4> --primary-colour <ASS颜色>
  ```

  口播转写在第 6 步已完成；音频未改则直接复用 `transcripts/` 缓存，禁止重跑。广告流程禁止对 TTS 成片使用 `render.py --build-subtitles`，该路径会采用 ASR 文本。`verify_tts_subtitles.py` 失败即禁止烧录（Hard Rule 13）。
- **锁定样式（1080p 基准，按成片高度缩放）**：Hiragino Sans GB W6，`FontSize=72`，`Spacing=1`，`Outline=3`（四周细描边），`Shadow=0`，`WrapStyle=2`，`MarginV=8`，左右 `MarginL/R=64`。烧录时必须同时带上 `PlayResX=<视频宽>` 和 `PlayResY=<视频高>`；720p / 4K 由 helper 自动缩放，不要手填。Linux 或未安装冬青黑体时，只允许把 `FontName` 换成 `Noto Sans SC`。
- **单行（硬性）**：每条字幕必须只有一行。`--max-chars 24` 按语义切分，超长子句由脚本硬切，禁止一条里出现换行。烧录用 `WrapStyle=2`，即使文本偏长也不许折成两行。
- **颜色与对比度**：默认白色 `&H00FFFFFF`。若产品有指定高亮色，用 `--primary-colour` 覆盖，必须仍是高亮度浅色；禁止低亮度或接近画面暗部的颜色。抽查首帧、中段、尾帧确认可读。粉色 `&H00FF8FCF` 只是可选强调色，不是默认字幕色。
- **特效**：只用四周细描边；**不使用**底框、投影阴影、弹跳或花哨特效。
- **烧录顺序**：必须在所有画面、转场和叠加层完成后**最后烧录**，确保始终位于最上层不被遮挡（Hard Rule 1）。
- **文字**：字幕文字必须逐字采用最终送入 TTS 的口播文案，且顺序完全一致。句读标点（。！？；，、）换成空格后，中文汉字之间的多余空格由脚本去掉；分数线 `/`、小数点、百分号、比例冒号等量化符号必须原样保留（「1/7」不得变成「1 7」）。字距只由 `Spacing=1` 控制。不得根据 ASR 文本改写、纠错、概括、删减或补写字幕。
- 每条字幕时长与文案自然停顿对齐，不手估时间。ASR/强制对齐**只用于取得最终音频的词级时间戳**。

### B站投稿简介规范

投稿简介只写给观众的产品与活动信息。用词见 §对外文本禁词；另不得写入内部制作过程、工具参数、文件路径、凭证或调试日志。

- 除非用户明确要求，简介不放素材来源 URL；需要记录授权或来源时，写入 `<素材目录>/edit/project.md`。用户明确要求外链时，链接必须独占一行，并在发布后核对平台没有扩大自动链接范围。
- 使用 API 或 CLI 发送简介时，必须传递真实换行符。禁止在单引号参数中写字面量 `\\n`、`\\r\\n` 或其他转义文本。
- 默认建议三行：一句产品定位、一句可见卖点、最后一行活动或行动信息。用户提供且要求保留的活动文案必须照录；不得自行添加营销口号。
- 发送前校验：简介符合 §对外文本禁词，且不得包含字面量反斜杠转义、文件系统路径、凭证标识，或非用户要求的 URL。
- 每次新投稿或编辑后，必须运行 `biliup show <BV>` 回读 `archive.desc`，精确核对文本、真实换行与链接范围。回读不一致时，停止商品挂载、评论等后续发布动作；修正简介并再次回读通过后才能继续。

### B站标题交付规范

最终视频交付时，必须同时提供 **1 个** 可直接发布的 B站标题；它与封面、成片同为强制交付物。标题生成前确认产品全名与常用圈内昵称；产品名称可写为“全名（圈内昵称）”，但不得编造昵称、场景或上手体验。用词见 §对外文本禁词。

只写这件商品：品类、外观、IP/角色、材质或一个真实卖点。

- 标题开头必须是“具体卖点／产品特质 + 强烈感受”的完整短句，再用感叹号衔接产品名。优先让卖点本身成为钩子，例如“桌面萌力超标！”“压迫感炸场！”“反差萌拉满！”。禁止使用“救命啊”“谁顶得住”“我破防了”等空泛语气词作为开头。
- 必须露出产品具体名或圈内昵称；只使用本商品自带的 IP、角色或圈层称呼。
- 用反差或悬念时，必须来自这件商品的外观或用途，不得使用“最”“第一”“100%”等绝对化表述。
- 文风应像真人发布：简洁、口语化、信息具体；不堆砌标签，不使用营销腔和标题党式承诺

**标题输出格式：** `B站标题：<单行标题>`。除这 1 个最终标题外，不提供备选列表。交付前自检：删掉商品名、卖点和 IP 后若仍能套到任意商品上，必须重写。

### B站封面交付规范

最终视频交付时，必须同时输出 **1 张** B站封面图和 **1 段本次实际使用的完整封面提示词**；封面是强制交付物。完整规范、提示词模板、后端顺序（`native` → `gcp-gemini` → `ark-seedream`）和脚本调用见 **`skills/bili-cover/SKILL.md`**。写到 `<videos_dir>/edit/cover.jpg`。画面上的字仍受 §对外文本禁词约束；发给图像模型的生成提示词可以使用「封面」。

### 示例

```text
使用 skill: video-use 任务：制作一个关于「明日香」手办的宣传广告视频，时长 <时长>。
素材在 <素材文件夹> 中。参考声音用 <参考音频.mp3>，
BGM 风格：电音。
```
