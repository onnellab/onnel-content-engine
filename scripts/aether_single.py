#!/usr/bin/env python3
"""Durable end-to-end Aether Inn single worker: Lyria -> cover -> render -> YouTube."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from functools import partial
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from aether_compilation import thumbnail
from aether_compose import audio_duration, media_info, validate_output
from aether_cover import generate_cover, lane_direction
from lyria_generate import generate as generate_music
from short_video_credentials import credential_status
from short_video_pipeline import VideoError, atomic_json, digest, file_hash, load_json, run_process
from short_video_youtube import YouTube, Uploader, UploadError
from youtube_report_store import directory

ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/singles"
POLICY = {
    "version": 1,
    "profile": "aether_inn",
    "kind": "generated_single",
    "music_provider": "lyria-3-pro-preview",
    "cover_provider": "gemini-2.5-flash-image",
    "synthetic_media": True,
    "made_for_kids": False,
    "privacy": "public",
}
FINAL = {"published", "uploaded_private", "uploaded_unlisted", "forced_private", "rejected"}


def _clean(value: str, name: str, limit: int) -> str:
    if not isinstance(value, str):
        raise VideoError(f"aether_single_{name}_invalid")
    value = " ".join(value.strip().split())
    if not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise VideoError(f"aether_single_{name}_invalid")
    return value


def brief_for(job: dict) -> dict:
    title = job["title"]
    style = job["style"]
    lane = job["lane"]
    youtube_title = f"{title} ✨ Fantasy RPG Music | Nostalgic JRPG Soundtrack"
    if len(youtube_title) > 100:
        youtube_title = f"{title} ✨ Fantasy RPG Music"
    description = (
        "🌙 A journey through a world that still remembers magic.\n\n"
        f"{style}\n\n"
        "This AI-generated fantasy soundtrack is part of Aether Inn — a growing archive of nostalgic "
        "JRPG and MMORPG-inspired travel music for reading, studying, gaming, relaxing, and daydreaming.\n\n"
        f"Journey theme: {lane.replace('_', ' ')}\n"
        "🎵 Fantasy RPG Music\n✨ Nostalgic JRPG Atmosphere\n🌌 Emotional Adventure Soundtrack\n\n"
        "Welcome to Aether Inn — a place where travelers rest before the next adventure.\n\n"
        "#fantasymusic #jrpg #rpgmusic #mmorpg #adventuremusic #aimusic"
    )
    return {
        "locale": "en",
        "content_kind": "aether_single",
        "youtube_profile": "aether_inn",
        "test_only": False,
        "title": youtube_title,
        "description": description,
    }


def _history_hashes(state: dict) -> set[str]:
    return {
        str((job.get("music") or {}).get("sha256"))
        for job in state.get("jobs", {}).values()
        if (job.get("music") or {}).get("sha256")
    }


def select_candidate(result: dict, prior_hashes: set[str]) -> dict:
    candidates = result.get("candidates") or []
    ranked = []
    for row in candidates:
        path = Path(row.get("file", ""))
        expected = row.get("sha256")
        if path.is_symlink() or not path.is_file() or not re.fullmatch(r"[0-9a-f]{64}", str(expected)):
            continue
        if file_hash(path) != expected or expected in prior_hashes:
            continue
        duration = audio_duration(path)
        if not 160 <= duration <= 210:
            continue
        ranked.append((abs(duration - 184), int(row.get("index", 999)), path, duration, expected))
    if not ranked:
        raise VideoError("aether_single_no_technical_candidate")
    _, index, path, duration, sha = min(ranked)
    return {"candidate_index": index, "path": str(path), "duration_seconds": duration, "sha256": sha}


def render_single(audio: Path, cover: Path, output: Path) -> dict:
    if audio.is_symlink() or cover.is_symlink() or not audio.is_file() or not cover.is_file():
        raise VideoError("aether_single_render_input_missing")
    duration = audio_duration(audio)
    cover_info = media_info(cover)
    image = next((s for s in cover_info.get("streams", []) if s.get("codec_type") == "video"), {})
    if (image.get("width"), image.get("height")) != (1920, 1080):
        raise VideoError("aether_single_cover_geometry_invalid")
    output = directory(output)
    partial = output / "render.partial.mp4"
    run_process([
        "ffmpeg", "-v", "error", "-nostdin", "-y",
        "-loop", "1", "-framerate", "30", "-i", str(cover),
        "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", "scale=1920:1080,setsar=1",
        "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-tune", "stillimage",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "256k",
        "-shortest", "-movflags", "+faststart", str(partial),
    ], timeout=1200)
    actual = validate_output(partial, duration)
    thumbnail_path = output / "thumbnail.jpg"
    run_process([
        "ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(cover),
        "-vf", "scale=1280:720", "-frames:v", "1", "-q:v", "3", str(thumbnail_path),
    ], timeout=90)
    if not 0 < thumbnail_path.stat().st_size <= 2 * 1024 * 1024:
        raise VideoError("aether_single_thumbnail_invalid")
    partial.replace(output / "video.mp4")
    return {
        "test_only": False,
        "upload_eligible": True,
        "duration_seconds": actual,
        "sha256": {
            "video.mp4": file_hash(output / "video.mp4"),
            "thumbnail.jpg": file_hash(thumbnail_path),
        },
    }


class SingleQueue:
    def __init__(self, root=ROOT):
        self.root = directory(root)
        self.state_path = self.root / "queue.json"
        directory(self.root / "jobs")
        self.clock = lambda: datetime.now(timezone.utc)

    @contextmanager
    def lock(self):
        fd = os.open(self.root / "worker.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise VideoError("aether_single_worker_already_running") from None
            yield
        finally:
            os.close(fd)

    def _read(self):
        if not self.state_path.exists():
            return {"schema_version": 1, "jobs": {}}
        if self.state_path.is_symlink() or self.state_path.stat().st_mode & 0o077:
            raise VideoError("aether_single_unsafe_queue")
        state = load_json(self.state_path, limit=16 * 1024 * 1024)
        if state.get("schema_version") != 1 or not isinstance(state.get("jobs"), dict):
            raise VideoError("aether_single_queue_invalid")
        for key, job in state["jobs"].items():
            if key != job.get("id") or not re.fullmatch(r"[0-9a-f]{24}", key):
                raise VideoError("aether_single_job_identity_changed")
            if brief_for(job) != job.get("brief") or digest(job["brief"]) != job.get("payload_hash"):
                raise VideoError("aether_single_brief_integrity")
        return state

    def _render(self, state, job, renderer):
        result = job.get("result") or {}
        path = self.root / "jobs" / job["id"] / "video.mp4"
        if result.get("job_id") != job["id"] or result.get("test_only") is not False or result.get("upload_eligible") is not True:
            raise UploadError("aether_single_production_proof_required")
        if path.is_symlink() or not path.is_file() or file_hash(path) != result.get("sha256", {}).get("video.mp4"):
            raise UploadError("aether_single_render_integrity")
        validate_output(path, result["duration_seconds"])


def readiness(root=ROOT) -> dict:
    return {
        "profile": "aether_inn",
        "worker": "generated_single",
        "credentials": credential_status(profile="aether_inn"),
        "lyria_and_google_adc": "configured_separately",
        "cover_model": "gemini-2.5-flash-image",
        "render": "implemented",
        "upload": "implemented",
        "technical_candidate_gate": "implemented",
        "melodic_originality_certification": "not_claimed",
    }


def worker(
    root=ROOT, *, slot=None, title=None, style=None, lane=None, publish=False, execute=False,
    api_factory=None, music_generator=generate_music, cover_generator=generate_cover,
    renderer=render_single, existing_only=False,
):
    if not execute:
        return {"dry_run": True, **readiness(root)}
    slot = slot or datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    try:
        datetime.strptime(slot, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise VideoError("aether_single_slot_invalid") from None
    q = SingleQueue(root)
    with q.lock():
        state = q._read()
        pending = [
            j for j in state["jobs"].values()
            if j.get("upload") and (j["status"] not in FINAL or j.get("thumbnail_status") != "set" and j["status"] != "rejected")
        ]
        same_slot = [j for j in state["jobs"].values() if j["slot"] == slot]
        unfinished = [j for j in state["jobs"].values() if not j.get("upload") and j["status"] not in FINAL]
        if existing_only:
            job = (pending or [j for j in unfinished if j.get("publish_requested")] or [None])[0]
            if job is None:
                return {"profile": "aether_inn", "status": "idle", "created_new_job": False}
        else:
            job = (pending or same_slot or unfinished or [None])[0]
        api = None
        if publish:
            api = (api_factory or partial(YouTube, profile="aether_inn"))()
            if getattr(api, "profile", None) != "aether_inn":
                raise UploadError("aether_profile_required")
            api.verify()
        if job is None:
            title = _clean(title, "title", 60)
            style = _clean(style, "style", 1200)
            lane = _clean(lane, "lane", 64)
            lane_direction(lane)
            seed = {"slot": slot, "title": title, "style": style, "lane": lane}
            key = digest(seed)[:24]
            job = {
                "id": key, **seed, "brief": None, "payload_hash": None,
                "status": "planned", "music": None, "cover": None, "result": None,
                "upload_eligible": False, "error": None, "publish_requested": publish,
            }
            job["brief"] = brief_for(job)
            job["payload_hash"] = digest(job["brief"])
            state["jobs"][key] = job
            atomic_json(q.state_path, state)
        if publish and not job.get("publish_requested"):
            job["publish_requested"] = True
            atomic_json(q.state_path, state)
        folder = directory(q.root / "jobs" / job["id"])
        try:
            if not job.get("music"):
                generated = music_generator(job["title"], job["style"], execute=True, output_root=folder / "lyria")
                chosen = select_candidate(generated, _history_hashes(state))
                job["music"] = chosen
                job["status"] = "music_ready"
                atomic_json(q.state_path, state)
            if not job.get("cover"):
                cover = cover_generator(job["title"], job["style"], job["lane"], folder / "cover", execute=True)
                if cover.get("state") != "generated" or not Path(cover.get("path", "")).is_file():
                    raise VideoError("aether_single_cover_generation_failed")
                job["cover"] = {
                    "path": cover["path"], "sha256": cover["sha256"],
                    "model": cover.get("model"), "layout": cover.get("layout"),
                }
                job["status"] = "cover_ready"
                atomic_json(q.state_path, state)
            if not job.get("result"):
                result = renderer(Path(job["music"]["path"]), Path(job["cover"]["path"]), folder)
                result["job_id"] = job["id"]
                job.update(result=result, status="rendered", upload_eligible=True, error=None)
                atomic_json(q.state_path, state)
            if publish:
                uploader = Uploader(q, partial(YouTube, profile="aether_inn"))
                if not job.get("approval"):
                    choices = {"made_for_kids": False, "synthetic_media": True, "privacy": "public", "publish_approved": True}
                    uploader.bind_approval_locked(state, job, choices, mode="automatic_fail_closed", policy_hash=digest(POLICY))
                if job["approval"].get("policy_hash") != digest(POLICY):
                    raise UploadError("aether_single_policy_changed")
                q._render(state, job, None)
                uploader.run_locked(state, job, reconcile=bool(job.get("upload")), api=api)
                if job.get("upload", {}).get("video_id") and job["status"] not in {"rejected", "reconcile_required", "blocked"}:
                    try:
                        thumbnail(q, state, job, api)
                    except UploadError as error:
                        job["thumbnail_status"] = "retry_required"
                        job["thumbnail_error"] = str(error)
                        atomic_json(q.state_path, state)
            return {
                "profile": "aether_inn", "status": job["status"], "job_id": job["id"],
                "title": job["title"], "lane": job["lane"],
                "video_id": job.get("upload", {}).get("video_id"),
                "thumbnail_status": job.get("thumbnail_status"),
                "error": job.get("error"),
                "publication_complete": job["status"] == "published" and job.get("thumbnail_status") == "set",
            }
        except (VideoError, OSError) as error:
            job.update(
                status="reconcile_required" if job.get("upload") else "blocked",
                error=str(error) if isinstance(error, VideoError) else "aether_single_storage_error",
            )
            atomic_json(q.state_path, state)
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("readiness")
    r = sub.add_parser("reconcile")
    r.add_argument("--execute", action="store_true")
    p = sub.add_parser("worker")
    p.add_argument("--slot")
    p.add_argument("--title")
    p.add_argument("--style")
    p.add_argument("--lane")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "readiness":
            result = readiness(args.root)
        elif args.command == "reconcile":
            result = worker(args.root, publish=True, execute=args.execute, existing_only=True)
        else:
            result = worker(
                args.root, slot=args.slot, title=args.title, style=args.style, lane=args.lane,
                publish=args.publish, execute=args.execute,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") in {"blocked", "reconcile_required", "rejected"} else 0
    except Exception as error:
        reason = str(error) if isinstance(error, VideoError) and re.fullmatch(r"[a-z_]{1,100}", str(error)) else "aether_single_operation_failed"
        print(json.dumps({"profile": "aether_inn", "status": "blocked", "error": reason}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
