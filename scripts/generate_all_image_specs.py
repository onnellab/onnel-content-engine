#!/usr/bin/env python3
"""Generate image specifications for every draft Markdown article."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generate_image_spec import ImageSpecError, generate_image_spec
from topic_management import DEFAULT_APPS_PATH, DEFAULT_TOPICS_PATH, LEGACY_TOPICS_PATH, TOPIC_HEADER, TopicError, read_csv


ROOT = Path(__file__).resolve().parents[1]


def draft_markdown_paths(topics_path: Path) -> list[Path]:
    project_root = topics_path.parent.parent
    paths: list[Path] = []
    for row in read_csv(topics_path, TOPIC_HEADER):
        if row["status"] == "draft" and row["canonical_path"]:
            paths.append(project_root / row["canonical_path"])
    return paths


def generate_all_image_specs(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    apps_path: Path = DEFAULT_APPS_PATH,
    output_root: Path = ROOT / "generated" / "images",
    legacy_topics_path: Path | None = LEGACY_TOPICS_PATH,
) -> list[Path]:
    generated: list[Path] = []
    for markdown_path in draft_markdown_paths(topics_path):
        generated.append(
            generate_image_spec(
                markdown_path,
                topics_path=topics_path,
                apps_path=apps_path,
                output_root=output_root,
                legacy_topics_path=legacy_topics_path,
            )
        )
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate image specifications for draft Markdown articles")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--apps", type=Path, default=DEFAULT_APPS_PATH)
    parser.add_argument("--output-root", type=Path, default=ROOT / "generated" / "images")
    parser.add_argument("--legacy-topics", type=Path, default=LEGACY_TOPICS_PATH)
    args = parser.parse_args()
    try:
        paths = generate_all_image_specs(args.topics, args.apps, args.output_root, args.legacy_topics)
    except (ImageSpecError, TopicError, OSError) as error:
        print(f"generate all image specs failed: {error}", file=sys.stderr)
        return 1
    print(f"generated {len(paths)} image specification file(s)")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
