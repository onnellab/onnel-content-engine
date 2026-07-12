#!/usr/bin/env python3
"""Build canonical website publishing artifacts for GitHub Pages.

Pipeline:
Markdown -> HTML -> RSS -> Sitemap -> Deployment-ready site directory.

This module does not support Blogger.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin
from xml.sax.saxutils import escape as xml_escape

from topic_management import DEFAULT_TOPICS_PATH, TOPIC_HEADER, TopicError, read_csv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_DIR = ROOT / "generated" / "html"
DEFAULT_SITE_URL = "https://onnellab.github.io/"
DEFAULT_SOCIAL_TEMPLATE_DIR = ROOT / "templates" / "social"
DEFAULT_SOCIAL_OUTPUT_DIR = ROOT / "generated" / "social"
LOCAL_RSVG_CONVERT = ROOT / ".tools" / "librsvg2-bin" / "usr" / "bin" / "rsvg-convert"
DEFAULT_PAGES_REPOSITORY = "https://github.com/onnellab/onnellab.github.io.git"
DEFAULT_PAGES_BRANCH = "main"
DEFAULT_HOMEPAGE_REPOSITORY_PATH = Path(
    os.environ.get("ONNELLAB_HOMEPAGE_REPOSITORY", "/mnt/c/dev/onnellab.github.io")
)
FAVICON_VERSION = "20260712-transparent"
FAVICON_ASSET_NAMES = ("favicon.svg", "favicon-32x32.png", "apple-touch-icon.png", "site.webmanifest")
PUBLISHABLE_STATUSES = {"published"}
REQUIRED_PUBLICATION_LANGUAGES = {"en", "ko"}

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
BLOG_ASSET_RE = re.compile(r"\]\((/blog-assets/[^)\s\"]+)")
IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]+)\")?\)$")
SOCIAL_PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


class PublishingError(ValueError):
    """Raised when publishing artifacts cannot be generated safely."""


@dataclass(frozen=True)
class Article:
    topic: dict[str, str]
    markdown_path: Path
    html_path: Path
    url_path: str
    title: str
    body_html: str
    description: str
    social_image_path: str
    social_image_url: str


@dataclass(frozen=True)
class HomepageExport:
    topic_id: str
    source: Path
    destination: Path
    action: str


@dataclass(frozen=True)
class SocialPost:
    topic_id: str
    platform: str
    destination: Path
    text: str


@dataclass(frozen=True)
class SocialTemplate:
    template_id: str
    platform: str
    filename: str
    is_variant: bool = False


def parse_front_matter(markdown: str) -> tuple[dict[str, str], str]:
    match = FRONT_MATTER_RE.match(markdown)
    if not match:
        return {}, markdown
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, markdown[match.end() :]


def inline_markdown(value: str) -> str:
    escaped = html.escape(value)
    escaped = BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    return LINK_RE.sub(lambda match: f'<a href="{html.escape(match.group(2), quote=True)}">{match.group(1)}</a>', escaped)


def markdown_to_html(markdown: str) -> str:
    _, body = parse_front_matter(markdown)
    lines = body.splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    ordered_items: list[str] = []
    blockquote: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(f"<p>{inline_markdown(' '.join(paragraph))}</p>")
            paragraph = []

    def flush_blockquote() -> None:
        nonlocal blockquote
        if blockquote:
            blocks.append(f"<blockquote>{inline_markdown(' '.join(blockquote))}</blockquote>")
            blockquote = []

    def flush_lists() -> None:
        nonlocal list_items, ordered_items
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{inline_markdown(item)}</li>" for item in list_items) + "</ul>")
            list_items = []
        if ordered_items:
            blocks.append("<ol>" + "".join(f"<li>{inline_markdown(item)}</li>" for item in ordered_items) + "</ol>")
            ordered_items = []

    def flush_all() -> None:
        flush_paragraph()
        flush_lists()
        flush_blockquote()

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            flush_all()
            index += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        unordered = re.match(r"^-\s+(.+)$", stripped)
        ordered = re.match(r"^\d+\.\s+(.+)$", stripped)
        quote = re.match(r"^>\s?(.+)$", stripped)
        image = IMAGE_RE.match(stripped)
        if heading:
            flush_all()
            level = min(len(heading.group(1)), 6)
            blocks.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>")
        elif image:
            flush_all()
            alt = html.escape(image.group(1), quote=True)
            src = html.escape(image.group(2), quote=True)
            title = image.group(3)
            title_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
            blocks.append(f'<figure><img src="{src}" alt="{alt}"{title_attr}></figure>')
        elif is_table_start(lines, index):
            flush_all()
            table_html, index = read_table_html(lines, index)
            blocks.append(table_html)
        elif unordered:
            flush_paragraph()
            flush_blockquote()
            if ordered_items:
                flush_lists()
            list_items.append(unordered.group(1))
        elif ordered:
            flush_paragraph()
            flush_blockquote()
            if list_items:
                flush_lists()
            ordered_items.append(ordered.group(1))
        elif quote:
            flush_paragraph()
            flush_lists()
            blockquote.append(quote.group(1))
        else:
            flush_lists()
            flush_blockquote()
            paragraph.append(stripped)
        index += 1

    flush_all()
    return "\n".join(blocks)


def is_table_start(lines: list[str], index: int) -> bool:
    header = lines[index].strip() if index < len(lines) else ""
    separator = lines[index + 1].strip() if index + 1 < len(lines) else ""
    return "|" in header and bool(re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", separator))


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def read_table_html(lines: list[str], index: int) -> tuple[str, int]:
    headers = table_cells(lines[index])
    rows: list[list[str]] = []
    cursor = index + 2
    while cursor < len(lines) and "|" in lines[cursor].strip() and lines[cursor].strip():
        rows.append(table_cells(lines[cursor]))
        cursor += 1
    head = "<thead><tr>" + "".join(f"<th>{inline_markdown(header)}</th>" for header in headers) + "</tr></thead>"
    body = "<tbody>" + "".join(
        "<tr>" + "".join(f"<td>{inline_markdown(cell)}</td>" for cell in row) + "</tr>" for row in rows
    ) + "</tbody>"
    return f"<table>{head}{body}</table>", cursor - 1


def first_paragraph_text(markdown: str) -> str:
    _, body = parse_front_matter(markdown)
    for block in body.split("\n\n"):
        stripped = block.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
            return re.sub(r"\s+", " ", stripped)[:180]
    return ""


def plain_text(value: str) -> str:
    value = LINK_RE.sub(r"\1", value)
    value = BOLD_RE.sub(r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def markdown_sections(markdown: str) -> dict[str, str]:
    _, body = parse_front_matter(markdown)
    sections: dict[str, list[str]] = {}
    current_heading = ""
    for line in body.splitlines():
        heading = re.match(r"^##\s+(.+)$", line.strip())
        if heading:
            current_heading = heading.group(1).strip().lower()
            sections.setdefault(current_heading, [])
            continue
        if current_heading:
            sections[current_heading].append(line)
    return {heading: "\n".join(lines).strip() for heading, lines in sections.items()}


def section_text(markdown: str, headings: tuple[str, ...]) -> str:
    sections = markdown_sections(markdown)
    for heading in headings:
        content = sections.get(heading.lower())
        if content:
            return content
    return ""


def first_paragraph_from_text(value: str) -> str:
    for block in value.split("\n\n"):
        stripped = block.strip()
        if stripped and not stripped.startswith(("!", "|", ">")):
            return plain_text(stripped)
    return ""


def first_sentences(value: str, limit: int) -> str:
    parts = re.split(r"(?<=[.!?。！？])\s+", value.strip())
    selected = [part for part in parts if part][:limit]
    return " ".join(selected) if selected else value


def list_items_from_text(value: str, limit: int = 3) -> list[str]:
    items: list[str] = []
    for line in value.splitlines():
        match = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", line.strip())
        if not match:
            continue
        items.append(plain_text(match.group(1)))
        if len(items) >= limit:
            break
    return items


def truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3].rstrip() + "..."


def wrap_text(value: str, max_chars: int, max_lines: int) -> list[str]:
    words = " ".join(value.split()).split(" ")
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if lines and len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = truncate_text(lines[-1], max_chars)
    return lines


def svg_tspans(lines: list[str], x: int, y: int, line_height: int) -> str:
    return "".join(
        f'<tspan x="{x}" y="{y + index * line_height}">{html.escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )


def social_card_svg(article: Article) -> str:
    language = article.topic["primary_language"]
    label = "ONNELLAB Article" if language == "en" else "ONNELLAB 아티클"
    title_lines = wrap_text(article.title, 34 if language == "en" else 24, 3)
    description_lines = wrap_text(article.description, 72 if language == "en" else 36, 2)
    category = article.topic["category"].upper()
    category_colors = {
        "reading": ("#e7f2fb", "#b9d7ea", "#24465c"),
        "music": ("#f3e9fb", "#d8c3ec", "#4e3568"),
        "productivity": ("#e8f5ee", "#b9dbc8", "#28543a"),
        "media": ("#fff0df", "#edcda6", "#684621"),
        "craft": ("#f9e8e3", "#e3c0b6", "#673a32"),
        "games": ("#e8edf9", "#bdcae6", "#2c3d66"),
        "research": ("#e9f3f1", "#b9d8d2", "#244f4a"),
    }
    badge_fill, badge_stroke, badge_text = category_colors.get(article.topic["category"], category_colors["reading"])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc">
  <title id="title">{html.escape(article.title)}</title>
  <desc id="desc">{html.escape(article.description)}</desc>
  <rect width="1200" height="630" fill="#f8f4ec"/>
  <rect x="58" y="54" width="1084" height="522" rx="30" fill="#fffdf8" stroke="#d8d0c3" stroke-width="2"/>
  <rect x="92" y="92" width="210" height="44" rx="22" fill="{badge_fill}" stroke="{badge_stroke}" stroke-width="1.4"/>
  <text x="118" y="121" fill="{badge_text}" font-family="Pretendard, SUIT, Noto Sans KR, Inter, system-ui, sans-serif" font-size="18" font-weight="700">{html.escape(category)}</text>
  <text x="92" y="218" fill="#282723" font-family="Pretendard, SUIT, Noto Sans KR, Inter, system-ui, sans-serif" font-size="54" font-weight="760">{svg_tspans(title_lines, 92, 218, 64)}</text>
  <text fill="#5f5b54" font-family="Pretendard, SUIT, Noto Sans KR, Inter, system-ui, sans-serif" font-size="24">{svg_tspans(description_lines, 92, 442, 34)}</text>
  <path d="M92 518H1108" stroke="#ded7ca" stroke-width="2"/>
  <text x="92" y="552" fill="#817c73" font-family="Pretendard, SUIT, Noto Sans KR, Inter, system-ui, sans-serif" font-size="19">{html.escape(label)}</text>
  <text x="1030" y="552" fill="#30302c" font-family="Pretendard, SUIT, Noto Sans KR, Inter, system-ui, sans-serif" font-size="19" font-weight="700">ONNELLAB</text>
</svg>
'''


def favicon_svg() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64" role="img" aria-labelledby="title desc">
  <title id="title">ONNELLAB</title>
  <desc id="desc">OL monogram favicon for ONNELLAB</desc>
  <circle cx="31" cy="32" r="20" fill="none" stroke="#282723" stroke-width="8"/>
  <path d="M35 19V42H46" fill="none" stroke="#282723" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="45" cy="19" r="4" fill="#b9d7ea" stroke="#282723" stroke-width="2"/>
</svg>
'''


def write_site_icons(site_dir: Path) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    svg_path = site_dir / "favicon.svg"
    png_path = site_dir / "favicon-32x32.png"
    apple_path = site_dir / "apple-touch-icon.png"
    manifest_path = site_dir / "site.webmanifest"
    svg_path.write_text(favicon_svg(), encoding="utf-8")
    command = rsvg_convert_command()
    subprocess.run(command + ["-w", "32", "-h", "32", str(svg_path), "-o", str(png_path)], check=True)
    subprocess.run(command + ["-w", "180", "-h", "180", str(svg_path), "-o", str(apple_path)], check=True)
    manifest_path.write_text(
        json.dumps(
            {
                "name": "ONNELLAB",
                "short_name": "ONNELLAB",
                "icons": [
                    {"src": f"/favicon.svg?v={FAVICON_VERSION}", "sizes": "64x64", "type": "image/svg+xml"},
                    {"src": f"/favicon-32x32.png?v={FAVICON_VERSION}", "sizes": "32x32", "type": "image/png"},
                    {"src": f"/apple-touch-icon.png?v={FAVICON_VERSION}", "sizes": "180x180", "type": "image/png"},
                ],
                "theme_color": "#f8f4ec",
                "background_color": "#f8f4ec",
                "display": "standalone",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def social_card_source_for(asset_path: str, project_root: Path = ROOT) -> Path:
    return blog_asset_source_for(asset_path, project_root)


def rsvg_convert_command() -> list[str]:
    if LOCAL_RSVG_CONVERT.exists():
        return [str(LOCAL_RSVG_CONVERT)]
    found = shutil.which("rsvg-convert")
    if found:
        return [found]
    raise PublishingError(
        "rsvg-convert is required to generate PNG social cards. "
        "Install librsvg2-bin or provide .tools/librsvg2-bin/usr/bin/rsvg-convert."
    )


def write_social_card(article: Article, project_root: Path = ROOT) -> Path:
    svg_path = social_card_source_for(social_card_svg_asset_path(article.topic), project_root)
    png_path = social_card_source_for(article.social_image_path, project_root)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(social_card_svg(article), encoding="utf-8")
    command = rsvg_convert_command() + ["-w", "1200", "-h", "630", str(svg_path), "-o", str(png_path)]
    subprocess.run(command, check=True)
    return png_path


URL_RE = re.compile(r"https?://\S+")


def x_weighted_length(text: str) -> int:
    total = 0
    cursor = 0
    for match in URL_RE.finditer(text):
        total += sum(2 if ord(char) > 0x10FF else 1 for char in text[cursor : match.start()])
        total += 23
        cursor = match.end()
    total += sum(2 if ord(char) > 0x10FF else 1 for char in text[cursor:])
    return total


def html_document(
    title: str,
    description: str,
    canonical_url: str,
    feed_url: str,
    body_html: str,
    social_image_url: str = "",
) -> str:
    image_meta = ""
    if social_image_url:
        escaped_image = html.escape(social_image_url, quote=True)
        image_meta = (
            f'  <meta property="og:image" content="{escaped_image}">\n'
            f'  <meta name="twitter:image" content="{escaped_image}">\n'
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description, quote=True)}">
  <link rel="icon" href="/favicon.svg?v={FAVICON_VERSION}" type="image/svg+xml">
  <link rel="icon" href="/favicon-32x32.png?v={FAVICON_VERSION}" sizes="32x32" type="image/png">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png?v={FAVICON_VERSION}">
  <link rel="manifest" href="/site.webmanifest?v={FAVICON_VERSION}">
  <meta name="theme-color" content="#f8f4ec">
  <link rel="canonical" href="{html.escape(canonical_url, quote=True)}">
  <link rel="alternate" type="application/rss+xml" title="ONNELLAB Content Engine RSS" href="{html.escape(feed_url, quote=True)}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{html.escape(title, quote=True)}">
  <meta property="og:description" content="{html.escape(description, quote=True)}">
  <meta property="og:url" content="{html.escape(canonical_url, quote=True)}">
  <meta name="twitter:card" content="{'summary_large_image' if social_image_url else 'summary'}">
  <meta name="twitter:title" content="{html.escape(title, quote=True)}">
  <meta name="twitter:description" content="{html.escape(description, quote=True)}">
{image_meta.rstrip()}
</head>
<body>
  <main>
{body_html}
  </main>
</body>
</html>
"""


