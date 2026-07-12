#!/usr/bin/env python3
"""Post approved core distribution drafts while isolating platform failures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from post_social_drafts import SocialPostingError, post_social_drafts
from post_syndication_drafts import SyndicationPostingError, post_syndication_drafts
from validate_social_posts import DEFAULT_MANIFEST_PATH as DEFAULT_SOCIAL_MANIFEST
from validate_social_posts import SocialValidationError
from validate_syndication_drafts import SyndicationValidationError
from validate_syndication_drafts import DEFAULT_MANIFEST_PATH as DEFAULT_SYNDICATION_MANIFEST


CORE_SOCIAL = ("x", "bluesky")
CORE_SYNDICATION = ("devto",)


def post_core_distribution(
    social_manifest: Path = DEFAULT_SOCIAL_MANIFEST,
    syndication_manifest: Path = DEFAULT_SYNDICATION_MANIFEST,
    dry_run: bool = False,
) -> list[str]:
    errors: list[str] = []
    for platform in CORE_SOCIAL:
        try:
            posts = post_social_drafts(social_manifest, platform=platform, adapter=platform, dry_run=dry_run)
            print(f"{platform}: {'would post' if dry_run else 'posted'} {len(posts)} social draft(s)")
        except Exception as error:
            message = f"{platform}: {error}"
            print(message, file=sys.stderr)
            errors.append(message)
    for platform in CORE_SYNDICATION:
        try:
            drafts = post_syndication_drafts(syndication_manifest, platform=platform, adapter=platform, dry_run=dry_run)
            print(f"{platform}: {'would post' if dry_run else 'posted'} {len(drafts)} syndication draft(s)")
        except Exception as error:
            message = f"{platform}: {error}"
            print(message, file=sys.stderr)
            errors.append(message)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Post approved core distribution drafts")
    parser.add_argument("--social-manifest", type=Path, default=DEFAULT_SOCIAL_MANIFEST)
    parser.add_argument("--syndication-manifest", type=Path, default=DEFAULT_SYNDICATION_MANIFEST)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        errors = post_core_distribution(args.social_manifest, args.syndication_manifest, args.dry_run)
    except (
        SocialValidationError,
        SyndicationValidationError,
        SocialPostingError,
        SyndicationPostingError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(f"post core distribution failed: {error}", file=sys.stderr)
        return 1
    if errors:
        print(f"core distribution completed with {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("core distribution completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
