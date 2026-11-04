"""Explicitly requested publication of one existing Aether single.

The owner's 2026-11-04 request is separate from unattended scheduled production.
Keep the existing job, source checks, one-candidate budget and upload transport.
This module never changes the automatic schedule or host tool permissions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path

from short_video_pipeline import VideoError, canonical, digest, load_json
from short_video_private_permissions import private_path_permissions

JOB_ID = "1f5cf414734a3a362b4db5cc"
TITLE = "The Pass Beyond the Racing Plains"
SLOT = "2026-11-03"
PROJECT = "aether-inn-music"
REQUEST = "기존 누락곡의 공개 완료해"
ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/singles"
RECEIPT = "manual-release-request.json"


def utc_now():
    return datetime.now(timezone.utc)


def binding(job):
    from lyria_generate import build_aether_prompt
    if (job.get("id") != JOB_ID or job.get("title") != TITLE or job.get("slot") != SLOT
            or job.get("source_kind", "new_lyria") != "new_lyria"
            or digest(job.get("brief")) != job.get("payload_hash")):
        raise VideoError("aether_manual_release_identity_invalid")
    return {"kind": "aether_explicit_manual_release", "version": 1,
            "job_id": JOB_ID, "title": TITLE, "original_slot": SLOT,
            "project_id": PROJECT, "request_text": REQUEST,
            "publication": "public_after_quality_checks", "candidate_count": 1,
            "provider_base_limit_usd": "0.08", "model": "lyria-3-pro-preview",
            "payload_hash": job["payload_hash"],
            "prompt_sha256": hashlib.sha256(build_aether_prompt(TITLE, job["style"]).encode()).hexdigest()}


def validate(job, *, root=None, expected_sha=None, now=None, active=True):
    root = ROOT if root is None else Path(root)
    expected = binding(job)
    folder = root / "jobs" / JOB_ID
    path = folder / RECEIPT
    if (any(p.is_symlink() for p in (path, *path.parents))
            or not private_path_permissions(folder) or not path.is_file()
            or not private_path_permissions(path) or not 0 < path.stat().st_size <= 16384):
        raise VideoError("aether_manual_release_request_missing_or_unsafe")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    from aether_paid_guard import _json
    record = _json(raw)
    if (set(record) != set(expected) | {"issued_at", "expires_at", "prior_state"}
            or any(record.get(k) != v for k, v in expected.items())
            or type(record.get("version")) is not int
            or type(record.get("candidate_count")) is not int
            or expected_sha is not None and sha != expected_sha
            or record.get("prior_state") != {"status": "rejected", "error": "aether_single_publish_time_stale"}):
        raise VideoError("aether_manual_release_request_changed")
    try:
        issued, expires = (datetime.fromisoformat(record[k]) for k in ("issued_at", "expires_at"))
        current = now or utc_now()
        valid = (issued.tzinfo is not None and expires.tzinfo is not None and current.tzinfo is not None
                 and timedelta(0) < expires - issued <= timedelta(hours=2))
    except (ValueError, TypeError):
        raise VideoError("aether_manual_release_time_invalid") from None
    if not valid or active and not issued <= current < expires:
        raise VideoError("aether_manual_release_expired")
    return {"job_id": JOB_ID, "request_sha256": sha, "project_id": PROJECT,
            "prompt_sha256": expected["prompt_sha256"], "expires_at": record["expires_at"]}


def require_generation(job_id, slot, project_id, prompt, sha, *, now=None):
    if job_id != JOB_ID or slot != SLOT or project_id != PROJECT or not sha:
        raise VideoError("aether_manual_release_identity_invalid")
    state = load_json(ROOT / "queue.json", limit=16 * 1024 * 1024)
    job = state.get("jobs", {}).get(JOB_ID, {})
    result = validate(job, expected_sha=sha, now=now)
    if hashlib.sha256(prompt.encode()).hexdigest() != result["prompt_sha256"]:
        raise VideoError("aether_manual_release_prompt_changed")


def record_request():
    from aether_single import SingleQueue
    q = SingleQueue(ROOT)
    with q.lock():
        job = q._read()["jobs"][JOB_ID]
        expected = binding(job)
        folder = q.root / "jobs" / JOB_ID
        path = folder / RECEIPT
        if path.exists():
            return validate(job)  # Do not renew, reset or replace a prior request.
        if (job.get("status") != "rejected" or job.get("error") != "aether_single_publish_time_stale"
                or any(job.get(k) for k in ("music", "result", "upload", "approval"))
                or (folder / "youtube-session.json").exists()):
            raise VideoError("aether_manual_release_requires_unproduced_job")
        if any(p.is_symlink() for p in (path, *path.parents)) or not private_path_permissions(folder):
            raise VideoError("aether_manual_release_request_missing_or_unsafe")
        current = utc_now()
        record = {**expected, "issued_at": current.isoformat(),
                  "expires_at": (current + timedelta(hours=2)).isoformat(),
                  "prior_state": {"status": job["status"], "error": job["error"]}}
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(record))
            stream.flush()
            os.fsync(stream.fileno())
        return validate(job)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("record-request", "publish"))
    args = parser.parse_args()
    try:
        if args.command == "record-request":
            result = record_request()
        else:
            from aether_single import worker
            result = worker(publish=True, execute=True, manual_release_id=JOB_ID)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except VideoError as error:
        print(json.dumps({"status": "blocked", "error": str(error)}))
        raise SystemExit(2)
