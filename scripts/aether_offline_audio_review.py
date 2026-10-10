"""No-cost, deterministic signal-quality gate for Aether Inn audio.

This is actual-audio DSP, not an AI listening review, music originality analysis,
genre classifier or copyright determination. Fail closed when decoding fails.
All decoding is local via owned ffmpeg; no provider API, network or credentials.
"""
from __future__ import annotations

from array import array
import hashlib
import math
from pathlib import Path
import sys
import tempfile

from short_video_pipeline import VideoError, run_process

MODEL = "local_signal_quality_v1"
SAMPLE_RATE = 16000
FRAME_SECONDS = 0.5
MAX_AUDIO_SECONDS = 900
MAX_PCM_BYTES = SAMPLE_RATE * 2 * MAX_AUDIO_SECONDS


def _dbfs(amplitude: float) -> float:
    return round(20 * math.log10(max(float(amplitude), 1.0 / 32768.0)), 2)


def _percentile(values: list[float], position: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = int(round((len(ordered) - 1) * position))
    return ordered[index]


def analyze_pcm(pcm: bytes, *, sample_rate: int = SAMPLE_RATE,
                min_duration_seconds: float = 45.0) -> dict:
    """Measure decoded mono s16le PCM, with explicit reasons for auto-rejection."""
    if (not isinstance(pcm, bytes) or len(pcm) % 2 != 0
            or not 8000 <= sample_rate <= 48000
            or not 0 <= min_duration_seconds <= MAX_AUDIO_SECONDS
            or len(pcm) > sample_rate * 2 * MAX_AUDIO_SECONDS):
        raise VideoError("aether_offline_audio_invalid_pcm")
    audio = array("h")
    audio.frombytes(pcm)
    if sys.byteorder != "little":
        audio.byteswap()
    frames = len(audio)
    duration = frames / sample_rate
    if frames == 0:
        raise VideoError("aether_offline_audio_invalid_pcm")
    window = max(1, round(sample_rate * FRAME_SECONDS))
    rms_levels: list[float] = []
    zcr_rates: list[float] = []
    clipped = 0
    square_sum = 0
    peak = 0
    silence_windows = 0
    longest_silence_windows = 0
    consecutive_silence = 0
    initial_silence_windows = 0
    audio_begun = False

    for start in range(0, frames, window):
        segment = audio[start:start + window]
        count = len(segment)
        frame_squared = sum(v * v for v in segment)
        square_sum += frame_squared
        amplitude = math.sqrt(frame_squared / count) / 32768.0
        level = _dbfs(amplitude)
        rms_levels.append(level)
        crossings = sum(1 for j in range(1, count)
                        if (segment[j - 1] < 0) != (segment[j] < 0))
        zcr_rates.append(crossings / count)
        peak = max(peak, max(abs(v) for v in segment))
        clipped += sum(1 for v in segment if abs(v) >= 32760)
        muted = level < -50.0
        if muted:
            consecutive_silence += 1
            silence_windows += 1
            longest_silence_windows = max(longest_silence_windows, consecutive_silence)
            if not audio_begun:
                initial_silence_windows += 1
        else:
            audio_begun = True
            consecutive_silence = 0

    overall_rms = math.sqrt(square_sum / frames) / 32768.0
    overall_db = _dbfs(overall_rms)
    peak_ratio = peak / 32768.0
    clip_fraction = clipped / frames
    quiet_fraction = silence_windows / len(rms_levels)
    longest_silence = round(longest_silence_windows * FRAME_SECONDS, 2)
    initial_silence = round(initial_silence_windows * FRAME_SECONDS, 2)
    last_sample = abs(audio[-1]) / 32768.0
    active = [level for level in rms_levels if level >= -50]
    dynamic_span = round(_percentile(active, .9) - _percentile(active, .1), 2) if active else 0.0
    zcr_span = round(_percentile(zcr_rates, .9) - _percentile(zcr_rates, .1), 4)
    reasons: list[str] = []
    if duration < min_duration_seconds or duration > MAX_AUDIO_SECONDS:
        reasons.append("duration_out_of_bounds")
    if overall_db < -38 or peak_ratio < .08:
        reasons.append("audio_too_quiet")
    if overall_db > -3:
        reasons.append("audio_excessively_loud")
    if clip_fraction > .006:
        reasons.append("audio_clipping")
    if longest_silence > 12 or quiet_fraction > .2:
        reasons.append("audio_long_silence")
    if initial_silence > 5:
        reasons.append("audio_initial_silence")
    # A large last sample is an objective indicator of a probable hard cut.
    # It does not purport to evaluate harmonic/tonal resolution.
    if last_sample > .22:
        reasons.append("audio_hard_cut")
    # A uniformly loud single-frequency drone is not a developed arrangement.
    # Mark the proxy, not an invented subjective melody score.
    if duration >= 80 and dynamic_span < 1.25 and zcr_span < .004:
        reasons.append("audio_low_variation")

    accepted = not reasons
    return {
        "state": "accepted" if accepted else "rejected",
        "accepted": accepted,
        "decision": "accept" if accepted else "reject",
        "review_model": MODEL,
        "review_kind": "offline_signal_quality",
        "actual_audio_analyzed": True,
        "human_listening_performed": False,
        "music_aesthetics_verified": False,
        "melodic_originality_certified": False,
        "weighted_score": round(max(0.0, min(10.0,
            8.5 - min(3.0, max(0.0, quiet_fraction - .02) * 10)
                - min(2.0, clip_fraction * 150))), 3) if accepted else 0.0,
        "reason_codes": reasons,
        "measurements": {
            "duration_seconds": round(duration, 2),
            "integrated_rms_dbfs": overall_db,
            "peak_dbfs": _dbfs(peak_ratio),
            "clipped_sample_fraction": round(clip_fraction, 7),
            "silence_fraction": round(quiet_fraction, 4),
            "longest_silence_seconds": longest_silence,
            "initial_silence_seconds": initial_silence,
            "rms_dynamic_span_db": dynamic_span,
            "zero_crossing_variation": zcr_span,
            "end_sample_amplitude": round(last_sample, 5),
        },
    }


def review_audio(path: Path, *, expected_duration: float | None = None) -> dict:
    """Decode the exact local audio once and return a SHA-bound QA decision."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".wav", ".mp3", ".flac", ".m4a"}:
        raise VideoError("aether_offline_audio_source_invalid")
    if not 1024 <= path.stat().st_size <= 1024 ** 3:
        raise VideoError("aether_offline_audio_source_invalid")
    with tempfile.TemporaryDirectory(prefix="aether-qa-") as folder:
        decoded = Path(folder) / "audio.pcm"
        try:
            run_process([
                "ffmpeg", "-hide_banner", "-v", "error", "-nostdin",
                "-threads", "1", "-protocol_whitelist", "file,pipe",
                "-i", str(path), "-map", "0:a:0",
                "-ac", "1", "-ar", str(SAMPLE_RATE),
                "-c:a", "pcm_s16le", "-f", "s16le", str(decoded),
            ], timeout=180)
            size = decoded.stat().st_size
            if not 2 <= size <= MAX_PCM_BYTES:
                raise VideoError("aether_offline_audio_invalid_pcm")
            pcm = decoded.read_bytes()
        except (OSError, VideoError):
            raise VideoError("aether_offline_audio_decode_failed") from None
    review = analyze_pcm(pcm)
    if expected_duration is not None and abs(
            review["measurements"]["duration_seconds"] - float(expected_duration)) > 3:
        review["accepted"] = False
        review["decision"] = "reject"
        review["state"] = "rejected"
        review["weighted_score"] = 0.0
        review["reason_codes"].append("duration_mismatch")
    # Bound a saved decision to the specific audio file, not just its title.
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    review["source_sha256"] = sha.hexdigest()
    return review
