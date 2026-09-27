#!/usr/bin/env python3
"""Build the private Aether compilation manifest from explicit owner approvals."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import unicodedata

from aether_planner import THEMES, read_catalog
from short_video_pipeline import VideoError, atomic_json, file_hash, load_json
from youtube_report_store import directory

ASSETS_ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/assets"
MYBOX_ROOT = Path.home() / "Library/CloudStorage/MYBOX-yungela1"
COVER_DEFAULTS = {
    "open_roads": "The Road Between Two Kingdoms.png",
    "lantern_towns": "The First Lantern of Autumn.png",
    "woodland_water": "Echoes from Crystal Brook.png",
    "starlit_rest": "A Sky Filled with Migrating Stars.png",
}


def _nfc_child(parent: Path, name: str, *, directory_only: bool = False) -> Path | None:
    expected = unicodedata.normalize("NFC", name)
    direct = parent / expected
    if direct.exists() and (not directory_only or direct.is_dir()):
        return direct
    matches = [
        child for child in parent.iterdir()
        if unicodedata.normalize("NFC", child.name) == expected
        and (not directory_only or child.is_dir())
    ]
    if len(matches) > 1:
        raise VideoError("aether_asset_source_ambiguous")
    return matches[0] if matches else None


def find_source_root(override: Path | None = None) -> Path:
    if override is not None:
        root = Path(override)
        if root.is_symlink() or not root.is_dir():
            raise VideoError("aether_asset_source_missing")
        return root.resolve()
    parent = MYBOX_ROOT
    for name in ("개인 폴더", "Aether Inn"):
        child = _nfc_child(parent, name, directory_only=True)
        if child is None:
            raise VideoError("aether_asset_source_missing")
        parent = child
    if parent.is_symlink():
        raise VideoError("aether_asset_source_unsafe")
    return parent.resolve()


def checked_private_source(root: Path, relative: str, suffixes: set[str]) -> Path:
    rel = Path(relative)
    if not relative or rel.is_absolute() or ".." in rel.parts:
        raise VideoError("aether_relative_asset_required")
    root = Path(root).resolve()
    path = root
    for part in rel.parts:
        path = path / part
        if path.is_symlink():
            raise VideoError("aether_symlink_asset_rejected")
    if not path.is_file() or path.suffix.lower() not in suffixes:
        raise VideoError("aether_asset_source_unavailable")
    return path


def source_title(row: dict) -> str:
    title = row["title"]
    return title[:-7] if title.endswith(" Style:") else title


def hash_private_source(path: Path) -> str:
    try:
        return file_hash(path)
    except OSError:
        raise VideoError("aether_asset_source_materialization_failed") from None


def approval_template() -> dict:
    return {
        "schema_version": 1,
        "profile": "aether_inn",
        "tracks": {
            row["id"]: {
                "title": row["title"],
                "commercial_use_confirmed": False,
                "quality_accepted": False,
            }
            for row in read_catalog()
        },
        "covers": {
            theme: {
                "filename": COVER_DEFAULTS[theme],
                "commercial_use_confirmed": False,
            }
            for theme in THEMES
        },
    }


def init_approval(assets_root: Path = ASSETS_ROOT, *, execute: bool = False) -> dict:
    root = directory(Path(assets_root))
    path = root / "approval.json"
    if path.exists():
        return {"status": "present", "approval_path": str(path)}
    if not execute:
        return {"status": "dry_run", "approval_path": str(path)}
    atomic_json(path, approval_template())
    os.chmod(path, 0o600)
    return {"status": "created", "approval_path": str(path)}


def asset_root_for_manifest(manifest: dict, fallback: Path) -> Path:
    source = manifest.get("asset_source")
    if source is None:
        return Path(fallback)
    if source != "mybox_aether_inn":
        raise VideoError("aether_asset_source_invalid")
    return find_source_root()


def sync(
    assets_root: Path = ASSETS_ROOT,
    *,
    source_root: Path | None = None,
    execute: bool = False,
) -> dict:
    assets_root = directory(Path(assets_root))
    approval_path = assets_root / "approval.json"
    if not approval_path.is_file() or approval_path.is_symlink():
        raise VideoError("aether_asset_approval_missing")
    approval = load_json(approval_path, limit=2 * 1024 * 1024)
    if approval.get("schema_version") != 1 or approval.get("profile") != "aether_inn":
        raise VideoError("aether_asset_approval_invalid")
    catalog = {row["id"]: row for row in read_catalog()}
    source = find_source_root(source_root)
    approved_tracks = {}
    for key, spec in (approval.get("tracks") or {}).items():
        if key not in catalog or not isinstance(spec, dict):
            raise VideoError("aether_asset_approval_invalid")
        if spec.get("commercial_use_confirmed") is not True or spec.get("quality_accepted") is not True:
            continue
        if spec.get("title") != catalog[key]["title"]:
            raise VideoError("aether_asset_approval_title_mismatch")
        relative = f"01_Audio_Master/{source_title(catalog[key])}.wav"
        path = checked_private_source(source, relative, {".wav"})
        approved_tracks[key] = {
            "path": relative,
            "sha256": hash_private_source(path),
            "commercial_use_confirmed": True,
            "quality_accepted": True,
        }
    if not approved_tracks:
        raise VideoError("aether_asset_approval_incomplete")

    approved_covers = {}
    cover_specs = approval.get("covers") or {}
    for theme in THEMES:
        spec = cover_specs.get(theme)
        if not isinstance(spec, dict) or spec.get("commercial_use_confirmed") is not True:
            raise VideoError("aether_asset_approval_incomplete")
        filename = spec.get("filename")
        if not isinstance(filename, str) or not filename or "/" in filename or "\\" in filename:
            raise VideoError("aether_asset_approval_invalid")
        relative = f"02_Cover_Original/{filename}"
        path = checked_private_source(source, relative, {".png", ".jpg", ".jpeg"})
        approved_covers[theme] = {
            "path": relative,
            "sha256": hash_private_source(path),
            "commercial_use_confirmed": True,
        }
    manifest = {
        "schema_version": 1,
        "profile": "aether_inn",
        "test_only": False,
        "asset_source": "mybox_aether_inn",
        "tracks": approved_tracks,
        "covers": approved_covers,
    }
    manifest_path = assets_root / "manifest.json"
    if execute:
        atomic_json(manifest_path, manifest)
        os.chmod(manifest_path, 0o600)
    return {
        "status": "ready" if execute else "dry_run",
        "asset_source": "mybox_aether_inn",
        "approved_track_count": len(approved_tracks),
        "cover_themes": sorted(approved_covers),
        "manifest_path": str(manifest_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-root", type=Path, default=ASSETS_ROOT)
    parser.add_argument("--source-root", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init-approval")
    p.add_argument("--execute", action="store_true")
    p = sub.add_parser("sync")
    p.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "init-approval":
            result = init_approval(args.assets_root, execute=args.execute)
        else:
            result = sync(args.assets_root, source_root=args.source_root, execute=args.execute)
        print(__import__("json").dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (VideoError, OSError, ValueError, TypeError):
        error = __import__("sys").exc_info()[1]
        reason = str(error) if isinstance(error, VideoError) and re.fullmatch(r"[a-z_]{1,90}", str(error)) else "aether_asset_registration_failed"
        print(__import__("json").dumps({"status": "blocked", "error": reason}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
