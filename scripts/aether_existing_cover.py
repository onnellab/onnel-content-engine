"""Import a hash-bound, owner-approved single cover without a generation API."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
import shutil

from aether_compose import checked_asset, media_info
from aether_cover import brand_background, validate_full_bleed_background
from short_video_pipeline import VideoError, file_hash, load_json, run_process
from youtube_report_store import directory

ASSETS_ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/assets"
APPROVAL_FILE = "single_cover_approvals.json"
MAX_COVER_BYTES = 32 * 1024 * 1024
MAX_REVIEW_BYTES = 64 * 1024


def _read_review(root: Path, relative: str) -> bytes:
    """Bounded regular-file read; do not follow replaced directories or FIFOs."""
    descriptors = []
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptors.append(os.open(root, directory_flags))
        parts = Path(relative).parts
        for part in parts[:-1]:
            descriptors.append(os.open(part, directory_flags, dir_fd=descriptors[-1]))
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=descriptors[-1])
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_REVIEW_BYTES:
                raise VideoError("aether_cover_review_invalid")
            return stream.read(MAX_REVIEW_BYTES + 1)
    except OSError:
        raise VideoError("aether_cover_review_missing") from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def delegated_quality_provenance(root: Path, spec: dict) -> dict:
    """Validate attributed inspection evidence, never create an approval.

    The private ledger remains a trusted, authorized input. A message reference
    records the delegation source; it is not online authentication of that message.
    Rights and quality flags are still independently required by the importer.
    """
    basis = spec.get("quality_basis", "owner_attested")
    if basis == "owner_attested":
        if "quality_review" in spec:
            raise VideoError("aether_cover_review_basis_conflict")
        return {}
    if basis != "dot_delegated_visual_v1" or spec.get("kind") != "finished_cover":
        raise VideoError("aether_cover_review_basis_invalid")
    reference = spec.get("quality_review")
    if not isinstance(reference, dict):
        raise VideoError("aether_cover_review_missing")
    relative, expected = reference.get("path"), reference.get("sha256")
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or ".." in Path(relative).parts or Path(relative).suffix != ".json"
            or not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected)):
        raise VideoError("aether_cover_review_reference_invalid")
    path = root
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise VideoError("aether_cover_review_unsafe")
    raw = _read_review(root, relative)
    if len(raw) > MAX_REVIEW_BYTES or hashlib.sha256(raw).hexdigest() != expected:
        raise VideoError("aether_cover_review_hash_mismatch")
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        review = json.loads(raw, object_pairs_hook=unique_pairs)
        if not isinstance(review, dict):
            raise ValueError()
        when = datetime.fromisoformat(review["reviewed_at"])
        if when.tzinfo is None or when > datetime.now(timezone.utc):
            raise ValueError()
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise VideoError("aether_cover_review_invalid") from None
    checks = review.get("checks")
    required = ("full_resolution", "thumbnail_scale", "song_scene_fit", "geometry_materials",
                "full_bleed", "exact_title", "legibility", "no_watermark_or_duplicate_brand")
    authority = review.get("authority_reference")
    if (type(review.get("schema_version")) is not int or review["schema_version"] != 1
            or review.get("kind") != "aether_cover_quality_review"
            or review.get("profile") != "aether_inn" or review.get("title") != spec["title"]
            or review.get("source_sha256") != spec.get("sha256")
            or review.get("reviewer_kind") != "dot_delegated" or review.get("verdict") != "accepted"
            or not isinstance(authority, str) or not re.fullmatch(r"[A-Za-z0-9_:-]{8,160}", authority)
            or not isinstance(checks, dict) or any(checks.get(key) is not True for key in required)
            or not isinstance(review.get("notes"), str) or not 1 <= len(review["notes"].strip()) <= 4000):
        raise VideoError("aether_cover_review_unconfirmed")
    current = _read_review(root, relative)
    if path.is_symlink() or hashlib.sha256(current).hexdigest() != expected:
        raise VideoError("aether_cover_review_changed")
    return {"quality_basis": basis, "quality_reviewer": "dot_delegated",
            "quality_review_sha256": expected, "quality_authority_reference": authority,
            "quality_reviewed_at": review["reviewed_at"]}


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
    provenance = delegated_quality_provenance(root, spec)
    _install_hash_bound_staged_cover(root, spec)
    source = checked_asset(root, spec, {".png", ".jpg", ".jpeg"})
    if source.stat().st_size > MAX_COVER_BYTES:
        raise VideoError("aether_single_cover_too_large")
    spec = {key: value for key, value in spec.items() if key != "_validated_quality_provenance"}
    if provenance:
        spec["_validated_quality_provenance"] = provenance
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
        provenance = spec.get("_validated_quality_provenance", {})
        delegated = bool(provenance)
        return {
            "state": "ready", "path": str(target), "sha256": file_hash(target),
            "model": "dot_reviewed_existing_cover" if delegated else "owner_approved_existing_cover",
            "layout": "dot_reviewed_finished_cover" if delegated else layout,
            "source_kind": "existing_approved_cover", "source_sha256": spec["sha256"],
            "approval_sha256": approval_hash, "approval_title": title,
            "generation_count": 0,
            **provenance,
        }
    finally:
        partial.unlink(missing_ok=True)

