#!/usr/bin/env python3
"""Import Android store version rows from a Play Console style CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from check_store_versions import ANDROID_HEADER, ANDROID_VERSIONS_PATH, play_package
from validate_android_store_versions import validate_android_store_versions
from validate_apps_registry import APP_HEADER, APPS_PATH


ROOT = Path(__file__).resolve().parents[1]

PACKAGE_COLUMNS = ["package", "package_name", "package name", "Package name", "Package"]
VERSION_COLUMNS = ["version", "version_name", "version name", "Version name", "Version"]
UPDATED_COLUMNS = ["last_updated", "last updated", "Last updated", "release_date", "Release date"]
NOTES_COLUMNS = ["release_notes", "release notes", "Release notes", "notes", "Notes"]


class AndroidStoreImportError(ValueError):
    """Raised when Android store version import cannot complete."""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise AndroidStoreImportError(f"{path} is missing a header")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_android_versions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANDROID_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def first_value(row: dict[str, str], columns: list[str]) -> str:
    lower_map = {key.lower(): value for key, value in row.items()}
    for column in columns:
        if column in row and row[column]:
            return row[column]
        value = lower_map.get(column.lower(), "")
        if value:
            return value
    return ""


def android_apps() -> dict[str, dict[str, str]]:
    apps: dict[str, dict[str, str]] = {}
    with APPS_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != APP_HEADER:
            raise AndroidStoreImportError("apps registry header mismatch")
        for row in reader:
            play_url = (row.get("play_store_url") or "").strip()
            if play_url:
                apps[play_package(play_url)] = {key: (value or "").strip() for key, value in row.items()}
    return apps


def imported_rows(input_path: Path, source: str) -> list[dict[str, str]]:
    apps_by_package = android_apps()
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_row in read_csv(input_path):
        package = first_value(source_row, PACKAGE_COLUMNS)
        version = first_value(source_row, VERSION_COLUMNS)
        if not package and not version:
            continue
        if not package:
            raise AndroidStoreImportError("input row is missing package")
        if not version:
            raise AndroidStoreImportError(f"{package} is missing version")
        app = apps_by_package.get(package)
        if not app:
            raise AndroidStoreImportError(f"unknown Android package: {package}")
        if app["app_id"] in seen:
            raise AndroidStoreImportError(f"duplicated app_id in import: {app['app_id']}")
        seen.add(app["app_id"])
        rows.append(
            {
                "app_id": app["app_id"],
                "app_slug": app["slug"],
                "package": package,
                "version": version,
                "last_updated": first_value(source_row, UPDATED_COLUMNS),
                "release_notes": first_value(source_row, NOTES_COLUMNS),
                "source": source,
                "notes": f"Imported from {input_path.name}.",
            }
        )
    return sorted(rows, key=lambda row: row["app_slug"])


def import_android_store_versions(
    input_path: Path,
    output_path: Path = ANDROID_VERSIONS_PATH,
    source: str = "play_console_export",
    dry_run: bool = False,
) -> list[dict[str, str]]:
    rows = imported_rows(input_path, source)
    if not dry_run:
        write_android_versions(output_path, rows)
        validate_android_store_versions(output_path)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Android store versions from a CSV export")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=ANDROID_VERSIONS_PATH)
    parser.add_argument("--source", default="play_console_export", choices=["play_console_export", "manual_entry", "local_build_metadata"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        rows = import_android_store_versions(args.input, args.output, args.source, args.dry_run)
    except (AndroidStoreImportError, OSError, ValueError) as error:
        print(f"import android store versions failed: {error}", file=sys.stderr)
        return 1
    action = "would import" if args.dry_run else "imported"
    print(f"{action} {len(rows)} android store version row(s)")
    for row in rows:
        print(f"{row['app_slug']} {row['package']} {row['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
