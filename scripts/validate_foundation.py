#!/usr/bin/env python3
"""Validate the v1 repository foundation before content generation exists."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "CODEX.md",
    "README.md",
    "docs/Workflow.md",
    "docs/Content_Guide.md",
    "docs/SEO_Guide.md",
    "docs/AEO_Guide.md",
    "docs/GEO_Guide.md",
    "docs/Image_Guide.md",
    "docs/Publishing_Guide.md",
    "docs/GitHub_Actions.md",
    "docs/Topic_Guide.md",
    "docs/Knowledge_Graph.md",
    "docs/topics.csv",
    "docs/apps_registry.csv",
    "topics/topics.csv",
    "topics/reading.csv",
    "topics/music.csv",
    "topics/productivity.csv",
    "topics/media.csv",
    "topics/craft.csv",
    "topics/games.csv",
    "topics/research.csv",
    "templates/blog",
    "templates/social",
    "templates/newsletter",
    "generated/markdown",
    "generated/html",
    "generated/images",
    "generated/metadata",
    "generated/social",
    "scripts",
    ".github/workflows",
    "archive",
    "data/apps_registry.csv",
    "data/topics.csv",
    "scripts/validate_apps_registry.py",
    "scripts/validate_topics.py",
    "generated/markdown/en/reading",
    "generated/markdown/en/music",
    "generated/markdown/en/productivity",
    "generated/markdown/en/media",
    "generated/markdown/en/craft",
    "generated/markdown/en/games",
    "generated/markdown/en/research",
    "generated/markdown/ko/reading",
    "generated/markdown/ko/music",
    "generated/markdown/ko/productivity",
    "generated/markdown/ko/media",
    "generated/markdown/ko/craft",
    "generated/markdown/ko/games",
    "generated/markdown/ko/research",
]

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

TOPIC_STATUSES = {
    "idea",
    "approved",
    "research",
    "outline",
    "draft",
    "image_planning",
    "review",
    "scheduled",
    "published",
    "update_required",
    "archived",
    "failed",
}
TOPIC_CATEGORIES = {"reading", "music", "productivity", "media", "craft", "games", "research"}
LANGUAGES = {"en", "ko"}
PRIORITIES = {"critical", "high", "normal", "low"}
SEARCH_INTENTS = {"learn", "solve", "compare", "workflow", "discover", "troubleshoot"}
SOURCE_TYPES = {
    "user_question",
    "faq",
    "product_documentation",
    "support_issue",
    "feature_request",
    "search_research",
    "community_discussion",
    "editorial",
    "release_note",
}

APP_STATUSES = {"concept", "planning", "development", "beta", "released", "paused", "retired"}
PRODUCT_GROUPS = {"apps", "games", "fonts", "research", "internal"}
APP_CATEGORIES = TOPIC_CATEGORIES | {"internal"}
PLATFORMS = {"ios", "android", "windows", "macos", "web", "linux", "steam"}
PRICING_MODELS = {
    "free",
    "paid",
    "freemium",
    "one_time_purchase",
    "subscription",
    "not_applicable",
    "undecided",
}

TOPIC_ID_RE = re.compile(r"^TOPIC-\d{4}$")
APP_ID_RE = re.compile(r"^APP-\d{4}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}$")


def load_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != expected_header:
            raise ValueError(f"{path.relative_to(ROOT)} header mismatch")
        rows = list(reader)

    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise ValueError(f"{path.relative_to(ROOT)} row {row_number} has too many columns")
        if any("\n" in value or "\r" in value for value in row.values()):
            raise ValueError(f"{path.relative_to(ROOT)} row {row_number} contains a line break")

    return rows


def validate_url(value: str, field: str, row_id: str) -> None:
    if not value:
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{row_id} has malformed {field}: {value}")


def validate_paths() -> None:
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).exists()]
    if missing:
        raise ValueError("missing required paths: " + ", ".join(missing))


def validate_apps() -> dict[str, dict[str, str]]:
    rows = load_csv(ROOT / "data/apps_registry.csv", APP_HEADER)
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    seen_slugs: set[str] = set()
    by_name: dict[str, dict[str, str]] = {}

    for row in rows:
        app_id = row["app_id"]
        app_name = row["app_name"]
        slug = row["slug"]

        if not APP_ID_RE.match(app_id):
            raise ValueError(f"invalid app_id: {app_id}")
        if app_id in seen_ids:
            raise ValueError(f"duplicated app_id: {app_id}")
        if app_name in seen_names:
            raise ValueError(f"duplicated app_name: {app_name}")
        if slug in seen_slugs:
            raise ValueError(f"duplicated app slug: {slug}")
        if not SLUG_RE.match(slug):
            raise ValueError(f"{app_id} has invalid slug: {slug}")
        if row["status"] not in APP_STATUSES:
            raise ValueError(f"{app_id} has unsupported status: {row['status']}")
        if row["product_group"] not in PRODUCT_GROUPS:
            raise ValueError(f"{app_id} has unsupported product_group: {row['product_group']}")
        if row["primary_category"] not in APP_CATEGORIES:
            raise ValueError(f"{app_id} has unsupported primary_category: {row['primary_category']}")
        if row["pricing_model"] not in PRICING_MODELS:
            raise ValueError(f"{app_id} has unsupported pricing_model: {row['pricing_model']}")
        if row["content_eligible"] not in {"true", "false"}:
            raise ValueError(f"{app_id} has invalid content_eligible: {row['content_eligible']}")
        if row["primary_language"] not in LANGUAGES:
            raise ValueError(f"{app_id} has unsupported primary_language: {row['primary_language']}")
        for platform in row["platforms"].split("|"):
            if platform not in PLATFORMS:
                raise ValueError(f"{app_id} has unsupported platform: {platform}")
        if row["status"] == "released" and row["content_eligible"] == "true" and not row["official_site_path"]:
            raise ValueError(f"{app_id} is released and eligible but has no official_site_path")
        if row["official_site_path"] and not row["official_site_path"].startswith("/"):
            raise ValueError(f"{app_id} official_site_path must be site-relative")
        validate_url(row["app_store_url"], "app_store_url", app_id)
        validate_url(row["play_store_url"], "play_store_url", app_id)

        seen_ids.add(app_id)
        seen_names.add(app_name)
        seen_slugs.add(slug)
        by_name[app_name] = row

    return by_name


def validate_topic_file(path: Path, apps: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    rows = load_csv(path, TOPIC_HEADER)
    seen_ids: set[str] = set()
    seen_language_slugs: set[tuple[str, str]] = set()

    for row in rows:
        topic_id = row["id"]
        if not TOPIC_ID_RE.match(topic_id):
            raise ValueError(f"invalid topic id in {path.relative_to(ROOT)}: {topic_id}")
        if topic_id in seen_ids:
            raise ValueError(f"duplicated topic id in {path.relative_to(ROOT)}: {topic_id}")
        for field in ["status", "category", "primary_question", "working_title", "slug", "primary_language", "priority", "search_intent", "primary_keyword", "evergreen", "source_type", "review_required"]:
            if not row[field]:
                raise ValueError(f"{topic_id} has empty required field: {field}")
        if row["status"] not in TOPIC_STATUSES:
            raise ValueError(f"{topic_id} has unsupported status: {row['status']}")
        if row["category"] not in TOPIC_CATEGORIES:
            raise ValueError(f"{topic_id} has unsupported category: {row['category']}")
        if row["primary_language"] not in LANGUAGES:
            raise ValueError(f"{topic_id} has unsupported primary_language: {row['primary_language']}")
        if row["priority"] not in PRIORITIES:
            raise ValueError(f"{topic_id} has unsupported priority: {row['priority']}")
        if row["search_intent"] not in SEARCH_INTENTS:
            raise ValueError(f"{topic_id} has unsupported search_intent: {row['search_intent']}")
        if row["source_type"] not in SOURCE_TYPES:
            raise ValueError(f"{topic_id} has unsupported source_type: {row['source_type']}")
        if row["evergreen"] not in {"true", "false"}:
            raise ValueError(f"{topic_id} has invalid evergreen: {row['evergreen']}")
        if row["review_required"] not in {"true", "false"}:
            raise ValueError(f"{topic_id} has invalid review_required: {row['review_required']}")
        if not SLUG_RE.match(row["slug"]):
            raise ValueError(f"{topic_id} has invalid slug: {row['slug']}")
        language_slug = (row["primary_language"], row["slug"])
        if language_slug in seen_language_slugs:
            raise ValueError(f"duplicated slug within language in {path.relative_to(ROOT)}: {row['slug']}")
        if row["status"] == "published" and not row["published_url"]:
            raise ValueError(f"{topic_id} is published with no published_url")
        if row["status"] == "scheduled" and not row["scheduled_at"]:
            raise ValueError(f"{topic_id} is scheduled with no scheduled_at")
        for field in ["scheduled_at", "published_at", "updated_at"]:
            if row[field] and not DATETIME_RE.match(row[field]):
                raise ValueError(f"{topic_id} has invalid {field}: {row[field]}")
        for app_name in filter(None, row["related_apps"].split("|")):
            if app_name not in apps:
                raise ValueError(f"{topic_id} references unknown app: {app_name}")

        seen_ids.add(topic_id)
        seen_language_slugs.add(language_slug)

    return rows


def validate_topics(apps: dict[str, dict[str, str]]) -> None:
    data_rows = validate_topic_file(ROOT / "data/topics.csv", apps)
    legacy_rows = validate_topic_file(ROOT / "topics/topics.csv", apps)
    canonical_ids = {row["id"] for row in data_rows}

    if data_rows != legacy_rows:
        raise ValueError("data/topics.csv and topics/topics.csv must remain identical during v1 foundation setup")

    for category in sorted(TOPIC_CATEGORIES):
        path = ROOT / "topics" / f"{category}.csv"
        rows = validate_topic_file(path, apps)
        for row in rows:
            if row["category"] != category:
                raise ValueError(f"{path.relative_to(ROOT)} contains non-{category} topic {row['id']}")
            if row["id"] not in canonical_ids:
                raise ValueError(f"{path.relative_to(ROOT)} topic {row['id']} is missing from topics/topics.csv")


def main() -> int:
    try:
        validate_paths()
        apps = validate_apps()
        validate_topics(apps)
    except ValueError as error:
        print(f"foundation validation failed: {error}", file=sys.stderr)
        return 1

    print("foundation validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