def normalize_site_url(site_url: str) -> str:
    return site_url if site_url.endswith("/") else site_url + "/"


def public_url(site_url: str, url_path: str) -> str:
    return urljoin(normalize_site_url(site_url), url_path.lstrip("/"))


def absolute_url(site_url: str, value: str) -> str:
    if value.startswith(("http://", "https://")):
        return value
    return urljoin(normalize_site_url(site_url), value.lstrip("/"))


def social_card_asset_path(topic: dict[str, str]) -> str:
    return f"/blog-assets/{topic['primary_language']}/{topic['slug']}/social-card.png"


def social_card_svg_asset_path(topic: dict[str, str]) -> str:
    return f"/blog-assets/{topic['primary_language']}/{topic['slug']}/social-card.svg"


def article_url_path(topic: dict[str, str]) -> str:
    return f"blog/{topic['primary_language']}/{topic['slug']}/"


def validate_publishable_language_pairs(rows: list[dict[str, str]]) -> None:
    groups: dict[tuple[str, str], set[str]] = {}
    for topic in rows:
        if topic["status"] not in PUBLISHABLE_STATUSES:
            continue
        groups.setdefault((topic["category"], topic["slug"]), set()).add(topic["primary_language"])
    for (category, slug), languages in groups.items():
        missing = REQUIRED_PUBLICATION_LANGUAGES - languages
        if missing:
            raise PublishingError(
                f"published article {category}/{slug} is missing language counterpart(s): {', '.join(sorted(missing))}"
            )


