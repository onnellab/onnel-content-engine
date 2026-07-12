#!/usr/bin/env python3
"""Generate long-form syndication drafts from canonical published Markdown."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urljoin

from publishing import DEFAULT_SITE_URL, PublishingError, article_public_url, load_publishable_articles, normalize_site_url, parse_front_matter
from topic_management import DEFAULT_TOPICS_PATH, TopicError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_DIR = ROOT / "templates" / "syndication"
DEFAULT_OUTPUT_DIR = ROOT / "generated" / "syndication"
PLATFORMS = ("devto", "hashnode", "medium")
PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


class SyndicationError(ValueError):
    """Raised when syndication drafts cannot be generated."""


def render_template(template: str, context: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise SyndicationError(f"unknown syndication template placeholder: {key}")
        return context[key]

    return PLACEHOLDER_RE.sub(replace, template).strip() + "\n"


def normalize_tag(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z가-힣]+", "-", value.strip().lower())
    value = value.strip("-")
    return value[:30]


def tag_list(metadata: dict[str, str], topic: dict[str, str]) -> str:
    tags = metadata.get("tags") or topic["primary_keyword"]
    normalized: list[str] = []
    for tag in tags.split("|"):
        value = normalize_tag(tag)
        if value and value not in normalized:
            normalized.append(value)
        if len(normalized) >= 4:
            break
    return ",".join(normalized)


def social_card_url(site_url: str, topic: dict[str, str]) -> str:
    return urljoin(normalize_site_url(site_url), f"blog-assets/{topic['primary_language']}/{topic['slug']}/social-card.png")


def generate_syndication_drafts(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    site_url: str = DEFAULT_SITE_URL,
    platforms: tuple[str, ...] = PLATFORMS,
) -> list[dict[str, object]]:
    site_url = normalize_site_url(site_url)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    project_root = topics_path.parent.parent
    articles = load_publishable_articles(topics_path, project_root / ".syndication-export-check", site_url)
    manifest: list[dict[str, object]] = []
    for article in articles:
        markdown = article.markdown_path.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(markdown)
        canonical_url = article_public_url(article, site_url)
        context = {
            "title": article.title,
            "canonical_url": canonical_url,
            "tags": tag_list(metadata, article.topic),
            "cover_image": social_card_url(site_url, article.topic),
            "body": body.strip(),
        }
        for platform in platforms:
            if platform not in PLATFORMS:
                raise SyndicationError(f"unsupported syndication platform: {platform}")
            template_path = DEFAULT_TEMPLATE_DIR / f"{platform}.md"
            if not template_path.exists():
                raise SyndicationError(f"syndication template does not exist: {template_path}")
            destination = output_dir / platform / article.topic["primary_language"] / article.topic["category"] / f"{article.topic['slug']}.md"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(render_template(template_path.read_text(encoding="utf-8"), context), encoding="utf-8")
            manifest.append(
                {
                    "topic_id": article.topic["id"],
                    "platform": platform,
                    "language": article.topic["primary_language"],
                    "category": article.topic["category"],
                    "slug": article.topic["slug"],
                    "draft_path": str(destination.relative_to(project_root)),
                    "canonical_url": canonical_url,
                    "status": "draft",
                    "approved_by": "",
                    "approved_at": "",
                    "post_id": "",
                    "posted_url": "",
                    "posted_at": "",
                    "last_attempt_at": "",
                    "error": "",
                    "error_type": "",
                    "retry_count": 0,
                }
            )
    (output_dir / "manifest.json").write_text(json.dumps({"drafts": manifest}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate long-form syndication drafts")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    args = parser.parse_args()
    try:
        drafts = generate_syndication_drafts(args.topics, args.output_dir, args.site_url)
    except (SyndicationError, PublishingError, TopicError, OSError, json.JSONDecodeError) as error:
        print(f"syndication generation failed: {error}", file=sys.stderr)
        return 1
    print(f"generated {len(drafts)} syndication draft(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
