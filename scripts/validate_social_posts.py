#!/usr/bin/env python3
"""Validate generated social drafts before manual or API posting."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from publishing import DEFAULT_SOCIAL_OUTPUT_DIR, x_weighted_length


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = DEFAULT_SOCIAL_OUTPUT_DIR / "manifest.json"
PLACEHOLDER_RE = re.compile(r"\{\{[a-zA-Z0-9_]+\}\}")
ELLIPSIS_RE = re.compile(r"\.{3}|…")


class SocialValidationError(ValueError):
    """Raised when generated social drafts fail validation."""


def require_string(post: dict[str, object], field: str) -> str:
    value = post.get(field)
    if not isinstance(value, str):
        raise SocialValidationError(f"post has invalid {field}: {value!r}")
    return value


def require_int(post: dict[str, object], field: str) -> int:
    value = post.get(field)
    if not isinstance(value, int):
        raise SocialValidationError(f"post has invalid {field}: {value!r}")
    return value


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise SocialValidationError(f"card asset is not a valid PNG: {path}")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def expected_link_policy(
    post: dict[str, object], project_root: Path
) -> tuple[str, str, str, str]:
    topic_id = require_string(post, "topic_id")
    platform = require_string(post, "platform")
    language = require_string(post, "language")
    canonical_url = require_string(post, "canonical_url")
    topics_path = project_root / "data" / "topics.csv"
    apps_path = project_root / "data" / "apps_registry.csv"
    if not topics_path.exists():
        raise SocialValidationError(f"{topic_id} cannot verify link policy without {topics_path}")
    with topics_path.open(encoding="utf-8", newline="") as handle:
        topic = next((row for row in csv.DictReader(handle) if row.get("id") == topic_id), None)
    if topic is None:
        raise SocialValidationError(f"{topic_id} is missing from topics registry")

    registry: dict[str, dict[str, str]] = {}
    if apps_path.exists():
        with apps_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                for key in (row.get("app_name", ""), row.get("slug", "")):
                    if key.strip():
                        registry[key.strip().casefold()] = row
    app: dict[str, str] | None = None
    related_name = ""
    for name in (part.strip() for part in topic.get("related_apps", "").split("|")):
        candidate = registry.get(name.casefold())
        if candidate and (candidate.get("app_store_url", "").strip() or candidate.get("play_store_url", "").strip()):
            app = candidate
            related_name = name
            break
    if platform in {"x", "bluesky"} and app is not None:
        app_store_url = app.get("app_store_url", "").strip()
        play_store_url = app.get("play_store_url", "").strip()
        destinations = "|".join(filter(None, (app_store_url, play_store_url)))
        app_name = app.get("app_name", "").strip() or related_name
        cta = f"{app_name} 설치:" if language == "ko" else f"Install {app_name}:"
        return "store_install", app_store_url or play_store_url, destinations, cta
    cta = "전체 글 읽기:" if language == "ko" else "Read the full article:"
    return "canonical_article", canonical_url, "", cta


def validate_post(post: dict[str, object], project_root: Path = ROOT) -> None:
    topic_id = require_string(post, "topic_id")
    platform = require_string(post, "platform")
    language = require_string(post, "language")
    draft_path = project_root / require_string(post, "draft_path")
    card_asset_path = project_root / require_string(post, "card_asset_path")
    canonical_url = require_string(post, "canonical_url")
    target_url = require_string(post, "target_url")
    destination_urls = require_string(post, "destination_urls")
    link_strategy = require_string(post, "link_strategy")
    cta = require_string(post, "cta_text")
    status = require_string(post, "status")
    template_id = require_string(post, "template_id")
    template_path = project_root / require_string(post, "template_path")
    weighted_length = require_int(post, "weighted_length")

    if platform not in {"x", "linkedin", "bluesky"}:
        raise SocialValidationError(f"{topic_id} has unsupported platform: {platform}")
    if language not in {"en", "ko"}:
        raise SocialValidationError(f"{topic_id} has unsupported language: {language}")
    if status not in {"draft", "variant", "approved", "posted", "failed"}:
        raise SocialValidationError(f"{topic_id} has unsupported social status: {status}")
    if status == "variant" and not post.get("is_variant"):
        raise SocialValidationError(f"{topic_id} has variant status without is_variant")
    if status == "draft" and post.get("is_variant") is True:
        raise SocialValidationError(f"{topic_id} variant must not use draft status")
    if not template_id:
        raise SocialValidationError(f"{topic_id} has empty template_id")
    if not template_path.exists():
        raise SocialValidationError(f"{topic_id} template does not exist: {template_path}")
    if not canonical_url.startswith(("http://", "https://")):
        raise SocialValidationError(f"{topic_id} has invalid canonical_url: {canonical_url}")
    if not target_url.startswith(("http://", "https://")):
        raise SocialValidationError(f"{topic_id} has invalid target_url: {target_url}")
    if link_strategy not in {"canonical_article", "store_install"}:
        raise SocialValidationError(f"{topic_id} has invalid link_strategy: {link_strategy}")
    destinations = [url for url in destination_urls.split("|") if url]
    if any(not url.startswith(("http://", "https://")) for url in destinations):
        raise SocialValidationError(f"{topic_id} has invalid destination_urls: {destination_urls}")
    if link_strategy == "canonical_article" and (target_url != canonical_url or destination_urls):
        raise SocialValidationError(f"{topic_id} canonical target metadata is internally inconsistent")
    if link_strategy == "store_install" and (not destinations or target_url not in destinations):
        raise SocialValidationError(f"{topic_id} store target metadata is internally inconsistent")
    if weighted_length < 0:
        raise SocialValidationError(f"{topic_id} has negative weighted_length")
    if not draft_path.exists():
        raise SocialValidationError(f"{topic_id} draft does not exist: {draft_path}")
    if not card_asset_path.exists():
        raise SocialValidationError(f"{topic_id} card asset does not exist: {card_asset_path}")
    if card_asset_path.suffix != ".png":
        raise SocialValidationError(f"{topic_id} card asset must be PNG: {card_asset_path}")
    if card_asset_path.stat().st_size < 10_000:
        raise SocialValidationError(f"{topic_id} card asset is unexpectedly small: {card_asset_path}")
    if png_size(card_asset_path) != (1200, 630):
        raise SocialValidationError(f"{topic_id} card asset must be 1200x630: {card_asset_path}")
    for metric in ["retry_count", "impressions", "clicks", "engagements"]:
        if require_int(post, metric) < 0:
            raise SocialValidationError(f"{topic_id} has negative {metric}")

    text = draft_path.read_text(encoding="utf-8").strip()
    if not text:
        raise SocialValidationError(f"{topic_id} draft is empty: {draft_path}")
    if PLACEHOLDER_RE.search(text):
        raise SocialValidationError(f"{topic_id} draft has unresolved placeholder: {draft_path}")
    if status == "posted":
        return
    if ELLIPSIS_RE.search(text):
        raise SocialValidationError(f"{topic_id} unposted draft contains an ellipsis: {draft_path}")
    expected_strategy, expected_target, expected_destinations, expected_cta = expected_link_policy(post, project_root)
    if link_strategy != expected_strategy:
        raise SocialValidationError(
            f"{topic_id} has incorrect {platform} link strategy: {link_strategy}; expected {expected_strategy}"
        )
    if target_url != expected_target:
        raise SocialValidationError(f"{topic_id} has incorrect target URL for {expected_strategy}: {target_url}")
    if destination_urls != expected_destinations:
        raise SocialValidationError(f"{topic_id} has incorrect destination URLs for {expected_strategy}")
    if cta != expected_cta:
        raise SocialValidationError(f"{topic_id} has incorrect CTA for {expected_strategy}: {cta}")
    if target_url not in text:
        raise SocialValidationError(f"{topic_id} draft does not include its target URL: {draft_path}")
    if cta not in text:
        raise SocialValidationError(f"{topic_id} draft is missing its CTA: {draft_path}")
    for destination_url in filter(None, destination_urls.split("|")):
        if destination_url not in text:
            raise SocialValidationError(f"{topic_id} draft is missing destination URL: {destination_url}")
    if platform == "x" and x_weighted_length(text) > 240:
        raise SocialValidationError(f"{topic_id} X draft exceeds weighted length: {x_weighted_length(text)}")
    if platform == "bluesky" and len(text) > 260:
        raise SocialValidationError(f"{topic_id} Bluesky draft exceeds length: {len(text)}")
    if platform == "linkedin" and len(text) > 900:
        raise SocialValidationError(f"{topic_id} LinkedIn draft exceeds length: {len(text)}")


def validate_social_posts(manifest_path: Path = DEFAULT_MANIFEST_PATH, project_root: Path = ROOT) -> int:
    if not manifest_path.exists():
        raise SocialValidationError(f"social manifest does not exist: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    posts = manifest.get("posts")
    if not isinstance(posts, list) or not posts:
        raise SocialValidationError("social manifest has no posts")
    for post in posts:
        if not isinstance(post, dict):
            raise SocialValidationError(f"invalid post entry: {post!r}")
        validate_post(post, project_root)
    return len(posts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated social drafts")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    args = parser.parse_args()
    try:
        count = validate_social_posts(args.manifest)
    except (SocialValidationError, OSError, json.JSONDecodeError) as error:
        print(f"social validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {count} social draft(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
