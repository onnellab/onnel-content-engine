#!/usr/bin/env python3
"""Build only centralized app privacy-policy pages."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from publishing import (
    DEFAULT_APPS_REGISTRY_PATH,
    DEFAULT_PRIVACY_POLICIES_PATH,
    DEFAULT_SITE_URL,
    PublishingError,
    normalize_site_url,
    write_privacy_pages,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ONNELLAB app privacy-policy pages")
    parser.add_argument("--policies", type=Path, default=DEFAULT_PRIVACY_POLICIES_PATH)
    parser.add_argument("--apps", type=Path, default=DEFAULT_APPS_REGISTRY_PATH)
    parser.add_argument("--site-dir", type=Path, required=True)
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    args = parser.parse_args()
    try:
        if args.site_dir.exists():
            shutil.rmtree(args.site_dir)
        args.site_dir.mkdir(parents=True)
        pages = write_privacy_pages(
            args.site_dir,
            normalize_site_url(args.site_url),
            args.policies,
            args.apps,
        )
    except (OSError, ValueError, KeyError, TypeError, PublishingError) as error:
        print(f"app privacy page build failed: {error}", file=sys.stderr)
        return 1
    print(f"built {len(pages)} localized app privacy pages in {args.site_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
