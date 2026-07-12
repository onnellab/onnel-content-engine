#!/usr/bin/env python3
"""Sync Android version source data from local Flutter app repositories."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from check_store_versions import ANDROID_HEADER, ANDROID_VERSIONS_PATH, play_package
from validate_android_store_versions import validate_android_store_versions
from validate_apps_registry import APP_HEADER, APPS_PATH


ROOT = Path(__file__).resolve().parents[1]
LOCAL_REPOSITORIES_PATH = ROOT / "data" / "local_repositories.csv"
LOCAL_REPOSITORIES_HEADER = ["app_id", "app_slug", "repository_name", "path", "pubspec_path", "source_priority", "notes"]
KST = ZoneInfo("Asia/Seoul")
PUBSPEC_VERSION_RE = re.compile(r"^version:\s*([0-9A-Za-z_.+\-]+)\s*$", re.MULTILINE)


class AndroidRepoSyncError(ValueError):
    """Raised when Android version metadata cannot be synced from local repos."""


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise AndroidRepoSyncError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_android_versions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANDROID_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def app_index() -> dict[str, dict[str, str]]:
    return {row["app_id"]: row for row in read_csv(APPS_PATH, APP_HEADER)}


def pubspec_version(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    match = PUBSPEC_VERSION_RE.search(text)
    if not match:
        raise AndroidRepoSyncError(f"{path} has no version field")
    raw = match.group(1)
    version = raw.split("+", 1)[0]
    return version, raw


def sync_android_versions_from_repos(
    repositories_path: Path = LOCAL_REPOSITORIES_PATH,
    output_path: Path = ANDROID_VERSIONS_PATH,
    today: str | None = None,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    apps = app_index()
    rows: list[dict[str, str]] = []
    date = today or datetime.now(KST).date().isoformat()
    seen: set[str] = set()

    for repo in read_csv(repositories_path, LOCAL_REPOSITORIES_HEADER):
        app_id = repo["app_id"]
        if app_id in seen:
            raise AndroidRepoSyncError(f"duplicated app_id in local repositories: {app_id}")
        seen.add(app_id)
        app = apps.get(app_id)
        if not app:
            raise AndroidRepoSyncError(f"unknown app_id: {app_id}")
        if repo["app_slug"] != app["slug"]:
            raise AndroidRepoSyncError(f"{app_id} app_slug does not match app registry")
        if not app["play_store_url"]:
            continue
        repo_path = Path(repo["path"])
        pubspec_path = repo_path / repo["pubspec_path"]
        if not pubspec_path.exists():
            raise AndroidRepoSyncError(f"{app_id} pubspec_path does not exist: {pubspec_path}")
        version, raw_version = pubspec_version(pubspec_path)
        rows.append(
            {
                "app_id": app_id,
                "app_slug": app["slug"],
                "package": play_package(app["play_store_url"]),
                "version": version,
                "last_updated": date,
                "release_notes": "Local Flutter build metadata version.",
                "source": "local_build_metadata",
                "notes": f"Imported from {pubspec_path.as_posix()} version {raw_version}; confirm against Play Console if needed.",
            }
        )

    rows.sort(key=lambda row: row["app_slug"])
    if not dry_run:
        write_android_versions(output_path, rows)
        validate_android_store_versions(output_path)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Android version rows from local Flutter app repositories")
    parser.add_argument("--repositories", type=Path, default=LOCAL_REPOSITORIES_PATH)
    parser.add_argument("--output", type=Path, default=ANDROID_VERSIONS_PATH)
    parser.add_argument("--date", help="Override last_updated date in YYYY-MM-DD format")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        rows = sync_android_versions_from_repos(args.repositories, args.output, args.date, args.dry_run)
    except (AndroidRepoSyncError, OSError, ValueError) as error:
        print(f"sync android versions from repos failed: {error}", file=sys.stderr)
        return 1
    action = "would sync" if args.dry_run else "synced"
    print(f"{action} {len(rows)} android store version row(s)")
    for row in rows:
        print(f"{row['app_slug']} {row['package']} {row['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
