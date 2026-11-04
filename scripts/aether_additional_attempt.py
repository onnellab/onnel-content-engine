"""Record the owner's single additional $0.08 attempt after lost Lyria output.

Prior bytes/dispatch claim are immutable. Acknowledgement accepts a possible
prior charge; it never asserts refund, zero cost, successful audio or publication.
Only the named first attempt is acknowledged. Any other unsettled request holds.
"""
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path

from short_video_pipeline import VideoError, canonical, load_json
from short_video_private_permissions import private_path_permissions

JOB_ID = "1f5cf414734a3a362b4db5cc"
TITLE = "The Pass Beyond the Racing Plains"
PRIOR_RUN = "20261104T061134Z-the-pass-beyond-the-racing-plains"
PRIOR_SHA = "3187515833849b4cc6c1bfbd52549ce8e58911eecabc3591929a80990254c17d"
REQUEST_SHA = "6f950d51a1abefe305826027464bcda5b3333df3259ff654d6013f2231724fa6"
ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/singles"
RECORD = "additional-generation-approval.json"
CLAIM = "additional-generation.claim"
EXPECTED = {
    "kind": "aether_owner_additional_attempt", "version": 1,
    "job_id": JOB_ID, "title": TITLE, "prior_run": PRIOR_RUN,
    "prior_manifest_sha256": PRIOR_SHA, "manual_request_sha256": REQUEST_SHA,
    "owner_reply": "승인", "additional_requests": 1,
    "additional_base_usd_limit": "0.08", "cumulative_base_usd_limit": "0.16",
    "prior_charge_status": "unknown_accepted_by_owner",
    "tax_and_currency_adjustments": "separate_unverified",
}


def folder():
    return ROOT / "jobs" / JOB_ID


def read_approval():
    path = folder() / RECORD
    if not path.exists():
        return None
    if (any(p.is_symlink() for p in (path, *path.parents))
            or not private_path_permissions(folder()) or not private_path_permissions(path)):
        raise VideoError("aether_additional_approval_unsafe")
    record = load_json(path, limit=16384)
    if (set(record) != set(EXPECTED) | {"approved_at"}
            or any(record.get(k) != v for k, v in EXPECTED.items())
            or type(record.get("additional_requests")) is not int
            or type(record.get("version")) is not int):
        raise VideoError("aether_additional_approval_changed")
    when = datetime.fromisoformat(record["approved_at"])
    if when.tzinfo is None or when > datetime.now(timezone.utc):
        raise VideoError("aether_additional_approval_time_invalid")
    old = folder() / "manual-release-request.json"
    if old.is_symlink() or hashlib.sha256(old.read_bytes()).hexdigest() != REQUEST_SHA:
        raise VideoError("aether_additional_original_approval_changed")
    return record


def acknowledged_prior(manifest):
    manifest = Path(manifest)
    completion = read_completion_request()
    if completion is not None:
        for run, sha in completion["prior_manifests"].items():
            if manifest == folder() / "lyria" / run / "manifest.json":
                return True  # Exact bytes were validated by read_completion_request.
    exact = folder() / "lyria" / PRIOR_RUN / "manifest.json"
    if manifest != exact or read_approval() is None:
        return False
    if manifest.is_symlink() or hashlib.sha256(manifest.read_bytes()).hexdigest() != PRIOR_SHA:
        raise VideoError("aether_additional_prior_manifest_changed")
    return True


