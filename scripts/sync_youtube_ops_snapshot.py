#!/usr/bin/env python3
"""Publish a public-safe YouTube snapshot into the unlisted /ops/ dashboard.

OAuth client secrets, refresh tokens and Keychain payloads are never serialized.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from short_video_pipeline import VideoError, atomic_json
from youtube_profiles import PROFILES
import youtube_report_store

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "youtube_ops_snapshot.json"
DASHBOARD = ROOT / "generated" / "manual-publish" / "index.html"
ASSET_NAMES = (
    "index.html",
    "manifest.webmanifest",
    "sw.js",
    "icon-180.png",
    "icon-192.png",
    "icon-512.png",
    "libsodium-sumo.js",
    "libsodium-wrappers.js",
)
ALLOWED_PROFILE_KEYS = {
    "profile", "state", "channel", "statistics", "summary", "period",
    "videos", "comments", "comments_status", "warnings",
}


def public_profile(source: dict, profile: str) -> dict:
    if not isinstance(source, dict) or source.get("profile") != profile:
        raise VideoError("youtube_report_profile_mismatch")
    extra = set(source) - ALLOWED_PROFILE_KEYS
    if extra:
        raise VideoError("youtube_report_public_field_rejected")
    # JSON round-trip gives us an owned plain-data copy and prevents accidental
    # references to credential-bearing objects.
    result = json.loads(json.dumps(source, ensure_ascii=False))
    return result


def build_snapshot(*, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    profiles: dict[str, dict] = {}
    for profile in PROFILES:
        try:
            report = youtube_report_store.sync(profile, now=now)
            profiles[profile] = public_profile(report["profiles"][profile], profile)
        except (VideoError, OSError):
            profiles[profile] = {
                "profile": profile,
                "state": "blocked",
                "channel": None,
                "statistics": None,
                "summary": None,
                "period": None,
                "videos": [],
                "comments": [],
                "comments_status": "unavailable",
                "warnings": ["connection_or_report_unavailable"],
            }
    return {
        "schema_version": 1,
        "kind": "onnellab_youtube_ops_snapshot",
        "generated_at": now.isoformat(),
        # Keep the last known snapshot visible for a week if the Mac misses a
        # run; the page shows the exact generated time so staleness is obvious.
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "profiles": profiles,
    }


def refresh_dashboard(homepage_repo: Path) -> None:
    manifest = DASHBOARD.parent / "manifest.webmanifest"
    needs_full_build = (
        not DASHBOARD.is_file()
        or not manifest.is_file()
        or '"start_url": "/ops/"' not in manifest.read_text(encoding="utf-8")
    )
    if needs_full_build:
        subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts" / "build_manual_publish_site.py"),
             "--homepage-repo", str(homepage_repo.expanduser().resolve())],
            cwd=ROOT,
            check=True,
        )
    else:
        subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts" / "refresh_youtube_workspace.py"), str(DASHBOARD)],
            cwd=ROOT,
            check=True,
        )


def copy_ops(homepage_repo: Path) -> None:
    homepage_repo = homepage_repo.expanduser().resolve()
    public = homepage_repo / "public"
    target = public / "ops"
    legacy = public / "manual-publish"
    target.mkdir(parents=True, exist_ok=True)
    for name in ASSET_NAMES:
        source = DASHBOARD.parent / name
        if not source.is_file():
            raise VideoError("ops_dashboard_asset_missing")
        shutil.copy2(source, target / name)
    if legacy.exists():
        if legacy.is_symlink():
            raise VideoError("unsafe_legacy_dashboard_path")
        shutil.rmtree(legacy)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--homepage-repo",
        type=Path,
        default=Path.home() / "Projects" / "onnellab.github.io",
    )
    parser.add_argument("--snapshot-only", action="store_true")
    args = parser.parse_args()

    snapshot = build_snapshot()
    atomic_json(SNAPSHOT, snapshot)
    refresh_dashboard(args.homepage_repo)
    if not args.snapshot_only:
        copy_ops(args.homepage_repo)
    print(json.dumps({
        "status": "ok",
        "snapshot": str(SNAPSHOT),
        "profiles": {
            key: {
                "state": value.get("state"),
                "comments": len(value.get("comments") or []),
            }
            for key, value in snapshot["profiles"].items()
        },
        "public_path": None if args.snapshot_only else "/ops/",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
