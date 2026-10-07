#!/usr/bin/env python3
"""Fill planned app release rows from release artifacts and publication approvals."""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import sys
from pathlib import Path

from check_store_versions import STORE_HEADER, STORE_VERSIONS_PATH
from prepare_app_release_rows import CONFIG_HEADER, CONFIG_PATH, read_csv
from validate_app_releases import RELEASE_HEADER, RELEASES_PATH, ROOT, validate_app_releases


BLOCKED_ARTIFACT_MARKERS = ("debug", "dev", "internal", "test")
PUBLIC_STORE_STATES = {"new", "updated", "unchanged"}


class FillReadyReleaseError(ValueError):
    """Raised when planned release rows cannot be safely promoted."""


def write_releases(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RELEASE_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def release_config(path: Path) -> dict[str, dict[str, str]]:
    return {row["app_id"]: row for row in read_csv(path, CONFIG_HEADER)}


def public_store_versions(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    """Only independently observed public store versions authorize publication."""
    if not path.exists():
        return {}
    return {
        (row["app_id"], row["platform"]): row
        for row in read_csv(path, STORE_HEADER)
        if row["status"] in PUBLIC_STORE_STATES
        and row["version"]
        and "public page lookup failed" not in row.get("notes", "").lower()
    }


def is_store_confirmed(
    release: dict[str, str],
    public_versions: dict[tuple[str, str], dict[str, str]],
) -> bool:
    if (release.get("release_channel") or "public") != "public":
        return False
    snapshot = public_versions.get((release["app_id"], release["platform"]))
    return bool(snapshot and snapshot["version"] == release["version"])


def mark_notes_ready(row: dict[str, str]) -> None:
    row["release_type"] = "notes_only"
    row["status"] = "ready"
    if not row["changes"].strip():
        row["changes"] = (
            f"Version {row['version']} is available in the public "
            f"{'App Store' if row['platform'] == 'ios' else 'Google Play'}; "
            "the store did not provide specific change notes."
        )
    append_note(row, "Public store version confirmed; GitHub release notes publish automatically.")


def append_note(row: dict[str, str], note: str) -> None:
    notes = row["notes"].strip()
    if note in notes:
        return
    row["notes"] = f"{notes} {note}".strip()


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
    store_versions_path: Path = STORE_VERSIONS_PATH,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    rows = read_csv(releases_path, RELEASE_HEADER)
    config = release_config(config_path)
    public_versions = public_store_versions(store_versions_path)
    updated: list[dict[str, str]] = []

    for row in rows:
        if row["status"] != "planned":
            continue
        if (row.get("release_channel") or "public") == "private_test":
            if row["artifact_path"] and row["checksum_sha256"]:
                row["status"] = "ready"
                append_note(row, "Private test artifact ready for manual internal-store upload.")
                updated.append(dict(row))
                continue
            if row["artifact_path"] or row["checksum_sha256"]:
                raise FillReadyReleaseError(f"{row['release_id']} artifact_path and checksum_sha256 must be filled together")
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
            append_note(row, "Private test artifact ready for manual internal-store upload.")
            updated.append(dict(row))
            continue
        if (row.get("release_channel") or "public") != "public":
            continue
        confirmed = is_store_confirmed(row, public_versions)
        if row["artifact_path"] or row["checksum_sha256"]:
            if not (row["artifact_path"] and row["checksum_sha256"]):
                raise FillReadyReleaseError(
                    f"{row['release_id']} artifact_path and checksum_sha256 must be filled together"
                )
            if confirmed:
                # The release creator verifies the artifact checksum again before upload.
                row["status"] = "ready"
                append_note(row, "Public store version confirmed; release publishes automatically.")
                updated.append(dict(row))
            continue
        if row.get("release_type") == "notes_only":
            if confirmed:
                mark_notes_ready(row)
                updated.append(dict(row))
            continue
        cfg = config.get(row["app_id"])
        artifacts: list[Path] = []
        if cfg and cfg.get("artifact_pattern"):
            pattern = format_artifact_pattern(cfg["artifact_pattern"], row)
            artifacts = candidate_artifacts(pattern)
            if len(artifacts) > 1:
                raise FillReadyReleaseError(
                    f"{row['release_id']} artifact pattern matched multiple files: {pattern}"
                )
        if artifacts:
            artifact = artifacts[0]
            safe_artifact(artifact, row["release_id"])
            row["artifact_path"] = relative(artifact)
            row["checksum_sha256"] = checksum(artifact)
            append_note(row, "Artifact and checksum filled automatically.")
            if confirmed:
                row["status"] = "ready"
                append_note(row, "Public store version confirmed; release publishes automatically.")
            updated.append(dict(row))
        elif confirmed:
            # The store already distributes the public binary: create release
            # notes without requiring a second, unnecessary binary attachment.
            mark_notes_ready(row)
            updated.append(dict(row))

    if updated and not dry_run:
        write_releases(releases_path, rows)
        validate_app_releases(releases_path)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare public-store-confirmed GitHub releases automatically")
    parser.add_argument("--releases", type=Path, default=RELEASES_PATH)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--stores", type=Path, default=STORE_VERSIONS_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        updated = fill_ready_app_releases(args.releases, args.config, args.stores, args.dry_run)
    except (FillReadyReleaseError, OSError) as error:
        print(f"fill ready app releases failed: {error}", file=sys.stderr)
        return 1
    action = "would update" if args.dry_run else "updated"
    print(f"{action} {len(updated)} app release row(s)")
    for row in updated:
        print(f"{row['release_id']} {row['app_slug']} {row['platform']} {row['tag']} {row['artifact_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
