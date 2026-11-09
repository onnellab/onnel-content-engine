import hashlib
from pathlib import Path
import sys
import shutil
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aether_sleep_render import source_info, render_command, render


class SleepRenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "test.wav"
        with wave.open(str(self.source), "wb") as wav:
            wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\x00\x00" * 24000 * 30)
        self.sha = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def test_verified_pcm(self):
        self.assertEqual(source_info(self.source, self.sha)["duration_seconds"], 30)

    def test_hash_failure(self):
        with self.assertRaisesRegex(ValueError, "hash_mismatch"):
            source_info(self.source, "a" * 64)

    def test_symlink_failure(self):
        link = self.source.with_name("link.wav")
        link.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "not_regular"):
            source_info(link, self.sha)

    def test_no_overwrite_or_execution(self):
        with patch("aether_sleep_render.subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "already_exists"):
                render(self.source, self.source, self.sha)
            run.assert_not_called()

    def test_changed_snapshot_rejected_before_execution(self):
        def corrupt(source, target):
            Path(target).write_bytes(b"changed")
        with patch("aether_sleep_render.shutil.copyfile", side_effect=corrupt), \
                patch("aether_sleep_render.subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "hash_mismatch"):
                render(self.source, self.source.with_name("out.wav"), self.sha)
            run.assert_not_called()

    def test_racing_output_never_overwritten(self):
        import os
        output = self.source.with_name("racing.wav")
        original_link = os.link
        def link_after_race(source, target):
            Path(target).write_bytes(b"other-worker")
            return original_link(source, target)
        def fake_render(command, **kwargs):
            with wave.open(str(command[-1]), "wb") as wav:
                wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\x00\x00" * 24000 * 1800)
        with patch("aether_sleep_render.subprocess.run", side_effect=fake_render), \
                patch("aether_sleep_render.os.link", side_effect=link_after_race):
            with self.assertRaises(FileExistsError):
                render(self.source, output, self.sha)
        self.assertEqual(output.read_bytes(), b"other-worker")

    def test_filter_bounded_and_equal_gain(self):
        command = render_command("in.wav", "out.wav", 184)
        self.assertIn("-n", command)
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("c1=tri:c2=tri", graph)
        self.assertIn("atrim=duration=1800", graph)
        self.assertIn("st=1780:d=20", graph)
        self.assertNotIn("http", " ".join(command))

    def test_invalid_fades(self):
        for fade in (0, -1, 16, float("nan"), float("inf")):
            with self.subTest(fade=fade), self.assertRaises(ValueError):
                render_command("a", "b", 30, crossfade_seconds=fade)

    def test_truncated_rejected(self):
        self.source.write_bytes(self.source.read_bytes()[:-8])
        sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "truncated"):
            source_info(self.source, sha)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg unavailable")
    def test_actual_30minute_render_is_not_quality_approval(self):
        output = self.source.with_name("render.wav")
        result = render(self.source, output, self.sha)
        self.assertEqual(result["duration_seconds"], 1800)
        self.assertFalse(result["publication_ready"])
        self.assertFalse(result["seam_reviewed"])
        with wave.open(str(output), "rb") as wav:
            self.assertEqual(wav.getnframes(), 1800 * 24000)


if __name__ == "__main__":
    unittest.main()
