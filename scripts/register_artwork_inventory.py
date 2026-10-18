#!/usr/bin/env python3
"""Compile a DATA-ONLY release/artwork.json draft and a blocked-readiness report.

Inputs are read, never imported or executed. This does not capture, render,
resize, approve, stage, publish, or update an app. Output must be a new owned
directory outside both input trees. A partial inventory is intentional: missing
paths are omitted, while missing/stale evidence remains in the report. Install
the draft only through a separately authorized app change and run the canonical
isolated gate plus independent review afterwards.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import zlib

PROMO = "assets/store_promo"
LOCALES = {"ko", "en", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es"}
SIZES = {"android": {(1080, 2160)}, "iphone_medium": {(1179, 2556), (1206, 2622)},
         "duo_outer": {(1398, 2034)}, "duo_inner": {(2007, 2853)},
         "ipad_13": {(2064, 2752), (2048, 2732)},
         "header": {(3840, 1646)}, "search": {(1920, 1280)}}
GROUPS = {"ios-screens": f"{PROMO}/ios_devices/manifest.json",
          "ios-header-search": f"{PROMO}/ios_creatives/manifest.json",
          "play": f"{PROMO}/play_creatives/manifest.json"}
SHARED_FILES = ("release_artwork.py", "store_asset_workflow.py", "render_store_device_slots.py",
                "render_app_screenshot.py", "render_editorial_latest.py", "creative_asset_core.py",
                "render_app_creatives.py", "verify_refresh_ios_creatives.py",
                "header_template.py", "search_template.py")
FINGERPRINT_FILES = {
    "android": ("render_app_screenshot.py", "render_store_device_slots.py",
                "render_editorial_latest.py", "creative_asset_core.py"),
    "ios": ("render_store_device_slots.py", "render_editorial_latest.py", "creative_asset_core.py")}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
INDEXED = re.compile(r"0*([1-9][0-9]*)(?:-[a-f0-9]+)?\.png")
MAX_FILE_BYTES = 128 * 1024 * 1024


class RegistrationError(ValueError):
    """Unsafe or ambiguous input; do not emit an inventory."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def absolute(path: Path) -> Path:
    path = Path(path)
    if ".." in path.parts:
        raise RegistrationError(f"Parent traversal is forbidden: {path}")
    path = Path(os.path.abspath(path))
    for part in reversed((path, *path.parents)):
        if part.is_symlink():
            raise RegistrationError(f"Symlinks are forbidden: {part}")
        if part.exists() and part != path and not part.is_dir():
            raise RegistrationError(f"Non-directory path component: {part}")
    return path


def root_directory(path: Path) -> Path:
    path = absolute(path)
    if not path.is_dir():
        raise RegistrationError(f"Input directory must exist: {path}")
    return path


