#!/usr/bin/env python3
"""Collect processing state for uploaded internal builds without promoting them."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sync_store_reviews import app_store_connect_token, google_play_access_token, urlopen_with_retry

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SUBMISSIONS_PATH = DATA / "internal_store_submissions.json"
RELEASES_PATH = DATA / "app_releases.csv"
ANDROID_VERSIONS_PATH = DATA / "android_store_versions.csv"
AVAILABILITY_PATH = DATA / "internal_test_availability.json"
OUTPUT_PATH = DATA / "internal_store_processing_status.json"
GOOGLE_API = "https://androidpublisher.googleapis.com/androidpublisher/v3"
APPLE_API = "https://api.appstoreconnect.apple.com/v1"


def read_json(path: Path, key: str) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"{path.name} has invalid shape")
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def request_json(
    url: str,
    token: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    opener=None,
) -> dict:
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    response = urlopen_with_retry(request, timeout=30, opener=opener)
    with response:
        body = response.read()
    if not body:
        return {}
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{urllib.parse.urlsplit(url).netloc} returned a non-object response")
    return payload


def google_processing_status(
    package_name: str,
    version_code: str,
    token: str,
    *,
    opener=None,
) -> dict[str, str]:
    package = urllib.parse.quote(package_name, safe="")
    edits_url = f"{GOOGLE_API}/applications/{package}/edits"
    edit = request_json(edits_url, token, method="POST", data=b"{}", opener=opener)
    edit_id = str(edit.get("id", "")).strip()
    if not edit_id:
        raise ValueError("Google Play edit response did not include an ID")
    track_url = f"{edits_url}/{urllib.parse.quote(edit_id, safe='')}/tracks/internal"
    try:
        track = request_json(track_url, token, opener=opener)
    finally:
        request_json(f"{edits_url}/{urllib.parse.quote(edit_id, safe='')}", token, method="DELETE", opener=opener)

    release = next(
        (
            item
            for item in track.get("releases", [])
            if isinstance(item, dict)
            and version_code in {str(code) for code in item.get("versionCodes", [])}
        ),
        None,
    )
    if not release:
        return {
            "processing_status": "not_found",
            "provider_status": "",
            "store_build_id": version_code,
            "source_url": track_url,
        }
    provider_status = str(release.get("status", "")).strip()
    normalized = {
        "completed": "processed",
        "halted": "failed",
        "draft": "processing",
        "inProgress": "processing",
    }.get(provider_status, "unknown")
    return {
        "processing_status": normalized,
        "provider_status": provider_status,
        "store_build_id": version_code,
        "source_url": track_url,
    }


def parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def apple_processing_status(
    bundle_id: str,
    release_version: str,
    uploaded_at: str,
    token: str,
    *,
    build_number: str = "",
    opener=None,
) -> dict[str, str]:
    bundle_query = urllib.parse.urlencode({"filter[identifier]": bundle_id, "limit": "2"})
    bundle_url = f"{APPLE_API}/bundleIds?{bundle_query}"
    bundle_payload = request_json(bundle_url, token, opener=opener)
    bundle_rows = bundle_payload.get("data", [])
    if not isinstance(bundle_rows, list) or len(bundle_rows) != 1:
        raise ValueError("App Store Connect bundle identifier did not resolve uniquely")
    bundle_resource_id = str(bundle_rows[0].get("id", "")).strip()
    if not bundle_resource_id:
        raise ValueError("App Store Connect bundle identifier response did not include an ID")

    build_query = urllib.parse.urlencode(
        {
            "filter[bundleId]": bundle_resource_id,
            "include": "preReleaseVersion",
            "limit": "200",
            "sort": "-uploadedDate",
        }
    )
    build_url = f"{APPLE_API}/builds?{build_query}"
    payload = request_json(build_url, token, opener=opener)
    versions = {
        str(item.get("id", "")): str(item.get("attributes", {}).get("version", ""))
        for item in payload.get("included", [])
        if isinstance(item, dict) and item.get("type") == "preReleaseVersions"
    }
    uploaded = parse_time(uploaded_at)
    candidates: list[dict] = []
    for item in payload.get("data", []):
        if not isinstance(item, dict):
            continue
        attributes = item.get("attributes", {})
        relationship = item.get("relationships", {}).get("preReleaseVersion", {}).get("data", {})
        version_id = str(relationship.get("id", "")) if isinstance(relationship, dict) else ""
        if versions.get(version_id) != release_version:
            continue
        if build_number and str(attributes.get("version", "")) != build_number:
            continue
        build_uploaded = parse_time(str(attributes.get("uploadedDate", "")))
        if uploaded and (not build_uploaded or build_uploaded < uploaded - timedelta(hours=1)):
            continue
        candidates.append(item)
    if not candidates:
        return {
            "processing_status": "not_found",
            "provider_status": "",
            "store_build_id": build_number,
            "source_url": build_url,
        }
    build = candidates[0]
    attributes = build.get("attributes", {})
    provider_status = str(attributes.get("processingState", "")).strip()
    normalized = {
        "VALID": "processed",
        "PROCESSING": "processing",
        "FAILED": "failed",
        "INVALID": "failed",
    }.get(provider_status, "unknown")
    return {
        "processing_status": normalized,
        "provider_status": provider_status,
        "store_build_id": str(build.get("id", "")),
        "build_number": str(attributes.get("version", "")),
        "source_url": build_url,
    }


def android_version_code(
    submission: dict,
    release: dict[str, str],
    android_versions: list[dict[str, str]],
) -> str:
    explicit = str(submission.get("build_number") or submission.get("version_code") or "").strip()
    if explicit.isdigit():
        return explicit
    match = next(
        (
            item
            for item in android_versions
            if item.get("package") == submission.get("identifier")
            and item.get("version") == release.get("version")
        ),
        None,
    )
    if not match:
        return ""
    raw = f"{match.get('notes', '')} {match.get('release_notes', '')}"
    found = re.search(rf"\b{re.escape(release.get('version', ''))}\+(\d+)\b", raw)
    return found.group(1) if found else ""


def update_record(records: list[dict], base: dict, observed: dict[str, str], now: str) -> None:
    record = next((item for item in records if item.get("release_id") == base["release_id"]), None)
    if record is None:
        record = {"release_id": base["release_id"], "history": []}
        records.append(record)
    history = record.setdefault("history", [])
    current = (
        observed.get("processing_status", ""),
        observed.get("provider_status", ""),
        observed.get("store_build_id", ""),
    )
    previous = (
        record.get("processing_status", ""),
        record.get("provider_status", ""),
        record.get("store_build_id", ""),
    )
    record.update(base)
    record.update(observed)
    record["last_checked_at"] = now
    if current != previous:
        history.append(
            {
                "processing_status": current[0],
                "provider_status": current[1],
                "store_build_id": current[2],
                "observed_at": now,
                "source_url": observed.get("source_url", ""),
            }
        )


def collect(
    submissions: list[dict],
    releases: list[dict[str, str]],
    android_versions: list[dict[str, str]],
    available_release_ids: set[str],
    records: list[dict],
    *,
    google_token: str,
    apple_token: str,
    now: str,
    opener=None,
) -> list[dict]:
    release_index = {row.get("release_id", ""): row for row in releases}
    for submission in submissions:
        if submission.get("status") != "uploaded" or submission.get("release_id") in available_release_ids:
            continue
        release = release_index.get(str(submission.get("release_id", "")))
        if not release:
            raise ValueError(f"release metadata is missing for {submission.get('release_id')}")
        provider = submission.get("provider")
        base = {
            "release_id": submission["release_id"],
            "provider": provider,
            "identifier": submission.get("identifier", ""),
            "channel": submission.get("channel", ""),
            "checksum_sha256": submission.get("checksum_sha256", ""),
            "version": release.get("version", ""),
            "uploaded_at": submission.get("uploaded_at", ""),
        }
        if provider == "google_play":
            if not google_token:
                raise ValueError("Google Play credentials are required for pending Android uploads")
            version_code = android_version_code(submission, release, android_versions)
            if not version_code:
                raise ValueError(f"Android version code is missing for {submission['release_id']}")
            observed = google_processing_status(
                str(submission.get("identifier", "")), version_code, google_token, opener=opener
            )
        elif provider == "app_store":
            if not apple_token:
                raise ValueError("App Store Connect credentials are required for pending iOS uploads")
            observed = apple_processing_status(
                str(submission.get("identifier", "")),
                release.get("version", ""),
                str(submission.get("uploaded_at", "")),
                apple_token,
                build_number=str(submission.get("build_number", "")),
                opener=opener,
            )
        else:
            raise ValueError(f"unsupported internal store provider: {provider}")
        update_record(records, base, observed, now)
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    submissions = read_json(SUBMISSIONS_PATH, "submissions")
    releases = read_csv(RELEASES_PATH)
    android_versions = read_csv(ANDROID_VERSIONS_PATH)
    availability = read_json(AVAILABILITY_PATH, "records")
    available_release_ids = {
        str(item.get("release_id", ""))
        for item in availability
        if item.get("status") == "available_to_testers"
    }
    records = read_json(args.output, "records") if args.output.exists() else []
    pending_providers = {
        item.get("provider")
        for item in submissions
        if item.get("status") == "uploaded" and item.get("release_id") not in available_release_ids
    }
    google_token = ""
    apple_token = ""
    if "google_play" in pending_providers:
        raw = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "")
        if not raw:
            raise SystemExit("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON is required")
        google_token = google_play_access_token(raw)
    if "app_store" in pending_providers:
        key_id = os.environ.get("APP_STORE_CONNECT_KEY_ID", "")
        issuer_id = os.environ.get("APP_STORE_CONNECT_ISSUER_ID", "")
        private_key = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY", "")
        if not key_id or not issuer_id or not private_key:
            raise SystemExit("App Store Connect credentials are required")
        apple_token = app_store_connect_token(key_id, issuer_id, private_key)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    collect(
        submissions,
        releases,
        android_versions,
        available_release_ids,
        records,
        google_token=google_token,
        apple_token=apple_token,
        now=now,
    )
    args.output.write_text(json.dumps({"records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"collected processing status for {len(records)} internal store build(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
