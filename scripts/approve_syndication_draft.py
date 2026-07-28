#!/usr/bin/env python3
"""Approve a generated syndication draft."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from evaluate_syndication_drafts import DEFAULT_MANIFEST_PATH
from validate_syndication_drafts import SyndicationValidationError, project_root_for_manifest, validate_syndication_drafts


class SyndicationApprovalError(ValueError):
    """Raised when a syndication draft cannot be approved."""


def load_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        raise SyndicationApprovalError(f"syndication manifest does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def approve_syndication_draft(
    topic_id: str,
    platform: str,
    language: str,
    approved_by: str,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    now: datetime | None = None,
    allow_medium: bool = False,
) -> dict[str, object]:
    if not approved_by.strip():
        raise SyndicationApprovalError("approved_by is required")
    validate_syndication_drafts(manifest_path, project_root_for_manifest(manifest_path))
    if platform == "medium" and not allow_medium:
        raise SyndicationApprovalError("Medium is export-only; pass --allow-medium only for manual tracking")
    manifest = load_manifest(manifest_path)
    drafts = manifest.get("drafts")
    if not isinstance(drafts, list):
        raise SyndicationApprovalError("syndication manifest has no drafts list")
    matches = [
        draft
        for draft in drafts
        if isinstance(draft, dict)
        and draft.get("topic_id") == topic_id
        and draft.get("platform") == platform
        and draft.get("language") == language
    ]
    if not matches:
        raise SyndicationApprovalError(f"syndication draft not found: {topic_id} {platform} {language}")
    if len(matches) > 1:
        raise SyndicationApprovalError(f"multiple syndication drafts matched: {topic_id} {platform} {language}")
    draft = matches[0]
    if draft.get("status") == "posted":
        raise SyndicationApprovalError(f"syndication draft is already posted: {topic_id} {platform} {language}")
    timestamp = (now or datetime.now(ZoneInfo("Asia/Seoul"))).replace(microsecond=0).isoformat()
    draft["status"] = "approved"
    draft["approved_by"] = approved_by
    draft["approved_at"] = timestamp
    draft.setdefault("post_id", "")
    draft.setdefault("posted_url", "")
    draft.setdefault("posted_at", "")
    draft.setdefault("error", "")
    write_manifest(manifest_path, manifest)
    return draft


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve a generated syndication draft")
    parser.add_argument("topic_id")
    parser.add_argument("platform", choices=("devto", "hashnode", "medium"))
    parser.add_argument("language", choices=("en", "ko"))
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--allow-medium", action="store_true")
    args = parser.parse_args()
    try:
        draft = approve_syndication_draft(
            args.topic_id,
            args.platform,
            args.language,
            args.approved_by,
            args.manifest,
            allow_medium=args.allow_medium,
        )
    except (SyndicationApprovalError, SyndicationValidationError, OSError, json.JSONDecodeError) as error:
        print(f"syndication approval failed: {error}", file=sys.stderr)
        return 1
    print(f"approved {draft['topic_id']} {draft['platform']} {draft['language']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