def relative(root: Path, value: str) -> Path:
    if (not isinstance(value, str) or not value or "\\" in value or "\0" in value
            or Path(value).is_absolute() or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise RegistrationError(f"Expected an unambiguous relative path: {value!r}")
    path = absolute(root / value)
    if path == root or not path.is_relative_to(root):
        raise RegistrationError(f"Path escapes input tree: {value}")
    return path


def open_directory(path: Path, *, dir_fd: int | None = None) -> int:
    """Open directories without following symlinks at any traversed component."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    if dir_fd is not None:
        return os.open(str(path), flags, dir_fd=dir_fd)
    descriptor = os.open("/", flags)
    try:
        for component in path.parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def read_bytes(root: Path, value: str) -> bytes | None:
    path = relative(root, value)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise RegistrationError(f"Expected regular file: {path}")
    if info.st_size > MAX_FILE_BYTES:
        raise RegistrationError(f"File exceeds bounded inspection limit: {path}")
    # Walk with O_NOFOLLOW on directory descriptors too. Checking only the final
    # file would allow a concurrently replaced parent symlink to escape a tree.
    directory = open_directory(path.parent)
    try:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                             dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(descriptor, "rb") as handle:
        opened = os.fstat(handle.fileno())
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise RegistrationError(f"Input changed during inspection: {path}")
        raw = handle.read(MAX_FILE_BYTES + 1)
        after = os.fstat(handle.fileno())
    current = path.lstat()
    if (len(raw) > MAX_FILE_BYTES or len(raw) != info.st_size
            or (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            != (info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            or (current.st_dev, current.st_ino, current.st_mode, current.st_size,
                current.st_mtime_ns, current.st_ctime_ns)
            != (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)):
        raise RegistrationError(f"Input changed during inspection: {path}")
    return raw


def directory_signature(path: Path) -> tuple | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(info.st_mode):
        raise RegistrationError(f"Expected non-symlink directory: {path}")
    return info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns


def children(root: Path, value: str, *, observations: dict | None = None) -> list[Path]:
    path = relative(root, value)
    before = directory_signature(path)
    if observations is not None:
        key = (root, value)
        if key in observations and observations[key] != before:
            raise RegistrationError(f"Input directory changed during inspection: {path}")
        observations[key] = before
    if before is None:
        return []
    result = sorted(path.iterdir())
    for child in result:
        relative(root, child.relative_to(root).as_posix())
        if not (child.is_file() or child.is_dir()):
            raise RegistrationError(f"Nonregular input: {child}")
    if directory_signature(path) != before:
        raise RegistrationError(f"Input directory changed during inspection: {path}")
    return result


def image_files(root: Path, value: str, *, observations: dict | None = None) -> list[Path]:
    result = []
    for path in children(root, value, observations=observations):
        if path.is_dir():
            result.extend(image_files(root, path.relative_to(root).as_posix(), observations=observations))
        elif path.suffix.lower() in IMAGE_SUFFIXES:
            result.append(path)
    return result


def indexed(root: Path, value: str, *, observations: dict | None = None) -> tuple[dict[int, Path], list[Path]]:
    """Count every present image, even corrupt or non-PNG images, before mapping."""
    all_images = image_files(root, value, observations=observations)
    result = {}
    for path in all_images:
        if path.parent != root / value or path.suffix != ".png":
            continue
        match = INDEXED.fullmatch(path.name)
        if not match:
            raise RegistrationError(f"Ambiguous numeric gallery filename: {path}")
        number = int(match[1])
        if number in result:
            raise RegistrationError(f"Duplicate gallery index {number}: {path.parent}")
        result[number] = path
    return result, all_images


def png_details(raw: bytes) -> dict:
    """Inspect actual bytes, retaining dimensions even when CRC/pixels are bad."""
    result = {"png_valid": False}
    try:
        if len(raw) < 33 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
            raise ValueError("Invalid PNG header")
        width, height = struct.unpack(">II", raw[16:24])
        result.update(size=[width, height], bit_depth=raw[24], color_type=raw[25])
        if (not 2 <= min(width, height) or max(width, height) > 10000
                or raw[24] != 8 or raw[25] not in {2, 6} or raw[26:29] != b"\0\0\0"):
            raise ValueError("Unsupported PNG dimensions, format or interlacing")
        stride = width * (3 if raw[25] == 2 else 4) + 1
        expected = stride * height
        if expected > MAX_FILE_BYTES:
            raise ValueError("PNG decoded pixels exceed bounded inspection limit")
        offset, compressed, ended, headers = 8, bytearray(), False, 0
        while offset + 12 <= len(raw):
            length = struct.unpack(">I", raw[offset:offset + 4])[0]
            end = offset + length + 12
            if end > len(raw):
                raise ValueError("Truncated PNG chunk")
            chunk = raw[offset + 4:end - 4]
            if zlib.crc32(chunk) != struct.unpack(">I", raw[end - 4:end])[0]:
                raise ValueError("Corrupt PNG chunk CRC")
            if chunk[:4] == b"IHDR":
                headers += 1
                if length != 13 or offset != 8:
                    raise ValueError("Invalid or duplicate PNG header")
            if chunk[:4] == b"IDAT":
                compressed.extend(chunk[4:])
            if chunk[:4] == b"IEND":
                ended = length == 0 and end == len(raw)
                break
            offset = end
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(compressed, expected + 1)
        if (not ended or headers != 1 or len(pixels) != expected or not decoder.eof
                or decoder.unused_data or any(pixels[i] > 4 for i in range(0, expected, stride))):
            raise ValueError("Invalid or truncated PNG pixel data")
        result["png_valid"] = True
    except (ValueError, zlib.error, struct.error) as error:
        result["png_error"] = str(error)
    return result


class Builder:
    def __init__(self, project: Path, site: Path):
        self.project, self.site = project, site
        self.blockers: list[dict] = []
        self.files: dict[str, dict] = {}
        self.missing: set[tuple[bool, str]] = set()
        self.capture_applicability: list[dict] = []

    def block(self, code: str, subject: str, detail: str) -> None:
        value = {"code": code, "subject": subject, "detail": detail}
        if value not in self.blockers:
            self.blockers.append(value)

    def file(self, value: str, *, site: bool = False, required: bool = True) -> dict | None:
        key = ("site:" if site else "project:") + value
        if key in self.files:
            return self.files[key]
        raw = read_bytes(self.site if site else self.project, value)
        if raw is None:
            self.missing.add((site, value))
            if required:
                self.block("missing_file", key, "Required evidence file does not exist")
            return None
        record = {"tree": "site" if site else "project", "path": value,
                  "sha256": sha(raw), "bytes": len(raw)}
        if Path(value).suffix.lower() == ".png":
            record.update(png_details(raw))
            if not record["png_valid"]:
                self.block("invalid_png", key, record["png_error"])
        self.files[key] = record
        return record

    def data(self, value: str, *, required: bool = True) -> dict | None:
        if self.file(value, required=required) is None:
            return None
        try:
            def pairs(items):
                result = {}
                for key, val in items:
                    if key in result:
                        raise ValueError(f"Duplicate JSON key: {key}")
                    result[key] = val
                return result
            raw = read_bytes(self.project, value)
            if raw is None or sha(raw) != self.files["project:" + value]["sha256"]:
                raise RegistrationError(f"Input changed during inspection: {value}")
            data = json.loads(raw, object_pairs_hook=pairs)
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object")
            return data
        except RegistrationError:
            raise
        except (ValueError, UnicodeError, TypeError) as error:
            self.block("invalid_json", value, str(error))
            return None

    def dependencies(self, names: list[str]) -> list[str]:
        return sorted({name for name in names if self.file(name) is not None})

    def match(self, data: dict, key: str, actual, subject: str) -> None:
        if data.get(key) != actual:
            self.block("stale_or_inconsistent_evidence", subject,
                       f"{key} differs from the inspected file or declared configuration")

    def capture(self, asset: dict, source: str | None, version: str | None,
                marker: dict, store: dict) -> None:
        key = f"{asset['locale']}/{asset['kind']}/{asset['index']}"
        if not isinstance(source, str) or not source:
            self.block("missing_source_reference", key, "No source path in actual provenance/spec")
            self.block("capture_evidence_missing", key, "Cannot bind an installed-build capture without an existing source reference")
            return
        raw = self.file(source)
        loc, kind = asset["locale"], asset["kind"]
        slot = {"duo_outer": "duo/outer", "duo_inner": "duo/inner"}.get(kind, kind)
        if not relative(self.project, source).is_relative_to(self.project / PROMO / "raw" / loc / slot):
            self.block("source_slot_mismatch", key, "Raw source is not in the same locale/device directory")
        if raw is not None:
            asset["raw_path"] = source
            asset["dependencies"].append(source)
            if not raw.get("png_valid"):
                self.block("invalid_raw_capture", source, "Capture source must be a valid PNG")
        if kind != "android":
            # Strict canonical device verification also consumes a separate
            # raw/normalized pair. Observe those paths; never create the pair.
            strict_source = f"{PROMO}/raw/{loc}/{slot}/{asset['index']:02d}.png"
            ready_path = (f"{PROMO}/{slot}/{loc}/{asset['index']:02d}.png" if kind.startswith("duo_")
                          else f"{PROMO}/captures/{kind}/{loc}/{asset['index']:02d}.png")
            strict_raw, ready = self.file(strict_source), self.file(ready_path)
            for name, info in ((strict_source, strict_raw), (ready_path, ready)):
                if info is not None:
                    asset["dependencies"].append(name)
            if strict_source != source:
                self.block("canonical_capture_source_mismatch", key, "Manifest source differs from canonical indexed capture pair")
            if strict_raw is None or ready is None:
                self.block("missing_native_capture_pair", key, "Strict capture verification requires both actual raw and normalized images")
            elif (not strict_raw.get("png_valid") or not ready.get("png_valid")
                  or tuple(strict_raw.get("size", [])) not in SIZES[kind]
                  or ready.get("size") != strict_raw.get("size") or ready.get("color_type") != 2
                  or (self.project / strict_source).samefile(self.project / ready_path)):
                self.block("invalid_native_capture_pair", key, "Raw and distinct normalized RGB images must have matching accepted native dimensions")
        receipt_name = str(Path(source).with_suffix(".capture.json"))
        receipt = self.data(receipt_name)
        if self.file(receipt_name, required=False) is not None:
            asset["capture_receipt"] = receipt_name
            asset["dependencies"].append(receipt_name)
        if receipt is None:
            self.block("capture_evidence_missing", key, "No valid installed-build capture receipt")
            return
        for field, expected in {"raw_path": source, "locale": loc, "kind": kind,
                                "screen_confirmed": True}.items():
            self.match(receipt, field, expected, receipt_name)
        if raw is not None:
            self.match(receipt, "raw_sha256", raw["sha256"], receipt_name)
        changed_identity = (receipt.get("version") != version or
                            (marker.get("source_commit") and receipt.get("source_commit") != marker["source_commit"]))
        reuse_name = str(Path(source).with_suffix(".reuse.json"))
        reuse = self.file(reuse_name, required=False)
        if reuse is not None:
            asset["capture_reuse"] = reuse_name
            asset["dependencies"].append(reuse_name)
            self.block("capture_reuse_unverified", reuse_name,
                       "Existing per-screen reuse evidence preserved; the canonical gate must validate its source/scope review and unchanged render inputs")
        if changed_identity:
            self.block("capture_identity_changed", receipt_name,
                       "Original capture version/source_commit differs from target; this alone does not require recapture. Review unchanged-screen reuse or identify affected visual inputs")
        self.capture_applicability.append({"screen": {"locale": loc, "kind": kind, "index": asset["index"]},
            "capture_version": receipt.get("version"), "capture_source_commit": receipt.get("source_commit"),
            "capture_receipt_sha256": self.files["project:" + receipt_name]["sha256"],
            "target_version": version, "target_source_commit_claim": marker.get("source_commit"),
            "identity_comparison": "PUBSPEC_AND_DECLARED_MARKER_ONLY",
            "identity_differs_from_declared_target": bool(changed_identity),
            "reuse_evidence": reuse_name if reuse is not None else None,
            "status": "UNVERIFIED"})
        provider, field = ("android", "package_name") if kind == "android" else ("ios", "bundle_id")
        provider_data = store.get(provider, {})
        expected_id = provider_data.get(field) if isinstance(provider_data, dict) else None
        if not expected_id or receipt.get(field) != expected_id:
            self.block("capture_app_identity", receipt_name, "Capture app identity missing or differs from store_upload.json")
        if (receipt.get("method") not in {"adb", "simctl", "physical-device"}
                or receipt.get("screen_confirmed") is not True
                or not isinstance(receipt.get("device_id"), str) or not receipt["device_id"]
                or not re.fullmatch(r"[a-f0-9]{40}", str(receipt.get("source_commit", "")))
                or any(not re.fullmatch(r"[a-f0-9]{64}", str(receipt.get(name, "")))
                       for name in ("installed_binary_sha256", "installed_identity_sha256"))):
            self.block("invalid_capture_evidence", receipt_name, "Missing device/method/installed-build identity evidence")


def build_inventory(*, project: Path, site: Path, slug: str, ipad_supported: bool,
                    android_renderer: str, shared_renderer_dir: str,
                    android_render_args: tuple[str, ...] = ()) -> tuple[dict, dict]:
    project, site = root_directory(project), root_directory(site)
    if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise RegistrationError("Explicit safe app slug required")
    if type(ipad_supported) is not bool:
        raise RegistrationError("Explicit boolean ipad_supported required")
    builder = Builder(project, site)
    pubspec = read_bytes(project, "pubspec.yaml")
    if pubspec is None:
        raise RegistrationError("Selected project has no pubspec.yaml")
    builder.file("pubspec.yaml")
    match = re.search(rb"(?m)^version:\s*['\"]?(\d+\.\d+\.\d+\+\d+)['\"]?\s*$", pubspec)
    version = match[1].decode() if match else None
    if version is None:
        builder.block("missing_app_version", "pubspec.yaml", "Explicit version+build required")
    renderer = builder.file(android_renderer)
    if renderer is None or Path(android_renderer).suffix != ".py":
        raise RegistrationError("Android renderer must be an explicit existing project-relative Python file")
    if (not isinstance(android_render_args, (list, tuple))
            or any(not isinstance(arg, str) or "\0" in arg for arg in android_render_args)):
        raise RegistrationError("Renderer arguments must be explicit strings, never a shell command")
    if not relative(project, shared_renderer_dir).is_dir():
        raise RegistrationError("Explicit existing shared renderer directory required")
    common = builder.dependencies([f"{shared_renderer_dir}/{name}" for name in SHARED_FILES]
                                  + [android_renderer] + list(GROUPS.values()))
    fingerprints = {}
    for kind, names in FINGERPRINT_FILES.items():
        parts = [read_bytes(project, f"{shared_renderer_dir}/{name}") for name in names]
        if all(part is not None for part in parts):
            fingerprints[kind] = sha(b"".join(parts))
    manifests = {group: builder.data(path) for group, path in GROUPS.items()}
    interface_manifest = f"{PROMO}/ios_creatives/interface_manifest.json"
    interface = builder.data(interface_manifest, required=False)
    if interface is not None:
        common.append(interface_manifest)
    marker = builder.data("assets/onnellab_release_identity.json") or {}
    store = builder.data("release/store_upload.json") or {}
    if marker:
        builder.match(marker, "version", version, "assets/onnellab_release_identity.json")
    detail = f"src/content/apps/{slug}/assets/screenshots"
    if not relative(site, detail).is_dir():
        builder.block("missing_site_gallery", detail, "Existing destination screenshot directory required")
    site_indices, android_indices, android_images, native_indices, legacy = {}, {}, {}, {}, []
    discovered = set()
    scanned_directories = {}

    def locale(value: str, subject: str) -> str:
        if value not in LOCALES:
            raise RegistrationError(f"Unknown locale directory/key {value!r}: {subject}")
        discovered.add(value)
        return value

    for path in children(site, detail, observations=scanned_directories):
        if not path.is_dir():
            builder.block("unexpected_site_entry", str(path.relative_to(site)), "Expected locale directories only")
            continue
        loc = locale(path.name, detail)
        entries, images = indexed(site, f"{detail}/{loc}", observations=scanned_directories)
        if set(entries) != set(range(1, 7)) or len(images) != 6:
            builder.block("site_mapping_incomplete", loc, "Exactly six existing unambiguous numeric PNG destinations required")
        site_indices[loc] = entries
        for image in images:
            builder.file(str(image.relative_to(site)), site=True)
    for path in children(project, f"{PROMO}/generated", observations=scanned_directories):
        if not path.is_dir():
            continue
        loc = locale(path.name, f"{PROMO}/generated")
        entries, images = indexed(project, f"{PROMO}/generated/{loc}/android", observations=scanned_directories)
        android_indices[loc], android_images[loc] = entries, images
        for image in image_files(project, f"{PROMO}/generated/{loc}/ios", observations=scanned_directories):
            record = builder.file(str(image.relative_to(project)))
            legacy.append(record)
    native_root = f"{PROMO}/ios_devices"
    for slot_path in children(project, native_root, observations=scanned_directories):
        if not slot_path.is_dir():
            continue
        slot = slot_path.name
        if slot not in {"iphone_medium", "duo_outer", "duo_inner", "ipad_13"}:
            raise RegistrationError(f"Unknown native slot: {slot_path}")
        if slot == "ipad_13" and not ipad_supported:
            builder.block("ipad_scope_conflict", slot, "Native iPad assets exist but ipad_supported was explicitly false")
        for path in children(project, str(slot_path.relative_to(project)), observations=scanned_directories):
            if not path.is_dir():
                raise RegistrationError(f"Expected native locale directory: {path}")
            loc = locale(path.name, str(slot_path))
            entries, images = indexed(project, str(path.relative_to(project)), observations=scanned_directories)
            native_indices[(loc, slot)] = entries
            if len(entries) != len(images):
                builder.block("unexpected_native_images", f"{loc}/{slot}", "Only direct numeric PNG files can be registered")
    for kind in ("header", "search"):
        for path in children(project, f"{PROMO}/{kind}", observations=scanned_directories):
            if path.suffix.lower() in IMAGE_SUFFIXES:
                locale(path.stem, f"{PROMO}/{kind}")
    manifest_coverage = {}
    for group, data in manifests.items():
        coverage = data.get("features" if group == "play" else "locales") if data else None
        if not isinstance(coverage, dict) or not coverage:
            builder.block("missing_group_manifest", group, "Required canonical group manifest/locale coverage missing or invalid")
            manifest_coverage[group] = []
            continue
        manifest_coverage[group] = sorted(locale(loc, GROUPS[group]) for loc in coverage)
        if data.get("schema_version") != 1:
            builder.block("invalid_manifest_schema", GROUPS[group], "Expected schema_version=1")
    locales = sorted(discovered)
    if not locales:
        builder.block("no_locale_evidence", slug, "No locale coverage can be inferred from existing inputs")
    for group, coverage in manifest_coverage.items():
        if coverage != locales:
            builder.block("locale_coverage_mismatch", group, "Canonical group locales differ from observed app/site locales")
    if sorted(site_indices) != locales:
        builder.block("locale_coverage_mismatch", "site", "Destination locales differ from observed app locales")
    if manifests["ios-header-search"] and manifest_coverage["ios-header-search"] != sorted(LOCALES):
        builder.block("placement_locale_coverage", "ios-header-search", "Canonical placement renderer requires all nine locales")
    device_manifest = manifests["ios-screens"] or {}
    if device_manifest.get("ipad_supported") is not ipad_supported:
        builder.block("ipad_manifest_mismatch", GROUPS["ios-screens"], "Canonical iPad declaration differs or is missing")
    if device_manifest.get("duo_enabled", True) is not True:
        builder.block("duo_disabled", GROUPS["ios-screens"], "Release gate requires duo_outer and duo_inner")
    slots = ["iphone_medium", "duo_outer", "duo_inner"] + (["ipad_13"] if ipad_supported else [])
    counts_by_locale, counts, assets, inspected = {}, {}, [], []
    android_present = any(android_images.values())
    for loc in locales:
        counts_by_locale[loc] = {"android": len(android_images.get(loc, [])),
                                 **{slot: len(native_indices.get((loc, slot), {})) for slot in slots}}
        images = android_images.get(loc, [])
        entries = android_indices.get(loc, {})
        if len(entries) != len(images):
            builder.block("unexpected_android_images", loc, "All present Android images count; nested/non-PNG files cannot be mapped")
        if sorted(entries) != list(range(1, len(entries) + 1)):
            builder.block("noncontiguous_android_gallery", loc, "Present Android image indices must be contiguous from one")
        for image in images:
            builder.file(str(image.relative_to(project)))
    for kind in ["android", *slots]:
        actual_counts = [counts_by_locale[loc][kind] for loc in locales]
        # A nonzero observation can NEVER become an Android absence declaration.
        counts[kind] = max(actual_counts, default=0)
        if len(set(actual_counts)) > 1:
            builder.block("gallery_count_mismatch", kind, "Observed screenshot counts differ across locales; draft uses maximum observed count")
        if kind != "android" and counts[kind] == 0:
            builder.block("missing_required_gallery", kind, "Required native screenshot group is absent")

    def add_asset(loc: str, kind: str, index: int, path: str, proof_path: str,
                  proof: dict | None, source: str | None, spec: dict | None = None):
        info = builder.file(path)
        if info is None:
            return
        deps = builder.dependencies(common + [proof_path, str(Path(path).with_suffix(".svg"))])
        asset = {"locale": loc, "kind": kind, "index": index, "path": path, "dependencies": deps}
        subject = f"{loc}/{kind}/{index}"
        if tuple(info.get("size", [])) not in SIZES[kind] or info.get("color_type") != 2:
            builder.block("wrong_output_dimensions_or_format", subject,
                          f"Actual size={info.get('size')} color_type={info.get('color_type')}; required={sorted(SIZES[kind])} RGB")
        svg = builder.file(str(Path(path).with_suffix(".svg")))
        if proof:
            builder.match(proof, "source", source, proof_path)
            builder.match(proof, "output_sha256" if kind in slots else "png_sha256", info["sha256"], proof_path)
            if svg:
                builder.match(proof, "svg_sha256", svg["sha256"], proof_path)
            if source:
                src = builder.file(source)
                if src:
                    builder.match(proof, "source_sha256", src["sha256"], proof_path)
                    deps.append(source)
            if kind == "android":
                builder.match(proof, "schema_version", 1, proof_path)
                builder.match(proof, "output", path, proof_path)
                builder.match(proof, "canvas", info.get("size"), proof_path)
                if "android" in fingerprints:
                    builder.match(proof, "renderer_sha256", fingerprints["android"], proof_path)
            if kind in slots:
                for field, expected in (("screen", index), ("slot", kind), ("locale", loc), ("size", info.get("size"))):
                    builder.match(proof, field, expected, proof_path)
                if spec:
                    builder.match(proof, "spec_sha256", sha(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()), proof_path)
            if kind in {"header", "search"}:
                for field, expected in (("schema_version", 1), ("kind", kind), ("locale", loc)):
                    builder.match(proof, field, expected, proof_path)
        else:
            builder.block("missing_render_provenance", subject, "No matching rendered evidence record")
        if kind not in {"header", "search"}:
            builder.capture(asset, source, version, marker, store)
        else:
            builder.block("placement_capture_binding_unverified", subject, "Canonical gate must bind interface media to current installed-build captures")
        if kind in {"android", "iphone_medium"}:
            dests = site_indices.get(loc, {})
            origins = android_indices.get(loc, {}) if kind == "android" else native_indices.get((loc, kind), {})
            if set(dests) == set(origins) == set(range(1, 7)):
                asset["site_path"] = str(dests[index].relative_to(site / detail))
            elif kind == "android" or not android_present:
                builder.block("source_site_mapping_mismatch", subject, "Source and existing six-file numeric destination mapping differ")
        asset["dependencies"] = sorted(set(deps))
        assets.append(asset)
        inspected.append({**asset, "sha256": info["sha256"], "size": info.get("size"),
                          "png_valid": info.get("png_valid", False)})

    for loc in locales:
        for index, path in sorted(android_indices.get(loc, {}).items()):
            proof_path = str(path.with_suffix(".provenance.json").relative_to(project))
            proof = builder.data(proof_path)
            add_asset(loc, "android", index, str(path.relative_to(project)), proof_path, proof,
                      proof.get("source") if proof else None)
        for slot in slots:
            entries = native_indices.get((loc, slot), {})
            if sorted(entries) != list(range(1, counts[slot] + 1)) or not entries:
                builder.block("incomplete_native_gallery", f"{loc}/{slot}", "Required contiguous native gallery is missing or incomplete")
            declared_locales = device_manifest.get("locales", {})
            loc_spec = declared_locales.get(loc, {}) if isinstance(declared_locales, dict) else {}
            specs = loc_spec.get(slot) if isinstance(loc_spec, dict) else None
            if not isinstance(specs, list) or len(specs) != len(entries) or not specs:
                builder.block("native_spec_coverage", f"{loc}/{slot}", "Canonical manifest does not describe every existing native image")
                specs = []
            proof_path = f"{native_root}/{slot}/{loc}/render_manifest.json"
            render = builder.data(proof_path) or {}
            screens = render.get("screens", [])
            if not isinstance(screens, list) or any(not isinstance(record, dict) for record in screens):
                builder.block("invalid_render_manifest", proof_path, "Expected screen record array")
                screens = []
            by_index = {}
            for record in screens:
                index = record.get("screen")
                if type(index) is not int or index < 1 or index in by_index:
                    raise RegistrationError(f"Invalid/duplicate render manifest screen index: {proof_path}")
                by_index[index] = record
            if set(by_index) != set(entries):
                builder.block("render_manifest_coverage", proof_path, "Render records differ from actual image indices")
            if render and "ios" in fingerprints:
                builder.match(render, "renderer_sha256", fingerprints["ios"], proof_path)
                builder.match(render, "schema_version", 1, proof_path)
                for field in ("app_name", "accent"):
                    if field in device_manifest:
                        builder.match(render, field, device_manifest[field], proof_path)
            for index, path in sorted(entries.items()):
                if path.name != f"{index:02d}.png":
                    builder.block("noncanonical_native_filename", str(path.relative_to(project)), "Native renderer requires exact zero-padded numeric PNG names")
                spec = specs[index - 1] if index <= len(specs) and isinstance(specs[index - 1], dict) else None
                record = by_index.get(index)
                source = spec.get("raw") if spec else record.get("source") if record else None
                add_asset(loc, slot, index, str(path.relative_to(project)), proof_path, record, source, spec)
        for kind in ("header", "search"):
            path = f"{PROMO}/{kind}/{loc}.png"
            proof_path = f"{PROMO}/{kind}/{loc}.provenance.json"
            proof = builder.data(proof_path)
            placement = manifests["ios-header-search"] or {}
            declared = placement.get("locales", {})
            loc_spec = declared.get(loc, {}) if isinstance(declared, dict) else {}
            spec = loc_spec.get(kind) if isinstance(loc_spec, dict) else None
            if not isinstance(spec, dict):
                builder.block("missing_placement_spec", f"{loc}/{kind}", "Canonical header/search spec is missing")
            source = spec.get("media") if isinstance(spec, dict) else proof.get("source") if proof else None
            add_asset(loc, kind, 1, path, proof_path, proof, source)
            if isinstance(spec, dict):
                renderer_inputs = {}
                names = (f"{kind}_template.py", f"{kind}_icon_template.svg" if spec.get("media_style") == "icon"
                         else f"{kind}_template.svg", "creative_asset_core.py", "render_app_creatives.py")
                for name in names:
                    dependency = f"{shared_renderer_dir}/{name}"
                    info = builder.file(dependency)
                    if info:
                        renderer_inputs[name] = info["sha256"]
                        if assets and assets[-1]["path"] == path:
                            assets[-1]["dependencies"] = sorted(set(assets[-1]["dependencies"] + [dependency]))
                            inspected[-1]["dependencies"] = assets[-1]["dependencies"]
                if proof and len(renderer_inputs) == len(names):
                    payload = {"app_name": placement.get("app_name"), "accent": placement.get("accent"),
                               "locale": loc, "kind": kind, "config": spec, "renderer_inputs": renderer_inputs}
                    builder.match(proof, "config_sha256", sha(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()), proof_path)
                if source and spec.get("media_style", "interface") == "interface":
                    if not relative(project, source).is_relative_to(project / PROMO / "raw" / loc):
                        builder.block("placement_source_locale_mismatch", path, "Interface source must be a same-locale raw capture")
                    receipt = str(Path(source).with_suffix(".capture.json"))
                    builder.data(receipt)
    play = manifests["play"] or {}
    play_paths = [play.get("icon")]
    features = play.get("features", {})
    if isinstance(features, dict):
        play_paths.extend(features.values())
    for path in play_paths:
        if isinstance(path, str):
            builder.file(path)
        else:
            builder.block("missing_play_source", GROUPS["play"], "Play icon/feature paths must name actual existing files")
    inventory = {"schema_version": 1, "app_slug": slug, "ipad_supported": ipad_supported,
                 "locales": locales, "screenshot_counts": counts,
                 "android_render_command": [android_renderer, *android_render_args],
                 "assets": sorted(assets, key=lambda a: (a["locale"], a["kind"], a["index"]))}
    seen_captures = set()
    for asset in assets:
        if "raw_path" in asset:
            key = (asset["locale"], asset["kind"], builder.files["project:" + asset["raw_path"]]["sha256"])
            if key in seen_captures:
                builder.block("duplicate_raw_capture", f"{key[0]}/{key[1]}", "Gallery reuses the same raw capture bytes")
            seen_captures.add(key)
    for record in builder.files.values():
        raw = read_bytes(site if record["tree"] == "site" else project, record["path"])
        if raw is None or sha(raw) != record["sha256"]:
            raise RegistrationError(f"Input changed during inspection: {record['path']}")
    for is_site, path in builder.missing:
        if read_bytes(site if is_site else project, path) is not None:
            raise RegistrationError(f"Missing input appeared during inspection: {path}")
    for (root, value), observed in scanned_directories.items():
        if directory_signature(relative(root, value)) != observed:
            raise RegistrationError(f"Input directory changed during inspection: {value}")
    data_blockers = sum(item["code"] != "placement_capture_binding_unverified" for item in builder.blockers)
    for code, detail_text in (
        ("source_currentness_unverified", "Data-only inspection cannot establish the latest committed app source or installed build"),
        ("canonical_gate_required", "Run the pinned isolated canonical snapshot/renderer/group/capture gate after authorized registration"),
        ("independent_review_required", "A fresh exact-candidate independent visual review is required; no candidate or approval was generated")):
        builder.block(code, slug, detail_text)
    report = {"schema_version": 1, "status": "BLOCKED", "app_slug": slug,
              "operation": "data_only_draft_registration", "project": str(project), "site": str(site),
              "version_observed": version,
              "source_identity_claim": {key: marker[key] for key in ("version", "source_commit") if key in marker},
              "data_checks": "BLOCKED" if data_blockers else "INSPECTED_NOT_VERIFIED",
              "structural_checks": "BLOCKED" if data_blockers else "COMPLETE_DATA_ONLY",
              "current_source_and_capture_checks": "UNVERIFIED", "review_checks": "NOT_PERFORMED",
              "capture_scope": {
                  "current_patch_required_screens": None, "never_captured_slots": None,
                  "scope_status": "NOT_ESTABLISHED_BY_DATA_ONLY_INVENTORY",
                  "policy": "Refresh only visually affected screens. Missing historical evidence or device slots are separate completeness gaps, not proof of current-patch design changes or never-captured history.",
                  "applicability": builder.capture_applicability,
                  "missing_required_slots": [b for b in builder.blockers if b["code"] == "missing_required_gallery"],
                  "missing_capture_evidence": [b for b in builder.blockers if b["code"] == "capture_evidence_missing"]},
              "android_presence": "present" if android_present else "absent",
              "gallery_preference": "android" if android_present else "iphone_medium_if_canonical_gate_accepts",
              "observed_counts_by_locale": counts_by_locale, "manifest_locale_coverage": manifest_coverage,
              "count_policy": "Maximum observed count per kind; disagreement blocks; present Android is never declared absent",
              "draft_sha256": sha(json.dumps(inventory, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()),
              "assets": inspected, "files": sorted(builder.files.values(), key=lambda f: (f["tree"], f["path"])),
              "excluded_legacy_ios": legacy, "blockers": builder.blockers,
              "not_performed": ["app_code_execution", "capture", "render", "resize", "app_or_site_write",
                                "canonical_gate", "candidate_generation", "visual_approval", "publication"]}
    return inventory, report


def write_registration(output_dir: Path, inventory: dict, report: dict, *, project: Path, site: Path) -> Path:
    output = absolute(output_dir)
    roots = (root_directory(project), root_directory(site))
    if any(output == root or output.is_relative_to(root) or root.is_relative_to(output) for root in roots):
        raise RegistrationError("Output must be outside and disjoint from the app and site trees")
    if output.exists():
        raise RegistrationError("Output directory already exists; refusing to overwrite unrelated data")
    parent = root_directory(output.parent)
    if parent.stat().st_uid != os.getuid():
        raise RegistrationError("Output parent must be owned by the current user")
    parent_fd = open_directory(parent)
    output_fd = release_fd = None
    try:
        if os.fstat(parent_fd).st_uid != os.getuid():
            raise RegistrationError("Output parent must be owned by the current user")
        os.mkdir(output.name, mode=0o700, dir_fd=parent_fd)
        output_fd = open_directory(Path(output.name), dir_fd=parent_fd)
        output_identity = os.fstat(output_fd)
        os.mkdir("release", mode=0o700, dir_fd=output_fd)
        release_fd = open_directory(Path("release"), dir_fd=output_fd)
        for directory, name, value in ((release_fd, "artwork.json", inventory), (output_fd, "readiness.json", report)):
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
            descriptor = os.open(name, flags, 0o600, dir_fd=directory)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        current = absolute(output).lstat()
        if (current.st_dev, current.st_ino) != (output_identity.st_dev, output_identity.st_ino):
            raise RegistrationError("Output directory changed during writing")
    finally:
        for descriptor in (release_fd, output_fd, parent_fd):
            if descriptor is not None:
                os.close(descriptor)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--ipad-supported", choices=("true", "false"), required=True)
    parser.add_argument("--android-renderer", required=True, help="Existing project-relative .py file, inspected only")
    parser.add_argument("--shared-renderer-dir", required=True, help="Existing project-relative renderer directory")
    parser.add_argument("--android-render-arg", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True, help="New owned directory outside project and site")
    args = parser.parse_args(argv)
    try:
        inventory, report = build_inventory(project=args.project, site=args.site, slug=args.slug,
            ipad_supported=args.ipad_supported == "true", android_renderer=args.android_renderer,
            shared_renderer_dir=args.shared_renderer_dir, android_render_args=tuple(args.android_render_arg))
        output = write_registration(args.output_dir, inventory, report, project=args.project, site=args.site)
        print(f"Draft written to {output}; release readiness BLOCKED ({len(report['blockers'])} blockers)")
        return 2  # A successful data-only draft is never release approval.
    except (OSError, ValueError) as error:
        print(f"Inventory registration refused: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
