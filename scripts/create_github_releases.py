#!/usr/bin/env python3
"""Create GitHub Releases from ready app release manifest rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from validate_app_releases import RELEASE_HEADER, RELEASES_PATH, ROOT, validate_app_releases


GITHUB_API = "https://api.github.com"
GITHUB_UPLOADS = "https://uploads.github.com"
USER_AGENT = "ONNELLAB content engine"


class GitHubReleaseError(ValueError):
    """Raised when a GitHub Release cannot be created safely."""


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != RELEASE_HEADER:
            raise GitHubReleaseError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RELEASE_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def github_token() -> str:
    token = os.environ.get("GITHUB_RELEASE_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubReleaseError("GITHUB_RELEASE_TOKEN or GITHUB_TOKEN is required")
    return token


def github_request(
    path_or_url: str,
    token: str,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    data: bytes | None = None,
    content_type: str = "application/json",
) -> dict[str, object]:
    url = path_or_url if path_or_url.startswith("https://") else f"{GITHUB_API}{path_or_url}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else data
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if body is not None:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status == 204:
                return {}
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise GitHubReleaseError(f"HTTP {error.code} from {url}: {detail}") from error


def release_exists(repository: str, tag: str, token: str) -> bool:
    path = f"/repos/{repository}/releases/tags/{urllib.parse.quote(tag, safe='')}"
    try:
        github_request(path, token)
        return True
    except GitHubReleaseError as error:
        if "HTTP 404" in str(error):
            return False
        raise


def release_body(row: dict[str, str]) -> str:
    parts = [
        f"# {row['release_title']}",
        "",
        "## What changed",
        row["changes"],
        "",
        "## Compatibility",
        row["compatibility"],
        "",
        "## Upgrade notes",
        row["upgrade_notes"] or "No special upgrade steps.",
        "",
        "## Checks",
        "- Release build verified",
        "- Debug build excluded",
        f"- Version tag: {row['tag']}",
        f"- SHA-256: `{row['checksum_sha256']}`",
    ]
    if row["summary"]:
        parts.insert(2, row["summary"])
        parts.insert(3, "")
    if row["previous_tag"]:
        parts.append(f"- Previous tag: {row['previous_tag']}")
    if row["notes"]:
        parts.extend(["", "## Notes", row["notes"]])
    return "\n".join(parts).strip() + "\n"


def create_release(row: dict[str, str], token: str, draft: bool) -> dict[str, object]:
    payload = {
        "tag_name": row["tag"],
        "name": row["release_title"],
        "body": release_body(row),
        "draft": draft,
        "prerelease": False,
        "generate_release_notes": False,
    }
    return github_request(f"/repos/{row['repository']}/releases", token, "POST", payload)


def upload_asset(upload_url: str, artifact_path: Path, token: str) -> dict[str, object]:
    base_url = upload_url.split("{", 1)[0]
    query = urllib.parse.urlencode({"name": artifact_path.name})
    url = f"{base_url}?{query}"
    content_type = mimetypes.guess_type(artifact_path.name)[0] or "application/octet-stream"
    upload_url = url.replace(GITHUB_API, GITHUB_UPLOADS)
    return github_request(upload_url, token, "POST", data=artifact_path.read_bytes(), content_type=content_type)


def verify_checksum(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise GitHubReleaseError(f"checksum mismatch for {path}: expected {expected}, got {actual}")


def process_release(row: dict[str, str], token: str, draft: bool, dry_run: bool) -> str:
    artifact_path = ROOT / row["artifact_path"]
    verify_checksum(artifact_path, row["checksum_sha256"])
    if dry_run:
        return f"would create {row['repository']} {row['tag']} with {row['artifact_path']}"
    if release_exists(row["repository"], row["tag"], token):
        raise GitHubReleaseError(f"release already exists: {row['repository']} {row['tag']}")
    release = create_release(row, token, draft)
    upload_url = release.get("upload_url")
    if not isinstance(upload_url, str) or not upload_url:
        raise GitHubReleaseError("GitHub release response did not include upload_url")
    upload_asset(upload_url, artifact_path, token)
    row["status"] = "released"
    return f"created {row['repository']} {row['tag']} with {row['artifact_path']}"


def create_github_releases(path: Path = RELEASES_PATH, dry_run: bool = False, draft: bool = True) -> list[str]:
    validate_app_releases(path)
    rows = read_manifest(path)
    ready = [row for row in rows if row["status"] == "ready"]
    if not ready:
        return []
    token = "dry-run-token" if dry_run else github_token()
    messages = [process_release(row, token, draft, dry_run) for row in ready]
    if not dry_run:
        write_manifest(path, rows)
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Create GitHub Releases from ready app release rows")
    parser.add_argument("--manifest", type=Path, default=RELEASES_PATH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--publish", action="store_true", help="Create a public release instead of a draft")
    args = parser.parse_args()
    try:
        messages = create_github_releases(args.manifest, args.dry_run, draft=not args.publish)
    except (GitHubReleaseError, OSError, json.JSONDecodeError) as error:
        print(f"create GitHub releases failed: {error}", file=sys.stderr)
        return 1
    if not messages:
        print("no ready app release row(s)")
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
