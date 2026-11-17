"""Owner-requested release of the retained 2026-11-17 single; zero generation.

Only the existing GUI LaunchAgent may execute publication. The interactive
record-request command writes an immutable two-hour, source-bound request.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from short_video_pipeline import VideoError, canonical, digest, file_hash, load_json
from short_video_private_permissions import private_path_permissions

JOB_ID = "ca7ecaa3c19738e4a852a59c"
TITLE = "The Ridge Where the Wild Road Begins"
SLOT = "2026-11-17"
PROJECT = "aether-inn-music"
REQUEST = "140초까지도 통과시키고 이 곡 공개완료해"
SOURCE_SHA256 = "90af9117fd588df0c50921fd3b6b99c0f3640dc2bc3149dd77fe8321a3591ef4"
MANIFEST_SHA256 = "7b4e17c6a66106489d80f52b440fbeeded11a69560a1d9ae88537a5fc6bd1262"
MANIFEST_RELATIVE = "lyria/20261116T212036Z-the-ridge-where-the-wild-road-begins/manifest.json"
ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/singles"
RECEIPT = "retained-release-request-20261117.json"
OWNER_SERVICE = "com.onnellab.aether-daily-local"
PRIOR_STATE = {"status": "blocked", "error": "aether_single_no_accepted_candidate"}


def utc_now():
    return datetime.now(timezone.utc)


def binding(job):
    from aether_single import brief_for
    from lyria_generate import build_aether_prompt
    if (job.get("id") != JOB_ID or job.get("title") != TITLE or job.get("slot") != SLOT
            or job.get("lane") != "frontier_surge"
            or job.get("source_kind", "new_lyria") != "new_lyria"
            or job.get("brief") != brief_for(job)
            or digest(job.get("brief")) != job.get("payload_hash")):
        raise VideoError("aether_retained_release_identity_invalid")
    return {"kind": "aether_retained_audio_manual_release", "version": 1,
            "job_id": JOB_ID, "title": TITLE, "original_slot": SLOT,
            "project_id": PROJECT, "request_text": REQUEST,
            "publication": "public_after_quality_checks", "new_generation_allowed": False,
            "minimum_duration_seconds": 140, "maximum_duration_seconds": 210,
            "source_sha256": SOURCE_SHA256, "manifest_sha256": MANIFEST_SHA256,
            "payload_hash": job["payload_hash"],
            "prompt_sha256": hashlib.sha256(build_aether_prompt(TITLE, job["style"]).encode()).hexdigest()}


def private_read(path, limit):
    from aether_paid_guard import _read
    if (any(p.is_symlink() for p in (path, *path.parents))
            or not path.is_file() or not private_path_permissions(path)
            or not private_path_permissions(path.parent)):
        raise VideoError("aether_retained_release_evidence_unsafe")
    return _read(path, limit=limit)


def require_source(job, root):
    from aether_paid_guard import _json
    folder = Path(root) / "jobs" / JOB_ID
    manifest = folder / MANIFEST_RELATIVE
    raw = private_read(manifest, 2 * 1024 * 1024)
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise VideoError("aether_retained_release_manifest_changed")
    data = _json(raw)
    expected = binding(job)
    rows = data.get("candidates")
    if (data.get("state") != "generated" or data.get("title") != TITLE
            or data.get("slot") != SLOT or data.get("project_id") != PROJECT
            or data.get("style") != job["style"] or data.get("model") != "lyria-3-pro-preview"
            or data.get("prompt_sha256") != expected["prompt_sha256"]
            or data.get("candidate_count") != 1 or not isinstance(rows, list) or len(rows) != 1
            or not isinstance(rows[0], dict)):
        raise VideoError("aether_retained_release_manifest_invalid")
    source = manifest.parent / "candidate-01.mp3"
    if (rows[0].get("file") != str(source) or rows[0].get("sha256") != SOURCE_SHA256
            or any(p.is_symlink() for p in (source, *source.parents))
            or not source.is_file() or not private_path_permissions(source)
            or file_hash(source) != SOURCE_SHA256):
        raise VideoError("aether_retained_release_source_changed")
    music = job.get("music")
    if music and (music.get("sha256") != SOURCE_SHA256 or music.get("path") != str(source)):
        raise VideoError("aether_retained_release_selected_source_changed")
    return {"generation_count": 1, "estimated_cost_usd": data.get("estimated_cost_usd"),
            "cost_basis": data.get("cost_basis"), "source_sha256": SOURCE_SHA256}


def validate(job, *, root=None, expected_sha=None, now=None, active=True):
    from aether_paid_guard import _json
    root = ROOT if root is None else Path(root)
    expected = binding(job)
    raw = private_read(root / "jobs" / JOB_ID / RECEIPT, 16384)
    sha = hashlib.sha256(raw).hexdigest()
    record = _json(raw)
    if (set(record) != set(expected) | {"issued_at", "expires_at", "prior_state"}
            or any(record.get(k) != v for k, v in expected.items())
            or record.get("new_generation_allowed") is not False
            or type(record.get("version")) is not int
            or expected_sha is not None and sha != expected_sha
            or record.get("prior_state") != PRIOR_STATE):
        raise VideoError("aether_retained_release_request_changed")
    try:
        issued, expires = (datetime.fromisoformat(record[k]) for k in ("issued_at", "expires_at"))
        current = now or utc_now()
        valid = (issued.tzinfo is not None and expires.tzinfo is not None and current.tzinfo is not None
                 and timedelta(0) < expires - issued <= timedelta(hours=2))
    except (ValueError, TypeError):
        raise VideoError("aether_retained_release_time_invalid") from None
    if not valid or active and not issued <= current < expires:
        raise VideoError("aether_retained_release_expired")
    # Uploaded jobs reconcile their exact existing render/video without requiring
    # source regeneration. Before first upload, recheck the immutable source.
    if not job.get("upload"):
        require_source(job, root)
    return {"job_id": JOB_ID, "request_sha256": sha, "project_id": PROJECT,
            "prompt_sha256": expected["prompt_sha256"], "expires_at": record["expires_at"],
            "retained_only": True, "source_sha256": SOURCE_SHA256}


def record_request():
    from aether_single import SingleQueue
    q = SingleQueue(ROOT)
    with q.lock():
        job = q._read()["jobs"].get(JOB_ID, {})
        expected = binding(job)
        folder = q.root / "jobs" / JOB_ID
        path = folder / RECEIPT
        if path.exists() or path.is_symlink():
            return validate(job, root=q.root)  # Never renew or replace.
        if ({k: job.get(k) for k in PRIOR_STATE} != PRIOR_STATE
                or any(job.get(k) for k in ("music", "result", "upload", "approval"))
                or (folder / "youtube-session.json").exists()):
            raise VideoError("aether_retained_release_initial_state_changed")
        require_source(job, q.root)
        if any(p.is_symlink() for p in (path, *path.parents)) or not private_path_permissions(folder):
            raise VideoError("aether_retained_release_evidence_unsafe")
        now = utc_now()
        record = {**expected, "issued_at": now.isoformat(),
                  "expires_at": (now + timedelta(hours=2)).isoformat(), "prior_state": PRIOR_STATE}
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(record))
            stream.flush()
            os.fsync(stream.fileno())
        return validate(job, root=q.root)


def pending_request(*, now=None):
    current = now or utc_now()
    if current.tzinfo is None or current.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat() != SLOT:
        return False
    path = ROOT / "jobs" / JOB_ID / RECEIPT
    if not path.exists() and not path.is_symlink():
        return False
    job = load_json(ROOT / "queue.json", limit=16 * 1024 * 1024).get("jobs", {}).get(JOB_ID, {})
    try:
        validate(job, now=current)
    except VideoError as error:
        if str(error) == "aether_retained_release_expired":
            return False
        raise
    return True


def forbid_generation(*args, **kwargs):
    raise VideoError("aether_retained_release_generation_forbidden")


def publish():
    if os.environ.get("XPC_SERVICE_NAME") != OWNER_SERVICE:
        raise VideoError("aether_retained_release_gui_owner_required")
    from aether_single import worker
    return worker(root=ROOT, publish=True, execute=True, manual_release_id=JOB_ID,
                  music_generator=forbid_generation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("record-request", "publish"))
    args = parser.parse_args()
    try:
        result = record_request() if args.command == "record-request" else publish()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") in {"blocked", "reconcile_required", "rejected"} else 0
    except (VideoError, OSError) as error:
        import re
        reason = str(error) if isinstance(error, VideoError) and re.fullmatch(r"[a-z_0-9]{1,100}", str(error)) else "aether_retained_release_failed"
        print(json.dumps({"status": "blocked", "job_id": JOB_ID, "error": reason}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
