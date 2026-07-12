#!/usr/bin/env python3
"""Collect local release artifacts into generated/releases for ready promotion."""

from __future__ import annotations

import argparse
import csv
import glob
import shutil
import sys
from pathlib import Path

from sync_android_versions_from_repos import LOCAL_REPOSITORIES_HEADER, LOCAL_REPOSITORIES_PATH
from validate_app_releases import RELEASE_HEADER, RELEASES_PATH, ROOT


COLLECT_PATTERNS = {
    "android": ["build/app/outputs/bundle/release/*-release.aab", "build/app/outputs/flutter-apk/*-release.apk"],
    "ios": ["build/ios/ipa/*-release.ipa", "build/ios/ipa/*.ipa"],
}
BLOCKED_ARTIFACT_MARKERS = ("debug", "dev", "internal", "test")


class CollectReleaseArtifactError(ValueError):
    """Raised when local release artifacts cannot be collected safely."""


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise CollectReleaseArtifactError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def local_repository_index(path: Path) -> dict[str, dict[str, str]]:
    return {row["app_id"]: row for row in read_csv(path, LOCAL_REPOSITORIES_HEADER)}


def safe_artifact(path: Path, release_id: str) -> None:
    name = path.name.lower()
    if any(marker in name for marker in BLOCKED_ARTIFACT_MARKERS):
        raise CollectReleaseArtifactError(f"{release_id} artifact looks like a non-release build: {path.name}")


def source_artifacts(repo_path: Path, platform: str) -> list[Path]:
    patterns = COLLECT_PATTERNS.get(platform, [])
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(Path(match) for match in glob.glob(str(repo_path / pattern)))
    return sorted(path for path in matches if path.is_file())


def destination_path(row: dict[str, str], artifact: Path) -> Path:
    suffix = artifact.suffix or ".artifact"
    filename = f"{row['app_slug']}-{row['platform']}-{row['version']}-release{suffix}"
    return ROOT / "generated" / "releases" / row["app_slug"] / row["version"] / row["platform"] / filename


def collect_release_artifacts(
    releases_path: Path = RELEASES_PATH,
    repositories_path: Path = LOCAL_REPOSITORIES_PATH,
    dry_run: bool = False,
) -> list[tuple[Path, Path]]:
    releases = read_csv(releases_path, RELEASE_HEADER)
    repositories = local_repository_index(repositories_path)
    copied: list[tuple[Path, Path]] = []

    for row in releases:
        if row["status"] != "planned":
            continue
        repo = repositories.get(row["app_id"])
        if not repo:
            continue
        artifacts = source_artifacts(Path(repo["path"]), row["platform"])
        if not artifacts:
            continue
        if len(artifacts) > 1:
            raise CollectReleaseArtifactError(f"{row['release_id']} matched multiple local artifacts")
        source = artifacts[0]
        safe_artifact(source, row["release_id"])
        destination = destination_path(row, source)
        copied.append((source, destination))
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect local release artifacts into generated/releases")
    parser.add_argument("--releases", type=Path, default=RELEASES_PATH)
    parser.add_argument("--repositories", type=Path, default=LOCAL_REPOSITORIES_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        copied = collect_release_artifacts(args.releases, args.repositories, args.dry_run)
    except (CollectReleaseArtifactError, OSError) as error:
        print(f"collect release artifacts failed: {error}", file=sys.stderr)
        return 1
    action = "would collect" if args.dry_run else "collected"
    print(f"{action} {len(copied)} release artifact(s)")
    for source, destination in copied:
        print(f"{source} -> {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
