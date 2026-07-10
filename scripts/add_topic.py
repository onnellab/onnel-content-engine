#!/usr/bin/env python3
"""Add a topic row with the next automatic TOPIC ID."""

from __future__ import annotations

import argparse
import sys

from topic_management import TopicError, TopicStore


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add a topic to data/topics.csv")
    parser.add_argument("--category", required=True)
    parser.add_argument("--primary-question", required=True)
    parser.add_argument("--working-title", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--primary-language", required=True)
    parser.add_argument("--priority", required=True)
    parser.add_argument("--search-intent", required=True)
    parser.add_argument("--primary-keyword", required=True)
    parser.add_argument("--source-type", required=True)
    parser.add_argument("--related-apps", default="")
    parser.add_argument("--secondary-keywords", default="")
    parser.add_argument("--evergreen", default="true")
    parser.add_argument("--review-required", default="true")
    parser.add_argument("--notes", default="")
    return parser


def main() -> int:
    args = parser().parse_args()
    fields = {
        "category": args.category,
        "primary_question": args.primary_question,
        "working_title": args.working_title,
        "slug": args.slug,
        "primary_language": args.primary_language,
        "priority": args.priority,
        "search_intent": args.search_intent,
        "related_apps": args.related_apps,
        "primary_keyword": args.primary_keyword,
        "secondary_keywords": args.secondary_keywords,
        "evergreen": args.evergreen,
        "source_type": args.source_type,
        "review_required": args.review_required,
        "notes": args.notes,
    }
    try:
        row = TopicStore().add(fields)
    except TopicError as error:
        print(f"add topic failed: {error}", file=sys.stderr)
        return 1
    print(row["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
