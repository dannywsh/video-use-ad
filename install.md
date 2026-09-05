---
name: video-use-install
description: Install video-use into the current agent (Claude Code, Codex, Hermes, Openclaw, etc.) and wire up ffmpeg + API keys so the user can start editing immediately.
---

# video-use install

Use this file only for first-time install or reconnect. For daily editing, read `SKILL.md`. Always read `helpers/` — that's where the scripts live.

## What you're doing

You're setting up a conversation-driven video editor for the user. After install, the user drops raw footage into any folder, runs their agent (`claude`, `codex`, etc.) there, and says "edit these into a launch video." You do the rest by reading `SKILL.md`.

Three things must exist on this machine:

1. This skill installed from **`dannywsh/video-use-ad`** (not upstream `browser-use/video-use`). Nested `skills/bili-cover/` ships with it.
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
python helpers/env_file.py --migrate
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

`pyproject.toml` lists `requests`, `librosa`, `matplotlib`, `pillow`, `numpy`. No console scripts — helpers are invoked directly as `python helpers/<name>.py`.

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

`USER_ENV` is `~/.config/video-use/.env` on all platforms, including Windows `%USERPROFILE%\.config\video-use\.env` (`python helpers/env_file.py --user-path` prints it). Create the parent dir if needed. Write keys to `"$USER_ENV"`. Never print a key. Never commit `.env`. Do not clobber an existing `.env`. Do not write keys into `$SKILL_ROOT` — `npx skills update` deletes that directory.

Transcription has two providers. Scribe (ElevenLabs) is the default. Paraformer is optional for Chinese TTS subtitle timing. Default TTS is Fish Audio. Cover generation uses `skills/bili-cover/` (`GCP_GEMINI_IMAGE_API_KEY`, `ARK_SEEDREAM_API_KEY`). MiMo is opt-in only.

#### ElevenLabs (default ASR + ElevenLabs TTS)

1. Check existing state and stop at the first hit:

    ```bash
    [ -n "$ELEVENLABS_API_KEY" ] && echo "env"
    grep -q '^ELEVENLABS_API_KEY=..' "$USER_ENV" 2>/dev/null && echo "dotenv"
    ```

2. If neither is set, ask the user exactly once for a key from https://elevenlabs.io/app/settings/api-keys and append it:

    ```bash
    touch "$USER_ENV"
    grep -q '^ELEVENLABS_API_KEY=' "$USER_ENV" \
      || printf 'ELEVENLABS_API_KEY=%s\n' "$KEY" >> "$USER_ENV"
    chmod 600 "$USER_ENV" 2>/dev/null || true
    ```

3. Sanity check with a cheap, quota-free call:

    ```bash
    curl -s -o /dev/null -w '%{http_code}\n' \
      -H "xi-api-key: $(sed -n 's/^ELEVENLABS_API_KEY=//p' "$USER_ENV")" \
      https://api.elevenlabs.io/v1/user
    ```

    `200` means the key works. `401` means ask once more and stop.

If the user only needs Chinese TTS subtitle timing and already has a Paraformer token, Scribe can be skipped for now.

#### Paraformer (optional — Chinese ASR)

Hosted FunASR Paraformer-large. Default URL is `https://paraformer.ow2shit.top`.

    ```bash
    [ -n "$PARAFORMER_API_TOKEN" ] && echo "env"
    grep -q '^PARAFORMER_API_TOKEN=..' "$USER_ENV" 2>/dev/null && echo "dotenv"
    touch "$USER_ENV"
    grep -q '^PARAFORMER_API_TOKEN=' "$USER_ENV" \
      || printf 'PARAFORMER_API_TOKEN=%s\n' "$PARAFORMER_TOKEN" >> "$USER_ENV"
    grep -q '^PARAFORMER_API_URL=' "$USER_ENV" \
      || printf 'PARAFORMER_API_URL=%s\n' 'https://paraformer.ow2shit.top' >> "$USER_ENV"
    chmod 600 "$USER_ENV" 2>/dev/null || true
    curl -s -o /dev/null -w '%{http_code}\n' https://paraformer.ow2shit.top/health
    ```

#### Fish Audio (default TTS)

    ```bash
    grep -q '^FISH_API_KEY=' "$USER_ENV" \
      || printf 'FISH_API_KEY=%s\n' "$FISH_KEY" >> "$USER_ENV"
    chmod 600 "$USER_ENV" 2>/dev/null || true
    ```

#### Cover backends (optional until a Bilibili cover is required)

    ```bash
    grep -q '^GCP_GEMINI_IMAGE_API_KEY=' "$USER_ENV" \
      || printf 'GCP_GEMINI_IMAGE_API_KEY=%s\n' "$GCP_GEMINI_IMAGE_API_KEY" >> "$USER_ENV"
    grep -q '^ARK_SEEDREAM_API_KEY=' "$USER_ENV" \
      || printf 'ARK_SEEDREAM_API_KEY=%s\n' "$ARK_SEEDREAM_API_KEY" >> "$USER_ENV"
    ```

Empty values count as missing. Model / endpoint overrides are in `.env.example`.

#### MiMo (opt-in only)

Ask for `MIMO_API_KEY` only if the user explicitly wants MiMo.

    ```bash
    grep -q '^MIMO_API_KEY=' "$USER_ENV" \
      || printf 'MIMO_API_KEY=%s\n' "$MIMO_KEY" >> "$USER_ENV"
    ```

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
- Outputs land in `<videos_dir>/edit/`.

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
