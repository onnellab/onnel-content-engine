"""Offline sleep PCM renderer. No provider, queue, timer or publication access.

The existing single worker may call this after its own lock/provenance checks.
This module does not turn a successful render into musical or publication approval.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

from aether_sleep_plan import repeat_timeline


def source_info(path, expected_sha256):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("sleep_source_not_regular_file")
    if path.stat().st_size > 150_000_000:
        raise ValueError("sleep_source_too_large")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError("sleep_source_hash_mismatch")
    with wave.open(str(path), "rb") as wav:
        rate, channels, width, frames = (wav.getframerate(), wav.getnchannels(),
                                        wav.getsampwidth(), wav.getnframes())
        if rate not in (24000, 44100, 48000) or channels not in (1, 2) or width != 2:
            raise ValueError("sleep_source_requires_supported_pcm16")
        duration = frames / rate
        if not 30 <= duration <= 184:
            raise ValueError("sleep_source_duration_invalid")
        # Read all declared PCM bytes: truncated containers must not become a
        # shorter render whose ffmpeg exit status falsely looks successful.
        if len(wav.readframes(frames)) != frames * channels * width:
            raise ValueError("sleep_source_truncated")
    return {"sha256": actual, "sample_rate": rate, "channels": channels,
            "sample_width": width, "frames": frames, "duration_seconds": duration}


def render_command(source, output, duration, *, crossfade_seconds=8):
    timeline = repeat_timeline(duration, crossfade_seconds=crossfade_seconds)
    count = timeline["repeat_count"]
    fade = timeline["crossfade_seconds"]
    # Linear equal-gain overlap avoids boosting identical correlated material
    # as an equal-power crossfade would. This is not an audible-seam certificate.
    # Separate demuxers are necessary. asplit's shared frame timeline is not
    # a repeat source and can prematurely exhaust acrossfade chains.
    parts = []
    current = "0:a"
    for index in range(1, count):
        target = f"x{index}"
        parts.append(f"[{current}][{index}:a]acrossfade=d={fade}:c1=tri:c2=tri[{target}]")
        current = target
    parts.append(f"[{current}]atrim=duration=1800,asetpts=PTS-STARTPTS,"
                 "afade=t=in:st=0:d=3,afade=t=out:st=1780:d=20[out]")
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
            "-threads", "1", *[arg for _ in range(count) for arg in ("-i", str(source))],
            "-filter_complex_threads", "1",
            "-filter_complex", ";".join(parts), "-map", "[out]", "-c:a", "pcm_s16le",
            "-f", "wav", str(output)]


def render(source, output, expected_sha256, *, crossfade_seconds=8, timeout=600):
    source, output = Path(source), Path(output)
    info = source_info(source, expected_sha256)
    if output.exists() or output.is_symlink() or source.resolve() == output.resolve():
        raise ValueError("sleep_output_already_exists")
    # Private snapshot pins the bytes consumed by every demuxer. A concurrent
    # source replacement during copy fails hash verification before execution.
    with tempfile.TemporaryDirectory(prefix=".sleep-render-", dir=output.parent) as temp:
        snapshot, staged = Path(temp) / "source.wav", Path(temp) / "render.wav"
        shutil.copyfile(source, snapshot)
        if source_info(snapshot, expected_sha256) != info:
            raise ValueError("sleep_source_changed_during_snapshot")
        command = render_command(snapshot, staged, info["duration_seconds"],
                                 crossfade_seconds=crossfade_seconds)
        subprocess.run(command, check=True, capture_output=True, timeout=timeout)
        with wave.open(str(staged), "rb") as wav:
            if (wav.getframerate() != info["sample_rate"]
                    or wav.getnchannels() != info["channels"]
                    or wav.getsampwidth() != 2
                    or wav.getnframes() != 1800 * info["sample_rate"]):
                raise ValueError("sleep_render_pcm_contract_failed")
        with staged.open("rb") as stream:
            os.fsync(stream.fileno())
        # Same-filesystem hard link is atomic create-only; an existing/racing
        # output fails, never replaces prior content. No rename/overwrite.
        os.link(staged, output)
    return {"state": "rendered_pending_audio_and_visual_review",
            "source": info, "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "duration_seconds": 1800,
            "timeline": repeat_timeline(info["duration_seconds"],
                                        crossfade_seconds=crossfade_seconds),
            "seam_reviewed": False, "music_quality_reviewed": False,
            "rights_verified": False, "publication_ready": False,
            "disclosure": "One newly composed short track repeated with gentle crossfades."}
