#!/usr/bin/env python3
"""Sync Flutter SDK and plugin dependency versions from local Flutter app repositories."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_REPOSITORIES_PATH = ROOT / "data" / "local_repositories.csv"
LOCAL_REPOSITORIES_HEADER = [
    "app_id",
    "app_slug",
    "repository_name",
    "path",
    "pubspec_path",
    "source_priority",
    "notes",
]
OUTPUT_CSV_PATH = ROOT / "data" / "app_flutter_dependency_versions.csv"
OUTPUT_REPORT_PATH = ROOT / "generated" / "reports" / "app_flutter_dependency_versions.md"
OUTPUT_HEADER = [
    "app_id",
    "app_slug",
    "package_type",
    "package_name",
    "declared_version",
    "resolved_version",
    "flutter_constraint",
    "status",
    "source",
]


class FlutterDependencySyncError(ValueError):
    """Raised when Flutter/dependency metadata cannot be read from local repos."""


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise FlutterDependencySyncError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    groups = defaultdict(list)
    for row in rows:
        groups[row["app_slug"]].append(row)

    lines: list[str] = [
        "# Flutter SDK + plugin dependency snapshot",
        "",
        "Generated from local repositories in `data/local_repositories.csv`.",
        "",
    ]
    for app_slug in sorted(groups):
        app_rows = groups[app_slug]
        app_id = app_rows[0]["app_id"] if app_rows else ""
        lines.append(f"## {app_slug} ({app_id})")
        lines.append("")
        lines.append("| Type | Package | Declared | Resolved | Flutter SDK | Status | Source |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for row in sorted(
            app_rows, key=lambda r: (r["package_type"], r["package_name"], r["source"])
        ):
            lines.append(
                "| "
                + " | ".join(
                    [
                        row["package_type"],
                        row["package_name"],
                        row["declared_version"] or "-",
                        row["resolved_version"] or "-",
                        row["flutter_constraint"] or "-",
                        row["status"],
                        row["source"],
                    ]
                )
                + " |"
            )
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def normalize_dependency_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        value = value[1:-1]
    return value.strip()


def parse_pubspec(
    path: Path,
) -> tuple[str, dict[str, str], dict[str, str]]:
    text = path.read_text(encoding="utf-8").splitlines()
    flutter_constraint = ""
    dependencies: dict[str, str] = {}
    dev_dependencies: dict[str, str] = {}
    section: str | None = None
    active_dependency: tuple[str, str] | None = None
    # tuple(package, section): capture nested entries like `git:` and `path:`

    for raw_line in text:
        line = raw_line.rstrip()
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue

        if not line.startswith(" "):
            key = line.split(":", 1)[0].strip()
            section = key if key in {"environment", "dependencies", "dev_dependencies"} else None
            active_dependency = None
            continue

        if section == "environment":
            if not line.startswith("  ") or line.startswith("    "):
                continue
            match = re.match(r"^\s{2}([a-zA-Z0-9_]+)\s*:\s*(.*)$", line)
            if match and match.group(1) == "flutter":
                flutter_constraint = normalize_dependency_value(match.group(2))
            continue

        if section not in {"dependencies", "dev_dependencies"}:
            continue

        indent = len(raw_line) - len(stripped)
        if indent == 2:
            match = re.match(r"^\s{2}([A-Za-z0-9_\\-]+)\s*:\s*(.*)$", line)
            if not match:
                active_dependency = None
                continue
            dependency_name = match.group(1)
            raw_value = normalize_dependency_value(match.group(2))
            if section == "dependencies":
                dependencies[dependency_name] = raw_value
            else:
                dev_dependencies[dependency_name] = raw_value
            active_dependency = (dependency_name, section) if not raw_value else None
            continue

        if indent >= 4 and active_dependency is not None:
            dependency_name, dependency_section = active_dependency
            match = re.match(r"^\s{4,6}([A-Za-z0-9_\\-]+)\s*:\s*(.*)$", line)
            if not match:
                continue
            nested_key = match.group(1)
            nested_value = normalize_dependency_value(match.group(2))
            value = nested_key if not nested_value else f"{nested_key}:{nested_value}"
            if dependency_section == "dependencies":
                dependencies[dependency_name] = value
            else:
                dev_dependencies[dependency_name] = value

    return flutter_constraint, dependencies, dev_dependencies


def parse_pubspec_lock(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    versions: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    in_packages = False
    current: str | None = None
    for raw_line in lines:
        line = raw_line.rstrip()
        if not in_packages:
            if line == "packages:":
                in_packages = True
            continue
        if line == "sdks:":
            break
        match_package = re.match(r"^\s{2}([A-Za-z0-9_\\-]+):\s*$", raw_line)
        if match_package:
            current = match_package.group(1)
            continue
        if not current:
            continue
        match_version = re.match(r'^\s{4}version:\s*"([^"]+)"\s*$', raw_line)
        if match_version:
            versions[current] = match_version.group(1)
    return versions


def dependency_rows(
    app_id: str,
    app_slug: str,
    dependency_map: dict[str, str],
    lock_versions: dict[str, str],
    package_type: str,
    source: str,
    has_lock: bool,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for package_name in sorted(dependency_map):
        declared = dependency_map[package_name]
        resolved = lock_versions.get(package_name, "")
        if resolved:
            status = "ok"
        elif not has_lock:
            status = "missing_pubspec_lock"
        elif declared in {"", "path", "path:", "hosted", "git", "dependency"}:
            status = "non_semver"
        else:
            status = "unresolved"
        rows.append(
            {
                "app_id": app_id,
                "app_slug": app_slug,
                "package_type": package_type,
                "package_name": package_name,
                "declared_version": declared,
                "resolved_version": resolved,
                "flutter_constraint": "",
                "status": status,
                "source": source,
            }
        )
    return rows


def sync_flutter_plugin_versions(
    repositories_path: Path = LOCAL_REPOSITORIES_PATH,
    output_csv: Path = OUTPUT_CSV_PATH,
    output_report: Path = OUTPUT_REPORT_PATH,
    include_dev_dependencies: bool = False,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for repository in read_csv(repositories_path, LOCAL_REPOSITORIES_HEADER):
        app_id = repository["app_id"]
        app_slug = repository["app_slug"]
        repo_root = Path(repository["path"])
        pubspec_path = repo_root / repository["pubspec_path"]
        source = pubspec_path.as_posix()

        if not repo_root.exists():
            rows.append(
                {
                    "app_id": app_id,
                    "app_slug": app_slug,
                    "package_type": "repository",
                    "package_name": "path",
                    "declared_version": "",
                    "resolved_version": "",
                    "flutter_constraint": "",
                    "status": "missing_repo",
                    "source": repo_root.as_posix(),
                }
            )
            continue

        if not pubspec_path.exists():
            rows.append(
                {
                    "app_id": app_id,
                    "app_slug": app_slug,
                    "package_type": "repository",
                    "package_name": "pubspec.yaml",
                    "declared_version": "",
                    "resolved_version": "",
                    "flutter_constraint": "",
                    "status": "missing_pubspec",
                    "source": source,
                }
            )
            continue

        flutter_constraint, dependencies, dev_dependencies = parse_pubspec(pubspec_path)
        lock_path = pubspec_path.with_name("pubspec.lock")
        lock_versions = parse_pubspec_lock(lock_path)
        has_lock = lock_path.exists()

        rows.append(
            {
                "app_id": app_id,
                "app_slug": app_slug,
                "package_type": "flutter_sdk",
                "package_name": "flutter",
                "declared_version": flutter_constraint,
                "resolved_version": "",
                "flutter_constraint": flutter_constraint,
                "status": "ok" if flutter_constraint else "missing_flutter_constraint",
                "source": source,
            }
        )

        rows.extend(
            dependency_rows(
                app_id=app_id,
                app_slug=app_slug,
                dependency_map=dependencies,
                lock_versions=lock_versions,
                package_type="dependency",
                source=source,
                has_lock=has_lock,
            )
        )
        if include_dev_dependencies:
            rows.extend(
                dependency_rows(
                    app_id=app_id,
                    app_slug=app_slug,
                    dependency_map=dev_dependencies,
                    lock_versions=lock_versions,
                    package_type="dev_dependency",
                    source=source,
                    has_lock=has_lock,
                )
            )

    rows.sort(key=lambda row: (row["app_slug"], row["package_type"], row["package_name"]))
    if not dry_run:
        write_csv(output_csv, rows)
        write_report(output_report, rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync Flutter SDK and plugin dependency versions from local repositories"
    )
    parser.add_argument("--repositories", type=Path, default=LOCAL_REPOSITORIES_PATH)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV_PATH)
    parser.add_argument("--output-report", type=Path, default=OUTPUT_REPORT_PATH)
    parser.add_argument("--include-dev-dependencies", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        rows = sync_flutter_plugin_versions(
            repositories_path=args.repositories,
            output_csv=args.output_csv,
            output_report=args.output_report,
            include_dev_dependencies=args.include_dev_dependencies,
            dry_run=args.dry_run,
        )
    except (FlutterDependencySyncError, OSError, ValueError) as error:
        print(f"sync flutter plugin versions failed: {error}", file=sys.stderr)
        return 1

    action = "would sync" if args.dry_run else "synced"
    app_count = len({row["app_id"] for row in rows})
    print(f"{action} {len(rows)} row(s) for {app_count} app(s)")
    for row in rows:
        print(f"{row['app_slug']} {row['package_type']} {row['package_name']} {row['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
