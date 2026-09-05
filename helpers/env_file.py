"""Load and persist API keys outside the skill install directory.

`npx skills update` deletes the installed skill folder and recreates it, so a
skill-root `.env` is wiped. Keys live in the user config dir instead.

Lookup order:
    $VIDEO_USE_ENV if set
    $XDG_CONFIG_HOME/video-use/.env
    ~/.config/video-use/.env  (all platforms; Windows: %USERPROFILE%\\.config\\video-use\\.env)
    <skill_root>/.env  (legacy; copied to the user path when missing)
    <cwd>/.env
    process environment
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

SKILL_NAME = "video-use"


def skill_root_dir() -> Path:
    """Directory that contains helpers/ and SKILL.md."""
    return Path(__file__).resolve().parent.parent


def user_env_path() -> Path:
    """Stable dotenv path that survives `npx skills update`."""
    explicit = os.environ.get("VIDEO_USE_ENV", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / SKILL_NAME / ".env"
    return Path.home() / ".config" / SKILL_NAME / ".env"


def env_files(*, skill_root: Path | None = None) -> list[Path]:
    """Candidate dotenv files, first existing key wins."""
    root = skill_root if skill_root is not None else skill_root_dir()
    ordered = [user_env_path(), root / ".env", Path.cwd() / ".env"]
    seen: set[str] = set()
    unique: list[Path] = []
    for path in ordered:
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _restrict_private(path: Path) -> None:
    """Best-effort owner-only mode. No-op if the OS cannot set Unix bits."""
    try:
        path.chmod(0o600)
    except OSError:
        pass


def migrate_skill_root_env(*, skill_root: Path | None = None) -> Path | None:
    """Copy a leftover skill-root .env into the user config path once.

    Returns the destination when a copy happened, otherwise None.
    Does not overwrite an existing user file.
    """
    root = skill_root if skill_root is not None else skill_root_dir()
    source = root / ".env"
    dest = user_env_path()
    if not source.is_file() or dest.is_file():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    _restrict_private(dest)
    return dest


def load_env_value(
    name: str,
    default: str = "",
    *,
    skill_root: Path | None = None,
    migrate: bool = True,
) -> str:
    """Read one dotenv/process value. Empty file values count as missing."""
    if migrate:
        migrate_skill_root_env(skill_root=skill_root)
    for candidate in env_files(skill_root=skill_root):
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() != name:
                continue
            stripped = value.strip().strip('"').strip("'")
            if stripped:
                return stripped
    return os.environ.get(name, default).strip() or default


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show or migrate the video-use dotenv that survives skill updates.",
    )
    parser.add_argument(
        "--user-path",
        action="store_true",
        help="Print the user config .env path and exit",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Copy skill-root .env to the user path if the user file is missing",
    )
    args = parser.parse_args()
    if args.user_path:
        print(user_env_path())
        return
    if args.migrate:
        dest = migrate_skill_root_env()
        if dest is not None:
            print(f"migrated {dest}")
        else:
            print(f"ok {user_env_path()}")
        return
    parser.error("use --user-path or --migrate")


if __name__ == "__main__":
    main()
