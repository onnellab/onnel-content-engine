#!/usr/bin/env python3
"""Validate data/apps_registry.csv against the Application Registry Specification."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
APPS_PATH = ROOT / "data" / "apps_registry.csv"
TOPICS_PATH = ROOT / "data" / "topics.csv"

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

APP_STATUSES = {"concept", "planning", "development", "beta", "released", "paused", "retired"}
PRODUCT_GROUPS = {"apps", "games", "fonts", "research", "internal"}
APP_CATEGORIES = {"reading", "music", "productivity", "media", "craft", "games", "research", "internal"}
PLATFORMS = {"ios", "android", "windows", "macos", "web", "linux", "steam"}
PRICING_MODELS = {"free", "paid", "freemium", "one_time_purchase", "subscription", "not_applicable", "undecided"}
LANGUAGES = {"en", "ko"}
BOOLEAN = {"true", "false"}

APP_ID_RE = re.compile(r"^APP-\d{4}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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


def require(value: str, field: str, app_id: str) -> None:
    if not value:
        raise ValueError(f"{app_id} has empty required field: {field}")


def validate_store_url(value: str, field: str, app_id: str) -> None:
    if not value:
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{app_id} has malformed {field}: {value}")


def validate_registry() -> dict[str, dict[str, str]]:
    rows = read_csv(APPS_PATH, APP_HEADER)
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    seen_slugs: set[str] = set()
    by_name: dict[str, dict[str, str]] = {}

    for row in rows:
        app_id = row["app_id"]
        for field in APP_HEADER:
            if field in {"app_store_url", "play_store_url", "notes"}:
                continue
            require(row[field], field, app_id or "<missing app_id>")

        if not APP_ID_RE.match(app_id):
            raise ValueError(f"invalid app_id: {app_id}")
        if app_id in seen_ids:
            raise ValueError(f"duplicated app_id: {app_id}")
        if row["app_name"] in seen_names:
            raise ValueError(f"duplicated app_name: {row['app_name']}")
        if row["slug"] in seen_slugs:
            raise ValueError(f"duplicated slug: {row['slug']}")
        if not SLUG_RE.match(row["slug"]):
            raise ValueError(f"{app_id} has invalid slug: {row['slug']}")
        if row["status"] not in APP_STATUSES:
            raise ValueError(f"{app_id} has unsupported status: {row['status']}")
        if row["product_group"] not in PRODUCT_GROUPS:
            raise ValueError(f"{app_id} has unsupported product_group: {row['product_group']}")
        if row["primary_category"] not in APP_CATEGORIES:
            raise ValueError(f"{app_id} has unsupported primary_category: {row['primary_category']}")
        if row["pricing_model"] not in PRICING_MODELS:
            raise ValueError(f"{app_id} has unsupported pricing_model: {row['pricing_model']}")
        if row["content_eligible"] not in BOOLEAN:
            raise ValueError(f"{app_id} has invalid content_eligible: {row['content_eligible']}")
        if row["primary_language"] not in LANGUAGES:
            raise ValueError(f"{app_id} has unsupported primary_language: {row['primary_language']}")
        for platform in row["platforms"].split("|"):
            if platform not in PLATFORMS:
                raise ValueError(f"{app_id} has unsupported platform: {platform}")
        if row["status"] == "released" and row["content_eligible"] == "true" and not row["official_site_path"]:
            raise ValueError(f"{app_id} is released and content-eligible without official_site_path")
        if row["official_site_path"] and not row["official_site_path"].startswith("/"):
            raise ValueError(f"{app_id} official_site_path must be site-relative")
        if row["docs_path"] and not (ROOT / row["docs_path"]).exists():
            raise ValueError(f"{app_id} docs_path does not exist: {row['docs_path']}")
        if len([sentence for sentence in row["one_line_description"].split(".") if sentence.strip()]) != 1:
            raise ValueError(f"{app_id} one_line_description must be one sentence")
        validate_store_url(row["app_store_url"], "app_store_url", app_id)
        validate_store_url(row["play_store_url"], "play_store_url", app_id)

        if row["status"] in {"concept", "planning", "development", "retired"} and row["content_eligible"] == "true":
            raise ValueError(f"{app_id} is not publicly recommendable but content_eligible is true")

        seen_ids.add(app_id)
        seen_names.add(row["app_name"])
        seen_slugs.add(row["slug"])
        by_name[row["app_name"]] = row

    return by_name


def validate_topic_references(app_names: set[str]) -> None:
    if not TOPICS_PATH.exists():
        return
    rows = read_csv(TOPICS_PATH, TOPIC_HEADER)
    for row in rows:
        for app_name in filter(None, row["related_apps"].split("|")):
            if app_name not in app_names:
                raise ValueError(f"{row['id']} references app not found in registry: {app_name}")


def main() -> int:
    try:
        apps = validate_registry()
        validate_topic_references(set(apps))
    except ValueError as error:
        print(f"apps registry validation failed: {error}", file=sys.stderr)
        return 1
    print("apps registry validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
