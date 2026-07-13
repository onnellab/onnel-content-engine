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
from sync_android_versions_from_repos import LOCAL_REPOSITORIES_HEADER, LOCAL_REPOSITORIES_PATH, pubspec_version
from validate_app_releases import RELEASE_HEADER, RELEASES_PATH


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "app_release_config.csv"
KST = ZoneInfo("Asia/Seoul")
VERSION_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?([-.+][0-9A-Za-z.-]+)?$")
VERSION_PART_RE = re.compile(r"\d+|[A-Za-z]+")
CONFIG_HEADER = ["app_id", "app_slug", "repository", "artifact_pattern", "notes"]


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
        match = re.fullmatch(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?", last_updated)
        if match:
            year, month, day = (int(part) for part in match.groups())
            return datetime(year, month, day).date().isoformat()
    return now.date().isoformat()


def release_config(path: Path = CONFIG_PATH) -> dict[str, dict[str, str]]:
    return {row["app_id"]: row for row in read_csv(path, CONFIG_HEADER)}


def local_version_index(rows: list[dict[str, str]]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for row in rows:
        pubspec_path = Path(row["path"]) / row["pubspec_path"]
        if not pubspec_path.exists():
            continue
        version, _raw = pubspec_version(pubspec_path)
        versions[row["app_id"]] = version
    return versions


def version_key(version: str) -> list[tuple[int, int | str]]:
    key: list[tuple[int, int | str]] = []
    for part in VERSION_PART_RE.findall(version):
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return key


def compare_versions(store_version: str, local_version: str) -> str:
    if not store_version or not local_version:
        return "unknown"
    store_key = version_key(store_version)
    local_key = version_key(local_version)
    if store_key == local_key:
        return "same"
    if local_key > store_key:
        return "local_ahead"
    return "store_ahead"


def repository_for(snapshot: dict[str, str], config: dict[str, dict[str, str]], owner: str) -> str:
    row = config.get(snapshot["app_id"], {})
    return row.get("repository") or f"{owner}/{snapshot['app_slug']}"


def tag_for(version: str) -> str:
    if not VERSION_RE.fullmatch(version):
        raise PrepareAppReleaseError(f"store version does not look like a release version: {version}")
    return f"v{version}"


def existing_keys(rows: list[dict[str, str]]) -> set[tuple[str, str, str]]:
    return {(row["app_id"], row["platform"], row["version"]) for row in rows}


def existing_release_tags(rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(row["repository"], row["tag"]) for row in rows}


def release_index_by_tag(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row["repository"], row["tag"]): row for row in rows}


def latest_public_release_tag(rows: list[dict[str, str]], snapshot: dict[str, str]) -> str:
    candidates = [
        row
        for row in rows
        if row.get("app_id") == snapshot["app_id"]
        and row.get("platform") == snapshot["platform"]
        and (row.get("release_channel") or "public") == "public"
        and row.get("status") in {"released", "ready"}
        and row.get("tag")
        and row.get("version")
    ]
    if not candidates:
        return ""
    candidates.sort(key=lambda row: version_key(row["version"]), reverse=True)
    return candidates[0]["tag"]


def refresh_existing_local_ahead_release(
    row: dict[str, str],
    snapshot: dict[str, str],
    now: datetime,
) -> bool:
    if row.get("status") not in {"planned", "ready"}:
        return False
    if "local build metadata is ahead of the store snapshot" not in row.get("summary", ""):
        return False
    if row.get("version") != snapshot.get("version"):
        return False
    row["platform"] = snapshot["platform"]
    row["release_channel"] = "public"
    row["release_date"] = release_date(snapshot, now)
    row["summary"] = f"{snapshot['app_name']} {snapshot['version']} public store update detected."
    row["changes"] = snapshot["release_notes"] or f"{snapshot['app_name']} {snapshot['version']} store update detected."
    row["compatibility"] = f"{snapshot['platform']} public release."
    row["notes"] = (
        "Updated from local-ahead metadata after the same version was confirmed on the public store. "
        "Add release artifact, checksum, and set status=ready after verifying the release build."
    )
    return True


def planned_row(
    snapshot: dict[str, str],
    release_id: str,
    config: dict[str, dict[str, str]],
    owner: str,
    now: datetime,
    reason: str = "store_updated",
    store_version: str = "",
    previous_public_tag: str = "",
) -> dict[str, str]:
    tag = tag_for(snapshot["version"])
    if reason == "local_ahead":
        previous_tag = tag_for(store_version) if store_version else ""
        notes = (
            "Generated from local build metadata because local version is ahead of store snapshot. "
            f"Store version: {store_version or 'unknown'}. "
            "Add release artifact and checksum only for private testing. Keep private until the version is publicly released."
        )
        summary = f"{snapshot['app_name']} {snapshot['version']} local build metadata is ahead of the store snapshot."
        release_channel = "private_test"
        compatibility = f"{snapshot['platform']} private test build."
    else:
        previous_tag = previous_public_tag
        notes = "Generated from public store version snapshot. Patch notes must describe changes since the previous public release."
        summary = f"{snapshot['app_name']} {snapshot['version']} public store update detected."
        release_channel = "public"
        compatibility = f"{snapshot['platform']} public release."
    release_notes = snapshot["release_notes"] or f"{snapshot['app_name']} {snapshot['version']} store update detected."
    return {
        "release_id": release_id,
        "app_id": snapshot["app_id"],
        "app_slug": snapshot["app_slug"],
        "app_name": snapshot["app_name"],
        "repository": repository_for(snapshot, config, owner),
        "tag": tag,
        "version": snapshot["version"],
        "platform": snapshot["platform"],
        "build_type": "release",
        "release_type": "binary",
        "release_channel": release_channel,
        "artifact_path": "",
        "checksum_sha256": "",
        "previous_tag": previous_tag,
        "status": "planned",
        "release_url": "",
        "github_release_id": "",
        "released_at": "",
        "release_date": release_date(snapshot, now),
        "release_title": f"{snapshot['app_name']} {tag}",
        "summary": summary,
        "changes": release_notes,
        "compatibility": compatibility,
        "upgrade_notes": "No special upgrade steps documented yet.",
        "notes": notes,
    }


def prepare_app_release_rows(
    store_versions_path: Path = STORE_VERSIONS_PATH,
    releases_path: Path = RELEASES_PATH,
    config_path: Path = CONFIG_PATH,
    local_repositories_path: Path = LOCAL_REPOSITORIES_PATH,
    owner: str = "onnellab",
    dry_run: bool = False,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    timestamp = now or datetime.now(KST)
    snapshots = read_csv(store_versions_path, STORE_HEADER)
    releases = read_csv(releases_path, RELEASE_HEADER)
    config = release_config(config_path)
    local_versions = local_version_index(read_csv(local_repositories_path, LOCAL_REPOSITORIES_HEADER))
    seen = existing_keys(releases)
    seen_tags = existing_release_tags(releases)
    release_by_tag = release_index_by_tag(releases)
    additions: list[dict[str, str]] = []
    refreshed = False
    next_id = next_release_id(releases)
    next_number = int(next_id.removeprefix("REL-"))

    for snapshot in snapshots:
        reason = ""
        candidate = dict(snapshot)
        local_version = local_versions.get(snapshot["app_id"], "")
        comparison = compare_versions(snapshot["version"], local_version)
        if comparison == "local_ahead":
            reason = "local_ahead"
            candidate["version"] = local_version
            candidate["release_notes"] = (
                f"Local build metadata version {local_version} is ahead of store snapshot {snapshot['version'] or 'unknown'}."
            )
        elif snapshot["status"] == "updated":
            reason = "store_updated"
        elif snapshot["version"]:
            tag = tag_for(snapshot["version"])
            repository = repository_for(snapshot, config, owner)
            existing = release_by_tag.get((repository, tag))
            if existing and refresh_existing_local_ahead_release(existing, snapshot, timestamp):
                refreshed = True
        if not reason:
            continue
        if not candidate["version"]:
            continue
        key = (candidate["app_id"], candidate["platform"], candidate["version"])
        if key in seen:
            continue
        tag = tag_for(candidate["version"])
        repository = repository_for(candidate, config, owner)
        if (repository, tag) in seen_tags:
            continue
        row = planned_row(
            candidate,
            f"REL-{next_number:04d}",
            config,
            owner,
            timestamp,
            reason,
            snapshot["version"],
            latest_public_release_tag(releases, candidate) if reason == "store_updated" else "",
        )
        additions.append(row)
        releases.append(row)
        seen.add(key)
        seen_tags.add((repository, tag))
        release_by_tag[(repository, tag)] = row
        next_number += 1

    if (additions or refreshed) and not dry_run:
        write_releases(releases_path, releases)
    return additions


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare planned GitHub Release rows from store updates")
    parser.add_argument("--store-versions", type=Path, default=STORE_VERSIONS_PATH)
    parser.add_argument("--releases", type=Path, default=RELEASES_PATH)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--local-repositories", type=Path, default=LOCAL_REPOSITORIES_PATH)
    parser.add_argument("--owner", default="onnellab")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        additions = prepare_app_release_rows(args.store_versions, args.releases, args.config, args.local_repositories, args.owner, args.dry_run)
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
