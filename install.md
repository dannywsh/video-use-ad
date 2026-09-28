---
name: video-use-install
description: Install video-use into the current agent (Claude Code, Codex, Hermes, Openclaw, etc.) and wire up ffmpeg + API keys so the user can start editing immediately.
---

# video-use install

Use this file only for first-time install or reconnect. For daily editing, read [SKILL.md](SKILL.md), then only the selected workflow and relevant references. Resolve helpers from the main skill root; do not infer script paths from a reference directory.

## What you're doing

You're setting up a conversation-driven video editor for the user. After install, the user drops raw footage into any folder, runs their agent (`claude`, `codex`, etc.) there, and says "edit these into a launch video." You do the rest by reading `SKILL.md`.

Three things must exist on this machine:

1. This skill installed from **`dannywsh/video-use-ad`** (not upstream `browser-use/video-use`). The root `references/` and nested `skills/bili-cover/` with its references ship with it; preserve these directories together with `helpers/`.
2. `ffmpeg` on `$PATH` (plus optional `yt-dlp` for online sources).
3. Credentials in the user-config `.env` (not the skill install folder): `~/.config/video-use/.env` on all platforms (Windows: `%USERPROFILE%\.config\video-use\.env`). `ELEVENLABS_API_KEY` for Scribe (default ASR), and/or `PARAFORMER_API_TOKEN` for Chinese Paraformer ASR. For default TTS add `FISH_API_KEY`. Cover backends optionally need `GCP_GEMINI_IMAGE_API_KEY` and `ARK_SEEDREAM_API_KEY`. MiMo is optional and only if the user asks for it.

And one thing must be true about the current agent:

4. It can discover `SKILL.md` — either via a global skills directory (`~/.agents/skills/`, `~/.claude/skills/`, `~/.codex/skills/`) or via a `CLAUDE.md` / system-prompt import.

## Install prompt contract

- Do everything yourself. Only ask the user for things you cannot generate — API keys, and confirmation before `brew install`.
- **Preferred install is `npx skills add dannywsh/video-use-ad -g -y`.** Do not clone `browser-use/video-use`. Do not invent a hard-coded `~/Developer/video-use` path.
- After the CLI install, skill root is usually `$HOME/.agents/skills/video-use`. Resolve helpers from that directory (or the symlink under `~/.claude/skills/video-use`).
- The skill references helpers by bare name (`transcribe.py`, `render.py`). That works because SKILL.md and `helpers/` ship together — keep them as siblings when you register the skill.
- After install, verify by running one real command against one real file. Don't declare success on file-existence checks alone.

## Steps

### 1. Install the skill

```bash
npx skills add dannywsh/video-use-ad -g -y
npx skills add dannywsh/biliup -g -y
npx skills update -g -y
```

Then:

```bash
SKILL_ROOT="${HOME}/.agents/skills/video-use"
test -d "$SKILL_ROOT" || SKILL_ROOT="${HOME}/.claude/skills/video-use"
cd "$SKILL_ROOT"
USER_ENV="${VIDEO_USE_ENV:-${XDG_CONFIG_HOME:-$HOME/.config}/video-use/.env}"
mkdir -p "$(dirname "$USER_ENV")"
python "$SKILL_ROOT/helpers/env_file.py" --migrate
```

If the Skills CLI is unavailable, clone **this** repo and symlink the whole directory (not just `SKILL.md`):

```bash
git clone https://github.com/dannywsh/video-use-ad "$SKILL_ROOT"
mkdir -p ~/.claude/skills
ln -sfn "$SKILL_ROOT" ~/.claude/skills/video-use
```

If a copy already exists, `npx skills update -g -y` (preferred) or `git -C "$SKILL_ROOT" pull --ff-only` when it is a git clone.

### 2. Install Python deps

```bash
command -v uv >/dev/null && uv sync || pip install -e .
```

`pyproject.toml` lists `requests`, `librosa`, `matplotlib`, `pillow`, `numpy`. No console scripts — helpers are invoked directly as `python "$SKILL_ROOT/helpers/<name>.py"`.

### 3. Install ffmpeg (+ optional yt-dlp)

