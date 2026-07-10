#!/usr/bin/env python3
"""Generate Markdown drafts for every approved topic."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generate_markdown import MarkdownGenerationError, generate_markdown
from topic_management import DEFAULT_APPS_PATH, DEFAULT_TOPICS_PATH, LEGACY_TOPICS_PATH, TOPIC_HEADER, TopicError, read_csv


ROOT = Path(__file__).resolve().parents[1]


def approved_topic_ids(topics_path: Path) -> list[str]:
    return [row["id"] for row in read_csv(topics_path, TOPIC_HEADER) if row["status"] == "approved"]


def generate_all_markdown(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    apps_path: Path = DEFAULT_APPS_PATH,
    output_root: Path = ROOT / "generated" / "markdown",
    legacy_topics_path: Path | None = LEGACY_TOPICS_PATH,
) -> list[Path]:
    generated: list[Path] = []
    for topic_id in approved_topic_ids(topics_path):
        generated.append(
            generate_markdown(
                topic_id,
                topics_path=topics_path,
                apps_path=apps_path,
                output_root=output_root,
                legacy_topics_path=legacy_topics_path,
            )
        )
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Markdown drafts for approved topics")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--apps", type=Path, default=DEFAULT_APPS_PATH)
    parser.add_argument("--output-root", type=Path, default=ROOT / "generated" / "markdown")
    parser.add_argument("--legacy-topics", type=Path, default=LEGACY_TOPICS_PATH)
    args = parser.parse_args()
    try:
        paths = generate_all_markdown(args.topics, args.apps, args.output_root, args.legacy_topics)
    except (MarkdownGenerationError, TopicError, OSError) as error:
        print(f"generate all markdown failed: {error}", file=sys.stderr)
        return 1
    print(f"generated {len(paths)} Markdown draft(s)")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
