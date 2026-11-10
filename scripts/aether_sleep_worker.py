"""Sleep lane adapter for the existing SingleQueue and resumable uploader.

No scheduler, credentials, transport or independent queue is defined here.
Review receipts must come from actual review, never from successful PCM rendering.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from zoneinfo import ZoneInfo

from aether_sleep_contract import CONCEPTS, SERIES, SOURCE_KIND, PROPOSED_SLOTS, validate_identity, today_exception_valid


def brief_for(job):
    validate_identity(job)
    return {
        "locale": "en", "content_kind": "aether_single", "youtube_profile": "aether_inn",
        "test_only": False, "source_kind": SOURCE_KIND, "series": SERIES,
        "concept_id": job["concept_id"],
        "title": f'{job["title"]} | 30 Minute Fantasy Sleep Music | Aether Inn Sleep',
        "description": (f'{job["title"]} from Aether Inn Sleep.\n\n'
                        'One newly composed short AI-generated instrumental sleep track repeated '
                        'with gentle crossfades into a 30-minute video. '
                        'Not 30 minutes of unique generated music.\n\n'
                        'Quiet fantasy ambience for rest. No medical or sleep-treatment claims.\n'
                        '#fantasysleepmusic #ambientmusic #aimusic'),
    }


def require_window(job, now=None):
    validate_identity(job)
    now = now or datetime.now(ZoneInfo("Asia/Seoul"))
    if now.tzinfo is None:
        raise ValueError("sleep_timezone_required")
    expected_slot = PROPOSED_SLOTS[[x[0] for x in CONCEPTS].index(job["concept_id"])]
    if job.get("slot") != expected_slot:
        raise ValueError("sleep_slot_invalid")
    if today_exception_valid(now, job["concept_id"], job["slot"]):
        return "public"
    local = now.astimezone(ZoneInfo("Asia/Seoul"))
    if local.date().isoformat() != job["slot"] or local.hour >= 9:
        raise ValueError("sleep_publication_window_closed")
    return "private"


def _sha(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("sleep_asset_missing")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_source(source, expected_sha256, destination):
    """Pin provider bytes, bounded local decode, preserve original provenance."""
    from aether_sleep_render import source_info
    source, destination = Path(source), Path(destination)
    if source.suffix.lower() not in {".mp3", ".wav"} or source.stat().st_size > 64000000:
        raise ValueError("sleep_source_format_invalid")
    if _sha(source) != expected_sha256:
        raise ValueError("sleep_source_integrity")
    if destination.exists() or destination.is_symlink():
        raise ValueError("sleep_pcm_output_exists")
    with tempfile.TemporaryDirectory(prefix=".sleep-decode-", dir=destination.parent) as temp:
        snapshot = Path(temp) / ("source" + source.suffix.lower())
        staged = Path(temp) / "decoded.wav"
        shutil.copyfile(source, snapshot)
        if _sha(snapshot) != expected_sha256:
            raise ValueError("sleep_source_integrity")
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n", "-threads", "1",
                        "-protocol_whitelist", "file,pipe", "-f", source.suffix.lower()[1:],
                        "-i", str(snapshot), "-map", "0:a:0", "-vn", "-t", "185",
                        "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(staged)],
                       check=True, capture_output=True, timeout=120)
        pcm_sha = _sha(staged)
        info = source_info(staged, pcm_sha)  # rejects the 185s cap, never silently truncates
        os.chmod(staged, 0o600)
        with staged.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(staged, destination)
    return {"path": str(destination), "sha256": pcm_sha,
            "original_path": str(source), "original_sha256": expected_sha256,
            "duration_seconds": info["duration_seconds"], "generation_count": 1,
            "source_kind": SOURCE_KIND}


def require_review(folder, job, stage, bindings):
    """Read a private, exact-job and exact-bytes review; never synthesize one."""
    path = Path(folder) / f"sleep-{stage}-review.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError(f"sleep_{stage}_review_required")
    if path.stat().st_size > 65536:
        raise ValueError("sleep_review_invalid")
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("sleep_review_invalid")
            out[key] = value
        return out
    receipt = json.loads(path.read_text(), object_pairs_hook=pairs)
    checks = {
        "source": ["purpose_composed_sleep", "commercial_rights_checked", "actual_audio_listened",
                   "no_abrupt_swells", "no_prominent_beat", "no_voice", "sleep_suitable"],
        "loop": ["actual_seams_listened", "endpoint_fades_listened", "stable_quiet_dynamics"],
        "video": ["actual_video_checked", "static_sleep_art_suitable", "audio_video_sync_checked"],
    }[stage]
    if (not isinstance(receipt, dict) or receipt.get("job_id") != job["id"]
            or receipt.get("series") != SERIES or receipt.get("stage") != stage
            or receipt.get("sha256") != bindings
            or receipt.get("accepted") is not True
            or any(receipt.get(key) is not True for key in checks)
            or not all(isinstance(receipt.get(key), str) and receipt[key].strip()
                       for key in ("reviewer", "reviewed_at", "authority_reference"))):
        raise ValueError("sleep_review_invalid")
    for name, expected in bindings.items():
        if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("sleep_review_invalid")
    return {"sha256": _sha(path), "reviewer": receipt["reviewer"], "authority_reference": receipt["authority_reference"]}


def verify_source_provenance(job, folder):
    from aether_sleep_guard import validate_generated_sleep
    source = job["music"]
    manifest = Path(source["manifest"])
    if manifest.parent.parent != Path(folder) / "lyria":
        raise ValueError("sleep_manifest_scope_invalid")
    generated = validate_generated_sleep(manifest, concept_id=job["concept_id"],
                                         job_id=job["id"], slot=job["slot"])
    candidate = generated["candidates"][0]
    if candidate["sha256"] != source["original_sha256"] or candidate["file"] != source["original_path"]:
        raise ValueError("sleep_source_provenance_invalid")


def verify_media(job, folder):
    verify_source_provenance(job, folder)
    validate_identity(job)
    source = job["music"]
    loop = job["sleep_loop"]
    cover = job["cover"]
    if _sha(source["original_path"]) != source["original_sha256"] or _sha(source["path"]) != source["sha256"] or _sha(loop["path"]) != loop["sha256"] or _sha(cover["path"]) != cover["sha256"]:
        raise ValueError("sleep_media_integrity")
    require_review(folder, job, "source", {"original": source["original_sha256"], "source": source["sha256"]})
    require_review(folder, job, "loop", {"source": source["sha256"], "loop": loop["sha256"]})
    video_sha = _sha(Path(folder) / "video.mp4")
    if video_sha != job["result"]["sha256"]["video.mp4"]:
        raise ValueError("sleep_video_integrity")
    require_review(folder, job, "video", {"source": source["sha256"], "loop": loop["sha256"],
                                        "cover": cover["sha256"], "video": video_sha})


def run_locked(q, state, job, *, publish, api_factory=None, reconcile_only=False):
    """Caller already holds SingleQueue.lock, including ordinary reconciliation."""
    import aether_single as single
    from lyria_generate import generate_sleep
    from aether_sleep_render import render as render_loop, source_info
    from aether_sleep_contract import require_activation
    folder = single.directory(q.root / "jobs" / job["id"])
    def save():
        single.atomic_json(q.state_path, state)
    try:
        validate_identity(job)
        if not job.get("upload"):
            try:
                require_window(job)
            except ValueError as error:
                if str(error) != "sleep_publication_window_closed":
                    raise
                # A missed pilot slot cannot block future fantasy singles.
                # Never bury a charge whose outcome is unresolved.
                single.paid_guard.require_no_unsettled_intents(single_root=q.root)
                for manifest in (folder / "lyria").glob("*/manifest.json"):
                    if single.load_json(manifest).get("state") not in {"generated", "not_sent"}:
                        raise ValueError("sleep_generation_uncertain")
                job.update(status="rejected", error="sleep_publication_window_closed")
                save()
                return {"profile": "aether_inn", "status": "idle", "created_new_job": False,
                        "retired_sleep_job": job["id"]}
        if reconcile_only and not job.get("upload") and not job.get("publish_requested"):
            return {"profile": "aether_inn", "status": "idle", "created_new_job": False,
                    "sleep_render_only_job": job["id"]}
        require_activation()
        api = (api_factory or (lambda: single.YouTube(profile="aether_inn")))()
        if getattr(api, "profile", None) != "aether_inn":
            raise ValueError("aether_profile_required")
        api.verify()
        if not job.get("upload"):
            require_window(job)
            single.paid_guard.require_no_unsettled_intents(single_root=q.root)
            single.require_no_owned_title_match(api, job["title"])
            single.approved_cover(job["title"], single.ASSETS_ROOT)
            if not job.get("music"):
                # Exactly one manifest; never ordinary recovery's extra-attempt escape.
                manifests = list((folder / "lyria").glob("*/manifest.json"))
                if len(manifests) > 1:
                    raise ValueError("sleep_paid_retry_forbidden")
                from aether_sleep_guard import validate_generated_sleep
                generated = validate_generated_sleep(manifests[0], concept_id=job["concept_id"],
                    job_id=job["id"], slot=job["slot"]) if manifests else generate_sleep(
                    job["concept_id"], execute=True, output_root=folder / "lyria", slot=job["slot"], job_id=job["id"])
                if generated.get("state") != "generated" or len(generated.get("candidates", [])) != 1:
                    raise ValueError("sleep_generation_uncertain")
                candidate = generated["candidates"][0]
                path = Path(candidate["file"])
                # Generated sources stay inside this exact job's private generation tree.
                if path.is_symlink() or path.resolve().parent.parent != (folder / "lyria").resolve():
                    raise ValueError("sleep_source_scope_invalid")
                if candidate["sha256"] in single._history_hashes(state):
                    raise ValueError("sleep_source_duplicate")
                if any((j.get("music") or {}).get("original_sha256") == candidate["sha256"]
                       for j in state["jobs"].values()):
                    raise ValueError("sleep_source_duplicate")
                job["music"] = decode_source(path, candidate["sha256"], folder / "sleep-source.wav")
                job["music"]["manifest"] = generated["manifest"]
                job["status"] = "sleep_source_pending_review"
                save()
            verify_source_provenance(job, folder)
            music = job["music"]
            if _sha(music["original_path"]) != music["original_sha256"] or _sha(music["path"]) != music["sha256"]:
                raise ValueError("sleep_source_integrity")
            require_review(folder, job, "source", {"original": music["original_sha256"], "source": music["sha256"]})
            if not job.get("sleep_loop"):
                # Existing orphan output is not silently adopted or overwritten.
                loop_path = folder / "sleep-loop.wav"
                result = render_loop(music["path"], loop_path, music["sha256"])
                job["sleep_loop"] = {"path": str(loop_path), "sha256": result["output_sha256"], "duration_seconds": 1800}
                job["status"] = "sleep_loop_pending_review"
                save()
            loop = job["sleep_loop"]
            if _sha(loop["path"]) != loop["sha256"]:
                raise ValueError("sleep_loop_integrity")
            require_review(folder, job, "loop", {"source": music["sha256"], "loop": loop["sha256"]})
            if not job.get("cover"):
                job["cover"] = single.import_existing_cover(job["title"], job["style"], job["lane"], folder / "cover", execute=True)
                save()
            if _sha(job["cover"]["path"]) != job["cover"]["sha256"]:
                raise ValueError("sleep_cover_integrity")
            if not job.get("result"):
                result = single.render_single(Path(loop["path"]), Path(job["cover"]["path"]), folder)
                result.update(job_id=job["id"], upload_eligible=False)
                job.update(result=result, status="sleep_video_pending_review", upload_eligible=False)
                save()
        verify_media(job, folder)
        if publish:
            uploader = single.Uploader(q, lambda: single.YouTube(profile="aether_inn"))
            if not job.get("upload"):
                privacy = require_window(job)
                if (folder / "youtube-session.json").exists():
                    raise ValueError("manual_reconcile_required")
                single.require_no_owned_title_match(api, job["title"])
                require_window(job)
                job["result"]["upload_eligible"] = True
                job["upload_eligible"] = True
                job["status"] = "rendered"
                save()
                choices = {"made_for_kids": False, "synthetic_media": True, "privacy": privacy,
                           "publish_at": None if privacy == "public" else single.scheduled_publish_at(job["slot"]),
                           "publish_approved": True}
                policy_hash = single.digest(single.policy_for(job))
                if not job.get("approval"):
                    uploader.bind_approval_locked(state, job, choices, mode="automatic_fail_closed", policy_hash=policy_hash)
                elif job["approval"].get("policy_hash") != policy_hash or job["approval"].get("choices") != choices:
                    raise ValueError("sleep_upload_policy_changed")
            q._render(state, job, None)
            uploader.run_locked(state, job, reconcile=bool(job.get("upload")), api=api)
            if job.get("upload", {}).get("video_id") and job["status"] not in {"rejected", "reconcile_required", "blocked"}:
                single.thumbnail(q, state, job, api)
        return {"profile": "aether_inn", "series": SERIES, "status": job["status"], "job_id": job["id"],
                "slot": job["slot"], "video_id": job.get("upload", {}).get("video_id"),
                "publication_complete": job["status"] == "published" and job.get("thumbnail_status") == "set"}
    except (ValueError, OSError, single.VideoError) as error:
        if str(error) in {"sleep_source_review_required", "sleep_loop_review_required", "sleep_video_review_required"}:
            stage = str(error).split("_")[1]
            job.update(status=f"sleep_{stage}_pending_review", error=str(error))
            save()
            return {"profile": "aether_inn", "series": SERIES, "status": job["status"],
                    "job_id": job["id"], "slot": job["slot"], "review_required": stage,
                    "publication_complete": False}
        job.update(status="reconcile_required" if job.get("upload") else "blocked", error=str(error))
        save()
        raise single.VideoError(str(error)) from error


def worker(*, root=None, concept_id, slot, execute=False, publish=False, api_factory=None):
    import aether_single as single
    from aether_sleep_plan import build_plan
    if not execute:
        return {"status": "planned", "paid_dispatch_allowed": False, "series": SERIES}
    from aether_sleep_contract import require_activation
    require_activation()
    q = single.SingleQueue(single.ROOT if root is None else root)
    concept = next((x for x in build_plan()["drafts"] if x["id"] == concept_id), None)
    if concept is None:
        raise single.VideoError("sleep_concept_invalid")
    seed = {"profile": "aether_inn", "series": SERIES, "source_kind": SOURCE_KIND,
            "concept_id": concept_id, "title": concept["title"], "slot": slot,
            "duration_seconds": 1800, "style": concept["prompt"], "lane": "sleep"}
    key = single.digest(seed)[:24]
    with q.lock():
        state = q._read()
        matches = [j for j in state["jobs"].values() if j.get("concept_id") == concept_id]
        if matches and (len(matches) != 1 or matches[0]["id"] != key):
            raise single.VideoError("sleep_concept_already_reserved")
        if any(j["id"] != key and (j["status"] not in single.FINAL or
               (j.get("upload") and j.get("thumbnail_status") != "set" and j["status"] != "rejected"))
               for j in state["jobs"].values()):
            raise single.VideoError("aether_single_existing_job_unsettled")
        job = state["jobs"].get(key)
        if job is None:
            require_window(seed)
            # Missing account evidence/art cannot create an unfinished queue job.
            from lyria_config import CONFIG_PATH, load_settings
            from aether_sleep_guard import load_cost_authorization, require_affordable_pilot
            settings = load_settings(CONFIG_PATH)
            if not settings or settings.get("enabled") is not True:
                raise single.VideoError("lyria_generation_disabled")
            require_affordable_pilot(load_cost_authorization(settings["project_id"]))
            single.approved_cover(seed["title"], single.ASSETS_ROOT)
            from aether_sleep_request import gui_requested
            # Exact same-day owner request may follow a settled fantasy single.
            # Other sleep concepts, dates and unfinished jobs remain excluded.
            if any(j["slot"] == slot and not (
                    gui_requested() and slot == PROPOSED_SLOTS[0]
                    and concept_id == CONCEPTS[0][0]
                    and j.get("source_kind", "new_lyria") == "new_lyria"
                    and j["status"] in single.FINAL
                    and (not j.get("upload") or j.get("thumbnail_status") == "set"))
                   for j in state["jobs"].values()):
                raise single.VideoError("sleep_slot_already_used")
            job = {**seed, "id": key, "status": "planned", "publish_requested": publish,
                   "music": None, "cover": None, "result": None, "upload_eligible": False}
            job["brief"] = brief_for(job)
            job["payload_hash"] = single.digest(job["brief"])
            state["jobs"][key] = job
            single.atomic_json(q.state_path, state)
        if publish and not job.get("publish_requested"):
            job["publish_requested"] = True
            single.atomic_json(q.state_path, state)
        return run_locked(q, state, job, publish=publish, api_factory=api_factory)
