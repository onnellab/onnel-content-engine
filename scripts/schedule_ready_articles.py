#!/usr/bin/env python3
"""Schedule reviewed articles at a fixed publication interval."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evaluate_article import DEFAULT_REVIEW_ROOT, DEFAULT_THRESHOLD
from topic_management import DEFAULT_TOPICS_PATH, LEGACY_TOPICS_PATH, TOPIC_HEADER, TopicError, TopicStore, read_csv


KST = timezone(timedelta(hours=9))
DEFAULT_PUBLICATION_TIME = "09:00"
DEFAULT_INTERVAL_DAYS = 3
REQUIRED_PUBLICATION_LANGUAGES = {"en", "ko"}


class SchedulingError(ValueError):
    """Raised when scheduling cannot proceed."""


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise SchedulingError(f"invalid datetime: {value}") from error


def review_path_for(topic: dict[str, str], review_root: Path) -> Path:
    return review_root / topic["primary_language"] / topic["category"] / topic["slug"] / "review.json"


def review_score(topic: dict[str, str], review_root: Path) -> float:
    path = review_path_for(topic, review_root)
    if not path.exists():
        raise SchedulingError(f"{topic['id']} has no review file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return float(data.get("score", 0.0))


def publication_key(topic: dict[str, str]) -> tuple[str, str]:
    return topic["category"], topic["slug"]


def grouped_by_publication(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(publication_key(row), []).append(row)
    return groups


def require_language_pair(group: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_language = {row["primary_language"]: row for row in group}
    missing = REQUIRED_PUBLICATION_LANGUAGES - set(by_language)
    if missing:
        ids = ", ".join(row["id"] for row in group)
        raise SchedulingError(f"publication group {ids} is missing language counterpart(s): {', '.join(sorted(missing))}")
    return {language: by_language[language] for language in sorted(REQUIRED_PUBLICATION_LANGUAGES)}


def publication_clock(value: str) -> tuple[int, int]:
    hour_text, minute_text = value.split(":", 1)
    return int(hour_text), int(minute_text)


def latest_publication_anchor(rows: list[dict[str, str]], now: datetime) -> datetime:
    anchors: list[datetime] = []
    for row in rows:
        for field in ["scheduled_at", "published_at"]:
            parsed = parse_datetime(row[field])
            if parsed:
                anchors.append(parsed.astimezone(KST))
    return max(anchors) if anchors else now.astimezone(KST)


def next_slot(anchor: datetime, interval_days: int, publication_time: str) -> datetime:
    hour, minute = publication_clock(publication_time)
    candidate = anchor.astimezone(KST) + timedelta(days=interval_days)
    return candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)


def schedule_ready_articles(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    review_root: Path = DEFAULT_REVIEW_ROOT,
    legacy_topics_path: Path | None = LEGACY_TOPICS_PATH,
    threshold: float = DEFAULT_THRESHOLD,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
    publication_time: str = DEFAULT_PUBLICATION_TIME,
    now: datetime | None = None,
    limit: int = 1,
) -> list[dict[str, str]]:
    rows = read_csv(topics_path, TOPIC_HEADER)
    now = now or datetime.now(KST)
    anchor = latest_publication_anchor(rows, now)
    store = TopicStore(topics_path, mirror_path=legacy_topics_path)
    scheduled: list[dict[str, str]] = []

    groups = grouped_by_publication(rows)
    candidates = [group for group in groups.values() if any(row["status"] == "review" for row in group)]
    candidates.sort(
        key=lambda group: (
            min({"critical": 0, "high": 1, "normal": 2, "low": 3}[row["priority"]] for row in group),
            min(row["id"] for row in group),
        )
    )
    for group in candidates:
        if len(scheduled) >= limit:
            break
        pair = require_language_pair(group)
        if any(row["status"] != "review" for row in pair.values()):
            raise SchedulingError("both English and Korean articles must be in review before scheduling")
        if any(review_score(row, review_root) <= threshold for row in pair.values()):
            continue
        anchor = next_slot(anchor, interval_days, publication_time)
        for topic in pair.values():
            row = store.edit(topic["id"], {"status": "scheduled", "scheduled_at": anchor.isoformat()})
            scheduled.append(row)
    return scheduled


def main() -> int:
    parser = argparse.ArgumentParser(description="Schedule reviewed articles that score above the publication threshold")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    parser.add_argument("--legacy-topics", type=Path, default=LEGACY_TOPICS_PATH)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--interval-days", type=int, default=DEFAULT_INTERVAL_DAYS)
    parser.add_argument("--publication-time", default=DEFAULT_PUBLICATION_TIME)
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    try:
        rows = schedule_ready_articles(
            args.topics,
            args.review_root,
            args.legacy_topics,
            args.threshold,
            args.interval_days,
            args.publication_time,
            limit=args.limit,
        )
    except (SchedulingError, TopicError, OSError, json.JSONDecodeError) as error:
        print(f"scheduling failed: {error}", file=sys.stderr)
        return 1
    print(f"scheduled {len(rows)} article(s)")
    for row in rows:
        print(f"{row['id']} {row['scheduled_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
