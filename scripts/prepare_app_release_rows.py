#!/usr/bin/env python3
"""Prepare planned GitHub Release rows from updated store version snapshots."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from check_store_versions import STORE_HEADER, STORE_VERSIONS_PATH
from validate_app_releases import RELEASE_HEADER, RELEASES_PATH


ROOT = Path(__file__).resolve().parents[1]
KST = ZoneInfo("Asia/Seoul")
VERSION_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?([-.+][0-9A-Za-z.-]+)?$")


class PrepareAppReleaseError(ValueError):
    """Raised when release candidate rows cannot be prepared."""


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise PrepareAppReleaseError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_releases(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RELEASE_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def next_release_id(rows: list[dict[str, str]]) -> str:
    highest = 0
    for row in rows:
        release_id = row.get("release_id", "")
        if release_id.startswith("REL-"):
            try:
                highest = max(highest, int(release_id.removeprefix("REL-")))
            except ValueError:
                continue
    return f"REL-{highest + 1:04d}"


def release_date(snapshot: dict[str, str], now: datetime) -> str:
    last_updated = snapshot["last_updated"]
    if last_updated:
        try:
            return datetime.fromisoformat(last_updated.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return now.date().isoformat()


def repository_for(snapshot: dict[str, str], owner: str) -> str:
    return f"{owner}/{snapshot['app_slug']}"


def tag_for(version: str) -> str:
    if not VERSION_RE.fullmatch(version):
        raise PrepareAppReleaseError(f"store version does not look like a release version: {version}")
    return f"v{version}"


def existing_keys(rows: list[dict[str, str]]) -> set[tuple[str, str, str]]:
    return {(row["app_id"], row["platform"], row["version"]) for row in rows}


def existing_release_tags(rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(row["repository"], row["tag"]) for row in rows}


def planned_row(snapshot: dict[str, str], release_id: str, owner: str, now: datetime) -> dict[str, str]:
    tag = tag_for(snapshot["version"])
    notes = "Generated from store version snapshot. Add release artifact, checksum, and set status=ready after verifying the release build."
    release_notes = snapshot["release_notes"] or f"{snapshot['app_name']} {snapshot['version']} store update detected."
    return {
        "release_id": release_id,
        "app_id": snapshot["app_id"],
        "app_slug": snapshot["app_slug"],
        "app_name": snapshot["app_name"],
        "repository": repository_for(snapshot, owner),
        "tag": tag,
        "version": snapshot["version"],
        "platform": snapshot["platform"],
        "build_type": "release",
        "artifact_path": "",
        "checksum_sha256": "",
        "previous_tag": "",
        "status": "planned",
        "release_date": release_date(snapshot, now),
        "release_title": f"{snapshot['app_name']} {tag}",
        "summary": f"{snapshot['app_name']} {snapshot['version']} public store update detected.",
        "changes": release_notes,
        "compatibility": f"{snapshot['platform']} public release.",
        "upgrade_notes": "No special upgrade steps documented yet.",
        "notes": notes,
    }


def prepare_app_release_rows(
    store_versions_path: Path = STORE_VERSIONS_PATH,
    releases_path: Path = RELEASES_PATH,
    owner: str = "onnelakin",
    dry_run: bool = False,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    timestamp = now or datetime.now(KST)
    snapshots = read_csv(store_versions_path, STORE_HEADER)
    releases = read_csv(releases_path, RELEASE_HEADER)
    seen = existing_keys(releases)
    seen_tags = existing_release_tags(releases)
    additions: list[dict[str, str]] = []
    next_id = next_release_id(releases)
    next_number = int(next_id.removeprefix("REL-"))

    for snapshot in snapshots:
        if snapshot["status"] != "updated":
            continue
        if not snapshot["version"]:
            continue
        key = (snapshot["app_id"], snapshot["platform"], snapshot["version"])
        if key in seen:
            continue
        tag = tag_for(snapshot["version"])
        repository = repository_for(snapshot, owner)
        if (repository, tag) in seen_tags:
            continue
        row = planned_row(snapshot, f"REL-{next_number:04d}", owner, timestamp)
        additions.append(row)
        releases.append(row)
        seen.add(key)
        seen_tags.add((repository, tag))
        next_number += 1

    if additions and not dry_run:
        write_releases(releases_path, releases)
    return additions


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare planned GitHub Release rows from store updates")
    parser.add_argument("--store-versions", type=Path, default=STORE_VERSIONS_PATH)
    parser.add_argument("--releases", type=Path, default=RELEASES_PATH)
    parser.add_argument("--owner", default="onnelakin")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        additions = prepare_app_release_rows(args.store_versions, args.releases, args.owner, args.dry_run)
    except (PrepareAppReleaseError, OSError) as error:
        print(f"prepare app release rows failed: {error}", file=sys.stderr)
        return 1
    action = "would add" if args.dry_run else "added"
    print(f"{action} {len(additions)} planned app release row(s)")
    for row in additions:
        print(f"{row['release_id']} {row['app_slug']} {row['platform']} {row['tag']} {row['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
