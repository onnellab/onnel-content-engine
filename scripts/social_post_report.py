#!/usr/bin/env python3
"""Print a dry-run report for generated social drafts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from validate_social_posts import DEFAULT_MANIFEST_PATH, SocialValidationError, validate_social_posts
from approve_social_post import project_root_for_manifest


def social_post_report(manifest_path: Path = DEFAULT_MANIFEST_PATH) -> str:
    validate_social_posts(manifest_path, project_root_for_manifest(manifest_path))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    posts = [post for post in manifest["posts"] if isinstance(post, dict)]
    counts = Counter(str(post["status"]) for post in posts)
    lines = [
        "Social post dry-run report",
        "",
        f"total: {len(posts)}",
        f"approved: {counts.get('approved', 0)}",
        f"draft: {counts.get('draft', 0)}",
        f"variant: {counts.get('variant', 0)}",
        f"posted: {counts.get('posted', 0)}",
        f"failed: {counts.get('failed', 0)}",
        "",
        "Posting readiness:",
    ]
    for post in posts:
        reasons: list[str] = []
        if post.get("status") != "approved":
            reasons.append(f"status={post.get('status')}")
        if post.get("status") == "posted":
            reasons.append("already posted")
        if post.get("is_variant") and post.get("status") != "approved":
            reasons.append("variant requires explicit approval")
        if post.get("platform") in {"x", "linkedin", "bluesky"}:
            reasons.append("real API token required for non-mock adapter")
        readiness = "ready for mock posting" if post.get("status") == "approved" else "not ready"
        lines.append(
            f"- {readiness}: {post['topic_id']} {post['platform']} {post['language']} "
            f"{post['template_id']} ({'; '.join(reasons) if reasons else 'approved'})"
        )
    lines.extend([
        "",
        "Approved posts:",
    ])
    approved = [post for post in posts if post.get("status") == "approved"]
    if not approved:
        lines.append("- none")
    for post in approved:
        lines.append(
            f"- {post['topic_id']} {post['platform']} {post['language']} "
            f"{post['template_id']} length={post['weighted_length']} card={post['card_asset_path']}"
        )
    lines.extend(["", "Pending drafts:"])
    pending = [post for post in posts if post.get("status") in {"draft", "variant"}]
    if not pending:
        lines.append("- none")
    for post in pending:
        lines.append(f"- {post['status']} {post['topic_id']} {post['platform']} {post['language']} {post['template_id']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a dry-run social posting report")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    args = parser.parse_args()
    try:
        print(social_post_report(args.manifest))
    except (SocialValidationError, OSError, json.JSONDecodeError) as error:
        print(f"social report failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
