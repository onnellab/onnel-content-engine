#!/usr/bin/env python3
"""Generate social distribution drafts for published articles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from publishing import DEFAULT_SITE_URL, DEFAULT_SOCIAL_OUTPUT_DIR, DEFAULT_TOPICS_PATH, PublishingError, generate_social_posts
from topic_management import TopicError


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate social distribution drafts")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_SOCIAL_OUTPUT_DIR)
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    args = parser.parse_args()
    try:
        posts = generate_social_posts(args.topics, args.output_dir, args.site_url)
    except (PublishingError, TopicError, OSError) as error:
        print(f"social generation failed: {error}", file=sys.stderr)
        return 1
    print(f"generated {len(posts)} primary social draft(s)")
    for post in posts:
        print(f"{post.topic_id} {post.platform} {post.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
