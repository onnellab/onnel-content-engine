#!/usr/bin/env python3
"""Validate data/topics.csv against the Topic Database Specification."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
TOPICS_PATH = ROOT / "data" / "topics.csv"
APPS_PATH = ROOT / "data" / "apps_registry.csv"

TOPIC_HEADER = [
    "id",
    "status",
    "category",
    "primary_question",
    "working_title",
    "slug",
    "primary_language",
    "priority",
    "search_intent",
    "related_apps",
    "primary_keyword",
    "secondary_keywords",
    "evergreen",
    "source_type",
    "canonical_path",
    "published_url",
    "scheduled_at",
    "published_at",
    "updated_at",
    "review_required",
    "notes",
]

APP_HEADER = [
    "app_id",
    "app_name",
    "slug",
    "status",
    "product_group",
    "primary_category",
    "platforms",
    "pricing_model",
    "content_eligible",
    "official_site_path",
    "app_store_url",
    "play_store_url",
    "docs_path",
    "one_line_description",
    "primary_language",
    "notes",
]

STATUSES = {"idea", "approved", "research", "outline", "draft", "image_planning", "review", "scheduled", "published", "update_required", "archived", "failed"}
CATEGORIES = {"reading", "music", "productivity", "media", "craft", "games", "research"}
LANGUAGES = {"en", "ko"}
PRIORITIES = {"critical", "high", "normal", "low"}
SEARCH_INTENTS = {"learn", "solve", "compare", "workflow", "discover", "troubleshoot"}
SOURCE_TYPES = {"user_question", "faq", "product_documentation", "support_issue", "feature_request", "search_research", "community_discussion", "editorial", "release_note"}
BOOLEAN = {"true", "false"}

TOPIC_ID_RE = re.compile(r"^TOPIC-\d{4}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}$")


def read_csv(path: Path, header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != header:
            raise ValueError(f"{path.relative_to(ROOT)} header does not match the v1 specification")
        rows = list(reader)

    for line_number, row in enumerate(rows, start=2):
        if None in row:
            raise ValueError(f"{path.relative_to(ROOT)} line {line_number} has too many columns")
        if any("\n" in value or "\r" in value for value in row.values()):
            raise ValueError(f"{path.relative_to(ROOT)} line {line_number} contains a line break inside a field")
    return rows


def app_names() -> set[str]:
    return {row["app_name"] for row in read_csv(APPS_PATH, APP_HEADER)}


def validate_url(value: str, field: str, topic_id: str) -> None:
    if not value:
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{topic_id} has malformed {field}: {value}")


def validate_datetime(value: str, field: str, topic_id: str) -> None:
    if value and not DATETIME_RE.match(value):
        raise ValueError(f"{topic_id} has invalid {field}: {value}")


def validate_topics() -> None:
    apps = app_names()
    rows = read_csv(TOPICS_PATH, TOPIC_HEADER)
    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    seen_intents: set[tuple[str, str, str, str]] = set()

    for row in rows:
        topic_id = row["id"]
        for field in ["id", "status", "category", "primary_question", "working_title", "slug", "primary_language", "priority", "search_intent", "primary_keyword", "evergreen", "source_type", "review_required"]:
            if not row[field]:
                raise ValueError(f"{topic_id or '<missing topic id>'} has empty required field: {field}")

        if not TOPIC_ID_RE.match(topic_id):
            raise ValueError(f"invalid topic id: {topic_id}")
        if topic_id in seen_ids:
            raise ValueError(f"duplicated topic id: {topic_id}")
        if row["status"] not in STATUSES:
            raise ValueError(f"{topic_id} has unsupported status: {row['status']}")
        if row["category"] not in CATEGORIES:
            raise ValueError(f"{topic_id} has unsupported category: {row['category']}")
        if row["primary_language"] not in LANGUAGES:
            raise ValueError(f"{topic_id} has unsupported primary_language: {row['primary_language']}")
        if row["priority"] not in PRIORITIES:
            raise ValueError(f"{topic_id} has unsupported priority: {row['priority']}")
        if row["search_intent"] not in SEARCH_INTENTS:
            raise ValueError(f"{topic_id} has unsupported search_intent: {row['search_intent']}")
        if row["source_type"] not in SOURCE_TYPES:
            raise ValueError(f"{topic_id} has unsupported source_type: {row['source_type']}")
        if row["evergreen"] not in BOOLEAN:
            raise ValueError(f"{topic_id} has invalid evergreen: {row['evergreen']}")
        if row["review_required"] not in BOOLEAN:
            raise ValueError(f"{topic_id} has invalid review_required: {row['review_required']}")
        if not row["primary_question"].strip().endswith("?"):
            raise ValueError(f"{topic_id} primary_question must be a complete question")
        if row["primary_question"].split(maxsplit=1)[0] in apps:
            raise ValueError(f"{topic_id} primary_question must not begin with an ONNELLAB product name")
        if not SLUG_RE.match(row["slug"]):
            raise ValueError(f"{topic_id} has invalid slug: {row['slug']}")
        if row["slug"] in seen_slugs:
            raise ValueError(f"{topic_id} duplicates slug: {row['slug']}")
        if row["status"] == "published" and not row["published_url"]:
            raise ValueError(f"{topic_id} is published with no published_url")
        if row["status"] == "scheduled" and not row["scheduled_at"]:
            raise ValueError(f"{topic_id} is scheduled with no scheduled_at")
        validate_url(row["published_url"], "published_url", topic_id)
        for field in ["scheduled_at", "published_at", "updated_at"]:
            validate_datetime(row[field], field, topic_id)
        if row["canonical_path"] and not row["canonical_path"].startswith("generated/markdown/"):
            raise ValueError(f"{topic_id} canonical_path must point under generated/markdown")
        for app_name in filter(None, row["related_apps"].split("|")):
            if app_name not in apps:
                raise ValueError(f"{topic_id} references unknown app: {app_name}")

        intent_key = (
            row["primary_language"],
            row["primary_question"].strip().lower(),
            row["working_title"].strip().lower(),
            row["primary_keyword"].strip().lower(),
        )
        if intent_key in seen_intents:
            raise ValueError(f"{topic_id} duplicates an existing topic intent")

        seen_ids.add(topic_id)
        seen_slugs.add(row["slug"])
        seen_intents.add(intent_key)


def main() -> int:
    try:
        validate_topics()
    except ValueError as error:
        print(f"topics validation failed: {error}", file=sys.stderr)
        return 1
    print("topics validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
