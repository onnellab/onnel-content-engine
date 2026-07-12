#!/usr/bin/env python3
"""Validate data/app_releases.csv before GitHub Release automation."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from validate_apps_registry import APP_HEADER, APPS_PATH


ROOT = Path(__file__).resolve().parents[1]
RELEASES_PATH = ROOT / "data" / "app_releases.csv"

RELEASE_HEADER = [
    "release_id",
    "app_id",
    "app_slug",
    "app_name",
    "repository",
    "tag",
    "version",
    "platform",
    "build_type",
    "artifact_path",
    "checksum_sha256",
    "previous_tag",
    "status",
    "release_date",
    "release_title",
    "summary",
    "changes",
    "compatibility",
    "upgrade_notes",
    "notes",
]

STATUS_VALUES = {"planned", "ready", "released", "failed", "archived"}
BUILD_TYPES = {"release"}
PLATFORMS = {"ios", "android", "windows", "macos", "linux", "web"}
BLOCKED_ARTIFACT_MARKERS = ("debug", "dev", "internal", "test")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TAG_RE = re.compile(r"^v?\d+\.\d+\.\d+([-.+][0-9A-Za-z.-]+)?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AppReleaseValidationError(ValueError):
    """Raised when app release metadata is invalid."""


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise AppReleaseValidationError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def app_index() -> dict[str, dict[str, str]]:
    return {row["app_id"]: row for row in read_csv(APPS_PATH, APP_HEADER)}


def validate_release(row: dict[str, str], apps: dict[str, dict[str, str]], seen: set[tuple[str, str]]) -> None:
    release_id = row["release_id"]
    if not release_id:
        raise AppReleaseValidationError("release_id is required")
    app = apps.get(row["app_id"])
    if not app:
        raise AppReleaseValidationError(f"{release_id} references unknown app_id: {row['app_id']}")
    if row["app_slug"] != app["slug"]:
        raise AppReleaseValidationError(f"{release_id} app_slug does not match app registry")
    if row["app_name"] != app["app_name"]:
        raise AppReleaseValidationError(f"{release_id} app_name does not match app registry")
    if row["status"] not in STATUS_VALUES:
        raise AppReleaseValidationError(f"{release_id} has invalid status: {row['status']}")
    if row["platform"] not in PLATFORMS:
        raise AppReleaseValidationError(f"{release_id} has invalid platform: {row['platform']}")
    if row["build_type"] not in BUILD_TYPES:
        raise AppReleaseValidationError(f"{release_id} build_type must be release")
    if not REPOSITORY_RE.fullmatch(row["repository"]):
        raise AppReleaseValidationError(f"{release_id} repository must use owner/name format")
    if not TAG_RE.fullmatch(row["tag"]):
        raise AppReleaseValidationError(f"{release_id} tag must look like a release version")
    key = (row["repository"], row["tag"])
    if key in seen:
        raise AppReleaseValidationError(f"{release_id} duplicates repository/tag: {row['repository']} {row['tag']}")
    seen.add(key)
    artifact = row["artifact_path"].strip()
    if not artifact:
        raise AppReleaseValidationError(f"{release_id} artifact_path is required")
    artifact_lower = Path(artifact).name.lower()
    if any(marker in artifact_lower for marker in BLOCKED_ARTIFACT_MARKERS):
        raise AppReleaseValidationError(f"{release_id} artifact_path looks like a non-release build")
    if row["status"] in {"ready", "released"}:
        artifact_path = ROOT / artifact
        if not artifact_path.exists():
            raise AppReleaseValidationError(f"{release_id} artifact does not exist: {artifact}")
        if not SHA256_RE.fullmatch(row["checksum_sha256"]):
            raise AppReleaseValidationError(f"{release_id} checksum_sha256 must be 64 lowercase hex characters")
        for field in ["release_title", "summary", "changes", "compatibility"]:
            if not row[field]:
                raise AppReleaseValidationError(f"{release_id} {field} is required when status is {row['status']}")


def validate_app_releases(path: Path = RELEASES_PATH) -> int:
    rows = read_csv(path, RELEASE_HEADER)
    apps = app_index()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        validate_release(row, apps, seen)
    return len(rows)


def main() -> int:
    try:
        count = validate_app_releases()
    except (AppReleaseValidationError, OSError) as error:
        print(f"app release validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {count} app release row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
