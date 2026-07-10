#!/usr/bin/env python3
"""Topic CSV management utilities.

This module manages topic rows only. It does not generate articles, publish
content, or advance workflow stages beyond explicit topic status commands.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOPICS_PATH = ROOT / "data" / "topics.csv"
LEGACY_TOPICS_PATH = ROOT / "topics" / "topics.csv"
DEFAULT_APPS_PATH = ROOT / "data" / "apps_registry.csv"

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
BOOLEAN = {"true", "false"}

EDITABLE_FIELDS = set(TOPIC_HEADER) - {"id"}
REQUIRED_FIELDS = {
    "id",
    "status",
    "category",
    "primary_question",
    "working_title",
    "slug",
    "primary_language",
    "priority",
    "search_intent",
    "primary_keyword",
    "evergreen",
    "source_type",
    "review_required",
}

FORWARD_TRANSITIONS = {
    "idea": {"approved", "archived", "failed"},
    "approved": {"research", "failed"},
    "research": {"outline", "failed"},
    "outline": {"draft", "failed"},
    "draft": {"image_planning", "failed"},
    "image_planning": {"review", "failed"},
    "review": {"scheduled", "failed"},
    "scheduled": {"published", "failed"},
    "published": {"update_required", "archived", "failed"},
    "update_required": {"review", "failed"},
    "archived": set(),
    "failed": set(),
}

TOPIC_ID_RE = re.compile(r"^TOPIC-(\d{4})$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class TopicError(ValueError):
    """Raised when a topic management operation violates the specification."""


def read_csv(path: Path, header: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != header:
            raise TopicError(f"{path} header does not match the v1 specification")
        rows = list(reader)

    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise TopicError(f"{path} row {row_number} has too many columns")
        if any("\n" in value or "\r" in value for value in row.values()):
            raise TopicError(f"{path} row {row_number} contains a line break")
    return rows


def write_topics(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=TOPIC_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_app_names(apps_path: Path = DEFAULT_APPS_PATH) -> set[str]:
    return {row["app_name"] for row in read_csv(apps_path, APP_HEADER)}


def next_topic_id(rows: list[dict[str, str]]) -> str:
    highest = 0
    for row in rows:
        match = TOPIC_ID_RE.match(row["id"])
        if not match:
            raise TopicError(f"invalid topic id: {row['id']}")
        highest = max(highest, int(match.group(1)))
    return f"TOPIC-{highest + 1:04d}"


def validate_transition(current: str, target: str) -> None:
    if target == current:
        return
    if target not in FORWARD_TRANSITIONS.get(current, set()):
        raise TopicError(f"invalid status transition: {current} -> {target}")


def validate_row(row: dict[str, str], app_names: set[str]) -> None:
    topic_id = row["id"]
    for field in REQUIRED_FIELDS:
        if not row[field]:
            raise TopicError(f"{topic_id or '<missing topic id>'} has empty required field: {field}")
    if not TOPIC_ID_RE.match(topic_id):
        raise TopicError(f"invalid topic id: {topic_id}")
    if row["status"] not in TOPIC_STATUSES:
        raise TopicError(f"{topic_id} has unsupported status: {row['status']}")
    if row["category"] not in TOPIC_CATEGORIES:
        raise TopicError(f"{topic_id} has unsupported category: {row['category']}")
    if row["primary_language"] not in LANGUAGES:
        raise TopicError(f"{topic_id} has unsupported primary_language: {row['primary_language']}")
    if row["priority"] not in PRIORITIES:
        raise TopicError(f"{topic_id} has unsupported priority: {row['priority']}")
    if row["search_intent"] not in SEARCH_INTENTS:
        raise TopicError(f"{topic_id} has unsupported search_intent: {row['search_intent']}")
    if row["source_type"] not in SOURCE_TYPES:
        raise TopicError(f"{topic_id} has unsupported source_type: {row['source_type']}")
    if row["evergreen"] not in BOOLEAN:
        raise TopicError(f"{topic_id} has invalid evergreen: {row['evergreen']}")
    if row["review_required"] not in BOOLEAN:
        raise TopicError(f"{topic_id} has invalid review_required: {row['review_required']}")
    if not row["primary_question"].strip().endswith("?"):
        raise TopicError(f"{topic_id} primary_question must be a complete question")
    if row["primary_question"].split(maxsplit=1)[0] in app_names:
        raise TopicError(f"{topic_id} primary_question must not begin with an ONNELLAB product name")
    if not SLUG_RE.match(row["slug"]):
        raise TopicError(f"{topic_id} has invalid slug: {row['slug']}")
    if row["status"] == "published" and not row["published_url"]:
        raise TopicError(f"{topic_id} is published with no published_url")
    if row["status"] == "scheduled" and not row["scheduled_at"]:
        raise TopicError(f"{topic_id} is scheduled with no scheduled_at")
    if row["canonical_path"] and not row["canonical_path"].startswith("generated/markdown/"):
        raise TopicError(f"{topic_id} canonical_path must point under generated/markdown")
    for app_name in filter(None, row["related_apps"].split("|")):
        if app_name not in app_names:
            raise TopicError(f"{topic_id} references unknown app: {app_name}")


def validate_rows(rows: list[dict[str, str]], app_names: set[str]) -> None:
    seen_ids: set[str] = set()
    seen_slugs: set[tuple[str, str]] = set()
    for row in rows:
        validate_row(row, app_names)
        if row["id"] in seen_ids:
            raise TopicError(f"duplicated topic id: {row['id']}")
        language_slug = (row["primary_language"], row["slug"])
        if language_slug in seen_slugs:
            raise TopicError(f"duplicated topic slug within language: {row['slug']}")
        seen_ids.add(row["id"])
        seen_slugs.add(language_slug)


class TopicStore:
    def __init__(
        self,
        topics_path: Path = DEFAULT_TOPICS_PATH,
        apps_path: Path = DEFAULT_APPS_PATH,
        mirror_path: Path | None = LEGACY_TOPICS_PATH,
    ) -> None:
        self.topics_path = topics_path
        self.apps_path = apps_path
        self.mirror_path = mirror_path

    def read(self) -> list[dict[str, str]]:
        return read_csv(self.topics_path, TOPIC_HEADER)

    def write(self, rows: list[dict[str, str]]) -> None:
        app_names = load_app_names(self.apps_path)
        validate_rows(rows, app_names)
        write_topics(self.topics_path, rows)
        if self.mirror_path is not None:
            write_topics(self.mirror_path, rows)

    def add(self, fields: dict[str, str]) -> dict[str, str]:
        rows = self.read()
        if "id" in fields and fields["id"]:
            raise TopicError("topic IDs are generated automatically and must not be provided")

        row = {field: "" for field in TOPIC_HEADER}
        row.update(fields)
        row["id"] = next_topic_id(rows)
        row["status"] = "idea"
        row.setdefault("review_required", "true")
        if not row["review_required"]:
            row["review_required"] = "true"

        self.write(rows + [row])
        return row

    def edit(self, topic_id: str, fields: dict[str, str]) -> dict[str, str]:
        if not fields:
            raise TopicError("no edit fields provided")
        unknown = set(fields) - EDITABLE_FIELDS
        if unknown:
            raise TopicError("unsupported edit field(s): " + ", ".join(sorted(unknown)))

        rows = self.read()
        for row in rows:
            if row["id"] == topic_id:
                if "status" in fields:
                    validate_transition(row["status"], fields["status"])
                row.update(fields)
                self.write(rows)
                return row
        raise TopicError(f"topic not found: {topic_id}")

    def approve(self, topic_id: str) -> dict[str, str]:
        return self.edit(topic_id, {"status": "approved"})

    def archive(self, topic_id: str) -> dict[str, str]:
        return self.edit(topic_id, {"status": "archived"})
