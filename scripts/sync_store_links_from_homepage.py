#!/usr/bin/env python3
"""Sync App Store and Google Play links from the ONNELLAB homepage app metadata."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from validate_apps_registry import APP_HEADER, APPS_PATH


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOMEPAGE_APPS_DIR = ROOT.parent / "onnelakin.github.io" / "src" / "content" / "apps"
FRONTMATTER_RE = re.compile(r"^---\n(?P<body>.*?)\n---", re.DOTALL)


class StoreLinkSyncError(ValueError):
    """Raised when homepage store links cannot be synced."""


def read_apps(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != APP_HEADER:
            raise StoreLinkSyncError(f"{path} header mismatch")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_apps(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=APP_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_homepage_app_meta(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.search(text)
    body = match.group("body") if match else text
    values: dict[str, str] = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def homepage_store_links(apps_dir: Path) -> dict[str, dict[str, str]]:
    if not apps_dir.exists():
        raise StoreLinkSyncError(f"homepage apps directory does not exist: {apps_dir}")
    links: dict[str, dict[str, str]] = {}
    for app_dir in sorted(path for path in apps_dir.iterdir() if path.is_dir()):
        app_file = app_dir / "app.md"
        if not app_file.exists():
            continue
        meta = parse_homepage_app_meta(app_file)
        links[app_dir.name] = {
            "app_store_url": meta.get("appstore", ""),
            "play_store_url": meta.get("googleplay", ""),
        }
    return links


def sync_store_links(
    apps_path: Path = APPS_PATH,
    homepage_apps_dir: Path = DEFAULT_HOMEPAGE_APPS_DIR,
    dry_run: bool = False,
) -> list[str]:
    rows = read_apps(apps_path)
    links = homepage_store_links(homepage_apps_dir)
    changes: list[str] = []
    for row in rows:
        slug = row["slug"]
        if slug not in links:
            continue
        source = links[slug]
        for field in ("app_store_url", "play_store_url"):
            current = row[field]
            incoming = source[field]
            if incoming and current != incoming:
                changes.append(f"{slug} {field}: {current or '<empty>'} -> {incoming}")
                if not dry_run:
                    row[field] = incoming
    if changes and not dry_run:
        write_apps(apps_path, rows)
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync store links from homepage app metadata")
    parser.add_argument("--apps", type=Path, default=APPS_PATH)
    parser.add_argument("--homepage-apps-dir", type=Path, default=DEFAULT_HOMEPAGE_APPS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        changes = sync_store_links(args.apps, args.homepage_apps_dir, args.dry_run)
    except (StoreLinkSyncError, OSError) as error:
        print(f"store link sync failed: {error}", file=sys.stderr)
        return 1
    action = "would update" if args.dry_run else "updated"
    print(f"{action} {len(changes)} store link field(s)")
    for change in changes:
        print(change)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
