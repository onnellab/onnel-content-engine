#!/usr/bin/env python3
"""Generate a Markdown report for app store and GitHub Release automation state."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from check_store_versions import ANDROID_HEADER, ANDROID_VERSIONS_PATH, STORE_HEADER, STORE_VERSIONS_PATH
from prepare_app_release_rows import CONFIG_HEADER, CONFIG_PATH
from sync_android_versions_from_repos import LOCAL_REPOSITORIES_HEADER, LOCAL_REPOSITORIES_PATH, pubspec_version
from validate_app_releases import RELEASE_HEADER, RELEASES_PATH


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "generated" / "reports" / "app_releases.md"
PUBLICATIONS_PATH = ROOT / "data" / "app_release_publications.csv"
PUBLICATION_HEADER = ["release_id", "public_release", "approved_at", "notes"]
KST = ZoneInfo("Asia/Seoul")
VERSION_PART_RE = re.compile(r"\d+|[A-Za-z]+")


class AppReleaseReportError(ValueError):
    """Raised when the app release report cannot be generated."""


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise AppReleaseReportError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def read_optional_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_csv(path, expected_header)


def markdown(value: str) -> str:
    cleaned = " ".join(value.split())
    return cleaned.replace("|", "\\|") or "-"


def store_action(row: dict[str, str]) -> str:
    status = row["status"]
    if status == "updated":
        return "Create or verify release candidate"
    if status == "manual_check":
        return "Check Google Play update manually"
    if status == "failed":
        return "Fix store lookup error"
    if status == "new":
        return "Baseline snapshot recorded"
    if status == "unchanged":
        return "No action"
    return "Review status"


def next_action(row: dict[str, str], comparison: str) -> str:
    if comparison == "local_ahead":
        if row["status"] in {"updated", "new"}:
            return "Release ready; prepare store rollout"
        return "Store not updated; confirm public rollout"
    if comparison == "store_ahead":
        return "Sync local metadata"
    return store_action(row)


def completed_release_action(comparison: str) -> str:
    if comparison == "store_ahead":
        return "Sync local metadata"
    if comparison == "local_ahead":
        return "Store release complete; confirm next public rollout"
    return "No action"


def release_action(row: dict[str, str]) -> str:
    status = row["status"]
    if (row.get("release_channel") or "public") != "public":
        return "Private test only; do not publish public GitHub Release"
    if "Local Flutter build metadata version" in row.get("changes", ""):
        return "Replace placeholder with public patch notes"
    if status == "planned":
        if row.get("release_type") == "notes_only":
            return "Release ready; approve public notes-only release"
        if row.get("artifact_path") and row.get("checksum_sha256"):
            return "Release ready; approve public release or keep private"
        return "Add release artifact and checksum"
    if status == "ready":
        return "GitHub Release can be created"
    if status == "released":
        return "No action"
    if status == "failed":
        return "Fix release error"
    if status == "archived":
        return "No action"
    return "Review status"


def config_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["app_id"]: row for row in rows}


def local_version_index(rows: list[dict[str, str]]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for row in rows:
        pubspec_path = Path(row["path"]) / row["pubspec_path"]
        if not pubspec_path.exists():
            continue
        version, _raw = pubspec_version(pubspec_path)
        versions[row["app_id"]] = version
    return versions


def local_metadata_version_index(rows: list[dict[str, str]]) -> dict[str, str]:
    return {
        row["app_id"]: row["version"]
        for row in rows
        if row.get("source") == "local_build_metadata" and row.get("app_id") and row.get("version")
    }


def version_key(version: str) -> list[tuple[int, int | str]]:
    key: list[tuple[int, int | str]] = []
    for part in VERSION_PART_RE.findall(version):
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return key


def compare_versions(store_version: str, local_version: str) -> str:
    if not store_version or not local_version:
        return "unknown"
    store_key = version_key(store_version)
    local_key = version_key(local_version)
    if store_key == local_key:
        return "same"
    if local_key > store_key:
        return "local_ahead"
    return "store_ahead"


def release_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    index: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        index.setdefault((row["app_id"], row["platform"]), []).append(row)
    return index


def release_matches_store(release_row: dict[str, str], store_row: dict[str, str]) -> bool:
    return (
        bool(release_row)
        and release_row.get("status") == "released"
        and (release_row.get("release_channel") or "public") == "public"
        and release_row.get("version") == store_row.get("version")
    )


def publication_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["release_id"]: row for row in rows}


def store_notes_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], str]:
    return {
        (row["app_id"], row["platform"]): row["release_notes"]
        for row in rows
        if row.get("release_notes")
    }


def publication_gate(row: dict[str, str], approvals: dict[str, dict[str, str]]) -> str:
    if (row.get("release_channel") or "public") != "public":
        return "Private test; public Release disabled"
    status = row["status"]
    approved = approvals.get(row["release_id"], {}).get("public_release", "").lower() == "true"
    has_artifact = bool(row["artifact_path"] and row["checksum_sha256"])
    notes_only = row.get("release_type") == "notes_only"
    if status == "released":
        return "Released"
    if status == "ready":
        return "Approved public release"
    if status == "planned" and approved and notes_only:
        return "Approved, notes-only ready fill pending"
    if status == "planned" and notes_only:
        return "Waiting for public notes approval"
    if status == "planned" and approved and has_artifact:
        return "Approved, ready fill pending"
    if status == "planned" and approved:
        return "Public approved, waiting for artifact"
    if status == "planned" and has_artifact:
        return "Private test or approval pending"
    if status == "planned":
        return "Waiting for artifact and public approval"
    if status == "failed":
        return "Fix release error"
    if status == "archived":
        return "Archived"
    return "Review"


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(markdown(cell) for cell in row) + " |")
    return lines


def report_markdown(
    store_rows: list[dict[str, str]],
    release_rows: list[dict[str, str]],
    config_rows: list[dict[str, str]],
    local_repo_rows: list[dict[str, str]],
    local_metadata_rows: list[dict[str, str]],
    publication_rows: list[dict[str, str]],
    generated_at: datetime,
) -> str:
    config = config_index(config_rows)
    local_versions = local_version_index(local_repo_rows)
    for app_id, version in local_metadata_version_index(local_metadata_rows).items():
        local_versions.setdefault(app_id, version)
    releases = release_index(release_rows)
    approvals = publication_index(publication_rows)
    store_notes = store_notes_index(store_rows)
    store_counts = Counter(row["status"] for row in store_rows)
    release_counts = Counter(row["status"] for row in release_rows)

    lines = [
        "# App Release Status",
        "",
        f"Generated: {generated_at.replace(microsecond=0).isoformat()}",
        "",
        "## Summary",
        "",
        *table(
            ["Area", "Status", "Count"],
            [["Store", status, str(count)] for status, count in sorted(store_counts.items())]
            + [["GitHub Release", status, str(count)] for status, count in sorted(release_counts.items())],
        ),
        "",
        "## Store Snapshots",
        "",
    ]

    store_table: list[list[str]] = []
    for row in sorted(store_rows, key=lambda item: (item["app_slug"], item["platform"])):
        latest_release = releases.get((row["app_id"], row["platform"]), [])
        latest_release_row = latest_release[-1] if latest_release else {}
        release_status = latest_release_row["status"] if latest_release_row else "-"
        cfg = config.get(row["app_id"], {})
        local_version = local_versions.get(row["app_id"], "")
        comparison = compare_versions(row["version"], local_version)
        if latest_release_row and release_status in {"planned", "ready", "failed"}:
            action = release_action(latest_release_row)
        elif release_matches_store(latest_release_row, row):
            action = completed_release_action(comparison)
        else:
            action = next_action(row, comparison)
        store_table.append(
            [
                row["app_name"],
                row["platform"],
                row["version"] or row["store_package"] or row["store_app_id"],
                local_version,
                comparison,
                row["status"],
                release_status,
                cfg.get("repository", ""),
                action,
            ]
        )
    lines.extend(
        table(
            ["App", "Platform", "Store version/package", "Local version", "Comparison", "Store", "Release", "Repository", "Next action"],
            store_table,
        )
    )

    lines.extend(["", "## Release Candidates", ""])
    if release_rows:
        release_table = [
            [
                row["release_id"],
                row["app_name"],
                row["platform"],
                row.get("release_channel") or "public",
                row["tag"],
                row["status"],
                publication_gate(row, approvals),
                row["release_url"],
                row["artifact_path"],
                store_notes.get((row["app_id"], row["platform"]), ""),
                release_action(row),
            ]
            for row in release_rows
        ]
        lines.extend(
            table(
                ["ID", "App", "Platform", "Channel", "Tag", "Status", "Publication gate", "Release URL", "Artifact", "Store notes", "Next action"],
                release_table,
            )
        )
    else:
        lines.append("No app release candidate rows exist yet.")

    attention: list[list[str]] = []
    for row in store_rows:
        local_version = local_versions.get(row["app_id"], "")
        comparison = compare_versions(row["version"], local_version)
        latest_release = releases.get((row["app_id"], row["platform"]), [])
        active_release = latest_release and latest_release[-1]["status"] in {"planned", "ready", "failed"}
        completed_release = bool(latest_release) and release_matches_store(latest_release[-1], row)
        if completed_release and comparison in {"local_ahead", "store_ahead"}:
            attention.append([row["app_name"], row["platform"], row["status"], completed_release_action(comparison), row["notes"]])
        elif not active_release and not completed_release and (
            row["status"] in {"updated", "manual_check", "failed"} or comparison in {"local_ahead", "store_ahead"}
        ):
            attention.append([row["app_name"], row["platform"], row["status"], next_action(row, comparison), row["notes"]])
    attention += [
        [row["app_name"], row["platform"], row["status"], release_action(row), row["notes"]]
        for row in release_rows
        if row["status"] in {"planned", "ready", "failed"}
    ]
    lines.extend(["", "## Attention Queue", ""])
    if attention:
        lines.extend(table(["App", "Platform", "Status", "Next action", "Notes"], attention))
    else:
        lines.append("No release automation items need attention.")

    return "\n".join(lines).rstrip() + "\n"


def generate_app_release_report(
    store_versions_path: Path = STORE_VERSIONS_PATH,
    releases_path: Path = RELEASES_PATH,
    config_path: Path = CONFIG_PATH,
    local_repositories_path: Path = LOCAL_REPOSITORIES_PATH,
    output_path: Path = REPORT_PATH,
    publications_path: Path = PUBLICATIONS_PATH,
    now: datetime | None = None,
    android_versions_path: Path = ANDROID_VERSIONS_PATH,
) -> str:
    store_rows = read_csv(store_versions_path, STORE_HEADER)
    release_rows = read_csv(releases_path, RELEASE_HEADER)
    config_rows = read_csv(config_path, CONFIG_HEADER)
    local_repo_rows = read_csv(local_repositories_path, LOCAL_REPOSITORIES_HEADER)
    local_metadata_rows = read_optional_csv(android_versions_path, ANDROID_HEADER)
    publication_rows = read_optional_csv(publications_path, PUBLICATION_HEADER)
    text = report_markdown(store_rows, release_rows, config_rows, local_repo_rows, local_metadata_rows, publication_rows, now or datetime.now(KST))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate app release automation status report")
    parser.add_argument("--store-versions", type=Path, default=STORE_VERSIONS_PATH)
    parser.add_argument("--releases", type=Path, default=RELEASES_PATH)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--local-repositories", type=Path, default=LOCAL_REPOSITORIES_PATH)
    parser.add_argument("--android-versions", type=Path, default=ANDROID_VERSIONS_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--publications", type=Path, default=PUBLICATIONS_PATH)
    args = parser.parse_args()
    try:
        generate_app_release_report(
            args.store_versions,
            args.releases,
            args.config,
            args.local_repositories,
            args.output,
            args.publications,
            android_versions_path=args.android_versions,
        )
    except (AppReleaseReportError, OSError) as error:
        print(f"generate app release report failed: {error}", file=sys.stderr)
        return 1
    print(f"generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
