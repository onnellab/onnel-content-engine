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

from hashnode_content import HASHNODE_CONTENT_PROFILE, hashnode_native_body, hashnode_tag_list
from publishing import DEFAULT_SITE_URL, PublishingError, article_public_url, load_publishable_articles, normalize_site_url, parse_front_matter, syndication_body, syndication_intro, syndication_note
from publishing import EXTERNAL_DISTRIBUTION_LANGUAGES
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


def platform_markdown_url(url: str, platform: str) -> str:
    if platform == "devto" and url.startswith("/blog-assets/") and url.endswith("/workflow-diagram.svg"):
        return url.removesuffix(".svg") + ".png"
    return url


def absolutize_markdown_links(markdown: str, site_url: str, platform: str = "") -> str:
    base = normalize_site_url(site_url)

    def replace_image(match: re.Match[str]) -> str:
        alt, url, title = match.groups()
        url = platform_markdown_url(url, platform)
        if url.startswith(("http://", "https://", "mailto:", "#")):
            return match.group(0)
        return f"![{alt}]({urljoin(base, url.lstrip('/'))}{title or ''})"

    def replace_link(match: re.Match[str]) -> str:
        label, url = match.groups()
        if url.startswith(("http://", "https://", "mailto:", "#")):
            return match.group(0)
        return f"[{label}]({urljoin(base, url.lstrip('/'))})"

    markdown = re.sub(r"!\[([^\]]*)\]\((\S+?)(\s+\"[^\"]*\")?\)", replace_image, markdown)
    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)", replace_link, markdown)


SYNDICATION_STATE_FIELDS = (
    "status",
    "approved_by",
    "approved_at",
    "post_id",
    "posted_url",
    "posted_at",
    "last_attempt_at",
    "error",
    "error_type",
    "retry_count",
)


def previous_syndication_state(output_dir: Path) -> dict[tuple[str, str, str], dict[str, object]]:
    path = output_dir / "manifest.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    drafts = data.get("drafts")
    if not isinstance(drafts, list):
        return {}
    state: dict[tuple[str, str, str], dict[str, object]] = {}
    for draft in drafts:
        if not isinstance(draft, dict):
            continue
        key = (
            str(draft.get("topic_id", "")),
            str(draft.get("platform", "")),
            str(draft.get("language", "")),
        )
        if all(key):
            state[key] = draft
    return state


def _previous_posted_draft_bodies(
    state: dict[tuple[str, str, str], dict[str, object]],
    output_dir: Path,
    project_root: Path,
) -> dict[tuple[str, str, str], bytes]:
    output_root = output_dir.resolve()
    bodies: dict[tuple[str, str, str], bytes] = {}
    for key, draft in state.items():
        if draft.get("status") != "posted":
            continue
        draft_path = (project_root / str(draft.get("draft_path", ""))).resolve()
        if not draft_path.is_relative_to(output_root):
            raise SyndicationError(f"posted syndication draft is outside output directory: {draft_path}")
        try:
            bodies[key] = draft_path.read_bytes()
        except OSError as error:
            raise SyndicationError(f"cannot preserve posted syndication draft: {draft_path}: {error}") from error
    return bodies


def apply_previous_syndication_state(item: dict[str, object], state: dict[tuple[str, str, str], dict[str, object]]) -> None:
    key = (
        str(item.get("topic_id", "")),
        str(item.get("platform", "")),
        str(item.get("language", "")),
    )
    previous = state.get(key)
    if not previous:
        return
    if item.get("publish_after_canonical") is True and previous.get("status") != "posted":
        item.update(
            {
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
        return
    for field in SYNDICATION_STATE_FIELDS:
        if field in previous:
            item[field] = previous[field]


def generate_syndication_drafts(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    site_url: str = DEFAULT_SITE_URL,
    platforms: tuple[str, ...] = PLATFORMS,
    include_prepublication: bool = False,
) -> list[dict[str, object]]:
    site_url = normalize_site_url(site_url)
    project_root = topics_path.parent.parent
    state = previous_syndication_state(output_dir)
    posted_bodies = _previous_posted_draft_bodies(state, output_dir, project_root)
    statuses = (
        {"published", "draft", "image_planning", "review", "scheduled"}
        if include_prepublication
        else None
    )
    articles = load_publishable_articles(
        topics_path,
        project_root / ".syndication-export-check",
        site_url,
        statuses=statuses,
    )
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    manifest: list[dict[str, object]] = []
    for article in articles:
        if article.topic["primary_language"] not in EXTERNAL_DISTRIBUTION_LANGUAGES:
            continue
        markdown = article.markdown_path.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(markdown)
        canonical_url = article_public_url(article, site_url)
        context = {
            "title": article.title,
            "canonical_url": canonical_url,
            "tags": tag_list(metadata, article.topic),
            "cover_image": social_card_url(site_url, article.topic),
            "body": body.strip(),
            "syndication_note": "",
            "syndication_intro": "",
            "content_profile": "",
        }
        for platform in platforms:
            if platform not in PLATFORMS:
                raise SyndicationError(f"unsupported syndication platform: {platform}")
            template_path = DEFAULT_TEMPLATE_DIR / f"{platform}.md"
            if not template_path.exists():
                raise SyndicationError(f"syndication template does not exist: {template_path}")
            destination = output_dir / platform / article.topic["primary_language"] / article.topic["category"] / f"{article.topic['slug']}.md"
            destination.parent.mkdir(parents=True, exist_ok=True)
            context["syndication_note"] = syndication_note(article, platform)
            context["syndication_intro"] = syndication_intro(article, platform)
            platform_body = syndication_body(article, body.strip(), platform)
            platform_body = absolutize_markdown_links(platform_body, site_url, platform)
            if platform == "hashnode":
                platform_body = hashnode_native_body(platform_body)
                context["tags"] = hashnode_tag_list(article.topic["category"])
                context["content_profile"] = HASHNODE_CONTENT_PROFILE
            else:
                context["tags"] = tag_list(metadata, article.topic)
                context["content_profile"] = ""
            context["body"] = platform_body
            destination.write_text(render_template(template_path.read_text(encoding="utf-8"), context), encoding="utf-8")
            item = {
                "topic_id": article.topic["id"],
                "source_status": article.topic["status"],
                "publish_after_canonical": article.topic["status"] != "published",
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
            apply_previous_syndication_state(item, state)
            key = (
                str(item["topic_id"]),
                str(item["platform"]),
                str(item["language"]),
            )
            if item.get("status") == "posted" and key in posted_bodies:
                destination.write_bytes(posted_bodies[key])
            manifest.append(item)
    (output_dir / "manifest.json").write_text(json.dumps({"drafts": manifest}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate long-form syndication drafts")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    parser.add_argument(
        "--include-prepublication",
        action="store_true",
        help="Also prepare drafts for draft, image-planning, review, and scheduled articles",
    )
    args = parser.parse_args()
    try:
        drafts = generate_syndication_drafts(
            args.topics,
            args.output_dir,
            args.site_url,
            include_prepublication=args.include_prepublication,
        )
    except (SyndicationError, PublishingError, TopicError, OSError, json.JSONDecodeError) as error:
        print(f"syndication generation failed: {error}", file=sys.stderr)
        return 1
    print(f"generated {len(drafts)} syndication draft(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
