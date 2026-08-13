#!/usr/bin/env python3
"""Build canonical website publishing artifacts for GitHub Pages.

Pipeline:
Markdown -> HTML -> RSS -> Sitemap -> Deployment-ready site directory.

This module does not support Blogger.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from xml.sax.saxutils import escape as xml_escape

from topic_management import DEFAULT_TOPICS_PATH, TOPIC_HEADER, TopicError, read_csv


UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_DIR = ROOT / "generated" / "html"
DEFAULT_SITE_URL = "https://onnellab.github.io/"
DEFAULT_PRIVACY_POLICIES_PATH = ROOT / "data" / "app_privacy_policies.json"
DEFAULT_APPS_REGISTRY_PATH = ROOT / "data" / "apps_registry.csv"
DEFAULT_SOCIAL_TEMPLATE_DIR = ROOT / "templates" / "social"
DEFAULT_SOCIAL_OUTPUT_DIR = ROOT / "generated" / "social"
LOCAL_RSVG_CONVERT = ROOT / ".tools" / "librsvg2-bin" / "usr" / "bin" / "rsvg-convert"
DEFAULT_PAGES_REPOSITORY = "https://github.com/onnellab/onnellab.github.io.git"
DEFAULT_PAGES_BRANCH = "main"
DEFAULT_HOMEPAGE_REPOSITORY_PATH = Path(
    os.environ.get("ONNELLAB_HOMEPAGE_REPOSITORY", "/mnt/c/dev/onnellab.github.io")
)
FAVICON_VERSION = "20260712-ol-transparent-v2"
FAVICON_ASSET_NAMES = ("favicon.svg", "favicon-32x32.png", "apple-touch-icon.png", "site.webmanifest")
PRIVACY_PAGE_STYLE = """
  <style>
    @font-face {
      font-family: "SUIT Variable";
      font-weight: 45 920;
      font-style: normal;
      font-display: swap;
      src: url("https://cdn.jsdelivr.net/gh/sunn-us/SUIT/fonts/variable/woff2/SUIT-Variable.woff2") format("woff2-variations");
    }
    :root {
      color-scheme: light;
      --background: #faf8f5;
      --surface: #f0ece5;
      --text: #3e3e3e;
      --muted: #766f66;
      --divider: #ded7cd;
      --accent: #afc8e8;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; background: var(--background); }
    main {
      max-width: 840px;
      margin: 0 auto;
      padding: 72px 28px 88px;
      background: var(--background);
      color: var(--text);
      font-family: "SUIT Variable", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Segoe UI", sans-serif;
      font-size: 16px;
      line-height: 1.72;
    }
    h1 { margin: 0 0 14px; font-size: clamp(2rem, 4vw, 3.25rem); line-height: 1.08; font-weight: 760; letter-spacing: 0; }
    h2 { margin: 56px 0 18px; font-size: 1.35rem; line-height: 1.25; font-weight: 720; }
    h3 { margin: 32px 0 10px; font-size: 1.02rem; line-height: 1.35; font-weight: 680; }
    p { margin: 0 0 14px; }
    ul { margin: 0 0 18px; padding-left: 1.25rem; }
    li { margin: 7px 0; }
    hr { margin: 44px 0; border: 0; border-top: 1px solid var(--divider); }
    a { color: #3d5f82; text-decoration-color: rgba(61, 95, 130, 0.36); text-underline-offset: 0.18em; }
    a:hover { text-decoration-color: currentColor; }
    main > p:first-of-type { max-width: 620px; margin-bottom: 28px; color: var(--muted); font-size: 1.05rem; }
    strong { font-weight: 720; }
    .topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 34px; }
    .topbar a { text-decoration: none; }
    .home-link { color: #737067; font-family: "Avenir Next", Avenir, "Helvetica Neue", Arial, sans-serif; font-size: 14px; font-weight: 560; letter-spacing: 0; }
    .language-link { min-height: 34px; display: inline-flex; align-items: center; border: 1px solid #ded6ca; border-radius: 999px; padding: 6px 12px; background: rgba(255, 253, 248, 0.72); color: #5f5a50; font-size: 13px; font-weight: 650; line-height: 1.35; }
    .home-link:hover, .home-link:focus-visible { color: #3e3e3e; }
    .language-link:hover, .language-link:focus-visible { border-color: #cfc5b7; background: #fffdf8; }
    .topbar a:focus-visible { outline: 2px solid #827d72; outline-offset: 3px; }
    @media (max-width: 640px) {
      main { padding: 48px 20px 64px; font-size: 15px; }
      h2 { margin-top: 44px; }
      hr { margin: 34px 0; }
    }
  </style>
"""
PUBLISHABLE_STATUSES = {"published"}
REQUIRED_PUBLICATION_LANGUAGES = {"en", "ko"}
EXTERNAL_DISTRIBUTION_LANGUAGES = {"en"}

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
BLOG_ASSET_RE = re.compile(r"\]\((/blog-assets/[^)\s\"]+)")
IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]+)\")?\)$")
SOCIAL_PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")
SOCIAL_ELLIPSIS_RE = re.compile(r"\.{3}|…")
SOCIAL_GENERATION_LOCKS: dict[Path, threading.Lock] = {}
SOCIAL_GENERATION_LOCKS_GUARD = threading.Lock()


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
class PrivacyPage:
    app_slug: str
    language: str
    url_path: str
    html_path: Path


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
        if stripped in {"---", "***", "___"}:
            flush_all()
            blocks.append("<hr>")
        elif heading:
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


def related_article_entries(value: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for item in value.split("|"):
        if "=>" not in item:
            continue
        title, url = (part.strip() for part in item.split("=>", 1))
        if title and url and (url.startswith("/") or url.startswith(("http://", "https://"))):
            entries.append((title, url))
    return entries


def related_articles_html(metadata: dict[str, str]) -> str:
    entries = related_article_entries(metadata.get("related_articles", ""))
    if not entries:
        return ""
    is_ko = metadata.get("language") == "ko"
    heading = "관련 글" if is_ko else "Related Articles"
    action = "글 열기" if is_ko else "Read article"
    cards = "\n".join(
        '<article class="related-article-card">'
        f'<h3>{html.escape(title)}</h3>'
        f'<a class="related-article-link" href="{html.escape(url, quote=True)}">{html.escape(action)}</a>'
        "</article>"
        for title, url in entries
    )
    return f'\n<section class="related-articles" aria-label="{html.escape(heading, quote=True)}">\n<h2>{html.escape(heading)}</h2>\n{cards}\n</section>'


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
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    cutoff = limit - 3
    prefix = value[:cutoff].rstrip()
    if len(prefix) < cutoff or value[cutoff].isspace() or re.search(r"[,.;:!?…)}\]]$", prefix):
        return prefix + "..."
    boundary = re.search(r"\s+\S*$", prefix)
    if boundary and prefix[: boundary.start()].rstrip():
        prefix = prefix[: boundary.start()].rstrip()
    return prefix + "..."


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


def social_card_font_defs(language: str) -> tuple[str, str]:
    if language != "ko":
        return "", "Inter, system-ui, sans-serif"
    font_path = Path("/mnt/c/Windows/Fonts/NotoSansKR-VF.ttf")
    if font_path.exists():
        font_uri = font_path.as_uri()
        defs = (
            "<defs><style>"
            "@font-face { font-family: 'ONNELLAB Korean'; "
            f"src: url('{font_uri}') format('truetype'); "
            "font-weight: 100 900; font-style: normal; }"
            "</style></defs>"
        )
        return defs, "ONNELLAB Korean, Noto Sans KR, Malgun Gothic, system-ui, sans-serif"
    return "", "ONNELLAB Korean, Noto Sans KR, Malgun Gothic, system-ui, sans-serif"


def social_card_svg(article: Article) -> str:
    language = article.topic["primary_language"]
    label = f"{article.topic['category'].upper()} · {language.upper()}"
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
    font_defs, font_stack = social_card_font_defs(language)
    font_defs_line = f"  {font_defs}\n" if font_defs else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc">
  <title id="title">{html.escape(article.title)}</title>
  <desc id="desc">{html.escape(article.description)}</desc>
{font_defs_line}  <rect width="1200" height="630" fill="#f8f4ec"/>
  <rect x="58" y="54" width="1084" height="522" rx="30" fill="#fffdf8" stroke="#d8d0c3" stroke-width="2"/>
  <rect x="92" y="92" width="210" height="44" rx="22" fill="{badge_fill}" stroke="{badge_stroke}" stroke-width="1.4"/>
  <text x="118" y="121" fill="{badge_text}" font-family="{font_stack}" font-size="18" font-weight="700">{html.escape(category)}</text>
  <text x="92" y="218" fill="#282723" font-family="{font_stack}" font-size="54" font-weight="760">{svg_tspans(title_lines, 92, 218, 64)}</text>
  <text fill="#5f5b54" font-family="{font_stack}" font-size="24">{svg_tspans(description_lines, 92, 442, 34)}</text>
  <path d="M92 518H1108" stroke="#ded7ca" stroke-width="2"/>
  <text x="92" y="552" fill="#817c73" font-family="{font_stack}" font-size="19">{html.escape(label)}</text>
  <text x="1048" y="552" fill="#30302c" font-family="{font_stack}" font-size="19" font-weight="800" text-anchor="end">ONNELLAB</text>
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
    language: str = "en",
    alternate_urls: dict[str, str] | None = None,
    inline_style: str = "",
) -> str:
    image_meta = ""
    if social_image_url:
        escaped_image = html.escape(social_image_url, quote=True)
        image_meta = (
            f'  <meta property="og:image" content="{escaped_image}">\n'
            f'  <meta name="twitter:image" content="{escaped_image}">\n'
        )
    alternates = "\n".join(
        f'  <link rel="alternate" hreflang="{html.escape(code, quote=True)}" href="{html.escape(url, quote=True)}">'
        for code, url in (alternate_urls or {}).items()
    )
    if alternates:
        alternates += "\n"
    return f"""<!doctype html>
<html lang="{html.escape(language, quote=True)}">
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
{alternates}  <link rel="alternate" type="application/rss+xml" title="ONNELLAB Content Engine RSS" href="{html.escape(feed_url, quote=True)}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{html.escape(title, quote=True)}">
  <meta property="og:description" content="{html.escape(description, quote=True)}">
  <meta property="og:url" content="{html.escape(canonical_url, quote=True)}">
  <meta name="twitter:card" content="{'summary_large_image' if social_image_url else 'summary'}">
  <meta name="twitter:title" content="{html.escape(title, quote=True)}">
  <meta name="twitter:description" content="{html.escape(description, quote=True)}">
{image_meta.rstrip()}{inline_style}
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


def load_publishable_articles(
    topics_path: Path,
    site_dir: Path,
    site_url: str,
    statuses: set[str] | None = None,
) -> list[Article]:
    rows = read_csv(topics_path, TOPIC_HEADER)
    allowed_statuses = statuses or PUBLISHABLE_STATUSES
    if statuses is None:
        validate_publishable_language_pairs(rows)
    articles: list[Article] = []
    for topic in rows:
        if topic["status"] not in allowed_statuses:
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
        body_html = markdown_to_html(markdown) + related_articles_html(metadata)
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


def localized_policy_markdown(policy: dict[str, object], language: str, developer_name: str, contact_email: str) -> str:
    app_name = str(policy["app_name"])
    local_data = policy["local_data"]
    local_processing = policy["local_processing"]
    if not isinstance(local_data, dict) or not isinstance(local_processing, dict):
        raise PublishingError(f"{app_name} privacy policy has invalid localized data")
    data_items = local_data.get(language)
    processing_items = local_processing.get(language)
    if not isinstance(data_items, list) or not data_items or not all(isinstance(item, str) and item for item in data_items):
        raise PublishingError(f"{app_name} privacy policy has invalid {language} local_data")
    if not isinstance(processing_items, list) or not processing_items or not all(isinstance(item, str) and item for item in processing_items):
        raise PublishingError(f"{app_name} privacy policy has invalid {language} local_processing")
    remote = policy.get("remote_processing")
    has_remote = isinstance(remote, dict)
    purchase = bool(policy.get("in_app_purchase"))
    bullets = lambda values: "\n".join(f"- {value}" for value in values)
    if language == "ko":
        remote_section = (
            "### 3. 선택형 서버 처리\n\n"
            + bullets(remote["data"]["ko"])
            + f"\n\n{remote['purpose']['ko']}\n"
            if has_remote
            else "### 3. 서버 전송\n\n위에 명시한 앱 기능은 ONNELLAB 서버로 파일 내용이나 사용 기록을 전송하지 않습니다.\n"
        )
        purchase_section = (
            "앱 내 구매는 Apple App Store 또는 Google Play가 처리합니다. "
            f"{app_name}와 {developer_name}은 카드번호나 은행계좌 정보에 접근하거나 저장하지 않습니다. "
            "스토어가 제공하는 상품·거래·구매 권한 정보는 구매 확인 및 복원에 사용될 수 있습니다."
            if purchase
            else "앱 구매가 발생하는 경우 결제는 해당 앱 스토어가 처리하며 ONNELLAB은 카드번호나 은행계좌 정보를 직접 처리하지 않습니다."
        )
        retention = (
            str(remote["retention"]["ko"])
            if has_remote
            else "앱이 관리하는 로컬 데이터는 해당 기능의 삭제 동작 또는 앱 삭제를 통해 기기에서 제거할 수 있습니다. 사용자가 관리하는 원본 및 결과 파일은 사용자가 직접 보관하거나 삭제합니다. ONNELLAB 서버에는 보관되는 앱 콘텐츠가 없습니다."
        )
        return f"""# {app_name} 개인정보 처리방침

이 개인정보 처리방침은 {developer_name}이 제공하는 {app_name} 앱에 적용됩니다.

**최종 업데이트:** {policy['last_updated']}

---

## 개인정보 처리방침

{app_name}는 사용자의 개인정보를 중요하게 생각하며 아래와 같은 방식으로 운영됩니다.

### 1. 계정 및 개인 식별 정보

{app_name}는 이름, 이메일 주소 또는 전화번호로 가입하거나 로그인하도록 요구하지 않습니다. 아래에 별도로 명시한 선택형 서버 기능을 제외하면 앱 콘텐츠와 사용 기록은 ONNELLAB로 전송되지 않습니다.

### 2. 앱이 접근하거나 기기에 저장하는 데이터

{bullets(data_items)}

{bullets(processing_items)}

{remote_section}
### 4. 결제 정보

{purchase_section}

### 5. 광고, 분석 및 제3자 제공

{app_name}는 광고 SDK, 사용자 행동 분석 SDK 또는 제3자 추적 도구를 사용하지 않습니다. 데이터는 위에 설명한 기능 제공 목적 외에는 판매하지 않으며, 사용자가 운영체제 공유 기능이나 다른 앱을 통해 직접 전달한 경우는 해당 서비스의 처리방침이 적용됩니다.

### 6. 보관 및 삭제

{retention}

### 7. 보안 및 아동의 개인정보

{developer_name}은 전송이 필요한 데이터에 합리적인 기술적·관리적 보호조치를 적용합니다. {app_name}는 만 13세 미만 아동을 대상으로 설계되지 않았으며 아동의 개인정보를 고의로 수집하지 않습니다.

### 8. 변경 및 문의

앱 기능이나 법적·스토어 요구사항이 변경되면 이 문서를 수정하고 최종 업데이트일을 변경합니다.

개인정보 관련 문의 또는 삭제 요청: [{contact_email}](mailto:{contact_email})
"""
    remote_section = (
        "### 3. Optional server processing\n\n"
        + bullets(remote["data"]["en"])
        + f"\n\n{remote['purpose']['en']}\n"
        if has_remote
        else "### 3. Server transmission\n\nThe app features described above do not transmit file contents or usage history to an ONNELLAB server.\n"
    )
    purchase_section = (
        "In-app purchases are processed by Apple App Store or Google Play. "
        f"Neither {app_name} nor {developer_name} accesses or stores card or bank-account details. "
        "Product, transaction, and entitlement information supplied by the store may be used to verify and restore purchases."
        if purchase
        else "If an app purchase occurs, the applicable app store processes the payment; ONNELLAB does not directly process card or bank-account details."
    )
    retention = (
        str(remote["retention"]["en"])
        if has_remote
        else "App-managed local data can be removed through the applicable delete controls or by uninstalling the app. Source and output files controlled by the user remain under the user's control. ONNELLAB retains no app content on its servers."
    )
    return f"""# {app_name} Privacy Policy

This Privacy Policy applies to the {app_name} app provided by {developer_name}.

**Last updated:** {policy['last_updated']}

---

## Privacy Policy

{app_name} values your privacy. This app operates as described below.

### 1. Accounts and direct identifiers

{app_name} does not require registration or sign-in with a name, email address, or phone number. Except for an optional server feature described below, app content and usage history are not transmitted to ONNELLAB.

### 2. Data accessed or stored on the device

{bullets(data_items)}

{bullets(processing_items)}

{remote_section}
### 4. Payment information

{purchase_section}

### 5. Advertising, analytics, and sharing

{app_name} does not use advertising SDKs, behavioral analytics SDKs, or third-party tracking tools. Data is not sold or shared outside the purposes described above. If the user deliberately hands content to another app or service through the operating-system share features, that service's policy applies.

### 6. Retention and deletion

{retention}

### 7. Security and children's privacy

{developer_name} applies reasonable technical and organizational safeguards to data that must be transmitted. {app_name} is not directed to children under 13 and does not knowingly collect personal information from children.

### 8. Changes and contact

If app functionality or legal or store requirements change, this document will be updated and its last-updated date will change.

Privacy questions or deletion requests: [{contact_email}](mailto:{contact_email})
"""


def load_privacy_policies(policies_path: Path, apps_registry_path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    if not policies_path.exists():
        raise PublishingError(f"privacy policy registry does not exist: {policies_path}")
    payload = json.loads(policies_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise PublishingError("privacy policy registry must use schema_version 1")
    policies = payload.get("policies")
    if not isinstance(policies, list):
        raise PublishingError("privacy policy registry has no policies list")
    by_slug: dict[str, dict[str, object]] = {}
    for policy in policies:
        if not isinstance(policy, dict):
            raise PublishingError("privacy policy registry contains a non-object policy")
        slug = policy.get("app_slug")
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise PublishingError(f"invalid privacy policy app_slug: {slug}")
        if slug in by_slug:
            raise PublishingError(f"duplicate privacy policy app_slug: {slug}")
        if not policy.get("app_name") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(policy.get("last_updated", ""))):
            raise PublishingError(f"{slug} privacy policy is missing app_name or a valid last_updated date")
        by_slug[slug] = policy
    with apps_registry_path.open(encoding="utf-8", newline="") as handle:
        registry = list(csv.DictReader(handle))
    public_slugs = {row["slug"] for row in registry if row.get("status") in {"beta", "released"} and row.get("product_group") == "apps"}
    missing = public_slugs - set(by_slug)
    extra = set(by_slug) - {row["slug"] for row in registry}
    if missing:
        raise PublishingError(f"public apps missing privacy policies: {', '.join(sorted(missing))}")
    if extra:
        raise PublishingError(f"privacy policies reference unknown apps: {', '.join(sorted(extra))}")
    return payload, [by_slug[slug] for slug in sorted(by_slug)]


def write_privacy_pages(
    site_dir: Path,
    site_url: str,
    policies_path: Path,
    apps_registry_path: Path,
) -> list[PrivacyPage]:
    payload, policies = load_privacy_policies(policies_path, apps_registry_path)
    developer_name = str(payload.get("developer_name") or "ONNELLAB")
    contact_email = str(payload.get("contact_email") or "")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact_email):
        raise PublishingError("privacy policy registry has an invalid contact_email")
    pages: list[PrivacyPage] = []
    for policy in policies:
        slug = str(policy["app_slug"])
        app_name = str(policy["app_name"])
        alternate_urls = {
            "en": public_url(site_url, f"privacy/{slug}/"),
            "ko": public_url(site_url, f"privacy/{slug}/ko/"),
            "x-default": public_url(site_url, f"privacy/{slug}/"),
        }
        for language, suffix in (("en", ""), ("ko", "ko/")):
            url_path = f"privacy/{slug}/{suffix}"
            output = site_dir / url_path / "index.html"
            output.parent.mkdir(parents=True, exist_ok=True)
            title = f"{app_name} {'개인정보 처리방침' if language == 'ko' else 'Privacy Policy'}"
            description = (
                f"{app_name} 앱의 개인정보 처리방침입니다."
                if language == "ko"
                else f"Privacy Policy for the {app_name} app."
            )
            home_url = public_url(site_url, "ko/" if language == "ko" else "")
            language_url = alternate_urls["en" if language == "ko" else "ko"]
            language_label = "English" if language == "ko" else "한국어"
            navigation = (
                '<nav class="topbar" aria-label="Navigation">\n'
                f'  <a class="home-link" href="{html.escape(home_url, quote=True)}">ONNELLAB</a>\n'
                f'  <a class="language-link" href="{html.escape(language_url, quote=True)}">{language_label}</a>\n'
                "</nav>"
            )
            body = navigation + "\n" + markdown_to_html(
                localized_policy_markdown(policy, language, developer_name, contact_email)
            )
            document = html_document(
                title,
                description,
                public_url(site_url, url_path),
                public_url(site_url, "feed.xml"),
                body,
                language=language,
                alternate_urls=alternate_urls,
                inline_style=PRIVACY_PAGE_STYLE,
            )
            output.write_text(document, encoding="utf-8")
            compatibility_paths = (
                site_dir / "apps" / slug / "privacy" / suffix / "index.html",
                site_dir / slug / "privacy" / suffix / "index.html",
            )
            for compatibility_output in compatibility_paths:
                compatibility_output.parent.mkdir(parents=True, exist_ok=True)
                compatibility_output.write_text(document, encoding="utf-8")
            pages.append(PrivacyPage(slug, language, url_path, output))
    return pages


def write_sitemap(
    site_dir: Path,
    site_url: str,
    articles: list[Article],
    additional_paths: list[str] | None = None,
) -> None:
    urls = [site_url] + [public_url(site_url, article.url_path) for article in articles]
    urls.extend(public_url(site_url, path) for path in (additional_paths or []))
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


def app_registry_by_name(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    registry: dict[str, dict[str, str]] = {}
    for row in rows:
        for key in (row.get("app_name", ""), row.get("slug", "")):
            if key.strip():
                registry[key.strip().casefold()] = row
    return registry


def attach_social_install_links(article: Article, registry: dict[str, dict[str, str]]) -> None:
    related_apps = [name.strip() for name in article.topic.get("related_apps", "").split("|") if name.strip()]
    for related_app in related_apps:
        app = registry.get(related_app.casefold())
        if not app:
            continue
        app_store_url = app.get("app_store_url", "").strip()
        play_store_url = app.get("play_store_url", "").strip()
        if not (app_store_url or play_store_url):
            continue
        article.topic["social_app_name"] = app.get("app_name", "").strip() or related_app
        article.topic["social_app_store_url"] = app_store_url
        article.topic["social_play_store_url"] = play_store_url
        return


def render_x_post(article: Article, site_url: str) -> str:
    return render_x_template(article, site_url, "x")


def render_x_template(article: Article, site_url: str, template_id: str) -> str:
    context = social_template_context(article, site_url, "x", template_id)
    template = load_social_template(template_id)
    rendered = render_social_template(template, context)
    if x_weighted_length(rendered) > 240:
        context["x_summary"] = ""
        rendered = render_social_template(template, context)
    if template_id == "x" and (x_weighted_length(rendered) > 240 or SOCIAL_ELLIPSIS_RE.search(rendered)):
        context["hook"] = context["title"]
        rendered = render_social_template(template, context)
    if x_weighted_length(rendered) > 240:
        raise PublishingError(f"{article.topic['id']} {template_id} cannot fit complete blocks within 240 weighted characters")
    require_social_text_without_ellipsis(article, template_id, rendered)
    return rendered


def render_bluesky_template(article: Article, site_url: str, template_id: str) -> str:
    context = social_template_context(article, site_url, "bluesky", template_id)
    template = load_social_template(template_id)
    rendered = render_social_template(template, context)
    if len(rendered) > 260:
        context["bsky_summary"] = ""
        rendered = render_social_template(template, context)
    if template_id == "bluesky" and (len(rendered) > 260 or SOCIAL_ELLIPSIS_RE.search(rendered)):
        context["hook"] = context["title"]
        rendered = render_social_template(template, context)
    if len(rendered) > 260:
        raise PublishingError(f"{article.topic['id']} {template_id} cannot fit complete blocks within 260 characters")
    require_social_text_without_ellipsis(article, template_id, rendered)
    return rendered


def render_linkedin_post(article: Article, site_url: str) -> str:
    return render_linkedin_template(article, site_url, "linkedin")


def render_linkedin_template(article: Article, site_url: str, template_id: str) -> str:
    context = social_template_context(article, site_url, "linkedin", template_id)
    template = load_social_template(template_id)
    rendered = render_social_template(template, context)
    if len(rendered) > 900:
        context["points_block"] = context["short_points_block"]
        rendered = render_social_template(template, context)
    if len(rendered) > 900:
        context["points_block"] = ""
        context["short_points"] = ""
        rendered = render_social_template(template, context)
    if len(rendered) > 900:
        context["lead"] = ""
        rendered = render_social_template(template, context)
    if len(rendered) > 900:
        raise PublishingError(f"{article.topic['id']} {template_id} cannot fit complete blocks within 900 characters")
    require_social_text_without_ellipsis(article, template_id, rendered)
    return rendered


def require_social_text_without_ellipsis(article: Article, template_id: str, text: str) -> None:
    if SOCIAL_ELLIPSIS_RE.search(text):
        raise PublishingError(f"{article.topic['id']} {template_id} contains an ellipsis; revise the complete source blocks")


def load_social_template(platform: str, template_dir: Path = DEFAULT_SOCIAL_TEMPLATE_DIR) -> str:
    path = template_dir / f"{platform}.txt"
    if not path.exists():
        raise PublishingError(f"social template does not exist: {path}")
    return path.read_text(encoding="utf-8")


def social_hook(article: Article, platform: str = "", template_id: str = "") -> str:
    title = plain_text(article.title)
    question = plain_text(article.topic["primary_question"])
    haystack = f"{title} {question} {article.description}".lower()

    def select(hooks: tuple[str, ...]) -> str:
        variant_offset = 1 if template_id and template_id != platform else 0
        return hooks[(stable_index(article.topic["id"], len(hooks)) + variant_offset) % len(hooks)]

    if "txt" in haystack and ("large" in haystack or "huge" in haystack or "lag" in haystack):
        hooks_by_platform = {
            "x": (
                "A huge TXT file should not freeze just because you opened it.",
                "A slow TXT file is often a workflow problem before it is a file problem.",
            ),
            "bluesky": (
                "Large TXT files are a good reminder that plain text can still be hard to read.",
                "Sometimes the best fix for a slow text file is changing how you open it.",
            ),
            "linkedin": (
                "Large plain-text files need a reading workflow before they need a new format.",
                "Teams often lose time on large TXT files because the first tool treats them like small notes.",
            ),
        }
        hooks = hooks_by_platform.get(
            platform,
            (
                "A huge TXT file should not freeze just because you opened it.",
                "When a TXT file feels slow, the file is not always the real problem.",
                "Large plain-text files need a reading workflow before they need a new format.",
            ),
        )
        return select(hooks)
    if "txt" in haystack and ("unreadable" in haystack or "encoding" in haystack or "utf-8" in haystack or "broken characters" in haystack):
        hooks_by_platform = {
            "x": (
                "Unreadable TXT characters usually point to an encoding mismatch.",
                "A TXT file can be valid and still look broken in the wrong encoding.",
            ),
            "bluesky": (
                "When plain text looks broken, the file is not always damaged.",
                "A text file can look unreadable simply because the app guessed the encoding wrong.",
            ),
            "linkedin": (
                "Broken-looking TXT files are often an encoding problem, not a content problem.",
                "Teams can lose time on TXT files when unreadable characters are treated as file damage too early.",
            ),
        }
        hooks = hooks_by_platform.get(platform, hooks_by_platform["x"])
        return select(hooks)
    if question.lower().startswith("how can i "):
        action = question[len("How can I ") :].rstrip("?")
        action_lower = action[0].lower() + action[1:] if action else action
        action_upper = action[0].upper() + action[1:] if action else action
        hooks_by_platform = {
            "x": (
                f"{action_upper} is easier when the process is clear before choosing an app.",
                f"Start with the constraints, then decide how to {action_lower}.",
            ),
            "bluesky": (
                f"A practical way to {action_lower} starts with the constraints, not the app.",
                f"Before you {action_lower}, separate the required result from the optional steps.",
            ),
            "linkedin": (
                f"A reliable plan for how to {action_lower} starts with the result and constraints.",
                f"The clearest way to {action_lower} is to separate the decision from the tool.",
            ),
        }
        return select(hooks_by_platform.get(platform, hooks_by_platform["x"]))
    if question:
        return question.rstrip("?") + "."
    return title


def stable_index(value: str, size: int) -> int:
    if size <= 0:
        return 0
    return sum(ord(char) for char in value) % size


def social_summary(article: Article, description: str, platform: str = "") -> str:
    haystack = f"{article.title} {article.topic['primary_question']} {description}".lower()
    if "txt" in haystack and ("large" in haystack or "huge" in haystack or "lag" in haystack):
        summaries = {
            "x": "The fix starts with how the app opens, renders, and searches the text.",
            "bluesky": "Opening the file is only step one; the reading path matters just as much.",
            "linkedin": "A good workflow separates quick reading from full editing before the tool choice is made.",
        }
        return summaries.get(platform, "The slow part is often how the app loads, renders, and searches the text.")
    if "txt" in haystack and ("unreadable" in haystack or "encoding" in haystack or "utf-8" in haystack or "broken characters" in haystack):
        summaries = {
            "x": "Start by checking encoding before converting or rewriting the file.",
            "bluesky": "The first useful check is whether the app is reading the bytes as UTF-8 or something else.",
            "linkedin": "The practical workflow is to preserve the original file, open a copy, and test the encoding before changing tools.",
        }
        return summaries.get(platform, description)
    return description


def linkedin_lead(article: Article, insight: str, description: str) -> str:
    haystack = f"{article.title} {article.topic['primary_question']} {description}".lower()
    if "txt" in haystack and ("large" in haystack or "huge" in haystack or "lag" in haystack):
        return "The useful test is simple: decide whether the file needs quick reading, search, light edits, or full editing before choosing the tool."
    if "txt" in haystack and ("unreadable" in haystack or "encoding" in haystack or "utf-8" in haystack or "broken characters" in haystack):
        return "The useful test is to keep the original file unchanged, open a copy, and check the encoding before assuming the content is damaged."
    return insight


def syndication_note(article: Article, platform: str) -> str:
    haystack = f"{article.title} {article.topic['primary_question']} {article.description}".lower()
    if "txt" in haystack and ("unreadable" in haystack or "encoding" in haystack or "utf-8" in haystack or "broken characters" in haystack):
        notes = {
            "medium": (
                "ONNELLAB note: This version keeps the troubleshooting steps first and treats app choice as context.",
                "ONNELLAB note: This edit focuses on the practical encoding checks before recommending tools.",
            ),
            "hashnode": (
                "ONNELLAB note: This version keeps the byte-to-text encoding issue visible for technical readers.",
                "ONNELLAB note: These are implementation-minded notes about text encoding and plain-text workflows.",
            ),
            "devto": (
                "ONNELLAB note: This version focuses on encoding mismatches, UTF-8 checks, and safe TXT file handling.",
                "ONNELLAB note: This is a field note for developers and power users who handle plain-text encoding issues.",
            ),
        }
        choices = notes.get(platform)
        if choices:
            return choices[stable_index(f"{article.topic['id']}:{platform}", len(choices))]
    notes = {
        "medium": (
            "ONNELLAB note: This version keeps the practical checklist and leaves the product details secondary.",
            "ONNELLAB note: This edit keeps the reader workflow first and treats the product mention as context.",
        ),
        "hashnode": (
            "ONNELLAB note: These are implementation-minded notes from our plain-text workflow research.",
            "ONNELLAB note: This version keeps the implementation trade-offs visible for technical readers.",
        ),
        "devto": (
            "ONNELLAB note: This is a field note for developers and power users who work with large text files.",
            "ONNELLAB note: This version focuses on the rendering and workflow details behind large text files.",
        ),
    }
    choices = notes.get(platform)
    if choices:
        return choices[stable_index(f"{article.topic['id']}:{platform}", len(choices))]
    return "ONNELLAB note: This is a practical checklist from our product and reading-workflow notes."


def syndication_intro(article: Article, platform: str) -> str:
    haystack = f"{article.title} {article.topic['primary_question']} {article.description}".lower()
    if "txt" in haystack and ("large" in haystack or "huge" in haystack or "lag" in haystack):
        intros = {
            "medium": (
                "The useful question is not only which app can open a large TXT file. "
                "It is what the reader needs to do after the file opens: inspect, search, bookmark, split, or edit."
            ),
            "hashnode": (
                "For large plain-text files, the practical bottleneck is usually the path from bytes to visible lines: "
                "decoding, layout, search, and memory use all show up in the reading experience."
            ),
            "devto": (
                "Large TXT files become interesting when the UI treats the whole document as one editable surface. "
                "Rendering strategy, memory pressure, and search indexing often matter more than the file extension."
            ),
        }
        return intros.get(platform, "")
    if "txt" in haystack and ("unreadable" in haystack or "encoding" in haystack or "utf-8" in haystack or "broken characters" in haystack):
        intros = {
            "medium": (
                "The first useful move is not to convert the file. "
                "It is to check whether the app is interpreting the same bytes with the right encoding."
            ),
            "hashnode": (
                "A TXT file does not carry a guaranteed visual layout. "
                "The important step is turning bytes into characters with the intended encoding."
            ),
            "devto": (
                "Unreadable text is often a decoding problem: the bytes are still there, "
                "but the app may be mapping them through the wrong character set."
            ),
        }
        return intros.get(platform, "")
    return ""


def syndication_body(article: Article, body: str, platform: str) -> str:
    haystack = f"{article.title} {article.topic['primary_question']} {article.description}".lower()
    if not ("txt" in haystack and ("large" in haystack or "huge" in haystack or "lag" in haystack)):
        return body
    if platform == "medium":
        return body.replace(
            "Large TXT files usually appear in practical workflows rather than as polished documents. You might be opening an exported chat history, a long web novel saved as plain text, a server log, a subtitle or transcript file, or a backup export from another tool.",
            "Large TXT files usually appear in practical workflows rather than polished documents. The file may be an exported chat history, a long web novel saved as plain text, a server log, a transcript, or a backup export that someone simply needs to inspect without turning it into another project.",
        )
    if platform == "hashnode":
        return body.replace(
            "Virtual rendering is a technique where an app renders only the visible portion of a large document instead of drawing every line immediately. It can reduce memory pressure and make scrolling feel more responsive. The exact implementation depends on the app, so avoid assuming that every TXT reader handles large files the same way.",
            "Virtual rendering is a common way to keep large text views responsive: the app prioritizes visible lines and avoids drawing the entire document at once. The exact implementation varies, but the important trade-off is the same: reduce memory pressure without making search and navigation feel disconnected.",
        )
    if platform == "devto":
        return body.replace(
            "Many general-purpose editors are designed for short notes or normal documents. When they open a huge text file, they may try to load the full file into memory, calculate layout for every line, and keep the whole editable document ready at all times. That can make scrolling, searching, and editing feel delayed.",
            "Many general-purpose editors are optimized for short notes or normal documents. With a huge text file, they may load the full buffer, calculate layout for every line, and keep the document ready for editing before the reader has done anything. That is where scrolling, search, and memory use start to feel connected.",
        )
    return body


def social_template_context(
    article: Article,
    site_url: str,
    platform: str = "",
    template_id: str = "",
) -> dict[str, str]:
    markdown = article.markdown_path.read_text(encoding="utf-8")
    title = plain_text(article.title)
    description = plain_text(article.description)
    canonical_url = article_public_url(article, site_url)
    app_name = article.topic.get("social_app_name", "").strip()
    app_store_url = article.topic.get("social_app_store_url", "").strip()
    play_store_url = article.topic.get("social_play_store_url", "").strip()
    use_store_install = platform in {"x", "bluesky"} and bool(app_store_url or play_store_url)
    install_links: list[str] = []
    if use_store_install and app_store_url:
        install_links.append(f"App Store: {app_store_url}")
    if use_store_install and play_store_url:
        install_links.append(f"Google Play: {play_store_url}")
    url = "\n".join(install_links) or canonical_url
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
    if use_store_install:
        cta = f"{app_name} 설치:" if article.topic["primary_language"] == "ko" else f"Install {app_name}:"
    else:
        cta = "전체 글 읽기:" if article.topic["primary_language"] == "ko" else "Read the full article:"
    insight = first_sentences(short_answer, 2)
    summary = social_summary(article, description, platform)
    lead = linkedin_lead(article, insight, description)
    points_block = f"Before changing tools:\n{key_points_text}"
    short_points_block = f"Before changing tools:\n{short_points_text}"
    return {
        "title": title,
        "hook": social_hook(article, platform, template_id),
        "question": plain_text(article.topic["primary_question"]),
        "description": description,
        "insight": insight,
        "lead": lead,
        "key_points": key_points_text,
        "short_points": short_points_text,
        "points_block": points_block,
        "short_points_block": short_points_block,
        "cta": cta,
        "url": url,
        "target_url": (app_store_url or play_store_url) if use_store_install else canonical_url,
        "destination_urls": "|".join(filter(None, (app_store_url, play_store_url))) if use_store_install else "",
        "link_strategy": "store_install" if use_store_install else "canonical_article",
        "cta_text": cta,
        "x_summary": summary if not SOCIAL_ELLIPSIS_RE.search(summary) else "",
        "bsky_summary": summary if not SOCIAL_ELLIPSIS_RE.search(summary) else "",
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
    context = social_template_context(article, site_url, template.platform, template.template_id)
    return {
        "topic_id": article.topic["id"],
        "source_status": article.topic["status"],
        "publish_after_canonical": article.topic["status"] != "published",
        "platform": template.platform,
        "language": article.topic["primary_language"],
        "category": article.topic["category"],
        "slug": article.topic["slug"],
        "template_id": template.template_id,
        "template_path": display_path(DEFAULT_SOCIAL_TEMPLATE_DIR / template.filename, project_root),
        "is_variant": template.is_variant,
        "draft_path": str(destination.relative_to(project_root)),
        "canonical_url": article_public_url(article, site_url),
        "target_url": context["target_url"],
        "destination_urls": context["destination_urls"],
        "link_strategy": context["link_strategy"],
        "cta_text": context["cta_text"],
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

SOCIAL_POSTED_HISTORY_FIELDS = (
    "canonical_url",
    "target_url",
    "destination_urls",
    "link_strategy",
    "cta_text",
    "card_asset_path",
    "weighted_length",
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
            draft_path = output_dir.parents[1] / str(post.get("draft_path", ""))
            if draft_path.exists():
                post = dict(post)
                post["_draft_text"] = draft_path.read_text(encoding="utf-8")
            state[key] = post
    return state


def apply_previous_social_state(
    item: dict[str, object], state: dict[tuple[str, str, str, str], dict[str, object]]
) -> dict[str, object] | None:
    key = (
        str(item.get("topic_id", "")),
        str(item.get("platform", "")),
        str(item.get("language", "")),
        str(item.get("template_id", "")),
    )
    previous = state.get(key)
    if not previous:
        return None
    if item.get("publish_after_canonical") is True and previous.get("status") != "posted":
        return None
    for field in SOCIAL_STATE_FIELDS:
        if field in previous:
            item[field] = previous[field]
    if previous.get("status") == "posted":
        for field in SOCIAL_POSTED_HISTORY_FIELDS:
            if field in previous:
                item[field] = previous[field]
    return previous


@contextmanager
def social_generation_lock(output_dir: Path):
    key = output_dir.resolve()
    with SOCIAL_GENERATION_LOCKS_GUARD:
        lock = SOCIAL_GENERATION_LOCKS.setdefault(key, threading.Lock())
    with lock:
        yield


@contextmanager
def social_process_lock(output_dir: Path):
    lock_dir = output_dir.parent / ".tools"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{output_dir.name}.generation.lock"
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def generate_social_posts(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    output_dir: Path = DEFAULT_SOCIAL_OUTPUT_DIR,
    site_url: str = DEFAULT_SITE_URL,
    platforms: tuple[str, ...] = ("x", "linkedin", "bluesky"),
    include_prepublication: bool = False,
) -> list[SocialPost]:
    with social_generation_lock(output_dir):
        with social_process_lock(output_dir):
            return _generate_social_posts_locked(
                topics_path, output_dir, site_url, platforms, include_prepublication
            )


def _generate_social_posts_locked(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    output_dir: Path = DEFAULT_SOCIAL_OUTPUT_DIR,
    site_url: str = DEFAULT_SITE_URL,
    platforms: tuple[str, ...] = ("x", "linkedin", "bluesky"),
    include_prepublication: bool = False,
) -> list[SocialPost]:
    site_url = normalize_site_url(site_url)
    state = previous_social_state(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    backup_dir: Path | None = None
    project_root = topics_path.parent.parent
    statuses = (
        PUBLISHABLE_STATUSES | {"draft", "image_planning", "review", "scheduled"}
        if include_prepublication
        else None
    )
    try:
        articles = load_publishable_articles(
            topics_path,
            project_root / ".social-export-check",
            site_url,
            statuses=statuses,
        )
        app_registry = app_registry_by_name(topics_path.parent / "apps_registry.csv")
        posts: list[SocialPost] = []
        manifest_items: list[dict[str, str | int]] = []
        templates = social_templates(platforms)
        for article in articles:
            if article.topic["primary_language"] not in EXTERNAL_DISTRIBUTION_LANGUAGES:
                continue
            attach_social_install_links(article, app_registry)
            card_path = write_social_card(article, project_root)
            for template in templates:
                text = render_social_template_post(article, template, site_url)
                weighted_length = x_weighted_length(text) if template.platform == "x" else len(text)
                if template.platform == "x" and weighted_length > 280:
                    raise PublishingError(f"{article.topic['id']} X post exceeds weighted length: {weighted_length}")
                if template.platform == "bluesky" and weighted_length > 300:
                    raise PublishingError(f"{article.topic['id']} Bluesky post exceeds length: {weighted_length}")
                final_destination = (
                    social_variant_destination_for(output_dir, template.template_id, article.topic)
                    if template.is_variant
                    else social_destination_for(output_dir, template.platform, article.topic)
                )
                staged_destination = staging_dir / final_destination.relative_to(output_dir)
                staged_destination.parent.mkdir(parents=True, exist_ok=True)
                item = manifest_item(
                    article, template, final_destination, card_path, site_url, project_root, weighted_length
                )
                previous = apply_previous_social_state(item, state)
                posted_history = bool(previous and previous.get("status") == "posted" and previous.get("_draft_text"))
                if posted_history:
                    text = str(previous["_draft_text"])
                staged_destination.write_text(text if posted_history else text + "\n", encoding="utf-8")
                if not template.is_variant:
                    posts.append(SocialPost(article.topic["id"], template.platform, final_destination, text))
                manifest_items.append(item)
        (staging_dir / "manifest.json").write_text(
            json.dumps({"posts": manifest_items}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        if output_dir.exists():
            backup_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.backup-", dir=output_dir.parent))
            backup_dir.rmdir()
            output_dir.rename(backup_dir)
        try:
            staging_dir.rename(output_dir)
        except Exception:
            if backup_dir is not None and backup_dir.exists() and not output_dir.exists():
                backup_dir.rename(output_dir)
            raise
        if backup_dir is not None and backup_dir.exists():
            shutil.rmtree(backup_dir)
        return posts
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)


def build_site(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    site_dir: Path = DEFAULT_SITE_DIR,
    site_url: str = DEFAULT_SITE_URL,
    privacy_policies_path: Path | None = None,
    apps_registry_path: Path | None = None,
) -> list[Article]:
    site_url = normalize_site_url(site_url)
    privacy_policies_path = privacy_policies_path or topics_path.parent / "app_privacy_policies.json"
    apps_registry_path = apps_registry_path or topics_path.parent / "apps_registry.csv"
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    write_site_icons(site_dir)
    articles = load_publishable_articles(topics_path, site_dir, site_url)
    for article in articles:
        write_social_card(article, topics_path.parent.parent)
        write_article(article, site_url)
    privacy_pages = write_privacy_pages(site_dir, site_url, privacy_policies_path, apps_registry_path)
    write_index(site_dir, site_url, articles)
    write_rss(site_dir, site_url, articles)
    write_sitemap(site_dir, site_url, articles, [page.url_path for page in privacy_pages])
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


def export_privacy_pages_to_homepage(
    site_dir: Path,
    topics_path: Path,
    homepage_repo: Path,
    dry_run: bool,
) -> list[HomepageExport]:
    policies_path = topics_path.parent / "app_privacy_policies.json"
    apps_registry_path = topics_path.parent / "apps_registry.csv"
    _, policies = load_privacy_policies(policies_path, apps_registry_path)
    exports: list[HomepageExport] = []
    for policy in policies:
        slug = str(policy["app_slug"])
        for language, suffix in (("en", ""), ("ko", "ko/")):
            source = site_dir / "apps" / slug / "privacy" / suffix / "index.html"
            destination = homepage_repo / "public" / "apps" / slug / "privacy" / suffix / "index.html"
            if not source.exists():
                raise PublishingError(f"generated privacy page does not exist: {source}")
            action = "create"
            if destination.exists():
                action = "unchanged" if destination.read_bytes() == source.read_bytes() else "overwrite"
            exports.append(HomepageExport(f"privacy-{slug}-{language}", source, destination, action))
            if dry_run or action == "unchanged":
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    return exports


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
    _ = repository
    _ = deploy_dir
    if dry_run and not homepage_repo.is_dir():
        return []
    validate_homepage_repository(homepage_repo)
    if dry_run:
        exports = export_markdown_to_homepage(topics_path, homepage_repo, dry_run=True)
        exports.extend(export_privacy_pages_to_homepage(site_dir, topics_path, homepage_repo, dry_run=True))
        return exports

    run_homepage_command(["git", "pull", "--rebase", "origin", branch], homepage_repo)
    exports = export_markdown_to_homepage(topics_path, homepage_repo, dry_run=False)
    exports.extend(export_privacy_pages_to_homepage(site_dir, topics_path, homepage_repo, dry_run=False))
    run_homepage_command(["npm", "run", "build"], homepage_repo)
    run_homepage_command(
        ["git", "add", "src/content/blog", "public/blog-assets", "public/apps", *[f"public/{name}" for name in FAVICON_ASSET_NAMES]],
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
    parser.add_argument("--privacy-policies", type=Path)
    parser.add_argument("--apps-registry", type=Path)
    parser.add_argument("--deploy", action="store_true", help="Deploy the built site to the GitHub Pages homepage repository")
    parser.add_argument("--repository", default=DEFAULT_PAGES_REPOSITORY)
    parser.add_argument("--branch", default=DEFAULT_PAGES_BRANCH)
    parser.add_argument("--homepage-repo", type=Path, default=DEFAULT_HOMEPAGE_REPOSITORY_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Preview homepage Markdown export without copying or deploying")
    parser.add_argument("--social", action="store_true", help="Generate social distribution drafts for published articles")
    args = parser.parse_args()
    try:
        articles = build_site(
            args.topics,
            args.site_dir,
            args.site_url,
            privacy_policies_path=args.privacy_policies,
            apps_registry_path=args.apps_registry,
        )
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
