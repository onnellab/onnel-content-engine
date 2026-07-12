#!/usr/bin/env python3
"""Approve a generated social draft in generated/social/manifest.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from validate_social_posts import validate_social_posts


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "generated" / "social" / "manifest.json"


class SocialApprovalError(ValueError):
    """Raised when a social draft cannot be approved."""


def load_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        raise SocialApprovalError(f"social manifest does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def project_root_for_manifest(path: Path) -> Path:
    if path.name == "manifest.json" and path.parent.name == "social" and path.parent.parent.name == "generated":
        return path.parent.parent.parent
    return ROOT


def approve_social_post(
    topic_id: str,
    platform: str,
    language: str,
    approved_by: str,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    now: datetime | None = None,
    allow_variant: bool = False,
    template_id: str | None = None,
) -> dict[str, object]:
    if not approved_by.strip():
        raise SocialApprovalError("approved_by is required")
    validate_social_posts(manifest_path, project_root_for_manifest(manifest_path))
    manifest = load_manifest(manifest_path)
    posts = manifest.get("posts")
    if not isinstance(posts, list):
        raise SocialApprovalError("social manifest has no posts list")
    matches = [
        post
        for post in posts
        if isinstance(post, dict)
        and post.get("topic_id") == topic_id
        and post.get("platform") == platform
        and post.get("language") == language
        and (post.get("template_id") == template_id if template_id else post.get("is_variant") is not True)
    ]
    if not matches:
        raise SocialApprovalError(f"social draft not found: {topic_id} {platform} {language}")
    if len(matches) > 1:
        raise SocialApprovalError(f"multiple social drafts matched: {topic_id} {platform} {language}")
    post = matches[0]
    if post.get("status") == "posted":
        raise SocialApprovalError(f"social draft is already posted: {topic_id} {platform} {language}")
    if post.get("status") == "variant" and not allow_variant:
        raise SocialApprovalError(f"variant drafts require --allow-variant before approval: {topic_id} {platform} {language}")
    timestamp = (now or datetime.now(ZoneInfo("Asia/Seoul"))).replace(microsecond=0).isoformat()
    post["status"] = "approved"
    post["approved_by"] = approved_by
    post["approved_at"] = timestamp
    post.setdefault("post_id", "")
    post.setdefault("posted_url", "")
    post.setdefault("posted_at", "")
    post.setdefault("last_attempt_at", "")
    post.setdefault("error", "")
    post.setdefault("retry_count", 0)
    write_manifest(manifest_path, manifest)
    return post


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve a generated social draft")
    parser.add_argument("topic_id")
    parser.add_argument("platform", choices=("x", "linkedin", "bluesky"))
    parser.add_argument("language", choices=("en", "ko"))
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--allow-variant", action="store_true")
    parser.add_argument("--template-id")
    args = parser.parse_args()
    try:
        post = approve_social_post(
            args.topic_id,
            args.platform,
            args.language,
            args.approved_by,
            args.manifest,
            allow_variant=args.allow_variant,
            template_id=args.template_id,
        )
    except (SocialApprovalError, OSError, json.JSONDecodeError) as error:
        print(f"social approval failed: {error}", file=sys.stderr)
        return 1
    print(f"approved {post['topic_id']} {post['platform']} {post['language']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
