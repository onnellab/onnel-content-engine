#!/usr/bin/env python3
"""Generate internal link metadata for every article-stage topic."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generate_internal_links import InternalLinkError, generate_internal_links
from topic_management import DEFAULT_APPS_PATH, DEFAULT_TOPICS_PATH, TOPIC_HEADER, read_csv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "generated" / "metadata"
LINKABLE_STATUSES = {"draft", "image_planning", "review", "scheduled", "published", "update_required"}


def linkable_topic_ids(topics_path: Path) -> list[str]:
    return [row["id"] for row in read_csv(topics_path, TOPIC_HEADER) if row["status"] in LINKABLE_STATUSES and row["canonical_path"]]


def generate_all_internal_links(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    apps_path: Path = DEFAULT_APPS_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> list[Path]:
    paths: list[Path] = []
    for topic_id in linkable_topic_ids(topics_path):
        paths.append(generate_internal_links(topic_id, topics_path, apps_path, output_root))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate internal link metadata for article-stage topics")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--apps", type=Path, default=DEFAULT_APPS_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    try:
        paths = generate_all_internal_links(args.topics, args.apps, args.output_root)
    except (InternalLinkError, OSError) as error:
        print(f"generate all internal links failed: {error}", file=sys.stderr)
        return 1
    print(f"generated {len(paths)} internal link metadata file(s)")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
