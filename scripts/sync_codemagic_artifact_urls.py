#!/usr/bin/env python3
"""Sync Codemagic build artifact URLs into data/codemagic_artifacts.csv."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from download_codemagic_artifacts import CODEMAGIC_API, CODEMAGIC_ARTIFACTS_PATH, CODEMAGIC_HEADER, safe_name
from validate_app_releases import RELEASE_HEADER, RELEASES_PATH, ROOT


CODEMAGIC_BUILDS_PATH = ROOT / "data" / "codemagic_builds.csv"
CODEMAGIC_BUILDS_HEADER = ["release_id", "codemagic_app_id", "workflow_id", "build_id", "artifact_name", "notes"]
ARTIFACT_SUFFIXES = (".ipa", ".aab", ".apk")


class CodemagicBuildSyncError(ValueError):
    """Raised when Codemagic build artifacts cannot be synced safely."""


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise CodemagicBuildSyncError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def codemagic_token(dry_run: bool = False) -> str:
    if dry_run:
        return "dry-run-token"
    token = os.environ.get("CODEMAGIC_API_TOKEN")
    if not token:
        raise CodemagicBuildSyncError("CODEMAGIC_API_TOKEN is required")
    return token


def release_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["release_id"]: row for row in rows}


def artifact_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row["release_id"], row["app_id"], row["platform"], row["version"]


def request_json(path_or_url: str, token: str) -> dict[str, Any]:
    url = path_or_url if path_or_url.startswith("https://") else f"{CODEMAGIC_API}{path_or_url}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-auth-token": token,
            "User-Agent": "ONNELLAB content engine",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise CodemagicBuildSyncError(f"HTTP {error.code} from Codemagic build lookup: {detail}") from error


def build_path(build_id: str) -> str:
    encoded = urllib.parse.quote(build_id, safe="")
    return f"/builds/{encoded}"


def artifact_candidates(payload: Any) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            url = first_string(value, ["url", "href", "downloadUrl", "download_url", "artifactUrl", "artifact_url"])
            name = first_string(value, ["name", "fileName", "filename", "path", "artifactName", "artifact_name"])
            if url and artifact_like(url):
                found.append((url, name or Path(urllib.parse.urlparse(url).path).name))
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str) and artifact_like(value):
            found.append((value, Path(urllib.parse.urlparse(value).path).name))

    visit(payload)
    unique: dict[str, tuple[str, str]] = {}
    for url, name in found:
        unique.setdefault(url, (url, name))
    return list(unique.values())


def first_string(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def artifact_like(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    path = parsed.path.lower()
    return path.endswith(ARTIFACT_SUFFIXES) and (value.startswith("https://") or value.startswith("/"))


def choose_artifact(candidates: list[tuple[str, str]], release_id: str, preferred_name: str) -> tuple[str, str]:
    if preferred_name:
        preferred = [item for item in candidates if Path(item[1]).name == preferred_name]
        if len(preferred) == 1:
            safe_name(preferred[0][1], release_id)
            return preferred[0]
        if len(preferred) > 1:
            raise CodemagicBuildSyncError(f"{release_id} preferred artifact name matched multiple URLs: {preferred_name}")
        raise CodemagicBuildSyncError(f"{release_id} preferred artifact name was not found: {preferred_name}")
    if len(candidates) != 1:
        raise CodemagicBuildSyncError(f"{release_id} build must expose exactly one release artifact or set artifact_name")
    safe_name(candidates[0][1], release_id)
    return candidates[0]


def artifact_row(release: dict[str, str], url: str, name: str, notes: str) -> dict[str, str]:
    return {
        "release_id": release["release_id"],
        "app_id": release["app_id"],
        "app_slug": release["app_slug"],
        "version": release["version"],
        "platform": release["platform"],
        "artifact_url": url,
        "artifact_name": Path(name).name,
        "notes": notes,
    }


def sync_codemagic_artifact_urls(
    releases_path: Path = RELEASES_PATH,
    builds_path: Path = CODEMAGIC_BUILDS_PATH,
    artifacts_path: Path = CODEMAGIC_ARTIFACTS_PATH,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    releases = release_index(read_csv(releases_path, RELEASE_HEADER))
    build_rows = read_csv(builds_path, CODEMAGIC_BUILDS_HEADER)
    artifacts = read_csv(artifacts_path, CODEMAGIC_HEADER)
    existing = {artifact_key(row): row for row in artifacts}
    token: str | None = None
    synced: list[dict[str, str]] = []

    for build in build_rows:
        if not build["build_id"]:
            continue
        release = releases.get(build["release_id"])
        if not release or release["status"] != "planned" or release["artifact_path"]:
            continue
        if token is None:
            token = codemagic_token(dry_run)
        payload = {} if dry_run else request_json(build_path(build["build_id"]), token)
        candidates = artifact_candidates(payload)
        if dry_run:
            row = artifact_row(release, f"/artifacts/{build['build_id']}/{release['app_slug']}.ipa", build["artifact_name"] or f"{release['app_slug']}.ipa", "Dry-run placeholder.")
        else:
            url, name = choose_artifact(candidates, build["release_id"], build["artifact_name"])
            row = artifact_row(release, url, name, build["notes"] or f"Synced from Codemagic build {build['build_id']}.")
        existing[artifact_key(row)] = row
        synced.append(row)

    output_rows = sorted(existing.values(), key=lambda row: (row["app_slug"], row["platform"], row["version"], row["release_id"]))
    if synced and not dry_run:
        write_csv(artifacts_path, CODEMAGIC_HEADER, output_rows)
    return synced


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Codemagic build artifact URLs into data/codemagic_artifacts.csv")
    parser.add_argument("--releases", type=Path, default=RELEASES_PATH)
    parser.add_argument("--builds", type=Path, default=CODEMAGIC_BUILDS_PATH)
    parser.add_argument("--artifacts", type=Path, default=CODEMAGIC_ARTIFACTS_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        synced = sync_codemagic_artifact_urls(args.releases, args.builds, args.artifacts, args.dry_run)
    except (CodemagicBuildSyncError, OSError, json.JSONDecodeError) as error:
        print(f"sync Codemagic artifact URLs failed: {error}", file=sys.stderr)
        return 1
    action = "would sync" if args.dry_run else "synced"
    print(f"{action} {len(synced)} Codemagic artifact URL row(s)")
    for row in synced:
        print(f"{row['release_id']} {row['app_slug']} {row['platform']} {row['artifact_name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
