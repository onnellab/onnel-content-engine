"""Pure-Python offline Aether signal review tests: no API or real ffmpeg."""
from __future__ import annotations

from array import array
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_offline_audio_review as quality
from short_video_pipeline import VideoError, file_hash


def pcm_song(seconds=8, sample_rate=quality.SAMPLE_RATE) -> bytes:
    samples = array("h")
    for i in range(seconds * sample_rate):
        t = i / sample_rate
        amplitude = 0.22 + 0.1 * math.sin(2 * math.pi * t / 5)
        tone = math.sin(2 * math.pi * (220 * t + 17 * t * t / (seconds * 2)))
        samples.append(round(32767 * amplitude * tone))
    samples[-1] = 0
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


class OfflineAudioReviewTests(unittest.TestCase):
    def test_actual_pcm_passes_without_network_or_owner_approval(self):
        result = quality.analyze_pcm(pcm_song(), min_duration_seconds=7)
        self.assertTrue(result["accepted"])
        self.assertEqual("offline_signal_quality", result["review_kind"])
        self.assertTrue(result["actual_audio_analyzed"])
        self.assertFalse(result["human_listening_performed"])
        self.assertFalse(result["music_aesthetics_verified"])
        self.assertFalse(result["melodic_originality_certified"])
        self.assertEqual([], result["reason_codes"])

    def test_silence_rejected_and_does_not_auto_accept(self):
        data = bytes(quality.SAMPLE_RATE * 2 * 8)
        result = quality.analyze_pcm(data, min_duration_seconds=7)
        self.assertFalse(result["accepted"])
        self.assertIn("audio_long_silence", result["reason_codes"])
        self.assertIn("audio_initial_silence", result["reason_codes"])

    def test_hard_cut_is_rejected(self):
        values = array("h")
        values.frombytes(pcm_song())
        if sys.byteorder != "little":
            values.byteswap()
        values[-1] = 15000
        if sys.byteorder != "little":
            values.byteswap()
        result = quality.analyze_pcm(values.tobytes(), min_duration_seconds=7)
        self.assertFalse(result["accepted"])
        self.assertIn("audio_hard_cut", result["reason_codes"])

    def test_heavily_clipped_audio_rejected(self):
        values = array("h", [32767] * (quality.SAMPLE_RATE * 8))
        if sys.byteorder != "little":
            values.byteswap()
        result = quality.analyze_pcm(values.tobytes(), min_duration_seconds=7)
        self.assertFalse(result["accepted"])
        self.assertIn("audio_clipping", result["reason_codes"])

    def test_pcm_length_and_format_are_fail_closed(self):
        with self.assertRaisesRegex(VideoError, "aether_offline_audio_invalid_pcm"):
            quality.analyze_pcm(b"abc")
        result = quality.analyze_pcm(pcm_song(seconds=8))
        self.assertFalse(result["accepted"])
        self.assertIn("duration_out_of_bounds", result["reason_codes"])

    def test_decode_is_hash_bound_and_expected_duration_checked(self):
        data = pcm_song()
        with tempfile.TemporaryDirectory() as tmp:
            song = Path(tmp) / "song.wav"
            song.write_bytes(b"RIFF" + b"x" * 4096)
            def simulate_decoder(command, timeout):
                self.assertIn("-nostdin", command)
                self.assertEqual("-f", command[-3])
                self.assertEqual("s16le", command[-2])
                Path(command[-1]).write_bytes(data)
                return b""
            with patch.object(quality, "run_process", side_effect=simulate_decoder):
                result = quality.review_audio(song, expected_duration=8)
                self.assertFalse(result["accepted"])  # 8s below default production minimum
                self.assertEqual(file_hash(song), result["source_sha256"])
                mismatch = quality.review_audio(song, expected_duration=50)
                self.assertIn("duration_mismatch", mismatch["reason_codes"])

    def test_decode_failure_does_not_become_a_quality_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            song = Path(tmp) / "song.wav"
            song.write_bytes(b"RIFF" + b"y" * 2048)
            with patch.object(quality, "run_process", side_effect=VideoError("codec failure")):
                with self.assertRaisesRegex(VideoError, "aether_offline_audio_decode_failed"):
                    quality.review_audio(song)


if __name__ == "__main__":
    unittest.main()
