#!/usr/bin/env python3
"""Validate generated social drafts before manual or API posting."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from publishing import DEFAULT_SOCIAL_OUTPUT_DIR, x_weighted_length


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = DEFAULT_SOCIAL_OUTPUT_DIR / "manifest.json"
PLACEHOLDER_RE = re.compile(r"\{\{[a-zA-Z0-9_]+\}\}")


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


def validate_post(post: dict[str, object], project_root: Path = ROOT) -> None:
    topic_id = require_string(post, "topic_id")
    platform = require_string(post, "platform")
    language = require_string(post, "language")
    draft_path = project_root / require_string(post, "draft_path")
    card_asset_path = project_root / require_string(post, "card_asset_path")
    canonical_url = require_string(post, "canonical_url")
    status = require_string(post, "status")
    template_id = require_string(post, "template_id")
    template_path = project_root / require_string(post, "template_path")

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
    if canonical_url not in text:
        raise SocialValidationError(f"{topic_id} draft does not include canonical URL: {draft_path}")
    if platform == "x" and x_weighted_length(text) > 280:
        raise SocialValidationError(f"{topic_id} X draft exceeds weighted length: {x_weighted_length(text)}")
    if platform == "bluesky" and len(text) > 300:
        raise SocialValidationError(f"{topic_id} Bluesky draft exceeds length: {len(text)}")
    if platform == "linkedin":
        cta = "전체 글 읽기:" if language == "ko" else "Read the full article:"
        if cta not in text:
            raise SocialValidationError(f"{topic_id} LinkedIn draft is missing CTA: {draft_path}")


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
