# Voiceover / TTS

需要配音或声音克隆时读取；广告任务继续使用 [广告流程](promo-common.md) 的整段 TTS、最终音频对齐及固定混音要求，不使用下文普通剪辑混音示例替代它们。

## Voiceover / TTS (when requested)

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
