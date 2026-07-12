#!/usr/bin/env python3
"""Validate Android store version source data."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from check_store_versions import ANDROID_HEADER, ANDROID_VERSIONS_PATH, play_package, read_csv
from validate_apps_registry import APP_HEADER, APPS_PATH


ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?([-.+][0-9A-Za-z.-]+)?$")
SOURCES = {"play_console_export", "manual_entry", "local_build_metadata"}


class AndroidStoreVersionError(ValueError):
    """Raised when Android store version source data is invalid."""


def app_index() -> dict[str, dict[str, str]]:
    return {row["app_id"]: row for row in read_csv(APPS_PATH, APP_HEADER)}


def validate_android_store_versions(path: Path = ANDROID_VERSIONS_PATH) -> int:
    apps = app_index()
    rows = read_csv(path, ANDROID_HEADER)
    seen: set[str] = set()
    for row in rows:
        app_id = row["app_id"]
        if app_id in seen:
            raise AndroidStoreVersionError(f"duplicated app_id: {app_id}")
        seen.add(app_id)
        app = apps.get(app_id)
        if not app:
            raise AndroidStoreVersionError(f"unknown app_id: {app_id}")
        if row["app_slug"] != app["slug"]:
            raise AndroidStoreVersionError(f"{app_id} app_slug does not match app registry")
        if not app["play_store_url"]:
            raise AndroidStoreVersionError(f"{app_id} has Android version data but no Play Store URL")
        expected_package = play_package(app["play_store_url"])
        if row["package"] != expected_package:
            raise AndroidStoreVersionError(f"{app_id} package does not match Play Store URL")
        if not VERSION_RE.fullmatch(row["version"]):
            raise AndroidStoreVersionError(f"{app_id} version does not look like a release version")
        if row["source"] not in SOURCES:
            raise AndroidStoreVersionError(f"{app_id} source must be one of: {', '.join(sorted(SOURCES))}")
    return len(rows)


def main() -> int:
    try:
        count = validate_android_store_versions()
    except (AndroidStoreVersionError, OSError) as error:
        print(f"android store versions validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {count} android store version row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