`ffmpeg` and `ffprobe` are hard requirements. `yt-dlp` is only needed if the user wants to pull sources from URLs. Animation engines such as HyperFrames, Remotion, and Manim are installed lazily the first time a project actually needs them.

```bash
# macOS
command -v ffmpeg >/dev/null || brew install ffmpeg
command -v yt-dlp >/dev/null || brew install yt-dlp     # optional

# Debian / Ubuntu
# sudo apt-get update && sudo apt-get install -y ffmpeg
# pip install yt-dlp

# Arch
# sudo pacman -S ffmpeg yt-dlp
```

If `brew` / `apt` / `pacman` requires a sudo prompt, tell the user the exact command and wait. Do not invent a password.

### 4. Register the skill with the current agent

`npx skills add … -g` already registers globally for discovered agents. If you had to clone manually, symlink the **whole** skill-root directory:

- **Claude Code** (`~/.claude/` present): `ln -sfn "$SKILL_ROOT" ~/.claude/skills/video-use`
- **Codex**: `ln -sfn "$SKILL_ROOT" "${CODEX_HOME:-$HOME/.codex}/skills/video-use"`
- **Hermes / Openclaw / another agent**: symlink `$SKILL_ROOT` into that agent's skills directory as `video-use`, or import `$SKILL_ROOT/SKILL.md` in its system prompt.

If you can't tell which agent you're in, ask once.

### 5. API keys

Resolve `USER_ENV` with `python "$SKILL_ROOT/helpers/env_file.py" --user-path`; it is normally `~/.config/video-use/.env` (Windows `%USERPROFILE%\.config\video-use\.env`), with `VIDEO_USE_ENV` / `XDG_CONFIG_HOME` overrides. Create the parent directory if needed. Write supplied keys there, never into the skill directory or footage directory. Never print a key, its prefix or the contents of `.env`; never commit `.env` or clobber unrelated entries.

Transcription uses ElevenLabs Scribe by default, or Paraformer for Chinese ASR. Default TTS is Fish Audio. Product image backends optionally need Gemini or Seedream credentials; official poster mode does not. MiMo is opt-in only.

#### Credential discovery before asking the user

Use the existing `env_file.load_env_value` parser. Lookup order remains user-config `.env` → leftover skill-root `.env` → current-directory `.env` → process environment. Whitespace around names/values and quoted values are accepted; empty or whitespace-only values are missing. Do not use a strict `^KEY=` search or read tokens with `sed`.

For example, check only the names needed for the selected task. This example reports presence, not values, and disables migration during the read-only check (the initial migration is in the installation step):

```bash
python - "$SKILL_ROOT" ELEVENLABS_API_KEY FISH_API_KEY <<'PYTHON'
import sys
from pathlib import Path

# 输入技能根目录和凭证名；使用已有解析器，仅输出是否配置，不输出凭证内容。
sys.path.insert(0, str(Path(sys.argv[1]) / "helpers"))
from env_file import load_env_value

for name in sys.argv[2:]:
    status = "configured" if load_env_value(name, migrate=False) else "missing"
    print(f"{name}: {status}")
PYTHON
```

Only if the relevant value is missing, ask for it and update that entry in `USER_ENV`. Use the same parser semantics to locate the entry: strip whitespace from the name before comparing, replace an empty entry instead of appending a duplicate, preserve unrelated lines, and write the supplied value without logging it. On Unix restrict the file to owner read/write with `chmod 600 "$USER_ENV"`.

#### ElevenLabs (default ASR + ElevenLabs TTS)

Check `ELEVENLABS_API_KEY` with the parser above. If missing, ask once for a key from https://elevenlabs.io/app/settings/api-keys and save it in `USER_ENV`.

Use the same resolved value for the existing quota-free user check; do not extract it using a strict shell pattern or display it:

```bash
python - "$SKILL_ROOT" <<'PYTHON'
import sys
from pathlib import Path
import requests

# 输入技能根目录；从已有解析器取得凭证，只输出用户接口的 HTTP 状态码。
sys.path.insert(0, str(Path(sys.argv[1]) / "helpers"))
from env_file import load_env_value

key = load_env_value("ELEVENLABS_API_KEY", migrate=False)
if not key:
    raise SystemExit("ELEVENLABS_API_KEY is missing")
response = requests.get(
    "https://api.elevenlabs.io/v1/user",
    headers={"xi-api-key": key},
    timeout=30,
)
print(response.status_code)
PYTHON
```

