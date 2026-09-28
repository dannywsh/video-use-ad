import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "helpers"))
import mix_ad_audio as mix  # noqa: E402


class DurationValidationTests(unittest.TestCase):
    # Supplies a probe response without media I/O. Input: JSON-compatible data. Return: mock result.
    def probe_result(self, data):
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(data))

    def test_video_stream_duration_ignores_longer_container_audio(self):
        result = self.probe_result({"streams": [{"duration": "8.2"}], "format": {"duration": "9"}})
        with patch.object(mix.subprocess, "run", return_value=result):
            self.assertEqual(mix.video_duration_seconds(Path("picture.mp4")), 8.2)

    def test_container_duration_is_used_when_stream_duration_is_unavailable(self):
        result = self.probe_result({"streams": [{}], "format": {"duration": "9"}})
        with patch.object(mix.subprocess, "run", return_value=result):
            self.assertEqual(mix.media_duration_seconds(Path("voice.wav"), "a:0"), 9)

    def test_missing_stream_and_invalid_durations_are_rejected(self):
        cases = [{"streams": [], "format": {"duration": "9"}}]
        cases += [{"streams": [{"duration": value}], "format": {"duration": value}}
                  for value in ("NaN", "Infinity", "0", "-1", "N/A")]
        for data in cases:
            with self.subTest(data=data), patch.object(
                mix.subprocess, "run", return_value=self.probe_result(data)
            ), self.assertRaises(ValueError):
                mix.media_duration_seconds(Path("voice.wav"), "a:0")

    def test_equal_or_shorter_narration_fits_without_retiming(self):
        for voice_duration in (8.5, 9):
            with self.subTest(duration=voice_duration), patch.object(
                mix, "media_duration_seconds", return_value=voice_duration
            ):
                mix.validate_narration_duration(Path("voice.wav"), 9)

    def test_invalid_programme_duration_is_rejected(self):
        for duration in (float("nan"), float("inf"), 0, -1):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                mix.validate_narration_duration(Path("voice.wav"), duration)

    def test_normalized_voice_is_checked_before_mix_or_overwrite(self):
        with patch.object(mix, "media_duration_seconds", return_value=9), patch.object(
            mix.subprocess, "run"
        ) as run, self.assertRaisesRegex(ValueError, "refusing to truncate narration"):
            mix.mix_tracks(Path("picture.mp4"), Path("voice.wav"), Path("bgm.wav"), 8.2, Path("mix.mp4"))
        run.assert_not_called()


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe required")
class ActualMixTimingTests(unittest.TestCase):
    # Creates isolated local audio/video fixtures. Input: None. Return: None; registers cleanup.
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="video-use-ad-timing-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.rate = 48000
        self.voice = self.root / "voice.wav"
        self.bgm = self.root / "bgm.wav"
        self.samples = np.zeros(2 * self.rate)
        self.references = []
        for start, length in ((.35, .25), (1.85, .12)):
            time = np.arange(round(length * self.rate)) / self.rate
            pulse = .2 * np.sin(2 * np.pi * (700 * time + 1800 * time ** 2)) * np.hanning(len(time))
            begin = round(start * self.rate)
            self.samples[begin:begin + len(pulse)] = pulse
            self.references.append((start, pulse))
        self.write_wave(self.samples, self.voice)
        time = np.arange(2 * self.rate) / self.rate
        self.write_wave(.003 * np.sin(2 * np.pi * 220 * time), self.bgm)

    # Writes PCM fixture audio. Input: float samples/path. Return: None after writing a WAV.
    def write_wave(self, samples, path):
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(self.rate)
            output.writeframes((samples * 32767).astype("<i2").tobytes())

    # Renders a silent picture of known length. Input: duration seconds. Return: media path.
    def picture(self, duration):
        path = self.root / f"picture-{duration}.mp4"
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
            f"color=c=blue:s=320x180:r=30:d={duration}", "-an", "-c:v", "libx264",
            "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path),
        ], capture_output=True, check=True)
        return path

    # Executes the existing CLI in isolation. Input: picture/output paths. Return: process result.
    def run_mix(self, picture, output):
        return subprocess.run([
            sys.executable, str(Path(mix.__file__).resolve()), str(picture), str(self.voice),
            str(self.bgm), "-o", str(output),
        ], capture_output=True, text=True)

    def test_short_picture_is_rejected_before_existing_output_is_touched(self):
        output = self.root / "existing.mp4"
        original = b"existing output must survive failed preflight"
        output.write_bytes(original)
        result = self.run_mix(self.picture(1.2), output)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("refusing to truncate narration", result.stderr)
        self.assertIn("--keep-duration", result.stderr)
        self.assertEqual(output.read_bytes(), original)

    def test_full_mix_preserves_voice_onsets_and_tail(self):
        output = self.root / "mixed.mp4"
        result = self.run_mix(self.picture(2), output)
        self.assertEqual(result.returncode, 0, result.stderr)
        decoded = subprocess.run([
            "ffmpeg", "-v", "error", "-xerror", "-i", str(output), "-vn", "-ac", "1",
            "-ar", str(self.rate), "-f", "f32le", "-",
        ], capture_output=True, check=True)
        samples = np.frombuffer(decoded.stdout, dtype="<f4")
        for start, pulse in self.references:
            with self.subTest(start=start):
                low = round((start - .015) * self.rate)
                high = round((start + .015) * self.rate) + len(pulse)
                window = samples[low:high]
                index = int(np.argmax(np.correlate(window, pulse, mode="valid")))
                onset = (low + index) / self.rate
                self.assertLessEqual(abs(onset - start), .001, (onset, start))
                match = window[index:index + len(pulse)]
                score = float(np.dot(match, pulse) / np.sqrt(np.dot(match, match) * np.dot(pulse, pulse)))
                self.assertGreater(score, .9, "tail or timing marker was lost")
        self.assertAlmostEqual(mix.video_duration_seconds(output), 2, places=3)


if __name__ == "__main__":
    unittest.main()
