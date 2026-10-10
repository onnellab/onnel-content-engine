"""Import a hash-bound, owner-approved single cover without a generation API."""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
from pathlib import Path
import shutil

from aether_compose import checked_asset, media_info
from aether_cover import brand_background, validate_full_bleed_background
from short_video_pipeline import VideoError, file_hash, load_json, run_process
from youtube_report_store import directory

ASSETS_ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/assets"
APPROVAL_FILE = "single_cover_approvals.json"
MAX_COVER_BYTES = 32 * 1024 * 1024


def _install_hash_bound_staged_cover(root: Path, spec: dict) -> None:
    """Materialize an already owner-approved PNG from a local Base64 transfer.

    This does not approve artwork or generate a replacement. The source remains
    fail-closed until its exact bytes match the owner's SHA-256 in the approval.
    """
    if spec.get("commercial_use_confirmed") is not True:
        return
    relative = spec.get("path")
    if not isinstance(relative, str):
        return
    fragment = Path(relative)
    if fragment.is_absolute() or ".." in fragment.parts or fragment.suffix.lower() != ".png":
        return
    target = root / fragment
    if target.exists() or target.is_symlink():
        return
    encoded = target.with_name(target.name + ".b64")
    if encoded.is_symlink():
        raise VideoError("aether_single_cover_staged_source_unsafe")
    if not encoded.is_file():
        return
    current = encoded.parent
    while current != root and current != current.parent:
        if current.is_symlink():
            raise VideoError("aether_single_cover_staged_source_unsafe")
        current = current.parent
    if not 0 < encoded.stat().st_size <= ((MAX_COVER_BYTES + 2) // 3) * 4:
        raise VideoError("aether_single_cover_staged_size_invalid")
    try:
        data = base64.b64decode(encoded.read_bytes(), validate=True)
    except (binascii.Error, ValueError):
        raise VideoError("aether_single_cover_staged_encoding_invalid") from None
    if not 0 < len(data) <= MAX_COVER_BYTES:
        raise VideoError("aether_single_cover_staged_size_invalid")
    if hashlib.sha256(data).hexdigest() != spec.get("sha256"):
        raise VideoError("aether_asset_hash_mismatch")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    if partial.is_symlink() or partial.exists():
        raise VideoError("aether_single_cover_staged_partial_exists")
    try:
        with partial.open("xb") as output:
            output.write(data)
        os.chmod(partial, 0o600)
        if file_hash(partial) != spec["sha256"]:
            raise VideoError("aether_asset_hash_mismatch")
        partial.replace(target)
    except OSError:
        raise VideoError("aether_single_cover_staging_failed") from None
    finally:
        if partial.is_file() and not partial.is_symlink():
            partial.unlink(missing_ok=True)


def approved_cover(title: str, assets_root: Path) -> tuple[Path, dict, str]:
    root = Path(assets_root)
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise VideoError("aether_symlink_asset_root_rejected")
    approval = root / APPROVAL_FILE
    if approval.is_symlink() or not approval.is_file():
        raise VideoError("aether_single_cover_approval_missing")
    approval_hash = file_hash(approval)
    payload = load_json(approval, limit=2 * 1024 * 1024)
    if file_hash(approval) != approval_hash:
        raise VideoError("aether_single_cover_approval_changed")
    if (payload.get("schema_version") != 1 or payload.get("profile") != "aether_inn"
            or payload.get("test_only") is not False or not isinstance(payload.get("covers"), dict)):
        raise VideoError("aether_single_cover_approval_invalid")
    spec = payload["covers"].get(title)
    if not isinstance(spec, dict) or spec.get("title") != title:
        raise VideoError("aether_single_cover_approval_missing")
    if spec.get("quality_accepted") is not True:
        raise VideoError("aether_single_cover_quality_unconfirmed")
    if spec.get("kind") not in {"finished_cover", "unbranded_background"}:
        raise VideoError("aether_single_cover_kind_invalid")
    _install_hash_bound_staged_cover(root, spec)
    source = checked_asset(root, spec, {".png", ".jpg", ".jpeg"})
    if source.stat().st_size > MAX_COVER_BYTES:
        raise VideoError("aether_single_cover_too_large")
    return source, spec, approval_hash


def import_existing_cover(title: str, style: str, lane: str, output_dir: Path, *,
                          execute: bool = False, assets_root: Path = ASSETS_ROOT) -> dict:
    # Style/lane do not authorize generating a replacement or reusing other artwork.
    if not execute:
        return {"state": "planned", "provider": "owner_approved_existing_cover", "generation_count": 0}
    source, spec, approval_hash = approved_cover(title, assets_root)
    output = directory(Path(output_dir))
    staged = output / ("approved-source" + source.suffix.lower())
    partial = staged.with_name("approved-source.partial" + source.suffix.lower())
    target = output / "cover.png"
    if any(path.is_symlink() for path in (staged, partial, target)):
        raise VideoError("aether_unsafe_cover_path")
    try:
        shutil.copyfile(source, partial)
        os.chmod(partial, 0o600)
        if file_hash(partial) != spec["sha256"]:
            raise VideoError("aether_asset_hash_mismatch")
        image = next((row for row in media_info(partial).get("streams", [])
                      if row.get("codec_type") == "video"), {})
        width, height = image.get("width", 0), image.get("height", 0)
        if width < 1280 or height < 720 or abs(width / max(1, height) - 16 / 9) > .02:
            raise VideoError("aether_landscape_cover_required")
        validate_full_bleed_background(partial)
        partial.replace(staged)
        if spec["kind"] == "unbranded_background":
            rendered = brand_background(staged, target, title)
            layout = rendered["layout"]
        else:
            # Finished artwork already has its approved typography. Never overlay it twice.
            run_process([
                "ffmpeg", "-v", "error", "-nostdin", "-y", "-threads", "1",
                "-protocol_whitelist", "file,pipe", "-i", str(staged),
                "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                "-frames:v", "1", str(target),
            ], timeout=120)
            layout = "owner_approved_finished_cover"
        result_image = next((row for row in media_info(target).get("streams", [])
                             if row.get("codec_type") == "video"), {})
        if ((result_image.get("width"), result_image.get("height")) != (1920, 1080)
                or not target.is_file() or not 0 < target.stat().st_size <= MAX_COVER_BYTES):
            raise VideoError("aether_single_cover_geometry_invalid")
        os.chmod(target, 0o600)
        return {
            "state": "ready", "path": str(target), "sha256": file_hash(target),
            "model": "owner_approved_existing_cover", "layout": layout,
            "source_kind": "existing_approved_cover", "source_sha256": spec["sha256"],
            "approval_sha256": approval_hash, "approval_title": title,
            "generation_count": 0,
        }
    finally:
        partial.unlink(missing_ok=True)
