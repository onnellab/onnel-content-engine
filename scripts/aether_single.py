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
import shutil
import stat
import time
import unicodedata
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from aether_compilation import thumbnail
from aether_offline_audio_review import review_audio
from aether_compose import audio_duration, checked_asset, media_info, validate_output
from aether_cover import lane_direction
from aether_existing_cover import ASSETS_ROOT, approved_cover, import_existing_cover
from aether_planner import inspect_candidate, read_catalog
from lyria_generate import generate as generate_music
import aether_paid_guard as paid_guard
from lyria_config import connection_status as lyria_connection_status
from short_video_credentials import credential_status
from short_video_pipeline import VideoError, atomic_json, digest, file_hash, load_json, run_process
from short_video_youtube import API, YouTube, Uploader, UploadError
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
    "privacy": "private",
    "publish_schedule": "09:00 Asia/Seoul",
}
FINAL = {"published", "uploaded_private", "uploaded_unlisted", "forced_private", "rejected"}
BACKLOG_LANES = {
    "Beyond the Road of Falling Petals": "quiet_road",
    "The First Lantern of Autumn": "quiet_road",
    "Beyond the Silent Stone Gate": "frontier_surge",
    "The Meadow Where Skylarks Sing": "quiet_road",
    "The Old Library of Everlight": "night_wonder",
    "When the Northern Lights Returned": "night_wonder",
}
MYBOX_ROOT = Path.home() / "Library/CloudStorage/MYBOX-yungela1"


def _clean(value: str, name: str, limit: int) -> str:
    if not isinstance(value, str):
        raise VideoError(f"aether_single_{name}_invalid")
    value = " ".join(value.strip().split())
    if not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise VideoError(f"aether_single_{name}_invalid")
    return value


def _nfc_child(parent: Path, name: str, *, directory_only: bool = False) -> Path | None:
    if not parent.is_dir():
        return None
    expected = unicodedata.normalize("NFC", name)
    direct = parent / expected
    try:
        if direct.exists() and (not directory_only or direct.is_dir()):
            return direct
    except OSError:
        pass
    matches = []
    for child in parent.iterdir():
        if unicodedata.normalize("NFC", child.name) != expected:
            continue
        if directory_only and not child.is_dir():
            continue
        matches.append(child)
    if len(matches) > 1:
        raise VideoError("aether_single_backlog_path_ambiguous")
    return matches[0] if matches else None


def _is_dataless(path: Path) -> bool:
    try:
        flags = getattr(path.stat(), "st_flags", 0)
    except OSError:
        raise VideoError("aether_single_backlog_wav_unavailable") from None
    return bool(flags & getattr(stat, "SF_DATALESS", 0))


def _warm_mybox_provider() -> bool:
    app = Path("/Applications/MYBOX.app")
    if not app.is_dir():
        return False
    try:
        run_process(["/usr/bin/open", "-g", "-a", "MYBOX"], timeout=15)
    except VideoError:
        return False
    time.sleep(1)
    return True


def resolve_backlog_wav(title: str, *, root: Path = MYBOX_ROOT) -> Path:
    title = _clean(title, "title", 60)
    parent = Path(root)
    for name in ("개인 폴더", "Aether Inn", "01_Audio_Master"):
        child = _nfc_child(parent, name, directory_only=True)
        if child is None:
            raise VideoError("aether_single_backlog_wav_not_synced")
        parent = child
    source = _nfc_child(parent, f"{title}.wav")
    if source is None or source.is_symlink() or not source.is_file():
        raise VideoError("aether_single_backlog_wav_not_synced")
    return source