def load_publishable_articles(topics_path: Path, site_dir: Path, site_url: str) -> list[Article]:
    rows = read_csv(topics_path, TOPIC_HEADER)
    validate_publishable_language_pairs(rows)
    articles: list[Article] = []
    for topic in rows:
        if topic["status"] not in PUBLISHABLE_STATUSES:
            continue
        if not topic["canonical_path"]:
            raise PublishingError(f"{topic['id']} is publishable but has no canonical_path")
        markdown_path = topics_path.parent.parent / topic["canonical_path"]
        if not markdown_path.exists():
            raise PublishingError(f"{topic['id']} Markdown file does not exist: {topic['canonical_path']}")
        markdown = markdown_path.read_text(encoding="utf-8")
        metadata, _ = parse_front_matter(markdown)
        title = metadata.get("title") or topic["working_title"]
        description = metadata.get("description") or first_paragraph_text(markdown) or topic["primary_question"]
        url_path = article_url_path(topic)
        html_path = site_dir / url_path / "index.html"
        body_html = markdown_to_html(markdown)
        social_image_path = social_card_asset_path(topic)
        social_image_url = absolute_url(site_url, social_image_path)
        articles.append(
            Article(
                topic=topic,
                markdown_path=markdown_path,
                html_path=html_path,
                url_path=url_path,
                title=title,
                body_html=body_html,
                description=description,
                social_image_path=social_image_path,
                social_image_url=social_image_url,
            )
        )
    return articles


