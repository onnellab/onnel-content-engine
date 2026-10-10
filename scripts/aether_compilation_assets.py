#!/usr/bin/env python3
"""Build the private Aether compilation manifest from explicit owner approvals."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import unicodedata

from aether_compose import audio_duration
from aether_offline_audio_review import review_audio
from aether_compilation_cover import build as build_compilation_cover
from aether_planner import THEMES, plan, read_catalog, tokens
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


def activate_mybox() -> None:
    try:
        completed = subprocess.run(
            ["/usr/bin/open", "-gja", "MYBOX"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise VideoError("aether_asset_source_provider_unavailable") from None
    if completed.returncode != 0:
        raise VideoError("aether_asset_source_provider_unavailable")
    time.sleep(3)


def find_source_root(override: Path | None = None) -> Path:
    if override is not None:
        root = Path(override)
        if root.is_symlink() or not root.is_dir():
            raise VideoError("aether_asset_source_missing")
        return root.resolve()
    activate_mybox()
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


def hash_private_source(path: Path, *, wake_provider: bool = False) -> str:
    last_error = None
    for attempt in range(3):
        try:
            return file_hash(path)
        except OSError as error:
            last_error = error
            if attempt < 2 and wake_provider:
                activate_mybox()
                time.sleep(2 * (attempt + 1))
    raise VideoError("aether_asset_source_materialization_failed") from last_error


def stage_private_source(source: Path, target: Path, *, wake_provider: bool = False) -> tuple[Path, str]:
    try:
        source_stat = source.stat()
    except OSError:
        raise VideoError("aether_asset_source_unavailable") from None
    if source_stat.st_size <= 0:
        raise VideoError("aether_asset_source_unavailable")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise VideoError("aether_symlink_asset_rejected")
    if target.is_file():
        target_stat = target.stat()
        if (
            target_stat.st_size == source_stat.st_size
            and target_stat.st_mtime_ns == source_stat.st_mtime_ns
        ):
            return target, file_hash(target)
    if shutil.disk_usage(target.parent).free < source_stat.st_size + 1024**3:
        raise VideoError("aether_insufficient_free_disk")
    partial = target.with_suffix(target.suffix + ".partial")
    if partial.is_symlink():
        raise VideoError("aether_symlink_asset_rejected")
    last_error = None
    for attempt in range(3):
        partial.unlink(missing_ok=True)
        try:
            shutil.copyfile(source, partial)
            os.chmod(partial, 0o600)
            os.utime(partial, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
            if partial.stat().st_size != source_stat.st_size:
                raise OSError("short staged copy")
            digest = file_hash(partial)
            partial.replace(target)
            return target, digest
        except OSError as error:
            last_error = error
            partial.unlink(missing_ok=True)
            if attempt < 2 and wake_provider:
                activate_mybox()
                time.sleep(2 * (attempt + 1))
    raise VideoError("aether_asset_source_materialization_failed") from last_error


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
    if source in {None, "local_private_cache"}:
        return Path(fallback)
    if source == "mybox_aether_inn":
        return find_source_root()
    raise VideoError("aether_asset_source_invalid")


def compilation_history(assets_root: Path, *, exclude_slot: str | None = None) -> list[dict]:
    path = Path(assets_root).parent / "queue.json"
    if not path.is_file() or path.is_symlink():
        return []
    state = load_json(path, limit=16 * 1024 * 1024)
    jobs = state.get("jobs")
    if state.get("schema_version") != 1 or not isinstance(jobs, dict):
        raise VideoError("aether_queue_invalid")
    ordered = sorted(jobs.values(), key=lambda job: (str(job.get("slot", "")), str(job.get("id", ""))))
    return [
        {"track_ids": job.get("selection", {}).get("track_ids", [])}
        for job in ordered
        if (
            job.get("upload")
            and job.get("slot") != exclude_slot
            and isinstance(job.get("selection"), dict)
        )
    ]


def sync(
    assets_root: Path = ASSETS_ROOT,
    *,
    source_root: Path | None = None,
    execute: bool = False,
    theme: str | None = None,
    slot: str | None = None,
) -> dict:
    assets_root = directory(Path(assets_root))
    approval_path = assets_root / "approval.json"
    if not approval_path.is_file() or approval_path.is_symlink():
        raise VideoError("aether_asset_approval_missing")
    approval = load_json(approval_path, limit=2 * 1024 * 1024)
    if approval.get("schema_version") != 1 or approval.get("profile") != "aether_inn":
        raise VideoError("aether_asset_approval_invalid")
    catalog = {row["id"]: row for row in read_catalog()}
    eligible = []
    for key, spec in (approval.get("tracks") or {}).items():
        if key not in catalog or not isinstance(spec, dict):
            raise VideoError("aether_asset_approval_invalid")
        if source_title({"title": str(spec.get("title", ""))}) != source_title(catalog[key]):
            raise VideoError("aether_asset_approval_title_mismatch")
        # Rights are owner-attested; quality may be measured automatically.
        # Only previously accepted or explicitly pending reviews are eligible.
        # An explicit quality rejection must not be silently overridden.
        if spec.get("commercial_use_confirmed") is True and (
            spec.get("quality_accepted") is True or (
                spec.get("quality_accepted") is False
                and spec.get("quality_basis") == "not_yet_owner_quality_approved"
            )
        ):
            eligible.append(catalog[key])
    if not eligible:
        raise VideoError("aether_asset_approval_incomplete")
    history = compilation_history(assets_root, exclude_slot=slot) if theme is not None else []
    if theme is not None and theme not in THEMES:
        raise VideoError("aether_theme_invalid")

    source = find_source_root(source_root)
    wake_provider = source_root is None
    stage_key = theme or "all"
    approved_tracks = {}
    quality_reviews = {}
    preselection = None
    measured_selection = None

    if theme is not None:
        keywords = THEMES[theme][1]
        relevant = [
            row for row in eligible
            if tokens(row["title"] + " " + row["style"]) & keywords
        ]
        try:
            preselection = plan(eligible, theme, history=history)
        except VideoError as error:
            if str(error) != "insufficient_coherent_tracks_for_target":
                raise
        preferred = list((preselection or {}).get("track_ids", []))
        by_id = {row["id"]: row for row in relevant}
        ordered = [by_id[key] for key in preferred if key in by_id]
        ordered += sorted(
            [row for row in relevant if row["id"] not in set(preferred)],
            key=lambda row: row["id"],
        )
        measured = []
        staged_specs = {}
        for row in ordered:
            relative = f"01_Audio_Master/{source_title(row)}.wav"
            source_path = checked_private_source(source, relative, {".wav"})
            target = assets_root / "staged" / stage_key / "masters" / f"{source_title(row)}.wav"
            staged, digest = stage_private_source(
                source_path, target, wake_provider=wake_provider,
            )
            review = review_audio(staged)
            if review["source_sha256"] != digest:
                raise VideoError("aether_offline_audio_source_changed")
            quality_reviews[row["id"]] = review
            if not review.get("accepted"):
                continue
            staged_specs[row["id"]] = {
                "path": staged.relative_to(assets_root).as_posix(),
                "sha256": digest,
                "commercial_use_confirmed": True,
                "quality_accepted": True,
                "quality_basis": "offline_signal_quality_v1",
                "quality_review": review,
            }
            measured.append({**row, "duration_seconds": audio_duration(staged)})
            if len(measured) < 3:
                continue
            try:
                measured_selection = plan(measured, theme, history=history)
                break
            except VideoError as error:
                if str(error) != "insufficient_coherent_tracks_for_target":
                    raise
        if measured_selection is None:
            measured_selection = plan(measured, theme, history=history)
        approved_tracks = {
            key: staged_specs[key] for key in measured_selection["track_ids"]
        }
    else:
        for row in eligible:
            relative = f"01_Audio_Master/{source_title(row)}.wav"
            source_path = checked_private_source(source, relative, {".wav"})
            target = assets_root / "staged" / stage_key / "masters" / f"{source_title(row)}.wav"
            staged, digest = stage_private_source(
                source_path, target, wake_provider=wake_provider,
            )
            review = review_audio(staged)
            if review["source_sha256"] != digest:
                raise VideoError("aether_offline_audio_source_changed")
            quality_reviews[row["id"]] = review
            if not review.get("accepted"):
                continue
            approved_tracks[row["id"]] = {
                "path": staged.relative_to(assets_root).as_posix(),
                "sha256": digest,
                "commercial_use_confirmed": True,
                "quality_accepted": True,
                "quality_basis": "offline_signal_quality_v1",
                "quality_review": review,
            }

    if not approved_tracks:
        raise VideoError("aether_asset_no_accepted_audio")
    approved_covers = {}
    cover_specs = approval.get("covers") or {}
    cover_themes = (theme,) if theme is not None else tuple(THEMES)
    for cover_theme in cover_themes:
        spec = cover_specs.get(cover_theme)
        if not isinstance(spec, dict) or spec.get("commercial_use_confirmed") is not True:
            raise VideoError("aether_asset_approval_incomplete")
        filename = spec.get("filename")
        if not isinstance(filename, str) or not filename or "/" in filename or "\\" in filename:
            raise VideoError("aether_asset_approval_invalid")
        relative = f"02_Cover_Original/{filename}"
        source_path = checked_private_source(source, relative, {".png", ".jpg", ".jpeg"})
        target = assets_root / "staged" / stage_key / "covers" / filename
        staged, _ = stage_private_source(
            source_path, target, wake_provider=wake_provider,
        )
        compilation_cover = (
            assets_root / "staged" / stage_key / "covers"
            / f"compilation-{cover_theme}.png"
        )
        branded = build_compilation_cover(
            staged, compilation_cover, THEMES[cover_theme][0],
        )
        approved_covers[cover_theme] = {
            "path": compilation_cover.relative_to(assets_root).as_posix(),
            "sha256": branded["sha256"],
            "commercial_use_confirmed": True,
        }
    manifest = {
        "schema_version": 1,
        "profile": "aether_inn",
        "test_only": False,
        "asset_source": "local_private_cache",
        "tracks": approved_tracks,
        "covers": approved_covers,
        "offline_quality_review": {
            "review_model": "local_signal_quality_v1",
            "accepted_track_count": len(approved_tracks),
            "rejected_track_ids": sorted(key for key, value in quality_reviews.items()
                                         if not value.get("accepted")),
        },
    }
    manifest_path = assets_root / "manifest.json"
    if execute:
        atomic_json(manifest_path, manifest)
        os.chmod(manifest_path, 0o600)
    return {
        "status": "ready" if execute else "dry_run",
        "asset_source": "local_private_cache",
        "theme": theme,
        "approved_track_count": len(approved_tracks),
        "offline_quality_rejected": len([review for review in quality_reviews.values()
                                         if not review.get("accepted")]),
        "offline_quality_review_model": "local_signal_quality_v1",
        "preselected_titles": [row["title"] for row in preselection["tracks"]] if preselection else [],
        "measured_selected_titles": [row["title"] for row in measured_selection["tracks"]] if measured_selection else [],
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
    p.add_argument("--theme", choices=THEMES)
    p.add_argument("--slot")
    args = parser.parse_args()
    try:
        if args.command == "init-approval":
            result = init_approval(args.assets_root, execute=args.execute)
        else:
            result = sync(
                args.assets_root, source_root=args.source_root, execute=args.execute,
                theme=args.theme, slot=args.slot,
            )
        print(__import__("json").dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (VideoError, OSError, ValueError, TypeError):
        error = __import__("sys").exc_info()[1]
        reason = str(error) if isinstance(error, VideoError) and re.fullmatch(r"[a-z_]{1,90}", str(error)) else "aether_asset_registration_failed"
        print(__import__("json").dumps({"status": "blocked", "error": reason}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
