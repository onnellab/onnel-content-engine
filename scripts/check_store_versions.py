#!/usr/bin/env python3
"""Check app store versions and record store update snapshots."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from validate_apps_registry import APP_HEADER, APPS_PATH


ROOT = Path(__file__).resolve().parents[1]
STORE_VERSIONS_PATH = ROOT / "data" / "store_versions.csv"
ANDROID_VERSIONS_PATH = ROOT / "data" / "android_store_versions.csv"
KST = ZoneInfo("Asia/Seoul")

STORE_HEADER = [
    "app_id",
    "app_slug",
    "app_name",
    "platform",
    "store_url",
    "store_app_id",
    "store_package",
    "version",
    "last_updated",
    "release_notes",
    "checked_at",
    "status",
    "notes",
]

ANDROID_HEADER = [
    "app_id",
    "app_slug",
    "package",
    "version",
    "last_updated",
    "release_notes",
    "source",
    "notes",
]

APP_STORE_ID_RE = re.compile(r"/id(\d+)")
PLAY_PACKAGE_RE = re.compile(r"[?&]id=([A-Za-z0-9_.]+)")


class StoreVersionError(ValueError):
    """Raised when store version checks cannot run."""


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise StoreVersionError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STORE_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def app_store_id(url: str) -> str:
    match = APP_STORE_ID_RE.search(url)
    if not match:
        raise StoreVersionError(f"App Store URL has no numeric id: {url}")
    return match.group(1)


def play_package(url: str) -> str:
    match = PLAY_PACKAGE_RE.search(url)
    if not match:
        raise StoreVersionError(f"Google Play URL has no package id: {url}")
    return match.group(1)


def json_get(url: str) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"User-Agent": "ONNELLAB content engine"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise StoreVersionError(f"HTTP {error.code} from {url}: {detail}") from error


def app_store_lookup(store_url: str, country: str = "kr") -> dict[str, str]:
    identifier = app_store_id(store_url)
    query = urllib.parse.urlencode({"id": identifier, "country": country})
    data = json_get(f"https://itunes.apple.com/lookup?{query}")
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise StoreVersionError(f"App Store lookup returned no result for {identifier}")
    result = results[0]
    if not isinstance(result, dict):
        raise StoreVersionError(f"App Store lookup returned invalid result for {identifier}")
    return {
        "store_app_id": identifier,
        "store_package": "",
        "version": str(result.get("version", "") or ""),
        "last_updated": str(result.get("currentVersionReleaseDate", "") or ""),
        "release_notes": str(result.get("releaseNotes", "") or "").replace("\r\n", "\n").replace("\n", " ").strip(),
    }


def google_play_placeholder(store_url: str) -> dict[str, str]:
    return {
        "store_app_id": "",
        "store_package": play_package(store_url),
        "version": "",
        "last_updated": "",
        "release_notes": "",
    }


def android_version_index(path: Path = ANDROID_VERSIONS_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row["app_id"]: row for row in read_csv(path, ANDROID_HEADER) if row["version"]}


def google_play_from_source(store_url: str, app_id: str, android_versions: dict[str, dict[str, str]]) -> dict[str, str]:
    package = play_package(store_url)
    row = android_versions.get(app_id)
    if not row:
        return google_play_placeholder(store_url)
    if row["package"] != package:
        raise StoreVersionError(f"Android version package does not match Play Store URL for {app_id}")
    return {
        "store_app_id": "",
        "store_package": package,
        "version": row["version"],
        "last_updated": row["last_updated"],
        "release_notes": row["release_notes"],
    }


def snapshot_key(row: dict[str, str]) -> tuple[str, str]:
    return row["app_id"], row["platform"]


def read_existing(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    return {snapshot_key(row): row for row in read_csv(path, STORE_HEADER)}


def store_rows_from_apps(
    apps_path: Path,
    existing: dict[tuple[str, str], dict[str, str]],
    now: str,
    android_versions: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    android_versions = android_versions or {}
    rows: list[dict[str, str]] = []
    for app in read_csv(apps_path, APP_HEADER):
        candidates = [("ios", app["app_store_url"]), ("android", app["play_store_url"])]
        for platform, store_url in candidates:
            if not store_url:
                continue
            previous = existing.get((app["app_id"], platform), {})
            try:
                if platform == "android":
                    current = google_play_from_source(store_url, app["app_id"], android_versions)
                else:
                    current = app_store_lookup(store_url)
                previous_version = previous.get("version", "")
                status = "new" if not previous else "unchanged"
                if current["version"] and previous_version and current["version"] != previous_version:
                    status = "updated"
                if platform == "android":
                    if current["version"]:
                        notes = android_versions.get(app["app_id"], {}).get("notes", "")
                    else:
                        status = "manual_check"
                        notes = "Google Play has no stable public version lookup in this automation."
                else:
                    notes = ""
                rows.append(
                    {
                        "app_id": app["app_id"],
                        "app_slug": app["slug"],
                        "app_name": app["app_name"],
                        "platform": platform,
                        "store_url": store_url,
                        "store_app_id": current["store_app_id"],
                        "store_package": current["store_package"],
                        "version": current["version"],
                        "last_updated": current["last_updated"],
                        "release_notes": current["release_notes"],
                        "checked_at": now,
                        "status": status,
                        "notes": notes,
                    }
                )
            except Exception as error:
                row = dict(previous) if previous else {field: "" for field in STORE_HEADER}
                row.update(
                    {
                        "app_id": app["app_id"],
                        "app_slug": app["slug"],
                        "app_name": app["app_name"],
                        "platform": platform,
                        "store_url": store_url,
                        "checked_at": now,
                        "status": "failed",
                        "notes": str(error),
                    }
                )
                rows.append(row)
    return rows


def check_store_versions(
    apps_path: Path = APPS_PATH,
    output_path: Path = STORE_VERSIONS_PATH,
    android_versions_path: Path = ANDROID_VERSIONS_PATH,
    dry_run: bool = False,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    timestamp = (now or datetime.now(KST)).replace(microsecond=0).isoformat()
    existing = read_existing(output_path)
    android_versions = android_version_index(android_versions_path)
    rows = store_rows_from_apps(apps_path, existing, timestamp, android_versions)
    if not dry_run:
        write_csv(output_path, rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Check App Store versions and record store snapshots")
    parser.add_argument("--apps", type=Path, default=APPS_PATH)
    parser.add_argument("--output", type=Path, default=STORE_VERSIONS_PATH)
    parser.add_argument("--android-versions", type=Path, default=ANDROID_VERSIONS_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        rows = check_store_versions(args.apps, args.output, args.android_versions, args.dry_run)
    except (StoreVersionError, OSError, json.JSONDecodeError) as error:
        print(f"store version check failed: {error}", file=sys.stderr)
        return 1
    action = "would record" if args.dry_run else "recorded"
    print(f"{action} {len(rows)} store version row(s)")
    for row in rows:
        version = row["version"] or row["store_package"] or row["store_app_id"]
        print(f"{row['app_slug']} {row['platform']} {row['status']} {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
