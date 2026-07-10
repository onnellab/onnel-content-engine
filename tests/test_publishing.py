from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from publishing import (
    DEFAULT_HOMEPAGE_REPOSITORY_PATH,
    DEFAULT_PAGES_BRANCH,
    DEFAULT_PAGES_REPOSITORY,
    DEFAULT_SITE_URL,
    PublishingError,
    build_site,
    export_markdown_to_homepage,
)
from topic_management import write_topics


def topic_row(status: str = "scheduled") -> dict[str, str]:
    return {
        "id": "TOPIC-0001",
        "status": status,
        "category": "reading",
        "primary_question": "How can I read very large TXT files?",
        "working_title": "How to Read Very Large TXT Files",
        "slug": "read-large-txt-files",
        "primary_language": "en",
        "priority": "normal",
        "search_intent": "solve",
        "related_apps": "VaultXT",
        "primary_keyword": "large TXT files",
        "secondary_keywords": "TXT reader|large text file",
        "evergreen": "true",
        "source_type": "user_question",
        "canonical_path": "generated/markdown/en/reading/read-large-txt-files.md",
        "published_url": "",
        "scheduled_at": "2026-07-14T09:00:00+09:00",
        "published_at": "",
        "updated_at": "",
        "review_required": "true",
        "notes": "",
    }


MARKDOWN = """---
title: "How to Read Very Large TXT Files"
slug: "read-large-txt-files"
category: "reading"
language: "en"
description: "A practical guide to reading very large TXT files without unnecessary lag."
topic_id: "TOPIC-0001"
---

# How to Read Very Large TXT Files

## Question

How can I read very large TXT files?

## Short Answer

Use a reader workflow that separates file size, encoding, and search behavior before choosing an app.

## Recommended Workflow

1. Identify the file size.
2. Check the encoding.
3. Choose a stable reader.

> Treat the file as a reference document before editing it.

![Workflow diagram](/blog-assets/read-large-txt-files/workflow-diagram.svg "Workflow diagram")

| Approach | Best for |
| --- | --- |
| Render visible text | Very large TXT files |
"""


class PublishingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.topics_path = self.root / "data" / "topics.csv"
        self.markdown_path = self.root / "generated" / "markdown" / "en" / "reading" / "read-large-txt-files.md"
        self.site_dir = self.root / "site"
        self.topics_path.parent.mkdir(parents=True)
        self.markdown_path.parent.mkdir(parents=True)
        write_topics(self.topics_path, [topic_row()])
        self.markdown_path.write_text(MARKDOWN, encoding="utf-8")
        self.asset_path = self.root / "generated" / "assets" / "blog" / "read-large-txt-files" / "workflow-diagram.svg"
        self.asset_path.parent.mkdir(parents=True)
        self.asset_path.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_build_site_generates_html_rss_and_sitemap(self) -> None:
        before = self.markdown_path.read_text(encoding="utf-8")

        articles = build_site(self.topics_path, self.site_dir, "https://example.com/")

        after = self.markdown_path.read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertEqual(len(articles), 1)
        article_html = self.site_dir / "blog" / "en" / "read-large-txt-files" / "index.html"
        self.assertTrue(article_html.exists())
        self.assertTrue((self.site_dir / "index.html").exists())
        self.assertTrue((self.site_dir / "feed.xml").exists())
        self.assertTrue((self.site_dir / "sitemap.xml").exists())
        html = article_html.read_text(encoding="utf-8")
        self.assertIn("<h1>How to Read Very Large TXT Files</h1>", html)
        self.assertIn('content="A practical guide to reading very large TXT files without unnecessary lag."', html)
        self.assertIn("<blockquote>Treat the file as a reference document before editing it.</blockquote>", html)
        self.assertIn("<table>", html)
        self.assertIn('<img src="/blog-assets/read-large-txt-files/workflow-diagram.svg"', html)
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", (self.site_dir / "feed.xml").read_text(encoding="utf-8"))
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", (self.site_dir / "sitemap.xml").read_text(encoding="utf-8"))

    def test_build_rejects_publishable_topic_without_markdown(self) -> None:
        self.markdown_path.unlink()

        with self.assertRaisesRegex(PublishingError, "Markdown file does not exist"):
            build_site(self.topics_path, self.site_dir, "https://example.com/")

    def test_non_publishable_topics_are_not_built(self) -> None:
        write_topics(self.topics_path, [topic_row(status="draft")])

        articles = build_site(self.topics_path, self.site_dir, "https://example.com/")

        self.assertEqual(articles, [])
        self.assertTrue((self.site_dir / "index.html").exists())
        self.assertTrue((self.site_dir / "feed.xml").exists())
        self.assertTrue((self.site_dir / "sitemap.xml").exists())

    def test_default_github_pages_target_is_main_homepage(self) -> None:
        self.assertEqual(DEFAULT_SITE_URL, "https://onnelakin.github.io/")
        self.assertEqual(DEFAULT_PAGES_REPOSITORY, "https://github.com/onnelakin/onnelakin.github.io.git")
        self.assertEqual(DEFAULT_PAGES_BRANCH, "main")
        self.assertEqual(str(DEFAULT_HOMEPAGE_REPOSITORY_PATH), "/mnt/c/dev/onnelakin.github.io")

    def test_export_markdown_to_homepage_writes_only_blog_content(self) -> None:
        homepage = self.root / "homepage"
        (homepage / ".git").mkdir(parents=True)
        (homepage / "src" / "content" / "blog" / "en").mkdir(parents=True)
        (homepage / "src" / "content" / "blog" / "ko").mkdir(parents=True)
        (homepage / "astro.config.mjs").write_text("export default {};\n", encoding="utf-8")
        (homepage / "src" / "components").mkdir(parents=True)
        existing_site_file = homepage / "src" / "components" / "HomePage.astro"
        existing_site_file.write_text("<main>keep</main>\n", encoding="utf-8")

        exports = export_markdown_to_homepage(self.topics_path, homepage)

        destination = homepage / "src" / "content" / "blog" / "en" / "read-large-txt-files.md"
        asset_destination = homepage / "public" / "blog-assets" / "read-large-txt-files" / "workflow-diagram.svg"
        self.assertEqual(len(exports), 1)
        self.assertEqual(exports[0].action, "create")
        self.assertEqual(destination.read_text(encoding="utf-8"), MARKDOWN)
        self.assertEqual(asset_destination.read_text(encoding="utf-8"), self.asset_path.read_text(encoding="utf-8"))
        self.assertEqual(existing_site_file.read_text(encoding="utf-8"), "<main>keep</main>\n")

    def test_export_markdown_to_homepage_dry_run_does_not_copy(self) -> None:
        homepage = self.root / "homepage"
        (homepage / ".git").mkdir(parents=True)
        (homepage / "src" / "content" / "blog" / "en").mkdir(parents=True)
        (homepage / "src" / "content" / "blog" / "ko").mkdir(parents=True)
        (homepage / "astro.config.mjs").write_text("export default {};\n", encoding="utf-8")

        exports = export_markdown_to_homepage(self.topics_path, homepage, dry_run=True)

        destination = homepage / "src" / "content" / "blog" / "en" / "read-large-txt-files.md"
        asset_destination = homepage / "public" / "blog-assets" / "read-large-txt-files" / "workflow-diagram.svg"
        self.assertEqual(len(exports), 1)
        self.assertEqual(exports[0].action, "create")
        self.assertFalse(destination.exists())
        self.assertFalse(asset_destination.exists())


if __name__ == "__main__":
    unittest.main()
