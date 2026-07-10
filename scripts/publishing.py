#!/usr/bin/env python3
"""Build canonical website publishing artifacts for GitHub Pages.

Pipeline:
Markdown -> HTML -> RSS -> Sitemap -> Deployment-ready site directory.

This module does not support Blogger.
"""

from __future__ import annotations

import argparse
import html
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
DEFAULT_SITE_URL = "https://onnelakin.github.io/"
DEFAULT_PAGES_REPOSITORY = "https://github.com/onnelakin/onnelakin.github.io.git"
DEFAULT_PAGES_BRANCH = "main"
PUBLISHABLE_STATUSES = {"scheduled", "published"}

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


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

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(f"<p>{inline_markdown(' '.join(paragraph))}</p>")
            paragraph = []

    def flush_lists() -> None:
        nonlocal list_items, ordered_items
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{inline_markdown(item)}</li>" for item in list_items) + "</ul>")
            list_items = []
        if ordered_items:
            blocks.append("<ol>" + "".join(f"<li>{inline_markdown(item)}</li>" for item in ordered_items) + "</ol>")
            ordered_items = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_lists()
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        unordered = re.match(r"^-\s+(.+)$", stripped)
        ordered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            flush_lists()
            level = min(len(heading.group(1)), 6)
            blocks.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>")
        elif unordered:
            flush_paragraph()
            if ordered_items:
                flush_lists()
            list_items.append(unordered.group(1))
        elif ordered:
            flush_paragraph()
            if list_items:
                flush_lists()
            ordered_items.append(ordered.group(1))
        else:
            flush_lists()
            paragraph.append(stripped)

    flush_paragraph()
    flush_lists()
    return "\n".join(blocks)


def first_paragraph_text(markdown: str) -> str:
    _, body = parse_front_matter(markdown)
    for block in body.split("\n\n"):
        stripped = block.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
            return re.sub(r"\s+", " ", stripped)[:180]
    return ""


def html_document(title: str, description: str, canonical_url: str, feed_url: str, body_html: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description, quote=True)}">
  <link rel="canonical" href="{html.escape(canonical_url, quote=True)}">
  <link rel="alternate" type="application/rss+xml" title="ONNELLAB Content Engine RSS" href="{html.escape(feed_url, quote=True)}">
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


def article_url_path(topic: dict[str, str]) -> str:
    return f"blog/{topic['primary_language']}/{topic['slug']}/"


def load_publishable_articles(topics_path: Path, site_dir: Path, site_url: str) -> list[Article]:
    rows = read_csv(topics_path, TOPIC_HEADER)
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
        description = first_paragraph_text(markdown) or topic["primary_question"]
        url_path = article_url_path(topic)
        html_path = site_dir / url_path / "index.html"
        body_html = markdown_to_html(markdown)
        articles.append(
            Article(
                topic=topic,
                markdown_path=markdown_path,
                html_path=html_path,
                url_path=url_path,
                title=title,
                body_html=body_html,
                description=description,
            )
        )
    return articles


def write_article(article: Article, site_url: str) -> None:
    article.html_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_url = public_url(site_url, article.url_path)
    article.html_path.write_text(
        html_document(article.title, article.description, canonical_url, public_url(site_url, "feed.xml"), article.body_html),
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


def build_site(topics_path: Path = DEFAULT_TOPICS_PATH, site_dir: Path = DEFAULT_SITE_DIR, site_url: str = DEFAULT_SITE_URL) -> list[Article]:
    site_url = normalize_site_url(site_url)
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    articles = load_publishable_articles(topics_path, site_dir, site_url)
    for article in articles:
        write_article(article, site_url)
    write_index(site_dir, site_url, articles)
    write_rss(site_dir, site_url, articles)
    write_sitemap(site_dir, site_url, articles)
    return articles


def deploy_github_pages(
    site_dir: Path = DEFAULT_SITE_DIR,
    repository: str = DEFAULT_PAGES_REPOSITORY,
    branch: str = DEFAULT_PAGES_BRANCH,
    deploy_dir: Path = ROOT / ".deploy-github-pages",
) -> None:
    if not site_dir.exists():
        raise PublishingError(f"site directory does not exist: {site_dir}")
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
    subprocess.run(["git", "clone", "--branch", branch, "--single-branch", repository, str(deploy_dir)], cwd=ROOT, check=True)

    for child in deploy_dir.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in site_dir.iterdir():
        destination = deploy_dir / child.name
        if child.is_dir():
            shutil.copytree(child, destination)
        else:
            shutil.copy2(child, destination)
    subprocess.run(["git", "add", "."], cwd=deploy_dir, check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=deploy_dir)
    if diff.returncode == 0:
        shutil.rmtree(deploy_dir)
        return
    subprocess.run(["git", "commit", "-m", "Deploy GitHub Pages site"], cwd=deploy_dir, check=True)
    subprocess.run(["git", "push", "origin", f"HEAD:{branch}"], cwd=deploy_dir, check=True)
    shutil.rmtree(deploy_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ONNELLAB GitHub Pages publishing artifacts")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--site-dir", type=Path, default=DEFAULT_SITE_DIR)
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    parser.add_argument("--deploy", action="store_true", help="Deploy the built site to the GitHub Pages homepage repository")
    parser.add_argument("--repository", default=DEFAULT_PAGES_REPOSITORY)
    parser.add_argument("--branch", default=DEFAULT_PAGES_BRANCH)
    args = parser.parse_args()
    try:
        articles = build_site(args.topics, args.site_dir, args.site_url)
        if args.deploy:
            deploy_github_pages(args.site_dir, repository=args.repository, branch=args.branch)
    except (PublishingError, TopicError, OSError, subprocess.CalledProcessError) as error:
        print(f"publishing failed: {error}", file=sys.stderr)
        return 1
    print(f"built {len(articles)} article(s) in {args.site_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
