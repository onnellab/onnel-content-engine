#!/usr/bin/env python3
"""Fill planned app release rows from local release artifacts."""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import sys
from pathlib import Path

from prepare_app_release_rows import CONFIG_HEADER, CONFIG_PATH, read_csv
from validate_app_releases import RELEASE_HEADER, RELEASES_PATH, ROOT, validate_app_releases


BLOCKED_ARTIFACT_MARKERS = ("debug", "dev", "internal", "test")


class FillReadyReleaseError(ValueError):
    """Raised when planned release rows cannot be safely promoted."""


def write_releases(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RELEASE_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def release_config(path: Path) -> dict[str, dict[str, str]]:
    return {row["app_id"]: row for row in read_csv(path, CONFIG_HEADER)}


def format_artifact_pattern(pattern: str, row: dict[str, str]) -> str:
    try:
        return pattern.format(
            app_id=row["app_id"],
            app_slug=row["app_slug"],
            version=row["version"],
            platform=row["platform"],
            tag=row["tag"],
        )
    except KeyError as error:
        raise FillReadyReleaseError(f"{row['release_id']} artifact_pattern has unsupported placeholder: {error}") from error


def candidate_artifacts(pattern: str) -> list[Path]:
    matches = [Path(match) for match in glob.glob(str(ROOT / pattern))]
    files = [path for path in matches if path.is_file()]
    return sorted(files)


def safe_artifact(path: Path, release_id: str) -> None:
    name = path.name.lower()
    if any(marker in name for marker in BLOCKED_ARTIFACT_MARKERS):
        raise FillReadyReleaseError(f"{release_id} artifact looks like a non-release build: {path.name}")


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def fill_ready_app_releases(
    releases_path: Path = RELEASES_PATH,
    config_path: Path = CONFIG_PATH,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    rows = read_csv(releases_path, RELEASE_HEADER)
    config = release_config(config_path)
    promoted: list[dict[str, str]] = []

    for row in rows:
        if row["status"] != "planned" or row["artifact_path"] or row["checksum_sha256"]:
            continue
        cfg = config.get(row["app_id"])
        if not cfg:
            continue
        pattern = format_artifact_pattern(cfg["artifact_pattern"], row)
        artifacts = candidate_artifacts(pattern)
        if not artifacts:
            continue
        if len(artifacts) > 1:
            raise FillReadyReleaseError(f"{row['release_id']} artifact pattern matched multiple files: {pattern}")
        artifact = artifacts[0]
        safe_artifact(artifact, row["release_id"])
        row["artifact_path"] = relative(artifact)
        row["checksum_sha256"] = checksum(artifact)
        row["status"] = "ready"
        row["notes"] = (row["notes"] + " Artifact and checksum filled automatically.").strip()
        promoted.append(dict(row))

    if promoted and not dry_run:
        write_releases(releases_path, rows)
        validate_app_releases(releases_path)
    return promoted


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote planned app release rows when release artifacts are present")
    parser.add_argument("--releases", type=Path, default=RELEASES_PATH)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        promoted = fill_ready_app_releases(args.releases, args.config, args.dry_run)
    except (FillReadyReleaseError, OSError) as error:
        print(f"fill ready app releases failed: {error}", file=sys.stderr)
        return 1
    action = "would promote" if args.dry_run else "promoted"
    print(f"{action} {len(promoted)} app release row(s)")
    for row in promoted:
        print(f"{row['release_id']} {row['app_slug']} {row['platform']} {row['tag']} {row['artifact_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
