import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "helpers"))
import env_file as E  # noqa: E402


class EnvFileTests(unittest.TestCase):
    def setUp(self):
        self._old_video_use_env = os.environ.get("VIDEO_USE_ENV")
        self._old_xdg = os.environ.get("XDG_CONFIG_HOME")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.skill = self.root / "skill"
        self.skill.mkdir()
        os.environ["VIDEO_USE_ENV"] = str(self.root / "user" / ".env")
        os.environ.pop("XDG_CONFIG_HOME", None)

    def tearDown(self):
        if self._old_video_use_env is None:
            os.environ.pop("VIDEO_USE_ENV", None)
        else:
            os.environ["VIDEO_USE_ENV"] = self._old_video_use_env
        if self._old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self._old_xdg
        self.tmp.cleanup()

    def test_user_config_wins_over_skill_root(self):
        (self.skill / ".env").write_text("FISH_API_KEY=from-skill\n", encoding="utf-8")
        user = Path(os.environ["VIDEO_USE_ENV"])
        user.parent.mkdir(parents=True)
        user.write_text("FISH_API_KEY=from-user\n", encoding="utf-8")
        self.assertEqual(
            E.load_env_value("FISH_API_KEY", skill_root=self.skill, migrate=False),
            "from-user",
        )

    def test_migrate_copies_skill_root_once(self):
        (self.skill / ".env").write_text("FISH_API_KEY=keep-me\n", encoding="utf-8")
        dest = E.migrate_skill_root_env(skill_root=self.skill)
        self.assertIsNotNone(dest)
        self.assertEqual(dest.read_text(encoding="utf-8"), "FISH_API_KEY=keep-me\n")
        self.assertIsNone(E.migrate_skill_root_env(skill_root=self.skill))

    def test_load_migrates_then_reads_after_skill_root_deleted(self):
        (self.skill / ".env").write_text("ELEVENLABS_API_KEY=abc\n", encoding="utf-8")
        self.assertEqual(
            E.load_env_value("ELEVENLABS_API_KEY", skill_root=self.skill),
            "abc",
        )
        (self.skill / ".env").unlink()
        self.assertEqual(
            E.load_env_value("ELEVENLABS_API_KEY", skill_root=self.skill),
            "abc",
        )

    def test_empty_file_value_falls_through(self):
        user = Path(os.environ["VIDEO_USE_ENV"])
        user.parent.mkdir(parents=True)
        user.write_text("FISH_API_KEY=\n", encoding="utf-8")
        (self.skill / ".env").write_text("FISH_API_KEY=real\n", encoding="utf-8")
        self.assertEqual(
            E.load_env_value("FISH_API_KEY", skill_root=self.skill, migrate=False),
            "real",
        )

    def test_default_user_path_is_home_config(self):
        os.environ.pop("VIDEO_USE_ENV", None)
        os.environ.pop("XDG_CONFIG_HOME", None)
        with patch.object(E.Path, "home", return_value=self.root):
            self.assertEqual(
                E.user_env_path(),
                self.root / ".config" / "video-use" / ".env",
            )

    def test_utf8_bom_value_is_readable(self):
        user = Path(os.environ["VIDEO_USE_ENV"])
        user.parent.mkdir(parents=True)
        user.write_bytes(b"\xef\xbb\xbfFISH_API_KEY=bom-key\n")
        self.assertEqual(
            E.load_env_value("FISH_API_KEY", skill_root=self.skill, migrate=False),
            "bom-key",
        )

    def test_migrate_survives_chmod_oserror(self):
        (self.skill / ".env").write_text("FISH_API_KEY=x\n", encoding="utf-8")
        with patch.object(Path, "chmod", side_effect=OSError("unsupported")):
            dest = E.migrate_skill_root_env(skill_root=self.skill)
        self.assertIsNotNone(dest)
        self.assertTrue(dest.is_file())


if __name__ == "__main__":
    unittest.main()
