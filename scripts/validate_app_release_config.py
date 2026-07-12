#!/usr/bin/env python3
"""Validate app release repository and artifact configuration."""

from __future__ import annotations

import csv
import re
import string
import sys
from pathlib import Path

from prepare_app_release_rows import CONFIG_HEADER, CONFIG_PATH
from validate_apps_registry import APP_HEADER, APPS_PATH


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ALLOWED_PLACEHOLDERS = {"app_id", "app_slug", "version", "platform", "tag"}
REQUIRED_PLACEHOLDERS = {"version", "platform"}


class AppReleaseConfigError(ValueError):
    """Raised when app release config is invalid."""


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise AppReleaseConfigError(f"{path.relative_to(ROOT)} header mismatch")
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    for line_number, row in enumerate(rows, start=2):
        if None in row:
            raise AppReleaseConfigError(f"{path.relative_to(ROOT)} line {line_number} has too many columns")
        if any("\n" in value or "\r" in value for value in row.values()):
            raise AppReleaseConfigError(f"{path.relative_to(ROOT)} line {line_number} contains a line break")
    return rows


def app_index() -> dict[str, dict[str, str]]:
    return {row["app_id"]: row for row in read_csv(APPS_PATH, APP_HEADER)}


def placeholders(pattern: str) -> set[str]:
    names: set[str] = set()
    for literal_text, field_name, _format_spec, _conversion in string.Formatter().parse(pattern):
        if "\\" in literal_text:
            raise AppReleaseConfigError(f"artifact_pattern must use forward slashes: {pattern}")
        if field_name:
            names.add(field_name)
    return names


def validate_pattern(pattern: str, app_slug: str, app_id: str) -> None:
    if not pattern:
        raise AppReleaseConfigError(f"{app_id} artifact_pattern is required")
    if pattern.startswith("/") or ".." in Path(pattern).parts:
        raise AppReleaseConfigError(f"{app_id} artifact_pattern must stay inside the repository")
    if not pattern.startswith("generated/releases/"):
        raise AppReleaseConfigError(f"{app_id} artifact_pattern must start with generated/releases/")
    if "*-release." not in pattern:
        raise AppReleaseConfigError(f"{app_id} artifact_pattern must match release artifacts only")
    names = placeholders(pattern)
    unsupported = names - ALLOWED_PLACEHOLDERS
    if unsupported:
        raise AppReleaseConfigError(f"{app_id} artifact_pattern has unsupported placeholder: {sorted(unsupported)[0]}")
    missing = REQUIRED_PLACEHOLDERS - names
    if missing:
        raise AppReleaseConfigError(f"{app_id} artifact_pattern is missing placeholder: {sorted(missing)[0]}")
    if app_slug not in pattern and "{app_slug}" not in pattern:
        raise AppReleaseConfigError(f"{app_id} artifact_pattern should include the app slug")


def validate_app_release_config(path: Path = CONFIG_PATH) -> int:
    apps = app_index()
    rows = read_csv(path, CONFIG_HEADER)
    seen: set[str] = set()
    released_apps = {app_id for app_id, app in apps.items() if app["status"] == "released"}

    for row in rows:
        app_id = row["app_id"]
        if app_id in seen:
            raise AppReleaseConfigError(f"duplicated app_id: {app_id}")
        seen.add(app_id)
        app = apps.get(app_id)
        if not app:
            raise AppReleaseConfigError(f"unknown app_id: {app_id}")
        if row["app_slug"] != app["slug"]:
            raise AppReleaseConfigError(f"{app_id} app_slug does not match app registry")
        if not REPOSITORY_RE.fullmatch(row["repository"]):
            raise AppReleaseConfigError(f"{app_id} repository must use owner/name format")
        validate_pattern(row["artifact_pattern"], row["app_slug"], app_id)

    missing = sorted(released_apps - seen)
    if missing:
        raise AppReleaseConfigError(f"missing release config for released app: {missing[0]}")
    return len(rows)


def main() -> int:
    try:
        count = validate_app_release_config()
    except (AppReleaseConfigError, OSError) as error:
        print(f"app release config validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {count} app release config row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
