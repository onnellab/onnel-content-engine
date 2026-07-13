#!/usr/bin/env python3
"""Validate generated long-form syndication drafts before posting."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from evaluate_syndication_drafts import DEFAULT_MANIFEST_PATH, frontmatter


ROOT = Path(__file__).resolve().parents[1]


class SyndicationValidationError(ValueError):
    """Raised when syndication drafts fail validation."""


def project_root_for_manifest(path: Path) -> Path:
    if path.name == "manifest.json" and path.parent.name == "syndication" and path.parent.parent.name == "generated":
        return path.parent.parent.parent
    return ROOT


def require_string(draft: dict[str, object], field: str) -> str:
    value = draft.get(field)
    if not isinstance(value, str):
        raise SyndicationValidationError(f"draft has invalid {field}: {value!r}")
    return value


def optional_int(draft: dict[str, object], field: str) -> int:
    value = draft.get(field, 0)
    if not isinstance(value, int):
        raise SyndicationValidationError(f"draft has invalid {field}: {value!r}")
    return value


def validate_draft(draft: dict[str, object], project_root: Path = ROOT) -> None:
    topic_id = require_string(draft, "topic_id")
    platform = require_string(draft, "platform")
    language = require_string(draft, "language")
    draft_path = project_root / require_string(draft, "draft_path")
    canonical_url = require_string(draft, "canonical_url")
    status = require_string(draft, "status")

    if platform not in {"devto", "hashnode", "medium"}:
        raise SyndicationValidationError(f"{topic_id} has unsupported syndication platform: {platform}")
    if language not in {"en", "ko"}:
        raise SyndicationValidationError(f"{topic_id} has unsupported language: {language}")
    if status not in {"draft", "approved", "posted", "failed"}:
        raise SyndicationValidationError(f"{topic_id} has unsupported syndication status: {status}")
    if optional_int(draft, "retry_count") < 0:
        raise SyndicationValidationError(f"{topic_id} has negative retry_count")
    if platform == "medium" and status != "draft":
        raise SyndicationValidationError(f"{topic_id} Medium is export-only and must remain draft")
    if not canonical_url.startswith(("http://", "https://")):
        raise SyndicationValidationError(f"{topic_id} has invalid canonical_url: {canonical_url}")
    if not draft_path.exists():
        raise SyndicationValidationError(f"{topic_id} draft does not exist: {draft_path}")
    content = draft_path.read_text(encoding="utf-8")
    metadata = frontmatter(content)
    if platform != "medium" and metadata.get("canonical_url") != canonical_url:
        raise SyndicationValidationError(f"{topic_id} canonical frontmatter mismatch: {draft_path}")
    if f"Originally published at {canonical_url}" not in content:
        raise SyndicationValidationError(f"{topic_id} missing canonical notice: {draft_path}")
    if not re.search(r"^#\s+", content, re.MULTILINE):
        raise SyndicationValidationError(f"{topic_id} draft body has no title heading: {draft_path}")
    if platform == "devto" and metadata.get("published") != "true":
        raise SyndicationValidationError(f"{topic_id} Dev.to draft must be public by default")
    if platform == "devto" and re.search(r"https?://[^\s)]+/workflow-diagram\.svg|/blog-assets/[^\s)]+/workflow-diagram\.svg", content):
        raise SyndicationValidationError(f"{topic_id} Dev.to draft must use PNG body images, not SVG")
    if platform in {"devto", "hashnode"} and not metadata.get("tags"):
        raise SyndicationValidationError(f"{topic_id} {platform} draft has no tags")
    if platform == "hashnode":
        if not metadata.get("cover_image", "").endswith("/social-card.png"):
            raise SyndicationValidationError(f"{topic_id} Hashnode draft has invalid cover_image")
        if "publication_id" not in metadata:
            raise SyndicationValidationError(f"{topic_id} Hashnode draft has no publication_id placeholder")


def validate_syndication_drafts(manifest_path: Path = DEFAULT_MANIFEST_PATH, project_root: Path | None = None) -> int:
    if not manifest_path.exists():
        raise SyndicationValidationError(f"syndication manifest does not exist: {manifest_path}")
    root = project_root or project_root_for_manifest(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    drafts = manifest.get("drafts")
    if not isinstance(drafts, list) or not drafts:
        raise SyndicationValidationError("syndication manifest has no drafts")
    for draft in drafts:
        if not isinstance(draft, dict):
            raise SyndicationValidationError(f"invalid draft entry: {draft!r}")
        validate_draft(draft, root)
    return len(drafts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated syndication drafts")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    args = parser.parse_args()
    try:
        count = validate_syndication_drafts(args.manifest)
    except (SyndicationValidationError, OSError, json.JSONDecodeError) as error:
        print(f"syndication validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {count} syndication draft(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
