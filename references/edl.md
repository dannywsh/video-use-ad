# EDL and transition timing

使用 EDL 或核对转场时间轴时读取。字幕最终音频对齐要求见主入口 Hard Rule 13；广告字幕构建与烧录使用 [广告字幕流程](promo-common.md#字幕规范中文单行字幕)。

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
