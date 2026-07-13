#!/usr/bin/env python3
"""Sync GitHub Release metadata for app release rows."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from create_github_releases import GitHubReleaseError, github_request, github_token, read_manifest, sync_release_metadata, write_manifest
from validate_app_releases import RELEASES_PATH, validate_app_releases

STATUS_PATH = Path(__file__).resolve().parents[1] / "data" / "app_release_sync_status.json"


def existing_release(repository: str, tag: str, token: str) -> dict[str, object] | None:
    path = f"/repos/{repository}/releases/tags/{urllib.parse.quote(tag, safe='')}"
    try:
        return github_request(path, token)
    except GitHubReleaseError as error:
        if "HTTP 404" in str(error):
            return None
        raise


def write_status(path: Path, outcome: str, messages: list[str], token_configured: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "outcome": outcome,
        "token_configured": token_configured,
        "messages": messages,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_github_release_status(
    path: Path = RELEASES_PATH,
    dry_run: bool = False,
    allow_missing_token: bool = False,
    status_output: Path = STATUS_PATH,
) -> list[str]:
    validate_app_releases(path)
    rows = read_manifest(path)
    try:
        token = github_token()
    except GitHubReleaseError:
        if allow_missing_token:
            messages = ["skipped GitHub release status sync: token not configured"]
            return messages
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
    if not dry_run:
        not_found = any(message.startswith("not found ") for message in messages)
        write_status(status_output, "not_found" if not_found else "synced", messages, True)
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync GitHub Release metadata for app release rows")
    parser.add_argument("--manifest", type=Path, default=RELEASES_PATH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-missing-token", action="store_true")
    parser.add_argument("--status-output", type=Path, default=STATUS_PATH)
    args = parser.parse_args()
    try:
        messages = sync_github_release_status(args.manifest, args.dry_run, args.allow_missing_token, args.status_output)
    except (GitHubReleaseError, OSError, json.JSONDecodeError) as error:
        print(f"sync GitHub release status failed: {error}", file=sys.stderr)
        return 1
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
