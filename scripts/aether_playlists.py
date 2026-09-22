#!/usr/bin/env python3
"""Idempotent Aether Inn YouTube playlist curator."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlencode

from short_video_pipeline import canonical
from short_video_youtube import API, UploadError, YouTube

ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/singles"
CATALOG = Path(__file__).resolve().parents[1] / "data" / "aether_catalog.json"

PLAYLISTS = {
    "all": {
        "title": "Aether Inn — All Fantasy RPG Music",
        "description": "The complete Aether Inn fantasy RPG music archive — nostalgic JRPG and MMORPG-inspired journeys, towns, forests, night skies, ruins, and returning roads. AI-generated fantasy soundtrack collection.",
    },
    "roads": {
        "title": "Open Roads & Skybound Journeys ✨ Fantasy RPG Travel Music",
        "description": "Fantasy RPG travel music for long roads, open fields, mountain passes, distant borders, airships, harbors, and journeys beyond the horizon. Nostalgic JRPG and MMORPG adventure atmosphere from Aether Inn.",
    },
    "towns": {
        "title": "Lantern Towns & Cozy Inns 🕯 Cozy JRPG Town Music",
        "description": "Warm fantasy town music for lantern streets, village mornings, quiet inns, taverns, libraries, and safe places between adventures. Cozy JRPG and MMORPG atmosphere from Aether Inn.",
    },
    "nature": {
        "title": "Forests, Rivers & Ancient Ruins 🌿 Fantasy Exploration Music",
        "description": "Fantasy exploration music for forests, rivers, lakes, gardens, forgotten gates, ancient ruins, and hidden places. Dreamy JRPG and MMORPG world-exploration music from Aether Inn.",
    },
    "rest": {
        "title": "Starlit Rest & Quiet Farewells 🌙 Emotional Fantasy Music",
        "description": "Emotional fantasy music for moonlit roads, stars, campfires, rain, dawn, homecoming, reflection, reunion, and farewell. Gentle nostalgic JRPG music from Aether Inn.",
    },
    "uplifting": {
        "title": "Uplifting Adventures & Grand Returns ✨ JRPG Fantasy Music",
        "description": "Uplifting fantasy adventure music with forward motion, hopeful departures, frontier crossings, skybound journeys, and warm returns. Energetic but non-combat JRPG-style music from Aether Inn.",
    },
}

TITLE_RULES = {
    "roads": (
        "road", "path", "field", "meadow", "hill", "highland", "ridge", "mountain",
        "valley", "bridge", "watchtower", "horizon", "airship", "kingdom", "harbor",
    ),
    "towns": (
        "inn", "tavern", "town", "village", "capital", "library", "street", "lantern",
        "fireplace", "windmill", "bells",
    ),
    "nature": (
        "forest", "pine", "river", "brook", "lake", "creek", "garden", "orchard",
        "ruin", "stone gate", "crystal", "rain", "willow", "clover", "petal",
    ),
    "rest": (
        "night", "moon", "star", "dawn", "sunrise", "evening", "sunset", "home",
        "campfire", "fireplace", "rain", "aurora", "winter", "lantern",
    ),
    "uplifting": (
        "airship", "first day", "keep walking", "home again", "capital", "pass",
        "highland", "watchtower", "gate", "kingdom",
    ),
}

STYLE_RULES = {
    "roads": (
        "world map", "mountain pass", "borderlands", "travel theme", "journey theme",
        "flight theme", "skybound", "open road", "long road", "road theme",
    ),
    "towns": (
        "village theme", "town theme", "safe zone", "inn theme", "tavern",
        "harbor town", "village morning",
    ),
    "nature": (
        "forest theme", "riverside", "lake theme", "ruins theme", "garden music",
        "sanctuary", "woodland", "river theme",
    ),
    "rest": (
        "night theme", "ending theme", "campfire", "cozy", "reflective", "farewell",
        "reunion", "winter", "evening theme", "sunset theme",
    ),
    "uplifting": (
        "uplifting", "world map", "departure theme", "frontier", "return theme",
        "flight theme", "skybound", "triumphant", "processional",
    ),
}

LANE_RULES = {
    "skybound_flight": {"roads", "uplifting"},
    "sailing": {"roads", "uplifting"},
    "underwater_ruins": {"nature", "uplifting"},
    "traveler_march": {"roads", "uplifting"},
    "triumphant_return": {"roads", "rest", "uplifting"},
    "frontier_surge": {"roads", "uplifting"},
    "quiet_road": {"roads", "rest"},
    "night_reflection": {"rest"},
}


def _catalog() -> list[dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = data.get("songs", [])
    if not isinstance(rows, list):
        raise ValueError("invalid aether catalog")
    return rows


def classify(title: str, style: str = "", lane: str = "") -> list[str]:
    title_text = title.casefold()
    style_text = style.casefold()
    result = {"all"}
    result.update(LANE_RULES.get(lane, set()))
    for key in TITLE_RULES:
        if (
            any(word in title_text for word in TITLE_RULES[key])
            or any(word in style_text for word in STYLE_RULES[key])
        ):
            result.add(key)
    return [key for key in PLAYLISTS if key in result]


def _style_for_title(video_title: str, catalog: list[dict]) -> tuple[str, str]:
    candidates = []
    for row in catalog:
        title = str(row.get("title", "")).strip()
        clean = re.sub(r"\s+Style:$", "", title)
        if clean and video_title.startswith(clean):
            candidates.append((len(clean), clean, str(row.get("style", ""))))
    if not candidates:
        return "", ""
    _, title, style = max(candidates)
    return title, style


def _queue_jobs(root: Path) -> dict[str, dict]:
    path = root / "queue.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    result = {}
    eligible_status = {"published", "scheduled", "processing"}
    for job in data.get("jobs", {}).values():
        video_id = (job.get("upload") or {}).get("video_id")
        if video_id and job.get("status") in eligible_status:
            result[video_id] = job
    return result


def _uploads_playlist(api: YouTube) -> str:
    _, _, data = api.request(
        "GET", API + "channels?" + urlencode({"part": "contentDetails", "id": api.channel}),
        headers=api.headers(), retry=True,
    )
    items = data.get("items", [])
    if len(items) != 1:
        raise UploadError("aether_playlist_channel_missing")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def _public_video_count(api: YouTube) -> int:
    _, _, data = api.request(
        "GET", API + "channels?" + urlencode({"part": "statistics", "id": api.channel}),
        headers=api.headers(), retry=True,
    )
    items = data.get("items", [])
    if len(items) != 1:
        raise UploadError("aether_playlist_channel_missing")
    raw = items[0].get("statistics", {}).get("videoCount")
    if not isinstance(raw, str) or not raw.isdigit():
        raise UploadError("aether_playlist_video_count_invalid")
    return int(raw)


def _search_public_video_ids(api: YouTube) -> list[str]:
    page = ""
    result, seen = [], set()
    while True:
        params = {
            "part": "id", "channelId": api.channel, "type": "video",
            "order": "date", "maxResults": "50",
        }
        if page:
            params["pageToken"] = page
        _, _, data = api.request(
            "GET", API + "search?" + urlencode(params), headers=api.headers(), retry=True
        )
        for item in data.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id and video_id not in seen:
                seen.add(video_id)
                result.append(video_id)
        page = data.get("nextPageToken", "")
        if not page:
            return result


def _uploaded_video_ids(api: YouTube) -> list[str]:
    playlist_id = _uploads_playlist(api)
    page = ""
    result, seen = [], set()
    while True:
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": "50"}
        if page:
            params["pageToken"] = page
        _, _, data = api.request(
            "GET", API + "playlistItems?" + urlencode(params), headers=api.headers(), retry=True
        )
        for item in data.get("items", []):
            video_id = item.get("contentDetails", {}).get("videoId")
            if video_id and video_id not in seen:
                seen.add(video_id)
                result.append(video_id)
        page = data.get("nextPageToken", "")
        if not page:
            break

    public_count = _public_video_count(api)
    if len(result) < public_count:
        for video_id in _search_public_video_ids(api):
            if video_id not in seen:
                seen.add(video_id)
                result.append(video_id)
        if len(result) < public_count:
            raise UploadError("aether_playlist_public_inventory_incomplete")
    return result


def _video_records(api: YouTube, root: Path) -> list[dict]:
    ids = _uploaded_video_ids(api)
    jobs = _queue_jobs(root)
    catalog = _catalog()
    records = []
    for offset in range(0, len(ids), 50):
        batch = ids[offset:offset + 50]
        _, _, data = api.request(
            "GET", API + "videos?" + urlencode({
                "part": "snippet,status", "id": ",".join(batch), "maxResults": "50"
            }), headers=api.headers(), retry=True,
        )
        for item in data.get("items", []):
            if item.get("snippet", {}).get("channelId") != api.channel:
                continue
            video_id = item["id"]
            privacy = item.get("status", {}).get("privacyStatus")
            job = jobs.get(video_id)
            if privacy != "public" and not job:
                continue
            yt_title = item.get("snippet", {}).get("title", "")
            catalog_title, catalog_style = _style_for_title(yt_title, catalog)
            title = (job or {}).get("title") or catalog_title or yt_title
            style = (job or {}).get("style") or catalog_style
            lane = (job or {}).get("lane") or ""
            records.append({
                "video_id": video_id, "title": title, "style": style, "lane": lane,
                "published_at": item.get("snippet", {}).get("publishedAt", ""),
                "privacy": privacy, "playlists": classify(title, style, lane),
            })
    return records


def _existing_playlists(api: YouTube) -> dict[str, str]:
    page = ""
    found = {}
    while True:
        params = {"part": "snippet,status", "mine": "true", "maxResults": "50"}
        if page:
            params["pageToken"] = page
        _, _, data = api.request(
            "GET", API + "playlists?" + urlencode(params), headers=api.headers(), retry=True
        )
        for item in data.get("items", []):
            found[item.get("snippet", {}).get("title", "")] = item["id"]
        page = data.get("nextPageToken", "")
        if not page:
            return found


def _ensure_playlists(api: YouTube) -> dict[str, str]:
    existing = _existing_playlists(api)
    result = {}
    for key, spec in PLAYLISTS.items():
        playlist_id = existing.get(spec["title"])
        if not playlist_id:
            body = {
                "snippet": {"title": spec["title"], "description": spec["description"]},
                "status": {"privacyStatus": "public"},
            }
            _, _, data = api.request(
                "POST", API + "playlists?part=snippet,status", canonical(body),
                api.headers(**{"Content-Type": "application/json; charset=UTF-8"}),
            )
            playlist_id = data.get("id")
            if not playlist_id:
                raise UploadError("aether_playlist_create_unconfirmed")
        result[key] = playlist_id
    return result


def _playlist_video_ids(api: YouTube, playlist_id: str) -> set[str]:
    page = ""
    found = set()
    while True:
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": "50"}
        if page:
            params["pageToken"] = page
        _, _, data = api.request(
            "GET", API + "playlistItems?" + urlencode(params), headers=api.headers(), retry=True
        )
        found.update(
            item.get("contentDetails", {}).get("videoId")
            for item in data.get("items", [])
            if item.get("contentDetails", {}).get("videoId")
        )
        page = data.get("nextPageToken", "")
        if not page:
            return found


def sync(root: Path = ROOT, *, execute: bool = False, api_factory=None) -> dict:
    if not execute:
        return {"profile": "aether_inn", "state": "planned", "playlists": list(PLAYLISTS)}
    api = (api_factory or (lambda: YouTube(profile="aether_inn")))()
    if getattr(api, "profile", None) != "aether_inn":
        raise UploadError("aether_profile_required")
    api.verify()
    playlist_ids = _ensure_playlists(api)
    records = _video_records(api, Path(root))
    added = {key: 0 for key in PLAYLISTS}
    totals = {}
    for key, playlist_id in playlist_ids.items():
        existing = _playlist_video_ids(api, playlist_id)
        eligible = [row for row in records if key in row["playlists"]]
        eligible.sort(key=lambda row: (row["published_at"], row["video_id"]))
        for row in eligible:
            if row["video_id"] in existing:
                continue
            body = {"snippet": {
                "playlistId": playlist_id,
                "position": 0,
                "resourceId": {"kind": "youtube#video", "videoId": row["video_id"]},
            }}
            api.request(
                "POST", API + "playlistItems?part=snippet", canonical(body),
                api.headers(**{"Content-Type": "application/json; charset=UTF-8"}),
            )
            existing.add(row["video_id"])
            added[key] += 1
        totals[key] = len(eligible)
    return {
        "profile": "aether_inn", "state": "synced", "videos_considered": len(records),
        "playlist_ids": playlist_ids, "eligible_totals": totals, "added": added,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(sync(args.root, execute=args.execute), ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        reason = str(error) if isinstance(error, UploadError) else "aether_playlist_operation_failed"
        print(json.dumps({"profile": "aether_inn", "state": "blocked", "error": reason}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
