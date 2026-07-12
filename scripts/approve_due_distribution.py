#!/usr/bin/env python3
"""Approve due core distribution drafts on a staggered cadence."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from approve_social_post import project_root_for_manifest as social_project_root
from approve_social_post import write_manifest as write_social_manifest
from approve_syndication_draft import write_manifest as write_syndication_manifest
from evaluate_syndication_drafts import DEFAULT_MANIFEST_PATH as DEFAULT_SYNDICATION_MANIFEST
from topic_management import DEFAULT_TOPICS_PATH, TOPIC_HEADER, read_csv
from validate_social_posts import DEFAULT_MANIFEST_PATH as DEFAULT_SOCIAL_MANIFEST
from validate_social_posts import SocialValidationError, validate_social_posts
from validate_syndication_drafts import SyndicationValidationError
from validate_syndication_drafts import project_root_for_manifest as syndication_project_root
from validate_syndication_drafts import validate_syndication_drafts


KST = ZoneInfo("Asia/Seoul")
DEFAULT_APPROVED_BY = "automation"
AUTOMATION_LANGUAGES = {"en"}
SOCIAL_DELAYS_DAYS = {"x": 0, "bluesky": 1}
SYNDICATION_DELAYS_DAYS = {"devto": 2}


class DistributionApprovalError(ValueError):
    """Raised when distribution drafts cannot be approved."""


def load_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        raise DistributionApprovalError(f"manifest does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise DistributionApprovalError(f"invalid published_at: {value}") from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def published_topics(topics_path: Path, languages: set[str]) -> dict[str, dict[str, str]]:
    topics: dict[str, dict[str, str]] = {}
    for row in read_csv(topics_path, TOPIC_HEADER):
        if row["status"] != "published":
            continue
        if row["primary_language"] not in languages:
            continue
        if not row["published_at"]:
            continue
        topics[row["id"]] = row
    return topics


def is_due(topic: dict[str, str], delay_days: int, now: datetime) -> bool:
    published_at = parse_datetime(topic["published_at"])
    return now.astimezone(KST) >= published_at + timedelta(days=delay_days)


def approve_item(item: dict[str, object], approved_by: str, timestamp: str) -> None:
    item["status"] = "approved"
    item["approved_by"] = approved_by
    item["approved_at"] = timestamp
    item["error"] = ""
    item["error_type"] = ""
    item.setdefault("post_id", "")
    item.setdefault("posted_url", "")
    item.setdefault("posted_at", "")
    item.setdefault("last_attempt_at", "")
    item.setdefault("retry_count", 0)


def approve_due_social(
    social_manifest: Path,
    topics: dict[str, dict[str, str]],
    now: datetime,
    approved_by: str,
    dry_run: bool = False,
) -> list[dict[str, object]]:
    validate_social_posts(social_manifest, social_project_root(social_manifest))
    manifest = load_manifest(social_manifest)
    posts = manifest.get("posts")
    if not isinstance(posts, list):
        raise DistributionApprovalError("social manifest has no posts list")
    timestamp = now.astimezone(KST).replace(microsecond=0).isoformat()
    approved: list[dict[str, object]] = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        topic = topics.get(str(post.get("topic_id", "")))
        platform = str(post.get("platform", ""))
        if not topic or platform not in SOCIAL_DELAYS_DAYS:
            continue
        if post.get("language") not in AUTOMATION_LANGUAGES:
            continue
        if post.get("is_variant") is True or post.get("template_id") != platform:
            continue
        if post.get("status") != "draft":
            continue
        if not is_due(topic, SOCIAL_DELAYS_DAYS[platform], now):
            continue
        if not dry_run:
            approve_item(post, approved_by, timestamp)
        approved.append(post)
    if approved and not dry_run:
        write_social_manifest(social_manifest, manifest)
    return approved


def approve_due_syndication(
    syndication_manifest: Path,
    topics: dict[str, dict[str, str]],
    now: datetime,
    approved_by: str,
    dry_run: bool = False,
) -> list[dict[str, object]]:
    validate_syndication_drafts(syndication_manifest, syndication_project_root(syndication_manifest))
    manifest = load_manifest(syndication_manifest)
    drafts = manifest.get("drafts")
    if not isinstance(drafts, list):
        raise DistributionApprovalError("syndication manifest has no drafts list")
    timestamp = now.astimezone(KST).replace(microsecond=0).isoformat()
    approved: list[dict[str, object]] = []
    for draft in drafts:
        if not isinstance(draft, dict):
            continue
        topic = topics.get(str(draft.get("topic_id", "")))
        platform = str(draft.get("platform", ""))
        if not topic or platform not in SYNDICATION_DELAYS_DAYS:
            continue
        if draft.get("language") not in AUTOMATION_LANGUAGES:
            continue
        if draft.get("status") != "draft":
            continue
        if not is_due(topic, SYNDICATION_DELAYS_DAYS[platform], now):
            continue
        if not dry_run:
            approve_item(draft, approved_by, timestamp)
        approved.append(draft)
    if approved and not dry_run:
        write_syndication_manifest(syndication_manifest, manifest)
    return approved


def approve_due_distribution(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    social_manifest: Path = DEFAULT_SOCIAL_MANIFEST,
    syndication_manifest: Path = DEFAULT_SYNDICATION_MANIFEST,
    now: datetime | None = None,
    approved_by: str = DEFAULT_APPROVED_BY,
    dry_run: bool = False,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    current_time = now or datetime.now(KST)
    topics = published_topics(topics_path, AUTOMATION_LANGUAGES)
    social = approve_due_social(social_manifest, topics, current_time, approved_by, dry_run)
    syndication = approve_due_syndication(syndication_manifest, topics, current_time, approved_by, dry_run)
    return social, syndication


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve due core distribution drafts")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--social-manifest", type=Path, default=DEFAULT_SOCIAL_MANIFEST)
    parser.add_argument("--syndication-manifest", type=Path, default=DEFAULT_SYNDICATION_MANIFEST)
    parser.add_argument("--approved-by", default=DEFAULT_APPROVED_BY)
    parser.add_argument("--now", help="ISO-8601 datetime for deterministic runs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        now = parse_datetime(args.now) if args.now else None
        social, syndication = approve_due_distribution(
            args.topics,
            args.social_manifest,
            args.syndication_manifest,
            now,
            args.approved_by,
            args.dry_run,
        )
    except (
        DistributionApprovalError,
        SocialValidationError,
        SyndicationValidationError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(f"approve due distribution failed: {error}", file=sys.stderr)
        return 1
    action = "would approve" if args.dry_run else "approved"
    print(f"{action} {len(social)} social draft(s), {len(syndication)} syndication draft(s)")
    for post in social:
        print(f"social {post['topic_id']} {post['platform']} {post['language']}")
    for draft in syndication:
        print(f"syndication {draft['topic_id']} {draft['platform']} {draft['language']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
