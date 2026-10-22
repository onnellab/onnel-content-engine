#!/usr/bin/env python3
"""Read-only, non-authorizing diagnostic for release artwork source drift.

This is an *explanation*, not an alternative gate. It never imports or
executes app code, creates inventory/captures, or makes a publication claim.
Only validate_vendored_bundle + the isolated canonical gate can authorize
staging; only the live verifier can confirm publication.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from isolated_vendored_artwork import (ROOT_ADAPTER, ROOT_ADAPTER_SHA256,
                                       VENDORED, load_allowlist)

MAX_BYTES = 4 * 1024 * 1024
SAFE_NAME = re.compile(r"[A-Za-z0-9_.-]{1,120}\Z")
PACKAGE = re.compile(rb"(?m)^name:\s*['\"]?([a-z0-9_]+)['\"]?\s*$")


def _read(root: Path, path: Path) -> bytes | None:
    """Bounded read of regular checkout files; never follow symlinks."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    if not relative.parts or ".." in relative.parts:
        return None
    current = root
    try:
        for part in relative.parts[:-1]:
            current /= part
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode):
                return None
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            return None
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(descriptor, "rb") as f:
            opened = os.fstat(f.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_size > MAX_BYTES:
                return None
            contents = f.read(MAX_BYTES + 1)
        if len(contents) > MAX_BYTES or len(contents) != opened.st_size:
            return None
        return contents
    except (OSError, ValueError):
        return None


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _valid_listing(repo: Path, paths: list[str], slug: str) -> list[Path]:
    matches: list[Path] = []
    for raw in paths:
        if raw != "pubspec.yaml" and not raw.endswith("/pubspec.yaml"):
            continue
        relative = Path(raw)
        if relative.is_absolute() or ".." in relative.parts:
            continue
        project = repo / relative.parent
        if not (project / VENDORED / "TEMPLATE_SOURCE.json").exists():
            continue
        pubspec = _read(repo, repo / relative)
        if not pubspec:
            continue
        match = PACKAGE.search(pubspec)
        if match and match.group(1).decode() == slug:
            matches.append(project)
    return matches


def inspect_project(repo: Path, project: Path, slug: str, ledger: dict,
                    tracked: set[str]) -> dict:
    """Inspect actual files independently of app metadata. Never assert release readiness."""
    prefix = project.relative_to(repo).as_posix()
    prefix = "" if prefix == "." else prefix + "/"
    inventory = prefix + "release/artwork.json"
    candidate = prefix + "release/artwork-candidate.json"
    review = prefix + "release/artwork-review.json"
    result = {
        "status": "data_only_blocked",
        "diagnostic_only": True,
        "project_path": prefix.rstrip("/") or ".",
        "inventory": "tracked" if inventory in tracked else "missing",
        "candidate": "tracked_unverified" if candidate in tracked else "missing",
        "independent_review": "tracked_unverified" if review in tracked else "missing",
        "source_pin": "unrecognized",
        "metadata_matches_approved": False,
        "root_adapter": "noncanonical",
        "mismatched_files": [],
        "missing_files": [],
        "unexpected_files": [],
        "blockers": [],
    }
    if result["inventory"] != "tracked":
        result["blockers"].append("missing_tracked_inventory")
    adapter = _read(repo, project / ROOT_ADAPTER)
    if adapter is not None and _digest(adapter) == ledger["root_adapter"]["sha256"] == ROOT_ADAPTER_SHA256:
        result["root_adapter"] = "canonical"
    else:
        result["blockers"].append("unsupported_root_adapter")
    bundle = project / VENDORED
    metadata_bytes = _read(repo, bundle / "TEMPLATE_SOURCE.json")
    try:
        metadata = json.loads(metadata_bytes) if metadata_bytes is not None else None
    except (ValueError, UnicodeError, TypeError):
        metadata = None
    if not isinstance(metadata, dict):
        result["blockers"].append("missing_or_invalid_bundle_metadata")
        return result
    selected = [(name, value) for name, value in ledger["bundles"].items()
                if metadata.get("commit") in value["source_commits"]]
    if len(selected) != 1:
        result["blockers"].append("unknown_bundle_source_pin")
        return result
    pin, expected = selected[0]
    result["source_pin"] = pin
    approved = expected["sha256"]
    if (metadata.get("repository") == ledger["repository"]
            and metadata.get("source_directory") == ledger["source_directory"]
            and metadata.get("preserved_safety_hardening") == []
            and metadata.get("sha256") == approved):
        result["metadata_matches_approved"] = True
    else:
        result["blockers"].append("bundle_metadata_mismatch")
    try:
        entries = list(bundle.iterdir())
    except OSError:
        result["blockers"].append("missing_bundle_directory")
        return result
    names = {entry.name for entry in entries}
    result["missing_files"] = sorted(set(approved) - names)
    result["unexpected_files"] = sorted(
        name for name in names - set(approved) - {"TEMPLATE_SOURCE.json", "SYNC_STATUS.md"}
        if SAFE_NAME.fullmatch(name)
    )
    for name, expected_sha in approved.items():
        if name not in names:
            continue
        content = _read(repo, bundle / name)
        if content is None or _digest(content) != expected_sha:
            result["mismatched_files"].append(name)
    result["mismatched_files"].sort()
    if result["missing_files"]:
        result["blockers"].append("canonical_files_missing")
    if result["unexpected_files"] or len(names - set(approved) - {"TEMPLATE_SOURCE.json", "SYNC_STATUS.md"}) != len(result["unexpected_files"]):
        result["blockers"].append("unexpected_bundle_files")
    if result["mismatched_files"]:
        result["blockers"].append("canonical_file_hash_mismatch")
    if not result["blockers"]:
        result["status"] = "data_only_source_conformant_release_unverified"
    return result


def probe(repo: Path, slug: str, *, paths: list[str] | None = None,
          ledger: dict | None = None) -> dict:
    """Run only in the existing release-staging checkout. No extra worker."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Unsafe release app slug")
    repo = repo.resolve()
    if paths is None:
        raw = subprocess.check_output(["git", "-C", str(repo), "ls-files", "-z"], timeout=30)
        paths = [item.decode("utf-8") for item in raw.split(b"\0") if item]
    paths = list(paths)
    projects = _valid_listing(repo, paths, slug)
    if len(projects) != 1:
        return {"status": "data_only_blocked", "diagnostic_only": True,
                "blockers": ["project_not_unambiguously_discoverable"],
                "matching_project_count": len(projects)}
    return inspect_project(repo, projects[0], slug, ledger or load_allowlist(), set(paths))