def write_article(article: Article, site_url: str) -> None:
    article.html_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_url = public_url(site_url, article.url_path)
    article.html_path.write_text(
        html_document(
            article.title,
            article.description,
            canonical_url,
            public_url(site_url, "feed.xml"),
            article.body_html,
            article.social_image_url,
        ),
        encoding="utf-8",
    )


def write_index(site_dir: Path, site_url: str, articles: list[Article]) -> None:
    items = "\n".join(
        f'<li><a href="{html.escape(public_url(site_url, article.url_path), quote=True)}">{html.escape(article.title)}</a></li>'
        for article in articles
    )
    body = f"<h1>ONNELLAB Content Engine</h1>\n<ul>\n{items}\n</ul>"
    (site_dir / "index.html").write_text(
        html_document(
            "ONNELLAB Content Engine",
            "Canonical ONNELLAB educational articles.",
            site_url,
            public_url(site_url, "feed.xml"),
            body,
        ),
        encoding="utf-8",
    )


def rss_date(topic: dict[str, str]) -> str:
    value = topic["published_at"] or topic["scheduled_at"] or topic["updated_at"]
    if value:
        try:
            return datetime.fromisoformat(value).astimezone(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
        except ValueError:
            pass
    return datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")


def write_rss(site_dir: Path, site_url: str, articles: list[Article]) -> None:
    items = []
    for article in articles:
        url = public_url(site_url, article.url_path)
        items.append(
            "  <item>\n"
            f"    <title>{xml_escape(article.title)}</title>\n"
            f"    <link>{xml_escape(url)}</link>\n"
            f"    <guid>{xml_escape(url)}</guid>\n"
            f"    <description>{xml_escape(article.description)}</description>\n"
            f"    <pubDate>{rss_date(article.topic)}</pubDate>\n"
            "  </item>"
        )
    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "<channel>\n"
        "  <title>ONNELLAB Content Engine</title>\n"
        f"  <link>{xml_escape(site_url)}</link>\n"
        "  <description>Canonical ONNELLAB educational articles.</description>\n"
        + "\n".join(items)
        + "\n</channel>\n</rss>\n"
    )
    (site_dir / "feed.xml").write_text(rss, encoding="utf-8")


