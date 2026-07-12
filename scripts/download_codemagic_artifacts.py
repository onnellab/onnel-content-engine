#!/usr/bin/env python3
"""Download Codemagic release artifacts into generated/releases."""

from __future__ import annotations

import argparse
import csv
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from validate_app_releases import RELEASE_HEADER, RELEASES_PATH, ROOT


CODEMAGIC_API = "https://api.codemagic.io"
CODEMAGIC_ARTIFACTS_PATH = ROOT / "data" / "codemagic_artifacts.csv"
CODEMAGIC_HEADER = ["release_id", "app_id", "app_slug", "version", "platform", "artifact_url", "artifact_name", "notes"]
BLOCKED_ARTIFACT_MARKERS = ("debug", "dev", "internal", "test")


class CodemagicArtifactError(ValueError):
    """Raised when Codemagic artifacts cannot be downloaded safely."""


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise CodemagicArtifactError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def codemagic_token(dry_run: bool = False) -> str:
    if dry_run:
        return "dry-run-token"
    token = os.environ.get("CODEMAGIC_API_TOKEN")
    if not token:
        raise CodemagicArtifactError("CODEMAGIC_API_TOKEN is required")
    return token


def artifact_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row["app_id"], row["platform"], row["version"]


def artifact_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    keyed: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        if row["release_id"]:
            index[row["release_id"]] = row
        key = artifact_key(row)
        if all(key):
            keyed[key] = row
    for key, row in keyed.items():
        index["|".join(key)] = row
    return index


def matching_artifact(row: dict[str, str], index: dict[str, dict[str, str]]) -> dict[str, str] | None:
    return index.get(row["release_id"]) or index.get("|".join(artifact_key(row)))


def safe_name(name: str, release_id: str) -> None:
    lower = name.lower()
    if any(marker in lower for marker in BLOCKED_ARTIFACT_MARKERS):
        raise CodemagicArtifactError(f"{release_id} artifact looks like a non-release build: {name}")
    if not lower.endswith((".ipa", ".aab", ".apk")):
        raise CodemagicArtifactError(f"{release_id} artifact must be .ipa, .aab, or .apk: {name}")


def destination_path(release: dict[str, str], artifact: dict[str, str]) -> Path:
    parsed = urllib.parse.urlparse(artifact["artifact_url"])
    source_name = artifact["artifact_name"] or Path(parsed.path).name
    safe_name(source_name, release["release_id"])
    suffix = Path(source_name).suffix
    filename = f"{release['app_slug']}-{release['platform']}-{release['version']}-release{suffix}"
    return ROOT / "generated" / "releases" / release["app_slug"] / release["version"] / release["platform"] / filename


def codemagic_url(value: str) -> str:
    if value.startswith("https://"):
        return value
    if value.startswith("/"):
        return f"{CODEMAGIC_API}{value}"
    raise CodemagicArtifactError("artifact_url must be an https URL or /artifacts path")


def download(url: str, token: str) -> bytes:
    request = urllib.request.Request(
        codemagic_url(url),
        headers={"x-auth-token": token, "User-Agent": "ONNELLAB content engine"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise CodemagicArtifactError(f"HTTP {error.code} from Codemagic artifact download: {detail}") from error


def download_codemagic_artifacts(
    releases_path: Path = RELEASES_PATH,
    artifacts_path: Path = CODEMAGIC_ARTIFACTS_PATH,
    dry_run: bool = False,
) -> list[tuple[str, Path]]:
    releases = read_csv(releases_path, RELEASE_HEADER)
    artifacts = artifact_index(read_csv(artifacts_path, CODEMAGIC_HEADER))
    token: str | None = None
    downloaded: list[tuple[str, Path]] = []

    for release in releases:
        if release["status"] != "planned" or release["artifact_path"]:
            continue
        artifact = matching_artifact(release, artifacts)
        if not artifact or not artifact["artifact_url"]:
            continue
        destination = destination_path(release, artifact)
        downloaded.append((release["release_id"], destination))
        if not dry_run:
            if token is None:
                token = codemagic_token()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(download(artifact["artifact_url"], token))

    return downloaded


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Codemagic artifacts into generated/releases")
    parser.add_argument("--releases", type=Path, default=RELEASES_PATH)
    parser.add_argument("--artifacts", type=Path, default=CODEMAGIC_ARTIFACTS_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        downloaded = download_codemagic_artifacts(args.releases, args.artifacts, args.dry_run)
    except (CodemagicArtifactError, OSError) as error:
        print(f"download Codemagic artifacts failed: {error}", file=sys.stderr)
        return 1
    action = "would download" if args.dry_run else "downloaded"
    print(f"{action} {len(downloaded)} Codemagic artifact(s)")
    for release_id, destination in downloaded:
        print(f"{release_id} -> {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