def claim_additional(output_root, manual_release):
    """Called under the existing paid-request lock before creating any new run."""
    if Path(output_root) != folder() / "lyria":
        return None
    if read_completion_request() is not None:
        return claim_completion_attempt(manual_release)
    if read_approval() is None:
        return None
    if manual_release != {"job_id": JOB_ID, "request_sha256": REQUEST_SHA}:
        raise VideoError("aether_additional_manual_approval_required")
    # Exactly the first recorded attempt may predate this one-use claim.
    runs = list((folder() / "lyria").glob("*/manifest.json"))
    if len(runs) != 1 or not acknowledged_prior(runs[0]):
        raise VideoError("aether_additional_attempt_already_consumed")
    receipt = {"kind": "aether_additional_attempt_claim", "job_id": JOB_ID,
               "approval_sha256": hashlib.sha256((folder() / RECORD).read_bytes()).hexdigest(),
               "claimed_at": datetime.now(timezone.utc).isoformat()}
    try:
        fd = os.open(folder() / CLAIM, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise VideoError("aether_additional_attempt_already_consumed") from None
    with os.fdopen(fd, "wb") as stream:
        stream.write(canonical(receipt)); stream.flush(); os.fsync(stream.fileno())
    return receipt


def record_approval():
    from aether_single import SingleQueue
    from aether_manual_release import validate
    from aether_paid_guard import paid_request_lock
    q = SingleQueue(ROOT)
    with q.lock(), paid_request_lock():
        job = q._read()["jobs"][JOB_ID]
        validate(job)
        if read_approval() is not None:
            return read_approval()
        prior = folder() / "lyria" / PRIOR_RUN / "manifest.json"
        runs = list((folder() / "lyria").glob("*/manifest.json"))
        if (job.get("title") != TITLE or job.get("error") != "lyria_audio_missing"
                or any(job.get(k) for k in ("music", "result", "upload", "approval"))
                or runs != [prior] or prior.is_symlink()
                or hashlib.sha256(prior.read_bytes()).hexdigest() != PRIOR_SHA
                or (folder() / "youtube-session.json").exists()):
            raise VideoError("aether_additional_attempt_state_changed")
        record = {**EXPECTED, "approved_at": datetime.now(timezone.utc).isoformat()}
        fd = os.open(folder() / RECORD, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(record)); stream.flush(); os.fsync(stream.fileno())
        return read_approval()


# Latest explicit completion instruction, after both no-audio outcomes were
# disclosed. Limit it to ONE corrected request, not an unlimited retry policy.
COMPLETION_RECORD = "completion-request-20261104.json"
COMPLETION_CLAIM = "completion-request-20261104.claim"
COMPLETION_EXPECTED = {
    "kind": "aether_corrected_request_completion", "version": 1,
    "job_id": JOB_ID, "title": TITLE, "manual_request_sha256": REQUEST_SHA,
    "owner_request": "어떤 방법을 쓰든 누락곡 공개업로드하고 앞으로의 예약까지 정상으로 만들어",
    "additional_requests": 1, "additional_base_usd_limit": "0.08",
    "cumulative_possible_base_usd": "0.24", "tax_and_currency_adjustments": "separate_unverified",
    "prior_charge_status": "unknown_retained", "request_correction": "explicit_audio_response_modality",
    "prior_manifests": {
        PRIOR_RUN: PRIOR_SHA,
        "20261104T063331Z-the-pass-beyond-the-racing-plains": "c25d548a4d53753b32bd8c94cfa9129a8c3df2f06e7e71d30cd757e3fa421fef",
    },
}


def read_completion_request():
    path = folder() / COMPLETION_RECORD
    if not path.exists():
        return None
    if (any(p.is_symlink() for p in (path, *path.parents))
            or not private_path_permissions(folder()) or not private_path_permissions(path)):
        raise VideoError("aether_completion_receipt_unsafe")
    record = load_json(path, limit=16384)
    if (set(record) != set(COMPLETION_EXPECTED) | {"issued_at"}
            or any(record.get(k) != v for k, v in COMPLETION_EXPECTED.items())
            or type(record.get("additional_requests")) is not int
            or type(record.get("version")) is not int):
        raise VideoError("aether_completion_receipt_changed")
    when = datetime.fromisoformat(record["issued_at"])
    if when.tzinfo is None or when > datetime.now(timezone.utc):
        raise VideoError("aether_completion_receipt_time_invalid")
    manual = folder() / "manual-release-request.json"
    if manual.is_symlink() or hashlib.sha256(manual.read_bytes()).hexdigest() != REQUEST_SHA:
        raise VideoError("aether_completion_manual_request_changed")
    for run, expected_sha in record["prior_manifests"].items():
        manifest = folder() / "lyria" / run / "manifest.json"
        if (manifest.is_symlink() or manifest.parent.is_symlink()
                or hashlib.sha256(manifest.read_bytes()).hexdigest() != expected_sha):
            raise VideoError("aether_completion_prior_manifest_changed")
    return record


def _write_completion_record(path, record):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(canonical(record)); stream.flush(); os.fsync(stream.fileno())


def record_completion_request():
    from aether_single import SingleQueue
    from aether_manual_release import validate
    from aether_paid_guard import paid_request_lock
    queue = SingleQueue(ROOT)
    with queue.lock(), paid_request_lock():
        job = queue._read()["jobs"][JOB_ID]
        validate(job)
        existing = read_completion_request()
        if existing is not None:
            return existing
        if (job.get("title") != TITLE or job.get("error") != "lyria_audio_missing"
                or any(job.get(k) for k in ("music", "result", "upload", "approval"))
                or (folder() / "youtube-session.json").exists()):
            raise VideoError("aether_completion_job_changed")
        runs = {p.parent.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (folder() / "lyria").glob("*/manifest.json")}
        if runs != COMPLETION_EXPECTED["prior_manifests"]:
            raise VideoError("aether_completion_prior_manifest_changed")
        _write_completion_record(folder() / COMPLETION_RECORD,
            {**COMPLETION_EXPECTED, "issued_at": datetime.now(timezone.utc).isoformat()})
        return read_completion_request()


def claim_completion_attempt(manual_release):
    record = read_completion_request()
    if record is None or manual_release != {"job_id": JOB_ID, "request_sha256": REQUEST_SHA}:
        raise VideoError("aether_completion_manual_request_changed")
    runs = {p.parent.name for p in (folder() / "lyria").glob("*/manifest.json")}
    if runs != set(record["prior_manifests"]):
        raise VideoError("aether_completion_attempt_consumed")
    receipt = {"kind": "aether_corrected_request_claim", "job_id": JOB_ID,
               "approval_sha256": hashlib.sha256((folder() / COMPLETION_RECORD).read_bytes()).hexdigest(),
               "claimed_at": datetime.now(timezone.utc).isoformat()}
    try:
        _write_completion_record(folder() / COMPLETION_CLAIM, receipt)
    except FileExistsError:
        raise VideoError("aether_completion_attempt_consumed") from None
    return receipt


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="record-additional",
                        choices=("record-additional", "record-completion"))
    args = parser.parse_args()
    result = record_completion_request() if args.command == "record-completion" else record_approval()
    print(json.dumps(result, ensure_ascii=False, indent=2))
