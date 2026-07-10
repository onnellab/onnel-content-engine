#!/usr/bin/env python3
"""Publish generated Markdown into the GitHub Pages homepage repository."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from publishing import (
    DEFAULT_HOMEPAGE_REPOSITORY_PATH,
    DEFAULT_PAGES_BRANCH,
    DEFAULT_PAGES_REPOSITORY,
    DEFAULT_SITE_DIR,
    PublishingError,
    deploy_github_pages,
)
from topic_management import DEFAULT_TOPICS_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Markdown drafts to the GitHub Pages homepage repository")
    parser.add_argument("--site-dir", type=Path, default=DEFAULT_SITE_DIR)
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--repository", default=DEFAULT_PAGES_REPOSITORY)
    parser.add_argument("--branch", default=DEFAULT_PAGES_BRANCH)
    parser.add_argument("--homepage-repo", type=Path, default=DEFAULT_HOMEPAGE_REPOSITORY_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Preview homepage Markdown export without copying or deploying")
    args = parser.parse_args()
    try:
        exports = deploy_github_pages(
            args.site_dir,
            repository=args.repository,
            branch=args.branch,
            topics_path=args.topics,
            homepage_repo=args.homepage_repo,
            dry_run=args.dry_run,
        )
    except (PublishingError, OSError, subprocess.CalledProcessError) as error:
        print(f"github pages deployment failed: {error}", file=sys.stderr)
        return 1
    for item in exports:
        print(f"{item.action}: {item.source} -> {item.destination}")
    if args.dry_run:
        print(f"dry-run completed for {args.homepage_repo}")
    else:
        print(f"published Markdown to {args.homepage_repo} {args.branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
