#!/usr/bin/env python3
"""Publish due scheduled articles after enforcing the review threshold."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from evaluate_article import DEFAULT_REVIEW_ROOT, DEFAULT_THRESHOLD
from schedule_ready_articles import grouped_by_publication, require_language_pair, review_score
from topic_management import DEFAULT_TOPICS_PATH, LEGACY_TOPICS_PATH, TOPIC_HEADER, TopicError, TopicStore, read_csv


KST = timezone(timedelta(hours=9))
DEFAULT_SITE_URL = "https://onnellab.github.io/"
DEFAULT_METADATA_ROOT = Path(__file__).resolve().parents[1] / "generated" / "metadata"


class DuePublicationError(ValueError):
    """Raised when a scheduled article cannot be published."""


def parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise DuePublicationError(f"invalid scheduled_at: {value}") from error


def public_url(site_url: str, topic: dict[str, str]) -> str:
    root = site_url if site_url.endswith("/") else site_url + "/"
    return f"{root}blog/{topic['primary_language']}/{topic['slug']}/"


def markdown_path(topic: dict[str, str], topics_path: Path) -> Path:
    if not topic["canonical_path"]:
        raise DuePublicationError(f"{topic['id']} has no canonical_path")
    path = topics_path.parent.parent / topic["canonical_path"]
    if not path.exists():
        raise DuePublicationError(f"{topic['id']} Markdown file does not exist: {topic['canonical_path']}")
    return path


def replace_frontmatter_value(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^({re.escape(key)}:\s*)\"?.*?\"?$", re.MULTILINE)
    replacement = rf'\1"{value}"'
    if pattern.search(content):
        return pattern.sub(replacement, content, count=1)
    end = content.find("\n---\n", 4)
    if end == -1:
        raise DuePublicationError("Markdown file has no frontmatter block")
    return content[:end] + f'\n{key}: "{value}"' + content[end:]


def metadata_path(topic: dict[str, str], metadata_root: Path) -> Path:
    return metadata_root / topic["primary_language"] / topic["category"] / topic["slug"] / "internal_links.json"


def public_related_article_value(topic: dict[str, str], metadata_root: Path) -> str:
    path = metadata_path(topic, metadata_root)
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[str] = []
    for item in data.get("recommendations", {}).get("related_articles", []):
        url = str(item.get("url", "")).strip()
        title = str(item.get("title", "")).strip()
        language = str(item.get("language", "")).strip()
        status = str(item.get("status", "")).strip()
        parsed = urlparse(url)
        if not title or language != topic["primary_language"] or status != "published":
            continue
        if not (url.startswith("/") or parsed.scheme in {"http", "https"}):
            continue
        items.append(f"{title} => {url}")
    return "|".join(items)


def update_markdown_publication_metadata(
    path: Path,
    topic: dict[str, str],
    site_url: str,
    published_at: str,
    metadata_root: Path = DEFAULT_METADATA_ROOT,
) -> None:
    content = path.read_text(encoding="utf-8")
    values = {
        "status": "published",
        "canonical_url": public_url(site_url, topic),
        "published_at": published_at,
        "updated_at": published_at,
    }
    related_articles = public_related_article_value(topic, metadata_root)
    if related_articles:
        values["related_articles"] = related_articles
    for key, value in values.items():
        content = replace_frontmatter_value(content, key, value)
    path.write_text(content, encoding="utf-8")


def publish_due_articles(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    review_root: Path = DEFAULT_REVIEW_ROOT,
    legacy_topics_path: Path | None = LEGACY_TOPICS_PATH,
    threshold: float = DEFAULT_THRESHOLD,
    site_url: str = DEFAULT_SITE_URL,
    now: datetime | None = None,
    limit: int = 1,
    metadata_root: Path = DEFAULT_METADATA_ROOT,
) -> list[dict[str, str]]:
    rows = read_csv(topics_path, TOPIC_HEADER)
    now = now or datetime.now(KST)
    store = TopicStore(topics_path, mirror_path=legacy_topics_path)
    published: list[dict[str, str]] = []
    due_groups = []
    for group in grouped_by_publication(rows).values():
        scheduled = [row for row in group if row["status"] == "scheduled"]
        if not scheduled:
            continue
        if any(parse_datetime(row["scheduled_at"]).astimezone(KST) <= now.astimezone(KST) for row in scheduled):
            due_groups.append(group)
    due_groups.sort(key=lambda group: (min(row["scheduled_at"] for row in group if row["status"] == "scheduled"), min(row["id"] for row in group)))

    for group in due_groups:
        if len(published) >= limit:
            break
        try:
            pair = require_language_pair(group)
        except ValueError as error:
            raise DuePublicationError(str(error)) from error
        if any(row["status"] != "scheduled" for row in pair.values()):
            raise DuePublicationError("both English and Korean articles must be scheduled before publishing")
        if any(parse_datetime(row["scheduled_at"]).astimezone(KST) > now.astimezone(KST) for row in pair.values()):
            continue
        for topic in pair.values():
            score = review_score(topic, review_root)
            if score <= threshold:
                raise DuePublicationError(f"{topic['id']} review score {score} does not exceed {threshold}")
        for topic in pair.values():
            published_at = topic["scheduled_at"]
            path = markdown_path(topic, topics_path)
            update_markdown_publication_metadata(path, topic, site_url, published_at, metadata_root)
            row = store.edit(
                topic["id"],
                {
                    "status": "published",
                    "published_url": public_url(site_url, topic),
                    "published_at": published_at,
                    "updated_at": published_at,
                },
            )
            published.append(row)
    return published


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish due scheduled articles that pass review")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    parser.add_argument("--legacy-topics", type=Path, default=LEGACY_TOPICS_PATH)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    try:
        rows = publish_due_articles(
            args.topics,
            args.review_root,
            args.legacy_topics,
            args.threshold,
            args.site_url,
            limit=args.limit,
        )
    except (DuePublicationError, TopicError, OSError, json.JSONDecodeError) as error:
        print(f"publish due articles failed: {error}", file=sys.stderr)
        return 1
    print(f"published {len(rows)} due article(s)")
    for row in rows:
        print(f"{row['id']} {row['published_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
