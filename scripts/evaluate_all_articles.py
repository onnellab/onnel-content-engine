#!/usr/bin/env python3
"""Evaluate every reviewable article."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evaluate_article import (
    DEFAULT_ASSETS_ROOT,
    DEFAULT_METADATA_ROOT,
    DEFAULT_REVIEW_ROOT,
    ArticleEvaluationError,
    evaluate_article,
)
from topic_management import DEFAULT_TOPICS_PATH, TOPIC_HEADER, read_csv


REVIEWABLE_STATUSES = {"review", "scheduled", "published", "update_required"}


def reviewable_topic_ids(topics_path: Path) -> list[str]:
    return [row["id"] for row in read_csv(topics_path, TOPIC_HEADER) if row["status"] in REVIEWABLE_STATUSES and row["canonical_path"]]


def evaluate_all_articles(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    metadata_root: Path = DEFAULT_METADATA_ROOT,
    assets_root: Path = DEFAULT_ASSETS_ROOT,
    review_root: Path = DEFAULT_REVIEW_ROOT,
) -> list[Path]:
    paths: list[Path] = []
    for topic_id in reviewable_topic_ids(topics_path):
        paths.append(evaluate_article(topic_id, topics_path, metadata_root, assets_root, review_root))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate every reviewable article")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--metadata-root", type=Path, default=DEFAULT_METADATA_ROOT)
    parser.add_argument("--assets-root", type=Path, default=DEFAULT_ASSETS_ROOT)
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    args = parser.parse_args()
    try:
        paths = evaluate_all_articles(args.topics, args.metadata_root, args.assets_root, args.review_root)
    except (ArticleEvaluationError, OSError) as error:
        print(f"evaluate all articles failed: {error}", file=sys.stderr)
        return 1
    print(f"evaluated {len(paths)} article(s)")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
