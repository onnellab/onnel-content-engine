#!/usr/bin/env python3
"""Reset a failed social post back to approved for explicit retry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from approve_social_post import load_manifest, project_root_for_manifest, write_manifest
from validate_social_posts import DEFAULT_MANIFEST_PATH, SocialValidationError, validate_social_posts


class SocialResetError(ValueError):
    """Raised when a failed social post cannot be reset."""


def reset_failed_social_post(
    topic_id: str,
    platform: str,
    language: str,
    template_id: str,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, object]:
    validate_social_posts(manifest_path, project_root_for_manifest(manifest_path))
    manifest = load_manifest(manifest_path)
    posts = manifest.get("posts")
    if not isinstance(posts, list):
        raise SocialResetError("social manifest has no posts list")
    matches = [
        post
        for post in posts
        if isinstance(post, dict)
        and post.get("topic_id") == topic_id
        and post.get("platform") == platform
        and post.get("language") == language
        and post.get("template_id") == template_id
    ]
    if not matches:
        raise SocialResetError(f"social post not found: {topic_id} {platform} {language} {template_id}")
    if len(matches) > 1:
        raise SocialResetError(f"multiple social posts matched: {topic_id} {platform} {language} {template_id}")
    post = matches[0]
    if post.get("status") != "failed":
        raise SocialResetError(f"social post is not failed: {topic_id} {platform} {language} {template_id}")
    post["status"] = "approved"
    post["error"] = ""
    write_manifest(manifest_path, manifest)
    return post


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset a failed social post to approved")
    parser.add_argument("topic_id")
    parser.add_argument("platform", choices=("x", "linkedin", "bluesky"))
    parser.add_argument("language", choices=("en", "ko"))
    parser.add_argument("template_id")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    args = parser.parse_args()
    try:
        post = reset_failed_social_post(args.topic_id, args.platform, args.language, args.template_id, args.manifest)
    except (SocialResetError, SocialValidationError, OSError, json.JSONDecodeError) as error:
        print(f"social reset failed: {error}", file=sys.stderr)
        return 1
    print(f"reset {post['topic_id']} {post['platform']} {post['language']} {post['template_id']} to approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
