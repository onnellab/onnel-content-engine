"""Import a hash-bound, owner-approved single cover without a generation API."""
from __future__ import annotations

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
