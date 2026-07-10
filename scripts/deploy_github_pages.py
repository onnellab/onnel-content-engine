#!/usr/bin/env python3
"""Deploy the generated site directory to the GitHub Pages branch."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from publishing import DEFAULT_PAGES_BRANCH, DEFAULT_PAGES_REPOSITORY, DEFAULT_SITE_DIR, PublishingError, deploy_github_pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy site/ to GitHub Pages")
    parser.add_argument("--site-dir", type=Path, default=DEFAULT_SITE_DIR)
    parser.add_argument("--repository", default=DEFAULT_PAGES_REPOSITORY)
    parser.add_argument("--branch", default=DEFAULT_PAGES_BRANCH)
    args = parser.parse_args()
    try:
        deploy_github_pages(args.site_dir, repository=args.repository, branch=args.branch)
    except (PublishingError, OSError, subprocess.CalledProcessError) as error:
        print(f"github pages deployment failed: {error}", file=sys.stderr)
        return 1
    print(f"deployed {args.site_dir} to {args.repository} {args.branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