def write_sitemap(site_dir: Path, site_url: str, articles: list[Article]) -> None:
    urls = [site_url] + [public_url(site_url, article.url_path) for article in articles]
    entries = "\n".join(f"  <url><loc>{xml_escape(url)}</loc></url>" for url in urls)
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )
    (site_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")


def social_destination_for(output_dir: Path, platform: str, topic: dict[str, str]) -> Path:
    return output_dir / platform / topic["primary_language"] / topic["category"] / f"{topic['slug']}.txt"


def social_variant_destination_for(output_dir: Path, template_id: str, topic: dict[str, str]) -> Path:
    return output_dir / "variants" / template_id / topic["primary_language"] / topic["category"] / f"{topic['slug']}.txt"


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def article_public_url(article: Article, site_url: str) -> str:
    return article.topic["published_url"] or public_url(site_url, article.url_path)


def render_x_post(article: Article, site_url: str) -> str:
    return render_x_template(article, site_url, "x")


def render_x_template(article: Article, site_url: str, template_id: str) -> str:
    context = social_template_context(article, site_url)
    template = load_social_template(template_id)
    rendered = render_social_template(template, context)
    while x_weighted_length(rendered) > 280 and context["x_summary"]:
        context["x_summary"] = truncate_text(context["x_summary"], max(0, len(context["x_summary"]) - 8))
        rendered = render_social_template(template, context)
    if x_weighted_length(rendered) > 280:
        context["x_summary"] = ""
        rendered = render_social_template(template, context)
    while x_weighted_length(rendered) > 280 and context["question"]:
        context["question"] = truncate_text(context["question"], max(0, len(context["question"]) - 8))
        rendered = render_social_template(template, context)
    return rendered


def render_bluesky_template(article: Article, site_url: str, template_id: str) -> str:
    context = social_template_context(article, site_url)
    template = load_social_template(template_id)
    rendered = render_social_template(template, context)
    while len(rendered) > 260 and context["bsky_summary"]:
        context["bsky_summary"] = truncate_text(context["bsky_summary"], max(0, len(context["bsky_summary"]) - 8))
        rendered = render_social_template(template, context)
    if len(rendered) > 300:
        context["bsky_summary"] = ""
        rendered = render_social_template(template, context)
    while len(rendered) > 260 and context["question"]:
        context["question"] = truncate_text(context["question"], max(0, len(context["question"]) - 8))
        rendered = render_social_template(template, context)
    return rendered


def render_linkedin_post(article: Article, site_url: str) -> str:
    context = social_template_context(article, site_url)
    return truncate_text(render_social_template(load_social_template("linkedin"), context), 3000)


def render_linkedin_template(article: Article, site_url: str, template_id: str) -> str:
    context = social_template_context(article, site_url)
    return truncate_text(render_social_template(load_social_template(template_id), context), 900 if template_id == "linkedin_short" else 3000)


def load_social_template(platform: str, template_dir: Path = DEFAULT_SOCIAL_TEMPLATE_DIR) -> str:
    path = template_dir / f"{platform}.txt"
    if not path.exists():
        raise PublishingError(f"social template does not exist: {path}")
    return path.read_text(encoding="utf-8")


def social_template_context(article: Article, site_url: str) -> dict[str, str]:
    markdown = article.markdown_path.read_text(encoding="utf-8")
    title = plain_text(article.title)
    description = plain_text(article.description)
    url = article_public_url(article, site_url)
    short_answer = first_paragraph_from_text(
        section_text(markdown, ("Short Answer", "요약 답변"))
    ) or description
    workflow = section_text(markdown, ("Recommended Workflow", "권장 워크플로"))
    key_points = list_items_from_text(workflow, limit=3)
    if not key_points:
        key_points = list_items_from_text(section_text(markdown, ("What To Check First", "먼저 확인할 항목")), limit=3)
    key_points_text = "\n".join(f"- {item}" for item in key_points) if key_points else f"- {description}"
    short_points = key_points[:2] if key_points else [description]
    short_points_text = "\n".join(f"- {item}" for item in short_points)
    fixed_length = len(title) + len(url) + 4
    x_summary_limit = max(0, 280 - fixed_length)
    cta = "전체 글 읽기:" if article.topic["primary_language"] == "ko" else "Read the full article:"
    insight = first_sentences(short_answer, 2)
    return {
        "title": title,
        "question": truncate_text(plain_text(article.topic["primary_question"]), 120),
        "description": description,
        "insight": truncate_text(insight, 420),
        "key_points": key_points_text,
        "short_points": short_points_text,
        "cta": cta,
        "url": url,
        "x_summary": truncate_text(description, x_summary_limit),
        "bsky_summary": truncate_text(description, 160),
    }


def render_social_template(template: str, context: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise PublishingError(f"unknown social template placeholder: {key}")
        return context[key]

    rendered = SOCIAL_PLACEHOLDER_RE.sub(replace, template)
    return re.sub(r"\n{3,}", "\n\n", rendered).strip()


def render_social_post(article: Article, platform: str, site_url: str) -> str:
    if platform == "x":
        return render_x_post(article, site_url)
    if platform == "bluesky":
        return render_bluesky_template(article, site_url, "bluesky")
    if platform == "linkedin":
        return render_linkedin_post(article, site_url)
    raise PublishingError(f"unsupported social platform: {platform}")


def render_social_template_post(article: Article, template: SocialTemplate, site_url: str) -> str:
    if template.platform == "x":
        return render_x_template(article, site_url, template.template_id)
    if template.platform == "bluesky":
        return render_bluesky_template(article, site_url, template.template_id)
    if template.platform == "linkedin":
        return render_linkedin_template(article, site_url, template.template_id)
    raise PublishingError(f"unsupported social platform: {template.platform}")


def social_templates(platforms: tuple[str, ...]) -> list[SocialTemplate]:
    selected: list[SocialTemplate] = []
    if "x" in platforms:
        selected.append(SocialTemplate("x", "x", "x.txt"))
        selected.append(SocialTemplate("x_question", "x", "x_question.txt", is_variant=True))
    if "bluesky" in platforms:
        selected.append(SocialTemplate("bluesky", "bluesky", "bluesky.txt"))
        selected.append(SocialTemplate("bluesky_question", "bluesky", "bluesky_question.txt", is_variant=True))
    if "linkedin" in platforms:
        selected.append(SocialTemplate("linkedin", "linkedin", "linkedin.txt"))
        selected.append(SocialTemplate("linkedin_short", "linkedin", "linkedin_short.txt", is_variant=True))
    return selected


def manifest_item(
    article: Article,
    template: SocialTemplate,
    destination: Path,
    card_path: Path,
    site_url: str,
    project_root: Path,
    weighted_length: int,
) -> dict[str, str | int | bool]:
    return {
        "topic_id": article.topic["id"],
        "platform": template.platform,
        "language": article.topic["primary_language"],
        "category": article.topic["category"],
        "slug": article.topic["slug"],
        "template_id": template.template_id,
        "template_path": display_path(DEFAULT_SOCIAL_TEMPLATE_DIR / template.filename, project_root),
        "is_variant": template.is_variant,
        "draft_path": str(destination.relative_to(project_root)),
        "canonical_url": article_public_url(article, site_url),
        "card_asset_path": str(card_path.relative_to(project_root)),
        "weighted_length": weighted_length,
        "status": "variant" if template.is_variant else "draft",
        "approved_by": "",
        "approved_at": "",
        "post_id": "",
        "posted_url": "",
        "posted_at": "",
        "last_attempt_at": "",
        "error": "",
        "error_type": "",
        "retry_count": 0,
        "impressions": 0,
        "clicks": 0,
        "engagements": 0,
        "last_metrics_at": "",
    }


SOCIAL_STATE_FIELDS = (
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
    "impressions",
    "clicks",
    "engagements",
    "last_metrics_at",
)


def previous_social_state(output_dir: Path) -> dict[tuple[str, str, str, str], dict[str, object]]:
    path = output_dir / "manifest.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    posts = data.get("posts")
    if not isinstance(posts, list):
        return {}
    state: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for post in posts:
        if not isinstance(post, dict):
            continue
        key = (
            str(post.get("topic_id", "")),
            str(post.get("platform", "")),
            str(post.get("language", "")),
            str(post.get("template_id", "")),
        )
        if all(key):
            state[key] = post
    return state


def apply_previous_social_state(item: dict[str, object], state: dict[tuple[str, str, str, str], dict[str, object]]) -> None:
    key = (
        str(item.get("topic_id", "")),
        str(item.get("platform", "")),
        str(item.get("language", "")),
        str(item.get("template_id", "")),
    )
    previous = state.get(key)
    if not previous:
        return
    for field in SOCIAL_STATE_FIELDS:
        if field in previous:
            item[field] = previous[field]


def generate_social_posts(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    output_dir: Path = DEFAULT_SOCIAL_OUTPUT_DIR,
    site_url: str = DEFAULT_SITE_URL,
    platforms: tuple[str, ...] = ("x", "linkedin", "bluesky"),
) -> list[SocialPost]:
    site_url = normalize_site_url(site_url)
    state = previous_social_state(output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    project_root = topics_path.parent.parent
    articles = load_publishable_articles(topics_path, project_root / ".social-export-check", site_url)
    posts: list[SocialPost] = []
    manifest_items: list[dict[str, str | int]] = []
    templates = social_templates(platforms)
    for article in articles:
        card_path = write_social_card(article, project_root)
        for template in templates:
            text = render_social_template_post(article, template, site_url)
            weighted_length = x_weighted_length(text) if template.platform == "x" else len(text)
            if template.platform == "x" and weighted_length > 280:
                raise PublishingError(f"{article.topic['id']} X post exceeds weighted length: {weighted_length}")
            if template.platform == "bluesky" and weighted_length > 300:
                raise PublishingError(f"{article.topic['id']} Bluesky post exceeds length: {weighted_length}")
            destination = (
                social_variant_destination_for(output_dir, template.template_id, article.topic)
                if template.is_variant
                else social_destination_for(output_dir, template.platform, article.topic)
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text + "\n", encoding="utf-8")
            if not template.is_variant:
                posts.append(SocialPost(article.topic["id"], template.platform, destination, text))
            item = manifest_item(article, template, destination, card_path, site_url, project_root, weighted_length)
            apply_previous_social_state(item, state)
            manifest_items.append(item)
    (output_dir / "manifest.json").write_text(json.dumps({"posts": manifest_items}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return posts


def build_site(topics_path: Path = DEFAULT_TOPICS_PATH, site_dir: Path = DEFAULT_SITE_DIR, site_url: str = DEFAULT_SITE_URL) -> list[Article]:
    site_url = normalize_site_url(site_url)
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    write_site_icons(site_dir)
    articles = load_publishable_articles(topics_path, site_dir, site_url)
    for article in articles:
        write_social_card(article, topics_path.parent.parent)
        write_article(article, site_url)
    write_index(site_dir, site_url, articles)
    write_rss(site_dir, site_url, articles)
    write_sitemap(site_dir, site_url, articles)
    return articles


def validate_homepage_repository(homepage_repo: Path) -> None:
    if not homepage_repo.exists():
        raise PublishingError(f"homepage repository does not exist: {homepage_repo}")
    if not (homepage_repo / ".git").exists():
        raise PublishingError(f"homepage repository is not a git checkout: {homepage_repo}")
    if not (homepage_repo / "astro.config.mjs").exists():
        raise PublishingError(f"homepage repository is not the Astro homepage checkout: {homepage_repo}")
    content_dir = homepage_repo / "src" / "content" / "blog"
    if not content_dir.exists():
        raise PublishingError(f"homepage blog content directory does not exist: {content_dir}")


def homepage_destination_for(topic: dict[str, str], homepage_repo: Path) -> Path:
    language = topic["primary_language"]
    if language not in {"en", "ko"}:
        raise PublishingError(f"{topic['id']} has unsupported homepage language: {language}")
    return homepage_repo / "src" / "content" / "blog" / language / f"{topic['slug']}.md"


def blog_asset_source_for(asset_path: str, project_root: Path = ROOT) -> Path:
    relative = asset_path.lstrip("/")
    if not relative.startswith("blog-assets/"):
        raise PublishingError(f"unsupported blog asset path: {asset_path}")
    return project_root / "generated" / "assets" / "blog" / relative.removeprefix("blog-assets/")


def blog_asset_destination_for(asset_path: str, homepage_repo: Path) -> Path:
    relative = asset_path.lstrip("/")
    if not relative.startswith("blog-assets/"):
        raise PublishingError(f"unsupported blog asset path: {asset_path}")
    return homepage_repo / "public" / relative


def referenced_blog_assets(markdown: str) -> list[str]:
    seen: set[str] = set()
    assets: list[str] = []
    for match in BLOG_ASSET_RE.finditer(markdown):
        asset_path = match.group(1)
        if asset_path in seen:
            continue
        seen.add(asset_path)
        assets.append(asset_path)
    return assets


def export_blog_assets_to_homepage(markdown: str, homepage_repo: Path, dry_run: bool, project_root: Path = ROOT) -> None:
    for asset_path in referenced_blog_assets(markdown):
        source = blog_asset_source_for(asset_path, project_root)
        if not source.exists():
            try:
                display_path = source.relative_to(project_root)
            except ValueError:
                display_path = source
            raise PublishingError(f"referenced blog asset does not exist: {display_path}")
        if dry_run:
            continue
        destination = blog_asset_destination_for(asset_path, homepage_repo)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def export_site_icons_to_homepage(homepage_repo: Path, dry_run: bool, project_root: Path = ROOT) -> None:
    icon_source_dir = project_root / "generated" / "html"
    if not dry_run:
        write_site_icons(icon_source_dir)
    for name in FAVICON_ASSET_NAMES:
        source = icon_source_dir / name
        if dry_run and not source.exists():
            continue
        if not source.exists():
            raise PublishingError(f"site icon does not exist: {source}")
        if dry_run:
            continue
        destination = homepage_repo / "public" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def export_markdown_to_homepage(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    homepage_repo: Path = DEFAULT_HOMEPAGE_REPOSITORY_PATH,
    dry_run: bool = False,
) -> list[HomepageExport]:
    validate_homepage_repository(homepage_repo)
    project_root = topics_path.parent.parent
    export_site_icons_to_homepage(homepage_repo, dry_run, project_root)
    articles = load_publishable_articles(topics_path, ROOT / ".homepage-export-check", DEFAULT_SITE_URL)
    exports: list[HomepageExport] = []

    for article in articles:
        markdown = article.markdown_path.read_text(encoding="utf-8")
        social_card_source = write_social_card(article, project_root)
        destination = homepage_destination_for(article.topic, homepage_repo)
        action = "create"
        if destination.exists():
            action = "unchanged" if destination.read_text(encoding="utf-8") == markdown else "overwrite"
        exports.append(HomepageExport(article.topic["id"], article.markdown_path, destination, action))
        export_blog_assets_to_homepage(markdown, homepage_repo, dry_run, project_root)
        if not dry_run:
            social_card_destination = blog_asset_destination_for(article.social_image_path, homepage_repo)
            social_card_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(social_card_source, social_card_destination)
            social_card_svg_source = social_card_source_for(social_card_svg_asset_path(article.topic), project_root)
            social_card_svg_destination = blog_asset_destination_for(social_card_svg_asset_path(article.topic), homepage_repo)
            shutil.copy2(social_card_svg_source, social_card_svg_destination)
        if dry_run or action == "unchanged":
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(article.markdown_path, destination)

    return exports


def run_homepage_command(command: list[str], homepage_repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=homepage_repo, check=True, text=True)


def deploy_github_pages(
    site_dir: Path = DEFAULT_SITE_DIR,
    repository: str = DEFAULT_PAGES_REPOSITORY,
    branch: str = DEFAULT_PAGES_BRANCH,
    deploy_dir: Path = ROOT / ".deploy-github-pages",
    topics_path: Path = DEFAULT_TOPICS_PATH,
    homepage_repo: Path = DEFAULT_HOMEPAGE_REPOSITORY_PATH,
    dry_run: bool = False,
) -> list[HomepageExport]:
    _ = site_dir
    _ = repository
    _ = deploy_dir
    validate_homepage_repository(homepage_repo)
    if dry_run:
        return export_markdown_to_homepage(topics_path, homepage_repo, dry_run=True)

    run_homepage_command(["git", "pull", "--rebase", "origin", branch], homepage_repo)
    exports = export_markdown_to_homepage(topics_path, homepage_repo, dry_run=False)
    run_homepage_command(["npm", "run", "build"], homepage_repo)
    run_homepage_command(
        ["git", "add", "src/content/blog", "public/blog-assets", *[f"public/{name}" for name in FAVICON_ASSET_NAMES]],
        homepage_repo,
    )
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=homepage_repo)
    if diff.returncode == 0:
        return exports
    run_homepage_command(["git", "commit", "-m", "Publish ONNELLAB blog content"], homepage_repo)
    run_homepage_command(["git", "pull", "--rebase", "origin", branch], homepage_repo)
    run_homepage_command(["git", "push", "origin", branch], homepage_repo)
    return exports


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ONNELLAB GitHub Pages publishing artifacts")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--site-dir", type=Path, default=DEFAULT_SITE_DIR)
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    parser.add_argument("--deploy", action="store_true", help="Deploy the built site to the GitHub Pages homepage repository")
    parser.add_argument("--repository", default=DEFAULT_PAGES_REPOSITORY)
    parser.add_argument("--branch", default=DEFAULT_PAGES_BRANCH)
    parser.add_argument("--homepage-repo", type=Path, default=DEFAULT_HOMEPAGE_REPOSITORY_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Preview homepage Markdown export without copying or deploying")
    parser.add_argument("--social", action="store_true", help="Generate social distribution drafts for published articles")
    args = parser.parse_args()
    try:
        articles = build_site(args.topics, args.site_dir, args.site_url)
        if args.social:
            posts = generate_social_posts(args.topics, site_url=args.site_url)
            for post in posts:
                print(f"social {post.platform}: {post.destination}")
        if args.deploy or args.dry_run:
            exports = deploy_github_pages(
                args.site_dir,
                repository=args.repository,
                branch=args.branch,
                topics_path=args.topics,
                homepage_repo=args.homepage_repo,
                dry_run=args.dry_run,
            )
            for item in exports:
                print(f"{item.action}: {item.source} -> {item.destination}")
    except (PublishingError, TopicError, OSError, subprocess.CalledProcessError) as error:
        print(f"publishing failed: {error}", file=sys.stderr)
        return 1
    print(f"built {len(articles)} article(s) in {args.site_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
