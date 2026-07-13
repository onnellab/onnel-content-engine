#!/usr/bin/env python3
"""Fill planned app release rows from release artifacts and publication approvals."""

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
PUBLICATIONS_PATH = ROOT / "data" / "app_release_publications.csv"
PUBLICATION_HEADER = ["release_id", "public_release", "approved_at", "notes"]


class FillReadyReleaseError(ValueError):
    """Raised when planned release rows cannot be safely promoted."""


def write_releases(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RELEASE_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def release_config(path: Path) -> dict[str, dict[str, str]]:
    return {row["app_id"]: row for row in read_csv(path, CONFIG_HEADER)}


def publication_approvals(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row["release_id"]: row for row in read_csv(path, PUBLICATION_HEADER)}


def is_public_approved(release_id: str, approvals: dict[str, dict[str, str]]) -> bool:
    row = approvals.get(release_id)
    return bool(row and row["public_release"].lower() == "true")


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
    publications_path: Path = PUBLICATIONS_PATH,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    rows = read_csv(releases_path, RELEASE_HEADER)
    config = release_config(config_path)
    approvals = publication_approvals(publications_path)
    updated: list[dict[str, str]] = []

    for row in rows:
        if row["status"] != "planned":
            continue
        if (row.get("release_channel") or "public") != "public":
            append_note(row, "Private test channel; not promoted to public GitHub Release.")
            updated.append(dict(row))
            continue
        approved = is_public_approved(row["release_id"], approvals)
        if row.get("release_type") == "notes_only":
            if approved:
                row["status"] = "ready"
                append_note(row, "Public release approved for notes-only GitHub Release.")
                updated.append(dict(row))
            continue
        if row["artifact_path"] and row["checksum_sha256"]:
            if approved:
                row["status"] = "ready"
                append_note(row, "Public release approved.")
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
        append_note(row, "Artifact and checksum filled automatically.")
        if approved:
            row["status"] = "ready"
            append_note(row, "Public release approved.")
        else:
            append_note(row, "Kept planned until public release is approved.")
        updated.append(dict(row))

    if updated and not dry_run:
        write_releases(releases_path, rows)
        validate_app_releases(releases_path)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill app release artifacts and promote only public-approved rows")
    parser.add_argument("--releases", type=Path, default=RELEASES_PATH)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--publications", type=Path, default=PUBLICATIONS_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        updated = fill_ready_app_releases(args.releases, args.config, args.publications, args.dry_run)
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
