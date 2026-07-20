#!/usr/bin/env python3
"""Report whether the bilingual publication queue has a qualified article pair."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evaluate_article import DEFAULT_REVIEW_ROOT, DEFAULT_THRESHOLD
from schedule_ready_articles import REQUIRED_PUBLICATION_LANGUAGES, grouped_by_publication
from topic_management import DEFAULT_TOPICS_PATH, TOPIC_HEADER, read_csv


ACTIVE_STATUSES = {"approved", "research", "outline", "draft", "image_planning", "review", "scheduled"}


def review_score(row: dict[str, str], review_root: Path) -> float | None:
    path = review_root / row["primary_language"] / row["category"] / row["slug"] / "review.json"
    if not path.exists():
        return None
    try:
        return float(json.loads(path.read_text(encoding="utf-8")).get("score", 0.0))
    except (OSError, ValueError, json.JSONDecodeError, AttributeError):
        return None


def content_supply_report(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    review_root: Path = DEFAULT_REVIEW_ROOT,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, object]:
    rows = read_csv(topics_path, TOPIC_HEADER)
    groups = grouped_by_publication(rows)
    qualified: list[dict[str, object]] = []
    active: list[dict[str, object]] = []
    for (category, slug), group in groups.items():
        languages = {row["primary_language"] for row in group}
        if not REQUIRED_PUBLICATION_LANGUAGES <= languages:
            continue
        pair = {row["primary_language"]: row for row in group if row["primary_language"] in REQUIRED_PUBLICATION_LANGUAGES}
        statuses = {row["status"] for row in pair.values()}
        scores = {language: review_score(row, review_root) for language, row in pair.items()}
        if statuses & ACTIVE_STATUSES:
            active.append({"category": category, "slug": slug, "statuses": sorted(statuses), "scores": scores})
        if statuses == {"scheduled"} or (
            statuses == {"review"}
            and all(score is not None and score > threshold for score in scores.values())
        ):
            qualified.append({"category": category, "slug": slug, "statuses": sorted(statuses), "scores": scores})
    return {
        "qualified_pair_count": len(qualified),
        "qualified_pairs": qualified,
        "active_pair_count": len(active),
        "active_pairs": active,
        "idea_count": sum(row["status"] == "idea" for row in rows),
        "unpaired_idea_count": sum(
            row["status"] == "idea"
            and not any(
                other["category"] == row["category"]
                and other["slug"] == row["slug"]
                and other["primary_language"] != row["primary_language"]
                for other in rows
            )
            for row in rows
        ),
        "threshold": threshold,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the bilingual content supply queue")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--require-qualified-pair", action="store_true")
    parser.add_argument("--require-healthy", action="store_true")
    parser.add_argument("--minimum-ideas", type=int, default=8)
    args = parser.parse_args()
    report = content_supply_report(args.topics, args.review_root, args.threshold)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_qualified_pair and int(report["qualified_pair_count"]) < 1:
        print("content supply check failed: no qualified English/Korean review or scheduled pair", file=sys.stderr)
        return 1
    if args.require_healthy and (
        int(report["qualified_pair_count"]) < 1 or int(report["idea_count"]) < args.minimum_ideas
    ):
        print(
            "content supply check failed: "
            f"qualified_pairs={report['qualified_pair_count']}, ideas={report['idea_count']}, "
            f"minimum_ideas={args.minimum_ideas}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