def reusable_backlog_master(title: str, singles_root: Path, assets_root: Path) -> dict | None:
    """Read retained canonical masters, never revive or rewrite their old jobs."""
    title = backlog_catalog_entry(title)["title"]
    root, assets = Path(singles_root), Path(assets_root)
    queue, approval = root / "queue.json", assets / "approval.json"
    for path in (queue, approval):
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise VideoError("aether_single_backlog_source_unsafe")
        if not path.is_file():
            return None
    state = load_json(queue, limit=2 * 1024 * 1024)
    rights = load_json(approval, limit=2 * 1024 * 1024)
    if (state.get("schema_version") != 1 or not isinstance(state.get("jobs"), dict)
            or rights.get("schema_version") != 1 or rights.get("profile") != "aether_inn"
            or not isinstance(rights.get("tracks"), dict)):
        raise VideoError("aether_single_backlog_reuse_record_invalid")
    if not any(isinstance(row, dict) and row.get("title") == title
               and row.get("commercial_use_confirmed") is True
               for row in rights["tracks"].values()):
        return None
    candidates = []
    # A recovered canonical WAV may be staged without creating a queue job.
    # The existing per-title rights row binds it; quality still runs on import.
    for row in rights["tracks"].values():
        if (not isinstance(row, dict) or row.get("title") != title
                or row.get("commercial_use_confirmed") is not True or "local_master" not in row):
            continue
        spec = row["local_master"]
        if (not isinstance(spec, dict) or spec.get("source_filename") != title + ".wav"
                or not isinstance(spec.get("path"), str)):
            raise VideoError("aether_single_backlog_reuse_record_invalid")
        relative = Path(spec["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.name != title + ".wav":
            raise VideoError("aether_single_backlog_source_unsafe")
        source = assets / relative
        if any(part.is_symlink() for part in (source, *source.parents)):
            raise VideoError("aether_single_backlog_source_unsafe")
        if not source.is_file() or _is_dataless(source):
            raise VideoError("aether_single_backlog_source_integrity")
        source = checked_asset(assets, {**spec, "commercial_use_confirmed": True}, {".wav"})
        candidates.append({"path": source, "sha256": spec["sha256"], "source_kind": "staged_canonical_wav"})
    for key, job in state["jobs"].items():
        if not isinstance(job, dict) or job.get("title") != title or job.get("source_kind") != "backlog_wav":
            continue
        music = job.get("music")
        if not isinstance(music, dict):
            continue
        if (not re.fullmatch(r"[0-9a-f]{24}", key) or job.get("id") != key
                or job.get("source_filename") != title + ".wav"
                or music.get("source_kind") != "backlog_wav"
                or music.get("source_filename") != title + ".wav"):
            raise VideoError("aether_single_backlog_reuse_record_invalid")
        source = root / "jobs" / key / "source/master.wav"
        if (music.get("path") != str(source)
                or any(part.is_symlink() for part in (source, *source.parents))):
            raise VideoError("aether_single_backlog_source_unsafe")
        if not source.is_file() or _is_dataless(source):
            continue
        expected = music.get("sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected) or file_hash(source) != expected:
            raise VideoError("aether_single_backlog_source_integrity")
        candidates.append({"path": source, "sha256": expected, "job_id": key})
    if len({candidate["sha256"] for candidate in candidates}) > 1:
        raise VideoError("aether_single_backlog_source_ambiguous")
    return candidates[0] if candidates else None


def backlog_catalog_entry(title: str) -> dict:
    title = _clean(title, "title", 60)
    wanted = unicodedata.normalize("NFC", title)
    rows = [row for row in read_catalog() if unicodedata.normalize("NFC", row["title"]) == wanted]
    if len(rows) != 1 or title not in BACKLOG_LANES:
        raise VideoError("aether_single_backlog_title_not_registered")
    return rows[0]


def _normalized_title(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def find_existing_public_video(api: YouTube, title: str) -> dict | None:
    wanted = _normalized_title(_clean(title, "title", 60))
    _, _, found = api.request(
        "GET",
        API + "search?" + urlencode({
            "part": "id", "channelId": api.channel, "q": title,
            "type": "video", "maxResults": "25",
        }),
        headers=api.headers(), retry=True,
    )
    ids = [
        item.get("id", {}).get("videoId")
        for item in found.get("items", [])
        if item.get("id", {}).get("videoId")
    ]
    if not ids:
        return None
    _, _, videos = api.request(
        "GET",
        API + "videos?" + urlencode({
            "part": "snippet,status", "id": ",".join(ids), "maxResults": "25",
        }),
        headers=api.headers(), retry=True,
    )
    for item in videos.get("items", []):
        snippet = item.get("snippet", {})
        actual = _normalized_title(str(snippet.get("title", "")))
        if (
            snippet.get("channelId") == api.channel
            and item.get("status", {}).get("privacyStatus") == "public"
            and re.match(rf"^{re.escape(wanted)}(?:$|\W)", actual)
        ):
            return {
                "video_id": item.get("id"),
                "title": snippet.get("title", ""),
                "published_at": snippet.get("publishedAt", ""),
            }
    return None


class RemoteInventoryUnverified(VideoError):
    """Private, bounded diagnostics for a failed owned-uploads preflight.

    The original blocker remains stable for existing callers. Do not record
    video titles, video IDs, OAuth material, request URLs or provider payloads.
    """
    def __init__(self, stage: str, *, pages_checked: int, videos_seen: int,
                 missing_details: int = 0):
        self.diagnostic = {
            "stage": stage,
            "pages_checked": pages_checked,
            "videos_seen": videos_seen,
            "missing_details": missing_details,
        }
        super().__init__("aether_single_remote_inventory_unverified")


def require_no_owned_title_match(api: YouTube, title: str) -> None:
    """Verify every owned upload, including private/scheduled videos, before spend.

    An incomplete or ambiguous owner inventory is a HOLD. Use only the API
    fields needed for the comparison (no privileged processingDetails or large
    video descriptions). A bounded, READ-ONLY second lookup may recover an
    omitted item from the first bulk response, but never treats an unobserved
    video as absent. No external write or job creation occurs here.
    """
    wanted = _normalized_title(_clean(title, "title", 60))
    pages_checked, seen = 0, set()

    def hold(stage: str, *, missing_details: int = 0):
        raise RemoteInventoryUnverified(stage, pages_checked=pages_checked,
                                        videos_seen=len(seen),
                                        missing_details=missing_details)

    _, _, channels = api.request("GET", API + "channels?" + urlencode({
        "part": "id,contentDetails,statistics", "mine": "true",
        "fields": "items(id,contentDetails(relatedPlaylists(uploads)),statistics(videoCount))",
    }), headers=api.headers(), retry=True)
    items = channels.get("items")
    if (not isinstance(items, list) or len(items) != 1
            or not isinstance(items[0], dict) or items[0].get("id") != api.channel):
        hold("owner_channel_mismatch")
    owner = items[0]
    details = owner.get("contentDetails")
    related = details.get("relatedPlaylists") if isinstance(details, dict) else None
    playlist = related.get("uploads") if isinstance(related, dict) else None
    if not isinstance(playlist, str) or not re.fullmatch(r"UU[A-Za-z0-9_-]{22}", playlist):
        hold("owner_uploads_playlist_invalid")
    stats = owner.get("statistics") or {}
    public_count = stats.get("videoCount") if isinstance(stats, dict) else None
    if public_count is not None and (not isinstance(public_count, str) or not public_count.isdigit()):
        hold("owner_public_count_invalid")

    token, visited = None, set()
    for _ in range(100):  # Bounded complete pagination. Never accept partial pages.
        pages_checked += 1
        query = {
            "part": "contentDetails", "playlistId": playlist, "maxResults": "50",
            "fields": "items(contentDetails(videoId)),nextPageToken",
        }
        if token:
            query["pageToken"] = token
        _, _, page = api.request("GET", API + "playlistItems?" + urlencode(query),
                                 headers=api.headers(), retry=True)
        rows = page.get("items")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            hold("uploads_page_invalid")
        ids = [
            row.get("contentDetails", {}).get("videoId")
            if isinstance(row.get("contentDetails"), dict) else None
            for row in rows
        ]
        if (any(not isinstance(value, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{11}", value)
                or value in seen for value in ids)
                or len(ids) != len(set(ids))):
            hold("uploads_ids_invalid_or_duplicate")
        seen.update(ids)
        if ids:
            # fields keeps the response small and avoids an unnecessary,
            # owner-only processingDetails permission surface.
            def details_for(video_ids):
                _, _, response = api.request("GET", API + "videos?" + urlencode({
                    "part": "snippet,status", "id": ",".join(video_ids),
                    "fields": "items(id,snippet(channelId,title),status(privacyStatus))",
                }), headers=api.headers(), retry=True)
                found = response.get("items")
                if not isinstance(found, list) or any(not isinstance(item, dict) for item in found):
                    hold("video_details_invalid")
                keys = [item.get("id") for item in found]
                if (any(not isinstance(key, str) for key in keys)
                        or len(keys) != len(set(keys))
                        or not set(keys).issubset(video_ids)):
                    hold("video_details_ids_mismatch")
                return {item["id"]: item for item in found}

            found = details_for(ids)
            missing = [id_ for id_ in ids if id_ not in found]
            if missing:
                # An inconsistent bulk GET may be transient. A second bounded
                # GET is read-only; a second missing result is a hard HOLD.
                found.update(details_for(missing))
                missing = [id_ for id_ in ids if id_ not in found]
            if missing:
                hold("video_details_missing_after_second_read",
                     missing_details=len(missing))
            for row in found.values():
                snippet, status = row.get("snippet"), row.get("status")
                if (not isinstance(snippet, dict) or not isinstance(status, dict)
                        or snippet.get("channelId") != api.channel):
                    hold("video_owner_or_metadata_mismatch")
                actual = snippet.get("title")
                if (not isinstance(actual, str) or not actual.strip()
                        or status.get("privacyStatus") not in ("public", "private", "unlisted")):
                    hold("video_title_or_privacy_invalid")
                if re.match(rf"^{re.escape(wanted)}(?:$|\W)", _normalized_title(actual)):
                    raise VideoError("aether_single_existing_remote_title_requires_reconcile")
        token = page.get("nextPageToken")
        if token is None:
            if public_count is not None and len(seen) < int(public_count):
                hold("uploads_less_than_public_count",
                     missing_details=int(public_count) - len(seen))
            return
        if not isinstance(token, str) or not token or len(token) > 2048 or token in visited:
            hold("uploads_page_token_invalid_or_repeated")
        visited.add(token)
    raise VideoError("aether_single_remote_inventory_incomplete")



def _hydrate_dataless_backlog_wav(source: Path) -> None:
    """Read the entire MYBOX placeholder before copying its canonical WAV.

    Merely launching MYBOX and sleeping is not sufficient: FileProvider may
    still show a size for a dataless file whose bytes have not downloaded.
    Reading in bounded chunks triggers hydration, with limited retries for
    transient provider errors. Never fall back to new music generation.
    """
    _warm_mybox_provider()
    for attempt in range(3):
        try:
            with source.open("rb") as stream:
                while stream.read(2 * 1024 * 1024):
                    pass
            return
        except OSError:
            if attempt == 2:
                raise VideoError("aether_single_backlog_wav_unavailable") from None
            time.sleep(2 * (attempt + 1))



def import_backlog_master(source: Path, folder: Path, expected_duration: float, *, expected_sha256=None) -> dict:
    source = Path(source)
    if source.suffix.lower() != ".wav" or source.is_symlink() or not source.is_file():
        raise VideoError("aether_single_backlog_wav_not_synced")
    source_was_dataless = _is_dataless(source)
    if source_was_dataless:
        _hydrate_dataless_backlog_wav(source)
    target_dir = directory(Path(folder) / "source")
    target = target_dir / "master.wav"
    partial = target_dir / "master.partial.wav"
    if target.is_symlink() or partial.is_symlink():
        raise VideoError("aether_single_backlog_source_unsafe")
    partial.unlink(missing_ok=True)
    try:
        shutil.copyfile(source, partial)
        os.chmod(partial, 0o600)
        source_hash = file_hash(partial)
        if expected_sha256 is not None and source_hash != expected_sha256:
            raise VideoError("aether_single_backlog_source_integrity")
        duration = audio_duration(partial)
        if abs(float(duration) - float(expected_duration)) > 5:
            raise VideoError("aether_single_backlog_duration_mismatch")
        review = review_audio(partial, expected_duration=duration)
        atomic_json(Path(folder) / "audio_review.json", review)
        if not review.get("accepted"):
            raise VideoError("aether_single_offline_audio_rejected")
        if target.exists():
            if not target.is_file() or file_hash(target) != source_hash:
                raise VideoError("aether_single_backlog_source_integrity")
            partial.unlink(missing_ok=True)
        else:
            partial.replace(target)
    except VideoError as error:
        partial.unlink(missing_ok=True)
        if str(error) in {
            "aether_single_backlog_duration_mismatch",
            "aether_single_backlog_source_integrity",
            "aether_single_offline_audio_rejected",
        }:
            raise
        raise VideoError("aether_single_backlog_wav_unavailable") from None
    except OSError:
        partial.unlink(missing_ok=True)
        raise VideoError("aether_single_backlog_wav_unavailable") from None
    return {
        "candidate_index": 0,
        "path": str(target),
        "duration_seconds": duration,
        "sha256": source_hash,
        "source_kind": "backlog_wav",
        "source_filename": source.name,
        "source_was_dataless": source_was_dataless,
        "review": review,
    }


def policy_for(job: dict) -> dict:
    policy = dict(POLICY)
    if job.get("source_kind") == "backlog_wav":
        policy.update({
            "version": 2,
            "kind": "catalog_backlog_single",
            "music_provider": "canonical_wav_master",
        })
    if (job.get("cover") or {}).get("source_kind") == "existing_approved_cover":
        policy.update({"version": 3, "cover_provider": "owner_approved_existing_cover"})
        if job["cover"].get("quality_basis") == "dot_delegated_visual_v1":
            policy.update({"version": 4, "cover_provider": "dot_reviewed_existing_cover"})
    return policy


def _scheduled_local(slot: str) -> datetime:
    try:
        return datetime.strptime(slot, "%Y-%m-%d").replace(
            hour=9, minute=0, second=0, microsecond=0,
            tzinfo=ZoneInfo("Asia/Seoul"),
        )
    except (TypeError, ValueError):
        raise VideoError("aether_single_slot_invalid") from None


def publish_slot_stale(slot: str, *, now: datetime | None = None) -> bool:
    current = now or datetime.now(ZoneInfo("Asia/Seoul"))
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZoneInfo("Asia/Seoul"))
    return current.astimezone(ZoneInfo("Asia/Seoul")) >= _scheduled_local(slot)


def scheduled_publish_at(slot: str) -> str:
    return _scheduled_local(slot).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")



def _lane_registry() -> dict:
    path = Path(__file__).resolve().parents[1] / "data" / "aether_single_lanes.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    lanes = {row["id"]: row for row in data.get("lanes", []) if isinstance(row, dict) and isinstance(row.get("id"), str)}
    if not lanes:
        raise VideoError("aether_single_lane_registry_invalid")
    return {"rules": data.get("rules", {}), "lanes": lanes}


def enforce_lane_rotation(state: dict, lane: str) -> None:
    registry = _lane_registry()
    if lane not in registry["lanes"]:
        raise VideoError("aether_single_lane_invalid")
    history = sorted(
        [job for job in state.get("jobs", {}).values() if job.get("lane") in registry["lanes"]],
        key=lambda job: (str(job.get("slot", "")), str(job.get("id", ""))),
    )
    recent = history[-7:]
    current = registry["lanes"][lane]
    max_calm = int(registry["rules"].get("max_consecutive_calm", 2))
    tail = history[-max_calm:] if max_calm > 0 else []
    if len(tail) == max_calm and all(registry["lanes"][job["lane"]].get("energy") == "calm" for job in tail):
        if current.get("energy") == "calm":
            raise VideoError("aether_single_calm_streak_blocked")
    if len(recent) == 7:
        high = sum(registry["lanes"][job["lane"]].get("energy") == "high_motion" for job in recent)
        traversal = sum(bool(registry["lanes"][job["lane"]].get("traversal")) for job in recent)
        if high < int(registry["rules"].get("min_high_motion_in_window", 3)) and current.get("energy") != "high_motion":
            raise VideoError("aether_single_high_motion_rotation_required")
        if traversal < int(registry["rules"].get("min_traversal_in_window", 2)) and not current.get("traversal"):
            raise VideoError("aether_single_traversal_rotation_required")

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
    brief = {
        "locale": "en",
        "content_kind": "aether_single",
        "youtube_profile": "aether_inn",
        "test_only": False,
        "title": youtube_title,
        "description": description,
    }
    if job.get("source_kind") == "backlog_wav":
        brief.update({
            "source_kind": "backlog_wav",
            "source_filename": job.get("source_filename"),
            "source_expected_duration": job.get("source_expected_duration"),
        })
    return brief


def _history_hashes(state: dict) -> set[str]:
    return {
        str((job.get("music") or {}).get("sha256"))
        for job in state.get("jobs", {}).values()
        if (job.get("music") or {}).get("sha256")
    }



def recover_generated_result(folder: Path) -> dict | None:
    root = Path(folder) / "lyria"
    if not root.is_dir():
        return None
    manifests = sorted(root.glob("*/manifest.json"))
    if not manifests:
        return None
    candidates = []
    seen = set()
    for manifest in manifests:
        try:
            data = load_json(manifest, limit=2 * 1024 * 1024)
        except Exception:
            raise VideoError("aether_single_generation_manifest_invalid") from None
        if data.get("state") in {"request_started", "prepared"}:
            raise VideoError("aether_lyria_generation_uncertain")
        if data.get("state") != "generated" or not isinstance(data.get("candidates"), list):
            raise VideoError("aether_single_generation_manifest_invalid")
        for row in data["candidates"]:
            if not isinstance(row, dict):
                raise VideoError("aether_single_generation_manifest_invalid")
            path = Path(row.get("file", ""))
            sha = row.get("sha256")
            if path.is_symlink() or not path.is_file() or not re.fullmatch(r"[0-9a-f]{64}", str(sha)):
                raise VideoError("aether_single_generation_manifest_invalid")
            if file_hash(path) != sha:
                raise VideoError("aether_single_generation_manifest_invalid")
            if sha in seen:
                continue
            seen.add(sha)
            candidates.append(dict(row))
    if not candidates:
        return None
    return {"state": "recovered", "candidates": candidates, "generation_manifest_count": len(manifests)}

def select_candidate(result: dict, prior_hashes: set[str], *, reviewer=None) -> dict:
    candidates = result.get("candidates") or []
    technical = []
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
        item = {"candidate_index": int(row.get("index", 999)), "path": str(path),
                "duration_seconds": duration, "sha256": expected}
        if reviewer is not None:
            review = reviewer(path)
            item["review"] = review
            if not review.get("accepted"):
                continue
        technical.append(item)
    if not technical:
        raise VideoError("aether_single_no_accepted_candidate" if reviewer else "aether_single_no_technical_candidate")
    if reviewer is None:
        return min(technical, key=lambda x: (abs(x["duration_seconds"]-184), x["candidate_index"]))
    return max(technical, key=lambda x: (x["review"]["weighted_score"], -abs(x["duration_seconds"]-184), -x["candidate_index"]))


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
        "youtube_credentials": credential_status(profile="aether_inn"),
        "lyria": lyria_connection_status(check_auth=False),
        "paid_api_allowed": False,  # Legacy generic boolean: no blanket paid-API permission.
        "lyria_3_pro_single_authorized": True,
        "lyria_3_pro_max_usd_per_song": 0.08,
        "lyria_3_pro_max_candidates_per_song": 1,
        "cover_model": "owner_approved_existing_cover",
        "cover_generation": "disabled_no_paid_api",
        "cover_import": "requires_per_title_sha_bound_rights_and_quality_approval",
        "cover_branding": "implemented_adaptive_ivory_baskerville_gold_brand",
        "render": "implemented_1920x1080_30fps_h264_yuv420p_aac256",
        "upload": "implemented_durable_aether_only",
        "technical_candidate_gate": "implemented",
        "actual_audio_quality_review": "offline_signal_quality_no_paid_api",
        "backlog_wav_import": "implemented_catalog_bound_hash_duration_and_offline_signal_gate",
        "melodic_originality_certification": "not_claimed",
    }


def worker(
    root=ROOT, *, slot=None, title=None, style=None, lane=None, publish=False, execute=False,
    api_factory=None, music_generator=generate_music, cover_generator=import_existing_cover,
    renderer=render_single, existing_only=False, source_kind=None, source_wav=None,
    source_expected_duration=None, source_filename=None, source_expected_sha256=None,
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
            # A previous slot's unuploaded job has no legal publishAt after 09:00.
            # Retire it durably without creating an upload or consuming the next
            # Tuesday/Saturday slot. Uploaded jobs always reconcile first.
            retired = []
            if publish and not pending:
                # FINAL queue status must not bury an uncertain prior charge.
                # Existing upload IDs/sessions above still reconcile normally.
                paid_guard.require_no_unsettled_intents(single_root=q.root)
                for prior in unfinished:
                    if prior.get("publish_requested") and publish_slot_stale(prior["slot"]):
                        prior.update(status="rejected", error="aether_single_publish_time_stale")
                        retired.append({"job_id": prior["id"], "slot": prior["slot"],
                                        "error": "aether_single_publish_time_stale"})
                if retired:
                    atomic_json(q.state_path, state)
            remaining = [j for j in unfinished if j.get("publish_requested") and j["status"] not in FINAL]
            job = (pending or remaining or [None])[0]
            if job is None:
                result = {"profile": "aether_inn", "status": "idle", "created_new_job": False}
                if retired:
                    result["retired_stale_jobs"] = retired
                return result
        else:
            job = (pending or same_slot or unfinished or [None])[0]
            if not pending and source_kind != "backlog_wav" and not (job or {}).get("music"):
                paid_guard.require_no_unsettled_intents(single_root=q.root)
        # Caller source bytes belong to one exact canonical title. Queue priority
        # may select another job; reject before stale retirement or any write.
        if source_kind == "backlog_wav" and not (job or {}).get("upload"):
            entry = backlog_catalog_entry(title)
            if (source_filename != entry["title"] + ".wav"
                    or source_expected_duration != entry["duration_seconds"]):
                raise VideoError("aether_single_backlog_source_job_mismatch")
            if job is not None and (
                job.get("title") != entry["title"]
                or job.get("source_kind") != "backlog_wav"
                or job.get("source_filename") != entry["title"] + ".wav"
                or job.get("source_expected_duration") != entry["duration_seconds"]
            ):
                raise VideoError("aether_single_backlog_source_job_mismatch")
            if source_expected_sha256 is not None:
                bound = reusable_backlog_master(entry["title"], q.root, ASSETS_ROOT)
                if (bound is None or source_wav is None or Path(source_wav) != bound["path"]
                        or source_expected_sha256 != bound["sha256"]):
                    raise VideoError("aether_single_backlog_source_job_mismatch")
        stale_slot = job["slot"] if job is not None else slot
        if publish and not (job or {}).get("upload") and publish_slot_stale(stale_slot):
            if job is not None:
                job.update(status="rejected", error="aether_single_publish_time_stale")
                atomic_json(q.state_path, state)
            raise VideoError("aether_single_publish_time_stale")
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
            if publish and source_kind != "backlog_wav":
                # Never buy a new candidate for a title already public on the
                # verified Aether Inn channel, even if the local queue lacks it.
                existing = find_existing_public_video(api, title)
                if existing:
                    return {
                        "profile": "aether_inn", "status": "already_public",
                        "created_new_job": False, "source_kind": "new_lyria",
                        "title": title, "video_id": existing["video_id"],
                        "existing_title": existing["title"],
                        "existing_published_at": existing["published_at"],
                        "generation_count": 0, "estimated_cost_usd": 0.0,
                        "publication_complete": False,
                    }
            if source_kind == "backlog_wav":
                if not source_filename or type(source_expected_duration) not in (int, float):
                    raise VideoError("aether_single_backlog_source_invalid")
            else:
                enforce_lane_rotation(state, lane)
                metadata_gate = inspect_candidate(title, style, read_catalog())
                if metadata_gate["metadata_gate"] == "rejected":
                    raise VideoError("aether_single_catalog_duplicate")
            seed = {"slot": slot, "title": title, "style": style, "lane": lane}
            if source_kind == "backlog_wav":
                seed.update({
                    "source_kind": "backlog_wav",
                    "source_filename": source_filename,
                    "source_expected_duration": source_expected_duration,
                })
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
            # Uploaded jobs reconcile their hash-bound production artifacts; never regenerate sources.
            if not job.get("upload"):
                if not job.get("music"):
                    if job.get("source_kind") == "backlog_wav":
                        retained = reusable_backlog_master(job["title"], q.root, ASSETS_ROOT) if source_wav is None else None
                        source = Path(source_wav) if source_wav is not None else (
                            retained["path"] if retained else resolve_backlog_wav(job["title"]))
                        chosen = import_backlog_master(
                            source, folder, job["source_expected_duration"],
                            expected_sha256=retained["sha256"] if retained else source_expected_sha256,
                        )
                        chosen["source_filename"] = job["source_filename"]
                    else:
                        generated = recover_generated_result(folder)
                        if generated is None:
                            paid_guard.require_no_unsettled_intents(single_root=q.root)
                            # Do not spend for audio that cannot become a video.
                            # Owner-approved cover rights, quality, exact title
                            # and hash must already be valid before the API call.
                            if cover_generator is import_existing_cover:
                                approved_cover(job["title"], ASSETS_ROOT)
                            if publish:
                                require_no_owned_title_match(api, job["title"])
                            generated = music_generator(job["title"], job["style"], execute=True,
                                                        output_root=folder / "lyria", slot=job["slot"])
                        chosen = select_candidate(
                            generated, _history_hashes(state),
                            reviewer=lambda path: review_audio(path),
                        )
                        chosen["generation_count"] = len(generated.get("candidates") or [])
                        chosen["estimated_cost_usd"] = generated.get("estimated_cost_usd")
                    job["music"] = chosen
                    job["status"] = "music_ready"
                    atomic_json(q.state_path, state)
                if not job.get("cover"):
                    cover = cover_generator(job["title"], job["style"], job["lane"], folder / "cover", execute=True)
                    if cover.get("state") not in {"generated", "ready"} or not Path(cover.get("path", "")).is_file():
                        raise VideoError("aether_single_cover_generation_failed")
                    job["cover"] = {
                        "path": cover["path"], "sha256": cover["sha256"],
                        "model": cover.get("model"), "layout": cover.get("layout"),
                        **{key: cover[key] for key in ("source_kind", "source_sha256", "approval_sha256", "approval_title",
                           "quality_basis", "quality_reviewer", "quality_review_sha256",
                           "quality_authority_reference", "quality_reviewed_at") if key in cover},
                    }
                    job["status"] = "cover_ready"
                    atomic_json(q.state_path, state)
                if not job.get("result"):
                    if job["cover"].get("source_kind") == "existing_approved_cover":
                        cover_path = Path(job["cover"]["path"])
                        if (cover_path.is_symlink() or not cover_path.is_file()
                                or file_hash(cover_path) != job["cover"].get("sha256")):
                            raise VideoError("aether_single_approved_cover_integrity")
                    result = renderer(Path(job["music"]["path"]), Path(job["cover"]["path"]), folder)
                    result["job_id"] = job["id"]
                    job.update(result=result, status="rendered", upload_eligible=True, error=None)
                    atomic_json(q.state_path, state)
            if publish:
                # Rendering and FileProvider hydration can cross 09:00. Never
                # start a first upload after the exact publishAt has gone stale.
                # Existing uploads are reconciled with their same durable ID.
                if not job.get("upload") and publish_slot_stale(job["slot"]):
                    raise VideoError("aether_single_publish_time_stale")
                if not job.get("upload"):
                    # Covers resumed, already-paid renders too. A remote title
                    # collision never justifies another insert; known sessions
                    # remain the uploader's reconciliation-only responsibility.
                    if (folder / "youtube-session.json").exists():
                        raise UploadError("manual_reconcile_required")
                    require_no_owned_title_match(api, job["title"])
                uploader = Uploader(q, partial(YouTube, profile="aether_inn"))
                if not job.get("approval"):
                    publish_at = scheduled_publish_at(job["slot"])
                    choices = {
                        "made_for_kids": False,
                        "synthetic_media": True,
                        "privacy": "private",
                        "publish_at": publish_at,
                        "publish_approved": True,
                    }
                    policy = policy_for(job)
                    uploader.bind_approval_locked(
                        state, job, choices,
                        mode="automatic_fail_closed",
                        policy_hash=digest(policy),
                    )
                if not job.get("upload") and job["approval"].get("policy_hash") != digest(policy_for(job)):
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
                "slot": job["slot"], "title": job["title"], "lane": job["lane"],
                "source_kind": job.get("source_kind", "new_lyria"),
                "source_filename": job.get("source_filename"),
                "generation_count": (job.get("music") or {}).get("generation_count"),
                "estimated_cost_usd": (job.get("music") or {}).get("estimated_cost_usd"),
                "audio_review": (job.get("music") or {}).get("review"),
                "video_id": job.get("upload", {}).get("video_id"),
                "thumbnail_status": job.get("thumbnail_status"),
                "publish_at": (job.get("approval", {}).get("choices", {}) or {}).get("publish_at"),
                "error": job.get("error"),
                "publication_complete": job["status"] == "published" and job.get("thumbnail_status") == "set",
            }
        except (VideoError, OSError) as error:
            job.update(
                status="reconcile_required" if job.get("upload") else "blocked",
                error=str(error) if isinstance(error, VideoError) else "aether_single_storage_error",
            )
            if isinstance(error, RemoteInventoryUnverified):
                job["remote_inventory_diagnostic"] = error.diagnostic
            atomic_json(q.state_path, state)
            raise


def backlog_worker(
    root=ROOT, *, slot=None, title=None, publish=False, execute=False, source_wav=None,
    api_factory=None, cover_generator=import_existing_cover, renderer=render_single, music_generator=generate_music,
):
    if not execute:
        return {"dry_run": True, "profile": "aether_inn", "worker": "backlog_wav_single"}
    entry = backlog_catalog_entry(title)
    lane = BACKLOG_LANES[entry["title"]]
    if publish and publish_slot_stale(slot or datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()):
        raise VideoError("aether_single_publish_time_stale")
    if publish:
        api = (api_factory or partial(YouTube, profile="aether_inn"))()
        if getattr(api, "profile", None) != "aether_inn":
            raise UploadError("aether_profile_required")
        api.verify()
        existing = find_existing_public_video(api, entry["title"])
        if existing:
            return {
                "profile": "aether_inn", "status": "already_public",
                "created_new_job": False, "title": entry["title"],
                "source_kind": "backlog_wav", "source_filename": None,
                "video_id": existing["video_id"], "thumbnail_status": None,
                "publish_at": None, "error": None, "publication_complete": False,
                "existing_title": existing["title"],
                "existing_published_at": existing["published_at"],
            }
        api_factory = lambda: api
    retained = reusable_backlog_master(entry["title"], Path(root), ASSETS_ROOT) if source_wav is None else None
    source = Path(source_wav) if source_wav is not None else (
        retained["path"] if retained else resolve_backlog_wav(entry["title"]))
    return worker(
        root, slot=slot, title=entry["title"], style=entry["style"], lane=lane,
        publish=publish, execute=True, api_factory=api_factory, music_generator=music_generator,
        cover_generator=cover_generator, renderer=renderer, source_kind="backlog_wav",
        source_wav=source, source_expected_duration=entry["duration_seconds"],
        source_filename=entry["title"] + ".wav",
        source_expected_sha256=retained["sha256"] if retained else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("readiness")
    r = sub.add_parser("reconcile")
    r.add_argument("--execute", action="store_true")
    b = sub.add_parser("backlog-worker")
    b.add_argument("--slot")
    b.add_argument("--title")
    b.add_argument("--execute", action="store_true")
    b.add_argument("--publish", action="store_true")
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
        elif args.command == "backlog-worker":
            result = backlog_worker(
                args.root, slot=args.slot, title=args.title, publish=args.publish, execute=args.execute,
            )
        else:
            result = worker(
                args.root, slot=args.slot, title=args.title, style=args.style, lane=args.lane,
                publish=args.publish, execute=args.execute,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") in {"blocked", "reconcile_required", "rejected"} else 0
    except Exception as error:
        reason = str(error) if isinstance(error, VideoError) and re.fullmatch(r"[a-z_]{1,100}", str(error)) else "aether_single_operation_failed"
        payload = {"profile": "aether_inn", "status": "blocked", "error": reason}
        if isinstance(error, RemoteInventoryUnverified):
            payload["remote_inventory_diagnostic"] = error.diagnostic
        print(json.dumps(payload))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


