#!/usr/bin/env python3
"""Sync GitHub Release metadata for app release rows."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

from create_github_releases import GitHubReleaseError, github_request, github_token, read_manifest, sync_release_metadata, write_manifest
from validate_app_releases import RELEASES_PATH, validate_app_releases


def existing_release(repository: str, tag: str, token: str) -> dict[str, object] | None:
    path = f"/repos/{repository}/releases/tags/{urllib.parse.quote(tag, safe='')}"
    try:
        return github_request(path, token)
    except GitHubReleaseError as error:
        if "HTTP 404" in str(error):
            return None
        raise


def sync_github_release_status(path: Path = RELEASES_PATH, dry_run: bool = False, allow_missing_token: bool = False) -> list[str]:
    validate_app_releases(path)
    rows = read_manifest(path)
    try:
        token = github_token()
    except GitHubReleaseError:
        if allow_missing_token:
            return ["skipped GitHub release status sync: token not configured"]
        raise

    messages: list[str] = []
    changed = False
    for row in rows:
        if (row.get("release_channel") or "public") != "public":
            continue
        if row.get("status") not in {"ready", "released"}:
            continue
        release = existing_release(row["repository"], row["tag"], token)
        if not release:
            messages.append(f"not found {row['repository']} {row['tag']}")
            continue
        before = dict(row)
        sync_release_metadata(row, release)
        row["status"] = "released"
        if row != before:
            changed = True
        messages.append(f"synced {row['repository']} {row['tag']} {row['release_url']}")

    if changed and not dry_run:
        write_manifest(path, rows)
    if not messages:
        messages.append("no public GitHub release rows to sync")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync GitHub Release metadata for app release rows")
    parser.add_argument("--manifest", type=Path, default=RELEASES_PATH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-missing-token", action="store_true")
    args = parser.parse_args()
    try:
        messages = sync_github_release_status(args.manifest, args.dry_run, args.allow_missing_token)
    except (GitHubReleaseError, OSError, json.JSONDecodeError) as error:
        print(f"sync GitHub release status failed: {error}", file=sys.stderr)
        return 1
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