`200` means the key works. `401` means ask once more and stop. If Chinese TTS timing is the only ASR need and Paraformer is already configured, Scribe can be skipped for now.

#### Paraformer (optional — Chinese ASR)

Check `PARAFORMER_API_TOKEN` with the same parser; ask only if it is required and missing, then update that entry in `USER_ENV`. Optional `PARAFORMER_API_URL` overrides the default `https://paraformer.ow2shit.top`; retain an existing override.

The original read-only health check is:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://paraformer.ow2shit.top/health
```

#### Fish Audio (default TTS)

Check `FISH_API_KEY` with the same parser and update the corresponding entry only if missing. Default Fish Audio voice clones stay private.

#### Cover backends (optional until a product cover is required)

Check `GCP_GEMINI_IMAGE_API_KEY` / `ARK_SEEDREAM_API_KEY` only for a selected product image backend. Ask only after the same lookup finds no non-empty value, and update the relevant entry. Official poster mode needs neither image key. Model / endpoint overrides remain in `.env.example`.

#### MiMo (opt-in only)

Check and ask for `MIMO_API_KEY` only if the user explicitly wants MiMo; use the same parser and persistence rules.

### 6. Verify end-to-end

```bash
python "$SKILL_ROOT/helpers/timeline_view.py" --help >/dev/null && echo "helpers OK"
python "$SKILL_ROOT/helpers/tts.py" --help >/dev/null && echo "tts OK"
test -f "$SKILL_ROOT/skills/bili-cover/SKILL.md" && echo "bili-cover OK"
ffprobe -version | head -1
```

Full transcription test is optional at install time — it burns Scribe credits.

### 7. Hand off

Tell the user, in one short message:

- Skill root (`$SKILL_ROOT`, usually `~/.agents/skills/video-use`).
- `cd` into the footage folder and start the agent there.
- A good first message: *"edit these into a launch video"* or *"inventory these takes and propose a strategy."*
- Daily work starts at [SKILL.md](SKILL.md): ordinary edits read [general-edit.md](references/general-edit.md); promos read [promo-common.md](references/promo-common.md) and the applicable [product](references/product.md) or [event](references/convention.md) reference. Convention, concert and game-expo titles follow the [event title instructions](references/convention.md#活动视频标题): filter fact-supported angles, then let the model choose one suitable angle directly without a random-selection script, and deliver one title. TTS, animations, EDL, covers and publishing are loaded only when needed. Outputs and generated editing projects land in `<videos_dir>/edit/`. Before production, create `<videos_dir>/edit/tmp/` and set `TMPDIR`, `TMP`, `TEMP` to that absolute path for every execution session and animation agent. This includes animation source projects, configs, local dependencies, caches, downloaded media, previews, and final files; keep the footage folder root and the skill repository free of session-generated files.

## Keeping the skill current

`npx skills update` deletes and recreates the skill directory. Keys are not stored there.

```bash
SKILL_ROOT="${HOME}/.agents/skills/video-use"
test -d "$SKILL_ROOT" || SKILL_ROOT="${HOME}/.claude/skills/video-use"
python "$SKILL_ROOT/helpers/env_file.py" --migrate
npx skills update -g -y
```

If `pyproject.toml` changed deps, re-run `uv sync` / `pip install -e .` in `$SKILL_ROOT` after updating. A git clone can `git pull --ff-only` instead of the CLI (that path does not wipe `.env`).

## Cold-start reminders

- Symlink the **whole directory**, not just `SKILL.md`.
- If the user-config `.env` exists but the key is empty, treat it as missing.
- `ffmpeg` ≥ 4.x is enough. `yt-dlp` is optional.
- Node.js 18+ is needed for `ark-seedream` covers; HyperFrames currently wants Node 22+.
- HyperFrames, Remotion, and Manim are optional; install per animation slot, not at setup.
- Never run transcription as part of install verification unless the user asks.
- Catalog of this author's skills: https://github.com/dannywsh/skills
