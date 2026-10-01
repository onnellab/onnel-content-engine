#!/usr/bin/env python3
"""Synchronize public store releases into the ONNELLAB homepage release-note feed."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE_VERSIONS = ROOT / "data" / "store_versions.csv"
OUTPUT_RELATIVE_PATH = Path("src/data/store-release-notes.json")

NON_PUBLIC_STATUSES = {
    "failed",
    "in_review",
    "manual_check",
    "not_released",
    "unavailable",
    "unknown",
}
PLATFORM_LABELS = {"ios": "iOS", "android": "Android"}
PLATFORM_ORDER = {"iOS": 0, "Android": 1}


def _normalize_date(value: str, fallback: str) -> str:
    text = (value or "").strip()
    if text:
        match = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", text)
        if match:
            year, month, day = (int(part) for part in match.groups())
            return f"{year:04d}-{month:02d}-{day:02d}"
    fallback_text = (fallback or "").strip()
    fallback_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", fallback_text)
    if fallback_match:
        return "-".join(fallback_match.groups())
    return "1970-01-01"


def _split_release_notes(value: str) -> list[str]:
    text = (value or "").strip()
    if not text:
        return []
    if text.startswith("-"):
        normalized = re.sub(r"\s+-\s+", "\n- ", text)
        items = [line.removeprefix("-").strip() for line in normalized.splitlines()]
        return [item for item in items if item]
    return [text]


def _has_hangul(value: str) -> bool:
    return bool(re.search(r"[가-힣]", value))


def _read_existing(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [item for item in payload if isinstance(item, dict)]


def _build_current(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        version = (row.get("version") or "").strip()
        slug = (row.get("app_slug") or "").strip()
        status = (row.get("status") or "").strip()
        platform_key = (row.get("platform") or "").strip().lower()
        if not slug or not version or status in NON_PUBLIC_STATUSES:
            continue
        platform = PLATFORM_LABELS.get(platform_key)
        if not platform:
            continue

        key = (slug, version)
        record = grouped.setdefault(
            key,
            {
                "appSlug": slug,
                "appName": (row.get("app_name") or slug).strip(),
                "version": version,
                "platforms": set(),
                "releasedDate": "1970-01-01",
                "storeNotes": [],
            },
        )
        record["platforms"].add(platform)
        released_date = _normalize_date(
            row.get("last_updated", ""), row.get("checked_at", "")
        )
        if released_date > record["releasedDate"]:
            record["releasedDate"] = released_date
        for note in _split_release_notes(row.get("release_notes", "")):
            if note not in record["storeNotes"]:
                record["storeNotes"].append(note)

    output: list[dict[str, object]] = []
    for record in grouped.values():
        platforms = sorted(record["platforms"], key=lambda item: PLATFORM_ORDER[item])
        platform_text = " · ".join(platforms)
        app_name = str(record["appName"])
        version = str(record["version"])
        store_notes = [str(item) for item in record["storeNotes"]]

        english_generic = f"{app_name} {version} is now available on {platform_text}."
        korean_generic = f"{app_name} {version} 버전이 {platform_text}에 공개됐어요."
        if store_notes and any(_has_hangul(item) for item in store_notes):
            changes = [english_generic]
            changes_ko = store_notes
        elif store_notes:
            changes = store_notes
            changes_ko = [korean_generic]
        else:
            changes = [english_generic]
            changes_ko = [korean_generic]

        output.append(
            {
                "appSlug": record["appSlug"],
                "appName": app_name,
                "version": version,
                "tag": f"v{version}",
                "platform": platform_text,
                "releasedDate": record["releasedDate"],
                "title": f"{app_name} v{version} ({platform_text})",
                "summary": f"Latest public store release of {app_name} {version} for {platform_text}.",
                "summaryKo": f"{app_name} {version} {platform_text} 공개 스토어 릴리즈 변경 사항이에요.",
                "changes": changes,
                "changesKo": changes_ko,
                "internalGitHubUrl": "",
            }
        )
    return output


def _merge_history(
    existing: list[dict[str, object]], current: list[dict[str, object]]
) -> list[dict[str, object]]:
    merged: dict[tuple[str, str], dict[str, object]] = {}
    for note in existing:
        slug = str(note.get("appSlug", "")).strip()
        version = str(note.get("version", "")).strip()
        if slug and version:
            merged[(slug, version)] = note
    for note in current:
        merged[(str(note["appSlug"]), str(note["version"]))] = note
    return sorted(
        merged.values(),
        key=lambda note: (
            str(note.get("appSlug", "")),
            str(note.get("releasedDate", "")),
            str(note.get("version", "")),
        ),
    )


def sync_homepage_release_notes(store_versions: Path, homepage_repo: Path) -> Path:
    with store_versions.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    output_path = homepage_repo / OUTPUT_RELATIVE_PATH
    existing = _read_existing(output_path)
    merged = _merge_history(existing, _build_current(rows))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--store-versions",
        type=Path,
        default=DEFAULT_STORE_VERSIONS,
    )
    parser.add_argument("--homepage-repo", type=Path, required=True)
    args = parser.parse_args()

    output = sync_homepage_release_notes(args.store_versions, args.homepage_repo)
    print(f"synced homepage release notes: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
