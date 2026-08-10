from __future__ import annotations

import tempfile
import unittest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

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
    generate_social_posts,
    x_weighted_length,
)
from approve_due_distribution import approve_due_distribution
from check_distribution_supply import DistributionSupplyError, require_distribution_supply
from evaluate_social_templates import evaluate_social_templates, repetition_warnings
from approve_social_post import SocialApprovalError, approve_social_post
from generate_syndication_drafts import generate_syndication_drafts
from hashnode_content import HASHNODE_CONTENT_PROFILE, hashnode_automod_risks
from evaluate_syndication_drafts import evaluate_syndication_drafts
from approve_syndication_draft import SyndicationApprovalError, approve_syndication_draft
from check_publishing_credentials import credential_report, credential_status
from publishing_adapters import AdapterError, missing_credentials, require_adapter_ready
from post_social_drafts import SocialPostingError, bluesky_link_facets, post_bluesky_text, post_social_drafts
from check_bluesky_connection import check_bluesky_connection
from reset_failed_social_post import SocialResetError, reset_failed_social_post
from post_syndication_drafts import SyndicationPostingError, hashnode_payload, post_syndication_drafts
from publishing_dry_run_report import publishing_dry_run_report
from social_post_report import social_post_report
from syndication_report import syndication_report
from topic_management import write_topics
from validate_social_posts import validate_social_posts
from validate_syndication_drafts import validate_syndication_drafts


def topic_row(status: str = "published", topic_id: str = "TOPIC-0001", language: str = "en") -> dict[str, str]:
    return {
        "id": topic_id,
        "status": status,
        "category": "reading",
        "primary_question": "How can I read very large TXT files?",
        "working_title": "How to Read Very Large TXT Files",
        "slug": "read-large-txt-files",
        "primary_language": language,
        "priority": "normal",
        "search_intent": "solve",
        "related_apps": "VaultXT",
        "primary_keyword": "large TXT files",
        "secondary_keywords": "TXT reader|large text file",
        "evergreen": "true",
        "source_type": "user_question",
        "canonical_path": f"generated/markdown/{language}/reading/read-large-txt-files.md",
        "published_url": f"https://example.com/blog/{language}/read-large-txt-files/",
        "scheduled_at": "2026-07-14T09:00:00+09:00",
        "published_at": "2026-07-14T09:00:00+09:00",
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
related_articles: "Encoding Basics => https://example.com/blog/en/encoding-basics/"
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

![Workflow diagram](/blog-assets/en/read-large-txt-files/workflow-diagram.svg "Workflow diagram")

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
        self.ko_markdown_path = self.root / "generated" / "markdown" / "ko" / "reading" / "read-large-txt-files.md"
        self.site_dir = self.root / "site"
        self.topics_path.parent.mkdir(parents=True)
        self.markdown_path.parent.mkdir(parents=True)
        self.ko_markdown_path.parent.mkdir(parents=True)
        write_topics(self.topics_path, [topic_row(), topic_row(topic_id="TOPIC-0002", language="ko")])
        (self.topics_path.parent / "apps_registry.csv").write_text(
            "slug,status,product_group\n"
            "vaultxt,released,apps\n",
            encoding="utf-8",
        )
        (self.topics_path.parent / "app_privacy_policies.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "developer_name": "ONNELLAB",
                    "contact_email": "privacy@example.com",
                    "policies": [
                        {
                            "app_slug": "vaultxt",
                            "app_name": "VaultXT",
                            "last_updated": "2026-07-30",
                            "legacy_urls": [],
                            "in_app_purchase": True,
                            "local_data": {
                                "en": ["Plain-text files selected by the user"],
                                "ko": ["사용자가 선택한 일반 텍스트 파일"],
                            },
                            "local_processing": {
                                "en": ["Files are processed on the device."],
                                "ko": ["파일은 기기에서 처리됩니다."],
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.markdown_path.write_text(MARKDOWN, encoding="utf-8")
        self.ko_markdown_path.write_text(
            MARKDOWN.replace('language: "en"', 'language: "ko"').replace('/blog-assets/en/', '/blog-assets/ko/'),
            encoding="utf-8",
        )
        self.asset_path = self.root / "generated" / "assets" / "blog" / "en" / "read-large-txt-files" / "workflow-diagram.svg"
        self.ko_asset_path = self.root / "generated" / "assets" / "blog" / "ko" / "read-large-txt-files" / "workflow-diagram.svg"
        self.asset_path.parent.mkdir(parents=True)
        self.ko_asset_path.parent.mkdir(parents=True)
        self.asset_path.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n", encoding="utf-8")
        self.ko_asset_path.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_private_draft_topic(self) -> dict[str, str]:
        private = topic_row(status="draft", topic_id="TOPIC-0012")
        private.update(
            {
                "category": "research",
                "working_title": "Private Draft",
                "slug": "private-draft",
                "canonical_path": "generated/markdown/en/research/private-draft.md",
                "published_url": "https://example.com/blog/en/private-draft/",
            }
        )
        private_path = self.root / private["canonical_path"]
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_text(
            MARKDOWN.replace('title: "How to Read Very Large TXT Files"', 'title: "Private Draft"')
            .replace('slug: "read-large-txt-files"', 'slug: "private-draft"')
            .replace('category: "reading"', 'category: "research"')
            .replace('topic_id: "TOPIC-0001"', 'topic_id: "TOPIC-0012"'),
            encoding="utf-8",
        )
        return private

    def test_build_site_generates_html_rss_and_sitemap(self) -> None:
        before = self.markdown_path.read_text(encoding="utf-8")

        articles = build_site(self.topics_path, self.site_dir, "https://example.com/")

        after = self.markdown_path.read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertEqual(len(articles), 2)
        article_html = self.site_dir / "blog" / "en" / "read-large-txt-files" / "index.html"
        self.assertTrue(article_html.exists())
        self.assertTrue((self.site_dir / "index.html").exists())
        self.assertTrue((self.site_dir / "feed.xml").exists())
        self.assertTrue((self.site_dir / "sitemap.xml").exists())
        privacy_en = self.site_dir / "privacy" / "vaultxt" / "index.html"
        privacy_ko = self.site_dir / "privacy" / "vaultxt" / "ko" / "index.html"
        privacy_apps_en = self.site_dir / "apps" / "vaultxt" / "privacy" / "index.html"
        privacy_apps_ko = self.site_dir / "apps" / "vaultxt" / "privacy" / "ko" / "index.html"
        privacy_legacy_en = self.site_dir / "vaultxt" / "privacy" / "index.html"
        privacy_legacy_ko = self.site_dir / "vaultxt" / "privacy" / "ko" / "index.html"
        self.assertTrue(privacy_en.exists())
        self.assertTrue(privacy_ko.exists())
        self.assertTrue(privacy_apps_en.exists())
        self.assertTrue(privacy_apps_ko.exists())
        self.assertTrue(privacy_legacy_en.exists())
        self.assertTrue(privacy_legacy_ko.exists())
        privacy_en_html = privacy_en.read_text(encoding="utf-8")
        privacy_ko_html = privacy_ko.read_text(encoding="utf-8")
        self.assertIn("VaultXT Privacy Policy", privacy_en_html)
        self.assertIn("VaultXT 개인정보 처리방침", privacy_ko_html)
        self.assertIn('--background: #faf8f5;', privacy_en_html)
        self.assertIn('font-family: "SUIT Variable";', privacy_en_html)
        self.assertIn('<nav class="topbar" aria-label="Navigation">', privacy_en_html)
        self.assertIn('<a class="home-link" href="https://example.com/">ONNELLAB</a>', privacy_en_html)
        self.assertIn(
            '.home-link { color: #737067; font-family: "Avenir Next", Avenir, "Helvetica Neue", Arial, sans-serif;',
            privacy_en_html,
        )
        self.assertIn(
            '<a class="language-link" href="https://example.com/privacy/vaultxt/ko/">한국어</a>',
            privacy_en_html,
        )
        self.assertIn('<a class="home-link" href="https://example.com/ko/">ONNELLAB</a>', privacy_ko_html)
        self.assertIn(
            '<a class="language-link" href="https://example.com/privacy/vaultxt/">English</a>',
            privacy_ko_html,
        )
        self.assertLess(privacy_en_html.index('class="home-link"'), privacy_en_html.index("<h1>"))
        self.assertLess(privacy_en_html.index('class="language-link"'), privacy_en_html.index("<h1>"))
        self.assertIn("<hr>", privacy_en_html)
        self.assertIn("<h2>Privacy Policy</h2>", privacy_en_html)
        self.assertIn("<h3>1. Accounts and direct identifiers</h3>", privacy_en_html)
        self.assertIn(
            '<link rel="canonical" href="https://example.com/privacy/vaultxt/">',
            privacy_apps_en.read_text(encoding="utf-8"),
        )
        self.assertIn(
            '<link rel="canonical" href="https://example.com/privacy/vaultxt/ko/">',
            privacy_legacy_ko.read_text(encoding="utf-8"),
        )
        self.assertIn("https://example.com/privacy/vaultxt/", (self.site_dir / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertTrue((self.site_dir / "favicon.svg").exists())
        self.assertTrue((self.site_dir / "favicon-32x32.png").exists())
        self.assertTrue((self.site_dir / "apple-touch-icon.png").exists())
        self.assertTrue((self.site_dir / "site.webmanifest").exists())
        html = article_html.read_text(encoding="utf-8")
        self.assertIn("<h1>How to Read Very Large TXT Files</h1>", html)
        self.assertIn('content="A practical guide to reading very large TXT files without unnecessary lag."', html)
        self.assertIn('<link rel="icon" href="/favicon.svg?v=20260712-ol-transparent-v2" type="image/svg+xml">', html)
        self.assertIn('<link rel="apple-touch-icon" href="/apple-touch-icon.png?v=20260712-ol-transparent-v2">', html)
        self.assertIn('<link rel="manifest" href="/site.webmanifest?v=20260712-ol-transparent-v2">', html)
        self.assertIn("<blockquote>Treat the file as a reference document before editing it.</blockquote>", html)
        self.assertIn("<table>", html)
        self.assertIn('<section class="related-articles"', html)
        self.assertIn("<h3>Encoding Basics</h3>", html)
        self.assertIn('<a class="related-article-link" href="https://example.com/blog/en/encoding-basics/">Read article</a>', html)
        self.assertIn('<img src="/blog-assets/en/read-large-txt-files/workflow-diagram.svg"', html)
        self.assertIn('<meta property="og:title" content="How to Read Very Large TXT Files">', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
        self.assertIn(
            '<meta name="twitter:image" content="https://example.com/blog-assets/en/read-large-txt-files/social-card.png">',
            html,
        )
        self.assertTrue((self.root / "generated" / "assets" / "blog" / "en" / "read-large-txt-files" / "social-card.svg").exists())
        self.assertTrue((self.root / "generated" / "assets" / "blog" / "en" / "read-large-txt-files" / "social-card.png").exists())
        en_card_svg = self.root / "generated" / "assets" / "blog" / "en" / "read-large-txt-files" / "social-card.svg"
        self.assertIn("READING · EN", en_card_svg.read_text(encoding="utf-8"))
        self.assertNotIn("ONNELLAB Article", en_card_svg.read_text(encoding="utf-8"))
        ko_card_svg = self.root / "generated" / "assets" / "blog" / "ko" / "read-large-txt-files" / "social-card.svg"
        ko_svg = ko_card_svg.read_text(encoding="utf-8")
        self.assertIn("ONNELLAB Korean", ko_svg)
        self.assertIn("READING · KO", ko_svg)
        self.assertNotIn("ONNELLAB 아티클", ko_svg)
        self.assertIn('text-anchor="end">ONNELLAB</text>', ko_svg)
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", (self.site_dir / "feed.xml").read_text(encoding="utf-8"))
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", (self.site_dir / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn('"short_name": "ONNELLAB"', (self.site_dir / "site.webmanifest").read_text(encoding="utf-8"))
        self.assertIn('/favicon.svg?v=20260712-ol-transparent-v2', (self.site_dir / "site.webmanifest").read_text(encoding="utf-8"))

    def test_build_rejects_publishable_topic_without_markdown(self) -> None:
        self.markdown_path.unlink()

        with self.assertRaisesRegex(PublishingError, "Markdown file does not exist"):
            build_site(self.topics_path, self.site_dir, "https://example.com/")

    def test_non_published_topics_are_not_built(self) -> None:
        write_topics(self.topics_path, [topic_row(status="scheduled"), topic_row(status="scheduled", topic_id="TOPIC-0002", language="ko")])

        articles = build_site(self.topics_path, self.site_dir, "https://example.com/")

        self.assertEqual(articles, [])
        self.assertTrue((self.site_dir / "index.html").exists())
        self.assertTrue((self.site_dir / "feed.xml").exists())
        self.assertTrue((self.site_dir / "sitemap.xml").exists())

    def test_published_topic_requires_language_counterpart(self) -> None:
        write_topics(self.topics_path, [topic_row()])

        with self.assertRaisesRegex(PublishingError, "missing language counterpart"):
            build_site(self.topics_path, self.site_dir, "https://example.com/")

    def test_default_github_pages_target_is_main_homepage(self) -> None:
        self.assertEqual(DEFAULT_SITE_URL, "https://onnellab.github.io/")
        self.assertEqual(DEFAULT_PAGES_REPOSITORY, "https://github.com/onnellab/onnellab.github.io.git")
        self.assertEqual(DEFAULT_PAGES_BRANCH, "main")
        self.assertEqual(str(DEFAULT_HOMEPAGE_REPOSITORY_PATH), "/mnt/c/dev/onnellab.github.io")

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
        ko_destination = homepage / "src" / "content" / "blog" / "ko" / "read-large-txt-files.md"
        asset_destination = homepage / "public" / "blog-assets" / "en" / "read-large-txt-files" / "workflow-diagram.svg"
        ko_asset_destination = homepage / "public" / "blog-assets" / "ko" / "read-large-txt-files" / "workflow-diagram.svg"
        social_card_destination = homepage / "public" / "blog-assets" / "en" / "read-large-txt-files" / "social-card.png"
        social_card_svg_destination = homepage / "public" / "blog-assets" / "en" / "read-large-txt-files" / "social-card.svg"
        favicon_destination = homepage / "public" / "favicon.svg"
        favicon_png_destination = homepage / "public" / "favicon-32x32.png"
        manifest_destination = homepage / "public" / "site.webmanifest"
        self.assertEqual(len(exports), 2)
        self.assertEqual(exports[0].action, "create")
        self.assertEqual(destination.read_text(encoding="utf-8"), MARKDOWN)
        self.assertEqual(ko_destination.read_text(encoding="utf-8"), self.ko_markdown_path.read_text(encoding="utf-8"))
        self.assertEqual(asset_destination.read_text(encoding="utf-8"), self.asset_path.read_text(encoding="utf-8"))
        self.assertEqual(ko_asset_destination.read_text(encoding="utf-8"), self.ko_asset_path.read_text(encoding="utf-8"))
        self.assertTrue(social_card_destination.exists())
        self.assertTrue(social_card_svg_destination.exists())
        self.assertTrue(favicon_destination.exists())
        self.assertTrue(favicon_png_destination.exists())
        self.assertIn('/favicon.svg?v=20260712-ol-transparent-v2', manifest_destination.read_text(encoding="utf-8"))
        self.assertEqual(existing_site_file.read_text(encoding="utf-8"), "<main>keep</main>\n")

    def test_export_markdown_to_homepage_dry_run_does_not_copy(self) -> None:
        homepage = self.root / "homepage"
        (homepage / ".git").mkdir(parents=True)
        (homepage / "src" / "content" / "blog" / "en").mkdir(parents=True)
        (homepage / "src" / "content" / "blog" / "ko").mkdir(parents=True)
        (homepage / "astro.config.mjs").write_text("export default {};\n", encoding="utf-8")

        exports = export_markdown_to_homepage(self.topics_path, homepage, dry_run=True)

        destination = homepage / "src" / "content" / "blog" / "en" / "read-large-txt-files.md"
        asset_destination = homepage / "public" / "blog-assets" / "en" / "read-large-txt-files" / "workflow-diagram.svg"
        self.assertEqual(len(exports), 2)
        self.assertEqual(exports[0].action, "create")
        self.assertFalse(destination.exists())
        self.assertFalse(asset_destination.exists())

    def test_generate_social_posts_for_linkedin_and_x(self) -> None:
        social_dir = self.root / "generated" / "social"

        posts = generate_social_posts(self.topics_path, social_dir, "https://example.com/")

        self.assertEqual(len(posts), 3)
        x_path = social_dir / "x" / "en" / "reading" / "read-large-txt-files.txt"
        linkedin_path = social_dir / "linkedin" / "en" / "reading" / "read-large-txt-files.txt"
        bluesky_path = social_dir / "bluesky" / "en" / "reading" / "read-large-txt-files.txt"
        self.assertTrue(x_path.exists())
        self.assertTrue(linkedin_path.exists())
        self.assertTrue(bluesky_path.exists())
        x_text = x_path.read_text(encoding="utf-8").strip()
        linkedin_text = linkedin_path.read_text(encoding="utf-8").strip()
        bluesky_text = bluesky_path.read_text(encoding="utf-8").strip()
        self.assertLessEqual(len(x_text), 280)
        self.assertLessEqual(x_weighted_length(x_text), 280)
        self.assertLessEqual(x_weighted_length(x_text), 240)
        self.assertLessEqual(len(bluesky_text), 300)
        self.assertIn("A slow TXT file is often a workflow problem before it is a file problem.", x_text)
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", x_text)
        self.assertIn("Sometimes the best fix for a slow text file is changing how you open it.", bluesky_text)
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", bluesky_text)
        self.assertIn("Teams often lose time on large TXT files because the first tool treats them like small notes.", linkedin_text)
        self.assertIn("Identify the file size.", linkedin_text)
        self.assertIn("Check the encoding.", linkedin_text)
        self.assertNotIn("{{", linkedin_text)
        self.assertIn("Read the full article:", linkedin_text)
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", linkedin_text)
        self.assertLessEqual(len(linkedin_text), 900)
        x_variant_text = (social_dir / "variants" / "x_question" / "en" / "reading" / "read-large-txt-files.txt").read_text(encoding="utf-8")
        bluesky_variant_text = (social_dir / "variants" / "bluesky_question" / "en" / "reading" / "read-large-txt-files.txt").read_text(encoding="utf-8")
        linkedin_variant_text = (social_dir / "variants" / "linkedin_short" / "en" / "reading" / "read-large-txt-files.txt").read_text(encoding="utf-8")
        self.assertNotEqual(x_text.splitlines()[0], x_variant_text.splitlines()[0])
        self.assertNotEqual(bluesky_text.splitlines()[0], bluesky_variant_text.splitlines()[0])
        self.assertNotEqual(linkedin_text.splitlines()[0], linkedin_variant_text.splitlines()[0])
        manifest = (social_dir / "manifest.json").read_text(encoding="utf-8")
        self.assertIn('"status": "draft"', manifest)
        self.assertIn('"status": "variant"', manifest)
        self.assertIn('"template_id": "x"', manifest)
        self.assertIn('"template_id": "x_question"', manifest)
        self.assertIn('"template_id": "bluesky"', manifest)
        self.assertIn('"template_id": "bluesky_question"', manifest)
        self.assertIn('"card_asset_path":', manifest)
        self.assertNotIn('"language": "ko"', manifest)
        self.assertIn('"approved_by": ""', manifest)
        self.assertIn('"post_id": ""', manifest)
        self.assertIn('"error_type": ""', manifest)
        self.assertIn('"retry_count": 0', manifest)
        self.assertIn('"impressions": 0', manifest)
        self.assertEqual(validate_social_posts(social_dir / "manifest.json", self.root), 6)
        self.assertEqual(evaluate_social_templates(social_dir / "manifest.json", self.root)["repetition_warnings"], [])

        approved = approve_social_post(
            "TOPIC-0001",
            "x",
            "en",
            "editor",
            social_dir / "manifest.json",
        )

        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["approved_by"], "editor")
        report = social_post_report(social_dir / "manifest.json")
        self.assertIn("ready for mock posting: TOPIC-0001 x en x", report)

        dry_run_posts = post_social_drafts(social_dir / "manifest.json", platform="x", dry_run=True)
        self.assertEqual(len(dry_run_posts), 1)
        posted = post_social_drafts(social_dir / "manifest.json", platform="x", adapter="mock")

        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]["status"], "posted")
        self.assertTrue(str(posted[0]["post_id"]).startswith("mock-TOPIC-0001-x-en-x"))
        self.assertIn("mock-social/x/en/TOPIC-0001/x", str(posted[0]["posted_url"]))
        self.assertIn("X_REFRESH_TOKEN", missing_credentials("x", {}))
        self.assertIn("BLUESKY_HANDLE", missing_credentials("bluesky", {}))
        self.assertIn("bluesky: not ready", credential_report("bluesky"))
        with self.assertRaises(AdapterError):
            require_adapter_ready("bluesky", "social", {})

    def test_product_social_posts_use_direct_store_install_links(self) -> None:
        (self.root / "data" / "apps_registry.csv").write_text(
            "app_id,app_name,slug,app_store_url,play_store_url\n"
            "APP-0003,VaultXT,vaultxt,https://apps.apple.com/app/id6760122045,"
            "https://play.google.com/store/apps/details?id=com.onnellab.vaultxt\n",
            encoding="utf-8",
        )
        social_dir = self.root / "generated" / "social"

        generate_social_posts(self.topics_path, social_dir, "https://example.com/")

        manifest = json.loads((social_dir / "manifest.json").read_text(encoding="utf-8"))
        x_post = next(post for post in manifest["posts"] if post["template_id"] == "x")
        x_text = (self.root / x_post["draft_path"]).read_text(encoding="utf-8")
        linkedin_post = next(post for post in manifest["posts"] if post["template_id"] == "linkedin")
        linkedin_text = (self.root / linkedin_post["draft_path"]).read_text(encoding="utf-8")

        self.assertEqual(x_post["link_strategy"], "store_install")
        self.assertEqual(x_post["target_url"], "https://apps.apple.com/app/id6760122045")
        self.assertIn("App Store: https://apps.apple.com/app/id6760122045", x_text)
        self.assertIn("Google Play: https://play.google.com/store/apps/details?id=com.onnellab.vaultxt", x_text)
        self.assertNotIn("https://example.com/blog/", x_text)
        self.assertIn("Install VaultXT:", linkedin_text)
        self.assertEqual(validate_social_posts(social_dir / "manifest.json", self.root), 6)

    def test_prepublication_social_posts_can_be_prepared_before_release(self) -> None:
        rows = [topic_row(status="draft"), topic_row(status="draft", topic_id="TOPIC-0002", language="ko")]
        write_topics(self.topics_path, rows)
        social_dir = self.root / "generated" / "social"

        posts = generate_social_posts(
            self.topics_path,
            social_dir,
            "https://example.com/",
            include_prepublication=True,
        )

        self.assertEqual(len(posts), 3)
        manifest = json.loads((social_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(all(post["source_status"] == "draft" for post in manifest["posts"]))
        self.assertTrue(all(post["publish_after_canonical"] for post in manifest["posts"]))
        self.assertEqual(validate_social_posts(social_dir / "manifest.json", self.root), 6)
        x_post = next(post for post in manifest["posts"] if post["template_id"] == "x")
        x_post.pop("publish_after_canonical")
        x_post.pop("source_status")
        (social_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(SocialApprovalError):
            approve_social_post("TOPIC-0001", "x", "en", "editor", social_dir / "manifest.json")

    def test_prepublication_social_regeneration_resets_unposted_state(self) -> None:
        social_dir = self.root / "generated" / "social"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        manifest_path = social_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        x_post = next(post for post in manifest["posts"] if post["template_id"] == "x")
        x_variant = next(post for post in manifest["posts"] if post["template_id"] == "x_question")
        for post, status in ((x_post, "approved"), (x_variant, "failed")):
            post.update(
                {
                    "status": status,
                    "approved_by": "editor",
                    "approved_at": "2026-07-20T09:00:00+09:00",
                    "post_id": "stale-id",
                    "posted_url": "https://social.example/stale",
                    "posted_at": "2026-07-20T10:00:00+09:00",
                    "last_attempt_at": "2026-07-20T10:00:00+09:00",
                    "error": "temporary failure",
                    "error_type": "transient",
                    "retry_count": 2,
                    "impressions": 10,
                    "clicks": 3,
                    "engagements": 4,
                    "last_metrics_at": "2026-07-21T09:00:00+09:00",
                }
            )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        write_topics(
            self.topics_path,
            [topic_row(status="draft"), topic_row(status="draft", topic_id="TOPIC-0002", language="ko")],
        )

        generate_social_posts(
            self.topics_path,
            social_dir,
            "https://example.com/",
            include_prepublication=True,
        )

        regenerated = json.loads(manifest_path.read_text(encoding="utf-8"))
        for template_id, expected_status in (("x", "draft"), ("x_question", "variant")):
            with self.subTest(template_id=template_id):
                post = next(item for item in regenerated["posts"] if item["template_id"] == template_id)
                self.assertTrue(post["publish_after_canonical"])
                self.assertEqual(post["status"], expected_status)
                for field in (
                    "approved_by",
                    "approved_at",
                    "post_id",
                    "posted_url",
                    "posted_at",
                    "last_attempt_at",
                    "error",
                    "error_type",
                    "last_metrics_at",
                ):
                    self.assertEqual(post[field], "")
                for field in ("retry_count", "impressions", "clicks", "engagements"):
                    self.assertEqual(post[field], 0)

    def test_prepublication_social_regeneration_preserves_posted_state_and_copy(self) -> None:
        social_dir = self.root / "generated" / "social"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        manifest_path = social_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        posted = next(post for post in manifest["posts"] if post["template_id"] == "x")
        original_text = (self.root / posted["draft_path"]).read_text(encoding="utf-8")
        posted.update(
            {
                "status": "posted",
                "approved_by": "editor",
                "approved_at": "2026-07-20T09:00:00+09:00",
                "post_id": "1234",
                "posted_url": "https://social.example/1234",
                "posted_at": "2026-07-20T10:00:00+09:00",
                "last_attempt_at": "2026-07-20T10:00:00+09:00",
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        write_topics(
            self.topics_path,
            [topic_row(status="draft"), topic_row(status="draft", topic_id="TOPIC-0002", language="ko")],
        )

        generate_social_posts(
            self.topics_path,
            social_dir,
            "https://example.com/",
            include_prepublication=True,
        )

        regenerated = json.loads(manifest_path.read_text(encoding="utf-8"))
        posted = next(post for post in regenerated["posts"] if post["template_id"] == "x")
        self.assertTrue(posted["publish_after_canonical"])
        self.assertEqual(posted["status"], "posted")
        self.assertEqual(posted["approved_by"], "editor")
        self.assertEqual(posted["post_id"], "1234")
        self.assertEqual(posted["posted_url"], "https://social.example/1234")
        self.assertEqual(posted["posted_at"], "2026-07-20T10:00:00+09:00")
        self.assertEqual((self.root / posted["draft_path"]).read_text(encoding="utf-8"), original_text)

    def test_prepublication_social_posting_fails_closed_before_dry_run_or_adapter(self) -> None:
        rows = [topic_row(status="draft"), topic_row(status="draft", topic_id="TOPIC-0002", language="ko")]
        write_topics(self.topics_path, rows)
        social_dir = self.root / "generated" / "social"
        generate_social_posts(
            self.topics_path,
            social_dir,
            "https://example.com/",
            include_prepublication=True,
        )
        manifest_path = social_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        x_post = next(post for post in manifest["posts"] if post["template_id"] == "x")
        x_post["status"] = "approved"
        x_post["approved_by"] = "tampered-client"
        x_post["approved_at"] = "2026-07-20T09:00:00+09:00"
        x_post.pop("publish_after_canonical")
        x_post.pop("source_status")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        with patch("post_social_drafts.require_adapter_ready") as adapter_preflight:
            with self.assertRaisesRegex(SocialPostingError, "before canonical publication"):
                post_social_drafts(manifest_path, platform="x", adapter="x", dry_run=True)

        adapter_preflight.assert_not_called()

    def test_social_topic_identity_swap_fails_approval_and_posting_before_adapter(self) -> None:
        private = self.write_private_draft_topic()
        write_topics(
            self.topics_path,
            [topic_row(), topic_row(topic_id="TOPIC-0002", language="ko"), private],
        )
        social_dir = self.root / "generated" / "social"
        generate_social_posts(
            self.topics_path,
            social_dir,
            "https://example.com/",
            include_prepublication=True,
        )
        manifest_path = social_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["posts"] = [post for post in manifest["posts"] if post["topic_id"] == "TOPIC-0012"]
        swapped = next(post for post in manifest["posts"] if post["template_id"] == "x")
        swapped.update(
            {
                "topic_id": "TOPIC-0001",
                "source_status": "published",
                "publish_after_canonical": False,
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(SocialApprovalError, "manifest slug"):
            approve_social_post("TOPIC-0001", "x", "en", "editor", manifest_path)

        swapped.update(
            {
                "status": "approved",
                "approved_by": "tampered-client",
                "approved_at": "2026-07-20T09:00:00+09:00",
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        with patch("post_social_drafts.require_adapter_ready") as adapter_preflight:
            with self.assertRaisesRegex(SocialPostingError, "manifest slug"):
                post_social_drafts(manifest_path, platform="x", adapter="x", dry_run=True)
        adapter_preflight.assert_not_called()

    def test_social_regeneration_preserves_already_posted_copy(self) -> None:
        social_dir = self.root / "generated" / "social"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        manifest_path = social_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        posted = next(post for post in manifest["posts"] if post["template_id"] == "x")
        original_text = (self.root / posted["draft_path"]).read_text(encoding="utf-8")
        posted["status"] = "posted"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        (self.root / "data" / "apps_registry.csv").write_text(
            "app_id,app_name,slug,app_store_url,play_store_url\n"
            "APP-0003,VaultXT,vaultxt,https://apps.apple.com/app/id6760122045,"
            "https://play.google.com/store/apps/details?id=com.onnellab.vaultxt\n",
            encoding="utf-8",
        )

        generate_social_posts(self.topics_path, social_dir, "https://example.com/")

        regenerated = json.loads(manifest_path.read_text(encoding="utf-8"))
        posted = next(post for post in regenerated["posts"] if post["template_id"] == "x")
        self.assertEqual((self.root / posted["draft_path"]).read_text(encoding="utf-8"), original_text)
        self.assertEqual(posted["link_strategy"], "canonical_article")
        self.assertEqual(posted["target_url"], posted["canonical_url"])

    def test_repetition_gate_ignores_posted_history_and_mutually_exclusive_variants(self) -> None:
        social_dir = self.root / "generated" / "social" / "repetition-test"
        social_dir.mkdir(parents=True)
        posts = []
        for index, (is_variant, status) in enumerate(
            [(False, "draft"), (True, "variant"), (True, "variant"), (False, "posted")]
        ):
            path = social_dir / f"post-{index}.txt"
            path.write_text("This workflow problem should not be counted as four active posts.\n", encoding="utf-8")
            posts.append({"draft_path": str(path.relative_to(self.root)), "is_variant": is_variant, "status": status})

        self.assertEqual(repetition_warnings(posts, self.root), [])

        for post in posts:
            post["is_variant"] = False
            post["status"] = "draft"
        self.assertEqual(repetition_warnings(posts, self.root), [{"phrase": "workflow problem", "count": 4, "severity": "warning"}])

    def test_distribution_generation_preserves_manifest_state(self) -> None:
        social_dir = self.root / "generated" / "social"
        syndication_dir = self.root / "generated" / "syndication"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        generate_syndication_drafts(self.topics_path, syndication_dir, "https://example.com/")
        approve_social_post("TOPIC-0001", "x", "en", "editor", social_dir / "manifest.json")
        approve_syndication_draft("TOPIC-0001", "devto", "en", "editor", syndication_dir / "manifest.json")

        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        generate_syndication_drafts(self.topics_path, syndication_dir, "https://example.com/")

        social_manifest = json.loads((social_dir / "manifest.json").read_text(encoding="utf-8"))
        x_post = next(
            post
            for post in social_manifest["posts"]
            if post["platform"] == "x" and post["language"] == "en" and not post["is_variant"]
        )
        self.assertEqual(x_post["status"], "approved")
        self.assertEqual(x_post["approved_by"], "editor")
        syndication_manifest = json.loads((syndication_dir / "manifest.json").read_text(encoding="utf-8"))
        devto_draft = next(
            draft for draft in syndication_manifest["drafts"] if draft["platform"] == "devto" and draft["language"] == "en"
        )
        self.assertEqual(devto_draft["status"], "approved")
        self.assertEqual(devto_draft["approved_by"], "editor")

    def test_approve_due_distribution_uses_staggered_core_cadence(self) -> None:
        social_dir = self.root / "generated" / "social"
        syndication_dir = self.root / "generated" / "syndication"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        generate_syndication_drafts(self.topics_path, syndication_dir, "https://example.com/")

        approve_due_distribution(
            self.topics_path,
            social_dir / "manifest.json",
            syndication_dir / "manifest.json",
            now=datetime.fromisoformat("2026-07-14T09:00:00+09:00"),
            approved_by="automation",
        )
        social_manifest = json.loads((social_dir / "manifest.json").read_text(encoding="utf-8"))
        x_post = next(
            post
            for post in social_manifest["posts"]
            if post["platform"] == "x" and post["language"] == "en" and not post["is_variant"]
        )
        bluesky_post = next(
            post
            for post in social_manifest["posts"]
            if post["platform"] == "bluesky" and post["language"] == "en" and not post["is_variant"]
        )
        self.assertEqual(x_post["status"], "approved")
        self.assertEqual(bluesky_post["status"], "draft")

        approve_due_distribution(
            self.topics_path,
            social_dir / "manifest.json",
            syndication_dir / "manifest.json",
            now=datetime.fromisoformat("2026-07-15T09:00:00+09:00"),
            approved_by="automation",
        )
        social_manifest = json.loads((social_dir / "manifest.json").read_text(encoding="utf-8"))
        bluesky_post = next(
            post
            for post in social_manifest["posts"]
            if post["platform"] == "bluesky" and post["language"] == "en" and not post["is_variant"]
        )
        self.assertEqual(bluesky_post["status"], "approved")

        approve_due_distribution(
            self.topics_path,
            social_dir / "manifest.json",
            syndication_dir / "manifest.json",
            now=datetime.fromisoformat("2026-07-16T09:00:00+09:00"),
            approved_by="automation",
        )
        syndication_manifest = json.loads((syndication_dir / "manifest.json").read_text(encoding="utf-8"))
        devto_draft = next(
            draft for draft in syndication_manifest["drafts"] if draft["platform"] == "devto" and draft["language"] == "en"
        )
        hashnode_draft = next(
            draft for draft in syndication_manifest["drafts"] if draft["platform"] == "hashnode" and draft["language"] == "en"
        )
        self.assertEqual(devto_draft["status"], "approved")
        self.assertEqual(hashnode_draft["status"], "draft")

    def test_live_credential_preflight_uses_safe_auth_endpoints(self) -> None:
        calls: list[tuple[str, str, dict[str, object] | None, dict[str, str] | None]] = []

        def fake_json_request(
            url: str,
            method: str = "GET",
            payload: dict[str, object] | None = None,
            headers: dict[str, str] | None = None,
        ) -> dict[str, object]:
            calls.append((url, method, payload, headers))
            if url.endswith("/api/users/me"):
                return {"username": "dev-user"}
            if url.endswith("/2/users/me"):
                return {"data": {"id": "1", "username": "x-user"}}
            if url == "https://gql.hashnode.com":
                return {"data": {"me": {"id": "2", "username": "hash-user"}}}
            return {"accessJwt": "jwt", "did": "did:plc:test"}

        env = {
            "DEVTO_API_KEY": "devto-key",
            "X_CLIENT_ID": "client-id",
            "X_CLIENT_SECRET": "client-secret",
            "X_REFRESH_TOKEN": "refresh-token",
            "HASHNODE_TOKEN": "hashnode-token",
            "HASHNODE_PUBLICATION_ID": "pub123",
            "BLUESKY_HANDLE": "onnel.test",
            "BLUESKY_APP_PASSWORD": "app-password",
        }
        with patch.dict("os.environ", env):
            with patch("check_publishing_credentials.json_request", fake_json_request):
                with patch("check_publishing_credentials.form_request", return_value={"access_token": "x-access-token"}):
                    self.assertEqual(credential_status("devto", live=True)["identity"], "dev-user")
                    self.assertEqual(credential_status("x", live=True)["identity"], "x-user")
                    hashnode_status = credential_status("hashnode", live=True)
                    self.assertFalse(hashnode_status["implemented"])
                    self.assertFalse(hashnode_status["live_checked"])
                    self.assertEqual(credential_status("bluesky", live=True)["identity"], "did:plc:test")

        self.assertIn(
            (
                "https://dev.to/api/users/me",
                "GET",
                None,
                {
                    "api-key": "devto-key",
                    "Accept": "application/vnd.forem.api-v1+json",
                    "User-Agent": "ONNELLAB content engine",
                },
            ),
            calls,
        )
        self.assertIn(("https://api.x.com/2/users/me", "GET", None, {"Authorization": "Bearer x-access-token"}), calls)
        self.assertNotIn(("https://gql.hashnode.com", "POST", {"query": "query Viewer { me { id username } }"}, {"Authorization": "hashnode-token"}), calls)

    def test_x_adapter_creates_post_payload(self) -> None:
        social_dir = self.root / "generated" / "social"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        approve_social_post("TOPIC-0001", "x", "en", "editor", social_dir / "manifest.json")
        calls: list[tuple[str, dict[str, object], dict[str, str] | None]] = []
        refresh_calls: list[tuple[str, dict[str, str], dict[str, str] | None]] = []

        def fake_json_post(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
            calls.append((url, payload, headers))
            return {"data": {"id": "1234567890", "text": str(payload["text"])}}

        def fake_form_post(url: str, payload: dict[str, str], headers: dict[str, str] | None = None) -> dict[str, object]:
            refresh_calls.append((url, payload, headers))
            return {"access_token": "x-access-token", "refresh_token": "refresh-token"}

        env = {"X_CLIENT_ID": "client-id", "X_CLIENT_SECRET": "client-secret", "X_REFRESH_TOKEN": "refresh-token"}
        with patch.dict("os.environ", env):
            with patch("post_social_drafts.json_post", fake_json_post):
                with patch("post_social_drafts.form_post", fake_form_post):
                    posted = post_social_drafts(social_dir / "manifest.json", platform="x", adapter="x")

        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]["status"], "posted")
        self.assertEqual(posted[0]["post_id"], "1234567890")
        self.assertEqual(posted[0]["posted_url"], "https://x.com/i/web/status/1234567890")
        self.assertEqual(refresh_calls[0][0], "https://api.x.com/2/oauth2/token")
        self.assertEqual(refresh_calls[0][1]["grant_type"], "refresh_token")
        self.assertEqual(refresh_calls[0][1]["refresh_token"], "refresh-token")
        self.assertEqual(refresh_calls[0][1]["client_id"], "client-id")
        self.assertTrue(str(refresh_calls[0][2]["Authorization"]).startswith("Basic "))
        self.assertEqual(calls[0][0], "https://api.x.com/2/tweets")
        self.assertEqual(calls[0][2]["Authorization"], "Bearer x-access-token")
        self.assertIn("A slow TXT file is often a workflow problem before it is a file problem.", calls[0][1]["text"])
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", calls[0][1]["text"])

    def test_social_posting_failure_records_error_type(self) -> None:
        social_dir = self.root / "generated" / "social"
        manifest_path = social_dir / "manifest.json"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        approve_social_post("TOPIC-0001", "x", "en", "editor", manifest_path)

        def fake_json_post(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
            raise SocialPostingError("HTTP 429 from https://api.x.com/2/tweets: rate limit")

        env = {"X_CLIENT_ID": "client-id", "X_CLIENT_SECRET": "client-secret", "X_REFRESH_TOKEN": "refresh-token"}
        with patch.dict("os.environ", env):
            with patch("post_social_drafts.json_post", fake_json_post):
                with patch("post_social_drafts.form_post", return_value={"access_token": "x-access-token"}):
                    with self.assertRaises(SocialPostingError):
                        post_social_drafts(manifest_path, platform="x", adapter="x")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        failed = next(post for post in manifest["posts"] if post["platform"] == "x" and post["language"] == "en" and not post["is_variant"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error_type"], "rate_limited")
        self.assertEqual(failed["retry_count"], 1)
        self.assertTrue(failed["last_attempt_at"])

    def test_bluesky_adapter_creates_text_post_payload(self) -> None:
        social_dir = self.root / "generated" / "social"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        manifest = json.loads((social_dir / "manifest.json").read_text(encoding="utf-8"))
        post = next(item for item in manifest["posts"] if item["platform"] == "bluesky" and item["language"] == "en" and not item["is_variant"])
        calls: list[tuple[str, dict[str, object], dict[str, str] | None]] = []
        uploads: list[tuple[str, bytes, str, dict[str, str] | None]] = []

        def fake_json_post(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
            calls.append((url, payload, headers))
            if url.endswith("createSession"):
                return {"accessJwt": "jwt"}
            return {"uri": "at://did:plc:test/app.bsky.feed.post/abc123", "cid": "cid"}

        def fake_binary_post(
            url: str,
            data: bytes,
            content_type: str,
            headers: dict[str, str] | None = None,
        ) -> dict[str, object]:
            uploads.append((url, data, content_type, headers))
            return {
                "blob": {
                    "$type": "blob",
                    "ref": {"$link": "bafytest"},
                    "mimeType": "image/png",
                    "size": len(data),
                }
            }

        with patch.dict("os.environ", {"BLUESKY_HANDLE": "onnel.test", "BLUESKY_APP_PASSWORD": "app-password"}):
            with patch("post_social_drafts.json_post", fake_json_post):
                with patch("post_social_drafts.binary_post", fake_binary_post):
                    post_id, posted_url = post_bluesky_text(post, self.root, "2026-07-12T09:00:00+09:00")

        self.assertEqual(post_id, "at://did:plc:test/app.bsky.feed.post/abc123")
        self.assertEqual(posted_url, "https://bsky.app/profile/onnel.test/post/abc123")
        self.assertEqual(calls[0][1], {"identifier": "onnel.test", "password": "app-password"})
        self.assertTrue(uploads[0][0].endswith("com.atproto.repo.uploadBlob"))
        self.assertEqual(uploads[0][2], "image/png")
        self.assertIn("Authorization", uploads[0][3])
        self.assertEqual(calls[1][1]["collection"], "app.bsky.feed.post")
        record = calls[1][1]["record"]
        self.assertEqual(record["$type"], "app.bsky.feed.post")
        self.assertIn("Sometimes the best fix for a slow text file is changing how you open it.", record["text"])
        self.assertEqual(record["langs"], ["en"])
        self.assertIn("facets", record)
        facets = record["facets"]
        self.assertEqual(len(facets), 1)
        self.assertEqual(facets[0]["features"][0]["$type"], "app.bsky.richtext.facet#link")
        self.assertEqual(facets[0]["features"][0]["uri"], "https://example.com/blog/en/read-large-txt-files/")
        embed = record["embed"]
        self.assertEqual(embed["$type"], "app.bsky.embed.external")
        self.assertEqual(embed["external"]["uri"], "https://example.com/blog/en/read-large-txt-files/")
        self.assertEqual(embed["external"]["thumb"]["ref"]["$link"], "bafytest")

    def test_bluesky_link_facets_use_utf8_byte_offsets(self) -> None:
        text = "읽기 팁 ✨ https://example.com/blog/ko/read-large-txt-files/."

        facets = bluesky_link_facets(text)

        self.assertEqual(len(facets), 1)
        facet = facets[0]
        uri = "https://example.com/blog/ko/read-large-txt-files/"
        start = text.index(uri)
        end = start + len(uri)
        self.assertEqual(
            facet["index"],
            {
                "byteStart": len(text[:start].encode("utf-8")),
                "byteEnd": len(text[:end].encode("utf-8")),
            },
        )
        self.assertEqual(facet["features"][0]["uri"], uri)

    def test_bluesky_preflight_and_failed_reset(self) -> None:
        calls: list[tuple[str, dict[str, object], dict[str, str] | None]] = []

        def fake_json_post(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
            calls.append((url, payload, headers))
            return {"accessJwt": "jwt", "did": "did:plc:test"}

        with patch.dict("os.environ", {"BLUESKY_HANDLE": "onnel.test", "BLUESKY_APP_PASSWORD": "app-password"}):
            with patch("check_bluesky_connection.json_post", fake_json_post):
                result = check_bluesky_connection()

        self.assertTrue(result["authenticated"])
        self.assertEqual(result["did"], "did:plc:test")
        self.assertEqual(calls[0][1], {"identifier": "onnel.test", "password": "app-password"})

        social_dir = self.root / "generated" / "social"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        approve_social_post("TOPIC-0001", "bluesky", "en", "editor", social_dir / "manifest.json")
        manifest_path = social_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        post = next(item for item in manifest["posts"] if item["platform"] == "bluesky" and item["language"] == "en" and not item["is_variant"])
        post["status"] = "failed"
        post["error"] = "temporary"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        reset = reset_failed_social_post("TOPIC-0001", "bluesky", "en", "bluesky", manifest_path)

        self.assertEqual(reset["status"], "approved")
        self.assertEqual(reset["error"], "")
        with self.assertRaises(SocialResetError):
            reset_failed_social_post("TOPIC-0001", "bluesky", "en", "bluesky", manifest_path)

    def test_generate_syndication_drafts_keeps_canonical_source(self) -> None:
        output_dir = self.root / "generated" / "syndication"

        drafts = generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")

        self.assertEqual(len(drafts), 3)
        devto_path = output_dir / "devto" / "en" / "reading" / "read-large-txt-files.md"
        hashnode_path = output_dir / "hashnode" / "en" / "reading" / "read-large-txt-files.md"
        medium_path = output_dir / "medium" / "en" / "reading" / "read-large-txt-files.md"
        self.assertTrue(devto_path.exists())
        self.assertTrue(hashnode_path.exists())
        self.assertTrue(medium_path.exists())
        content = devto_path.read_text(encoding="utf-8")
        self.assertIn("published: true", content)
        self.assertIn('canonical_url: "https://example.com/blog/en/read-large-txt-files/"', content)
        self.assertIn('tags: "large-txt-files"', content)
        self.assertIn("![Workflow diagram](https://example.com/blog-assets/en/read-large-txt-files/workflow-diagram.png", content)
        self.assertNotIn("https://example.com/blog-assets/en/read-large-txt-files/workflow-diagram.svg", content)
        self.assertIn("Originally published at https://example.com/blog/en/read-large-txt-files/", content)
        self.assertIn("# How to Read Very Large TXT Files", content)
        hashnode_content = hashnode_path.read_text(encoding="utf-8")
        self.assertIn('cover_image: "https://example.com/blog-assets/en/read-large-txt-files/social-card.png"', hashnode_content)
        self.assertIn(f'content_profile: "{HASHNODE_CONTENT_PROFILE}"', hashnode_content)
        self.assertIn('tags: "programming,performance,text-processing"', hashnode_content)
        self.assertIn("## The constraint to solve", hashnode_content)
        self.assertIn("## Implementation path", hashnode_content)
        self.assertNotIn("ONNELLAB note:", hashnode_content)
        self.assertNotIn("## Question", hashnode_content)
        self.assertNotIn("Originally published at https://example.com/blog/en/read-large-txt-files/", hashnode_content)
        self.assertEqual(hashnode_automod_risks(hashnode_content, "https://example.com/blog/en/read-large-txt-files/"), [])
        medium_content = medium_path.read_text(encoding="utf-8")
        self.assertTrue(medium_content.startswith("> ONNELLAB note:"))
        self.assertIn("Originally published at https://example.com/blog/en/read-large-txt-files/", medium_content)
        self.assertNotIn("canonical_url:", medium_content)
        self.assertFalse(medium_content.startswith("---"))
        manifest = (output_dir / "manifest.json").read_text(encoding="utf-8")
        self.assertIn('"platform": "devto"', manifest)
        self.assertIn('"platform": "hashnode"', manifest)
        self.assertIn('"platform": "medium"', manifest)
        self.assertNotIn('"language": "ko"', manifest)
        self.assertIn('"last_attempt_at": ""', manifest)
        self.assertIn('"error_type": ""', manifest)
        self.assertIn('"retry_count": 0', manifest)
        evaluation = evaluate_syndication_drafts(output_dir / "manifest.json", self.root)
        self.assertGreaterEqual(evaluation["average_score"], 9.0)
        self.assertEqual(validate_syndication_drafts(output_dir / "manifest.json", self.root), 3)

        approved = approve_syndication_draft(
            "TOPIC-0001",
            "devto",
            "en",
            "editor",
            output_dir / "manifest.json",
        )

        self.assertEqual(approved["status"], "approved")
        report = syndication_report(output_dir / "manifest.json")
        self.assertIn("ready for mock posting: TOPIC-0001 devto en", report)
        dry_run = post_syndication_drafts(output_dir / "manifest.json", platform="devto", dry_run=True)
        self.assertEqual(len(dry_run), 1)
        posted = post_syndication_drafts(output_dir / "manifest.json", platform="devto", adapter="mock")
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]["status"], "posted")
        self.assertTrue(str(posted[0]["post_id"]).startswith("mock-TOPIC-0001-devto-en"))
        self.assertEqual(posted[0]["retry_count"], 0)
        self.assertTrue(posted[0]["last_attempt_at"])
        with self.assertRaises(SyndicationApprovalError):
            approve_syndication_draft(
                "TOPIC-0001",
                "medium",
                "en",
                "editor",
                output_dir / "manifest.json",
            )

    def test_hashnode_generator_budgets_plain_and_autolink_research_urls_deterministically(self) -> None:
        research_shape = MARKDOWN + """

## References

Store a stable identifier such as `https://doi.org/10.xxxx/xxxxx` and keep the
resolver guidance at <https://doi.org/doi-handbook/> for later verification.

- [DOI Handbook](https://www.doi.org/doi-handbook/html/) documents resolution.
- [Crossref display guidelines](https://www.crossref.org/display-guidelines/) preserve DOI usefulness.
- [Crossref metadata](https://www.crossref.org/documentation/retrieve-metadata/) supports verification.
- [DataCite versions](https://support.datacite.org/docs/connecting-versions) distinguishes editions.
"""
        self.markdown_path.write_text(research_shape, encoding="utf-8")
        output_dir = self.root / "generated" / "syndication"

        generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")
        hashnode_path = output_dir / "hashnode" / "en" / "reading" / "read-large-txt-files.md"
        first = hashnode_path.read_text(encoding="utf-8")

        self.assertEqual(hashnode_automod_risks(first, "https://example.com/blog/en/read-large-txt-files/"), [])
        self.assertIn("`doi.org/10.xxxx/xxxxx`", first)
        self.assertIn("doi.org/doi-handbook/", first)
        self.assertNotIn("<doi.org/doi-handbook/>", first)
        self.assertIn("[DOI Handbook](https://www.doi.org/doi-handbook/html/)", first)
        self.assertIn("[Crossref display guidelines](https://www.crossref.org/display-guidelines/)", first)
        self.assertNotIn("https://www.crossref.org/documentation/retrieve-metadata/", first)
        hashnode_body = first.split("\n---\n", 1)[1]
        self.assertEqual(hashnode_body.count("http://") + hashnode_body.count("https://"), 3)
        self.assertEqual(validate_syndication_drafts(output_dir / "manifest.json", self.root), 3)

        generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")
        self.assertEqual(hashnode_path.read_text(encoding="utf-8"), first)

    def test_syndication_drafts_default_to_published_sources_only(self) -> None:
        rows = [topic_row(status="draft"), topic_row(status="draft", topic_id="TOPIC-0002", language="ko")]
        write_topics(self.topics_path, rows)
        output_dir = self.root / "generated" / "syndication"

        drafts = generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")

        self.assertEqual(drafts, [])
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest, {"drafts": []})

    def test_prepublication_syndication_drafts_are_generated_but_cannot_be_approved(self) -> None:
        output_dir = self.root / "generated" / "syndication"

        for source_status in ("draft", "review"):
            with self.subTest(source_status=source_status):
                rows = [
                    topic_row(status=source_status),
                    topic_row(status=source_status, topic_id="TOPIC-0002", language="ko"),
                ]
                write_topics(self.topics_path, rows)

                drafts = generate_syndication_drafts(
                    self.topics_path,
                    output_dir,
                    "https://example.com/",
                    include_prepublication=True,
                )

                self.assertEqual(len(drafts), 3)
                self.assertEqual({draft["platform"] for draft in drafts}, {"devto", "hashnode", "medium"})
                self.assertEqual({draft["language"] for draft in drafts}, {"en"})
                self.assertTrue(all(draft["source_status"] == source_status for draft in drafts))
                self.assertTrue(all(draft["publish_after_canonical"] is True for draft in drafts))
                manifest_path = output_dir / "manifest.json"
                self.assertEqual(validate_syndication_drafts(manifest_path, self.root), 3)
                evaluation = evaluate_syndication_drafts(manifest_path, self.root)
                self.assertEqual(len(evaluation["drafts"]), 3)
                self.assertGreaterEqual(evaluation["average_score"], 9.0)

                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                devto = next(draft for draft in manifest["drafts"] if draft["platform"] == "devto")
                devto.pop("publish_after_canonical")
                devto.pop("source_status")
                manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                manifest_before = manifest_path.read_text(encoding="utf-8")
                with self.assertRaisesRegex(SyndicationApprovalError, "before canonical publication"):
                    approve_syndication_draft("TOPIC-0001", "devto", "en", "editor", manifest_path)
                self.assertEqual(manifest_path.read_text(encoding="utf-8"), manifest_before)

    def test_prepublication_syndication_regeneration_resets_unposted_state(self) -> None:
        output_dir = self.root / "generated" / "syndication"
        generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")
        manifest_path = output_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        devto = next(draft for draft in manifest["drafts"] if draft["platform"] == "devto")
        devto.update(
            {
                "status": "approved",
                "approved_by": "editor",
                "approved_at": "2026-07-20T09:00:00+09:00",
            }
        )
        hashnode = next(draft for draft in manifest["drafts"] if draft["platform"] == "hashnode")
        hashnode.update(
            {
                "status": "failed",
                "approved_by": "editor",
                "approved_at": "2026-07-20T09:00:00+09:00",
                "last_attempt_at": "2026-07-21T09:00:00+09:00",
                "error": "temporary failure",
                "error_type": "transient",
                "retry_count": 2,
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        write_topics(
            self.topics_path,
            [topic_row(status="draft"), topic_row(status="draft", topic_id="TOPIC-0002", language="ko")],
        )

        regenerated = generate_syndication_drafts(
            self.topics_path,
            output_dir,
            "https://example.com/",
            include_prepublication=True,
        )

        for platform in ("devto", "hashnode"):
            with self.subTest(platform=platform):
                draft = next(item for item in regenerated if item["platform"] == platform)
                self.assertEqual(draft["status"], "draft")
                self.assertEqual(draft["approved_by"], "")
                self.assertEqual(draft["approved_at"], "")
                self.assertEqual(draft["post_id"], "")
                self.assertEqual(draft["posted_url"], "")
                self.assertEqual(draft["posted_at"], "")
                self.assertEqual(draft["last_attempt_at"], "")
                self.assertEqual(draft["error"], "")
                self.assertEqual(draft["error_type"], "")
                self.assertEqual(draft["retry_count"], 0)

    def test_prepublication_syndication_regeneration_preserves_posted_state(self) -> None:
        output_dir = self.root / "generated" / "syndication"
        generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")
        manifest_path = output_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        posted = next(draft for draft in manifest["drafts"] if draft["platform"] == "devto")
        posted_path = self.root / posted["draft_path"]
        original_posted_body = posted_path.read_bytes()
        posted.update(
            {
                "status": "posted",
                "approved_by": "editor",
                "approved_at": "2026-07-20T09:00:00+09:00",
                "post_id": "1234",
                "posted_url": "https://dev.to/onnel/example",
                "posted_at": "2026-07-21T09:00:00+09:00",
                "last_attempt_at": "2026-07-21T09:00:00+09:00",
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.markdown_path.write_text(
            MARKDOWN.replace("Choose a stable reader.", "Use newly revised source content."),
            encoding="utf-8",
        )
        write_topics(
            self.topics_path,
            [topic_row(status="draft"), topic_row(status="draft", topic_id="TOPIC-0002", language="ko")],
        )

        regenerated = generate_syndication_drafts(
            self.topics_path,
            output_dir,
            "https://example.com/",
            include_prepublication=True,
        )

        posted = next(draft for draft in regenerated if draft["platform"] == "devto")
        self.assertTrue(posted["publish_after_canonical"])
        self.assertEqual(posted["status"], "posted")
        self.assertEqual(posted["approved_by"], "editor")
        self.assertEqual(posted["post_id"], "1234")
        self.assertEqual(posted["posted_url"], "https://dev.to/onnel/example")
        self.assertEqual(posted["posted_at"], "2026-07-21T09:00:00+09:00")
        self.assertEqual(posted_path.read_bytes(), original_posted_body)

    def test_prepublication_syndication_posting_fails_closed_before_dry_run_or_adapter(self) -> None:
        rows = [topic_row(status="draft"), topic_row(status="draft", topic_id="TOPIC-0002", language="ko")]
        write_topics(self.topics_path, rows)
        output_dir = self.root / "generated" / "syndication"
        generate_syndication_drafts(
            self.topics_path,
            output_dir,
            "https://example.com/",
            include_prepublication=True,
        )
        manifest_path = output_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        devto = next(draft for draft in manifest["drafts"] if draft["platform"] == "devto")
        devto["status"] = "approved"
        devto["approved_by"] = "tampered-client"
        devto["approved_at"] = "2026-07-20T09:00:00+09:00"
        devto.pop("publish_after_canonical")
        devto.pop("source_status")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        with patch("post_syndication_drafts.require_adapter_ready") as adapter_preflight:
            with self.assertRaisesRegex(SyndicationPostingError, "before canonical publication"):
                post_syndication_drafts(manifest_path, platform="devto", adapter="devto", dry_run=True)

        adapter_preflight.assert_not_called()

    def test_syndication_topic_identity_swap_fails_approval_and_posting_before_adapter(self) -> None:
        private = self.write_private_draft_topic()
        write_topics(
            self.topics_path,
            [topic_row(), topic_row(topic_id="TOPIC-0002", language="ko"), private],
        )
        output_dir = self.root / "generated" / "syndication"
        generate_syndication_drafts(
            self.topics_path,
            output_dir,
            "https://example.com/",
            include_prepublication=True,
        )
        manifest_path = output_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["drafts"] = [draft for draft in manifest["drafts"] if draft["topic_id"] == "TOPIC-0012"]
        swapped = next(draft for draft in manifest["drafts"] if draft["platform"] == "devto")
        swapped.update(
            {
                "topic_id": "TOPIC-0001",
                "source_status": "published",
                "publish_after_canonical": False,
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(SyndicationApprovalError, "manifest slug"):
            approve_syndication_draft("TOPIC-0001", "devto", "en", "editor", manifest_path)

        swapped.update(
            {
                "status": "approved",
                "approved_by": "tampered-client",
                "approved_at": "2026-07-20T09:00:00+09:00",
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        with patch("post_syndication_drafts.require_adapter_ready") as adapter_preflight:
            with self.assertRaisesRegex(SyndicationPostingError, "manifest slug"):
                post_syndication_drafts(manifest_path, platform="devto", adapter="devto", dry_run=True)
        adapter_preflight.assert_not_called()

    def test_syndication_generation_canonical_error_preserves_existing_output(self) -> None:
        output_dir = self.root / "generated" / "syndication"
        generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")
        manifest_path = output_dir / "manifest.json"
        draft_path = output_dir / "devto" / "en" / "reading" / "read-large-txt-files.md"
        previous_manifest = manifest_path.read_text(encoding="utf-8")
        previous_draft = draft_path.read_text(encoding="utf-8")
        rows = [topic_row(), topic_row(topic_id="TOPIC-0002", language="ko")]
        rows[0]["canonical_path"] = ""
        write_topics(self.topics_path, rows)

        with self.assertRaisesRegex(PublishingError, "no canonical_path"):
            generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")

        self.assertEqual(manifest_path.read_text(encoding="utf-8"), previous_manifest)
        self.assertEqual(draft_path.read_text(encoding="utf-8"), previous_draft)

    def test_distribution_supply_requires_every_supported_channel(self) -> None:
        social_dir = self.root / "generated" / "social"
        syndication_dir = self.root / "generated" / "syndication"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        generate_syndication_drafts(self.topics_path, syndication_dir, "https://example.com/")

        report = require_distribution_supply(
            topics_path=self.topics_path,
            social_manifest=social_dir / "manifest.json",
            syndication_manifest=syndication_dir / "manifest.json",
            project_root=self.root,
        )

        self.assertTrue(report["ready"])
        self.assertEqual(report["published_source_count"], 1)
        manifest_path = syndication_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["drafts"] = [item for item in manifest["drafts"] if item["platform"] != "medium"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(DistributionSupplyError):
            require_distribution_supply(
                topics_path=self.topics_path,
                social_manifest=social_dir / "manifest.json",
                syndication_manifest=manifest_path,
                project_root=self.root,
            )

    def test_devto_adapter_posts_public_article_payload(self) -> None:
        output_dir = self.root / "generated" / "syndication"
        generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")
        approve_syndication_draft("TOPIC-0001", "devto", "en", "editor", output_dir / "manifest.json")
        calls: list[tuple[str, dict[str, object], dict[str, str] | None]] = []

        def fake_json_post(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
            calls.append((url, payload, headers))
            return {"id": 1234, "url": "https://dev.to/onnel/read-large-txt-files"}

        with patch.dict("os.environ", {"DEVTO_API_KEY": "devto-key"}):
            with patch("post_syndication_drafts.json_post", fake_json_post):
                posted = post_syndication_drafts(output_dir / "manifest.json", platform="devto", adapter="devto")

        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]["status"], "posted")
        self.assertEqual(posted[0]["post_id"], "1234")
        self.assertEqual(posted[0]["posted_url"], "https://dev.to/onnel/read-large-txt-files")
        self.assertEqual(calls[0][0], "https://dev.to/api/articles")
        self.assertEqual(calls[0][2]["api-key"], "devto-key")
        self.assertEqual(calls[0][2]["Accept"], "application/vnd.forem.api-v1+json")
        self.assertEqual(calls[0][2]["User-Agent"], "ONNELLAB content engine")
        article = calls[0][1]["article"]
        self.assertEqual(article["title"], "How to Read Very Large TXT Files")
        self.assertTrue(article["published"])
        self.assertEqual(article["canonical_url"], "https://example.com/blog/en/read-large-txt-files/")
        self.assertEqual(article["tags"], "large-txt-files")
        self.assertIn("Originally published at https://example.com/blog/en/read-large-txt-files/", article["body_markdown"])
        self.assertIn("https://example.com/blog-assets/en/read-large-txt-files/workflow-diagram.png", article["body_markdown"])
        self.assertNotIn("https://example.com/blog-assets/en/read-large-txt-files/workflow-diagram.svg", article["body_markdown"])

    def test_hashnode_adapter_is_export_only_without_paid_api(self) -> None:
        output_dir = self.root / "generated" / "syndication"
        generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")
        approve_syndication_draft("TOPIC-0001", "hashnode", "en", "editor", output_dir / "manifest.json")

        dry_run = post_syndication_drafts(output_dir / "manifest.json", platform="hashnode", adapter="hashnode", dry_run=True)

        self.assertEqual(len(dry_run), 1)
        payload = hashnode_payload(dry_run[0], self.root)
        self.assertIn("mutation CreateDraft", payload["query"])
        variables = payload["variables"]
        input_payload = variables["input"]
        self.assertEqual(input_payload["title"], "How to Read Very Large TXT Files")
        self.assertEqual(input_payload["publicationId"], "")
        self.assertEqual(input_payload["slug"], "read-large-txt-files")
        self.assertEqual(input_payload["originalArticleURL"], "https://example.com/blog/en/read-large-txt-files/")
        self.assertEqual(
            input_payload["tags"],
            [
                {"slug": "programming", "name": "programming"},
                {"slug": "performance", "name": "performance"},
                {"slug": "text-processing", "name": "text-processing"},
            ],
        )
        with self.assertRaises(SyndicationPostingError):
            post_syndication_drafts(output_dir / "manifest.json", platform="hashnode", adapter="hashnode")
        self.assertEqual(
            input_payload["coverImageOptions"]["coverImageURL"],
            "https://example.com/blog-assets/en/read-large-txt-files/social-card.png",
        )
        self.assertFalse(input_payload["settings"]["activateNewsletter"])

    def test_hashnode_automod_gate_rejects_repetitive_promotional_copy(self) -> None:
        content = """---
title: "Repeated Draft"
canonical_url: "https://example.com/original/"
tags: "programming"
cover_image: "https://example.com/card.png"
publication_id: ""
content_profile: "hashnode-native-v2"
---

> ONNELLAB note: This version keeps the implementation trade-offs visible.

# Repeated Draft

## Question

What should I do?

[Product](https://onnellab.github.io/apps/example/)
[Store](https://play.google.com/store/apps/details?id=example)

Originally published at https://example.com/original/
"""

        risks = hashnode_automod_risks(content, "https://example.com/original/")

        self.assertIn("repeated ONNELLAB note is not allowed", risks)
        self.assertIn("canonical URL must be set as metadata, not repeated in the body", risks)
        self.assertIn("body must not repeat the article title as an H1", risks)
        self.assertIn("generic canonical section headings must be adapted for Hashnode", risks)
        self.assertIn("body must not contain product or store links", risks)

    def test_hashnode_automod_gate_rejects_promotional_language_and_link_volume(self) -> None:
        content = f'''---
title: "Technical Draft"
canonical_url: "https://example.com/original/"
tags: "programming"
cover_image: "https://example.com/card.png"
publication_id: ""
content_profile: "{HASHNODE_CONTENT_PROFILE}"
---

## Implementation

Run `tool verify` before deploying.

1. Reproduce the issue.
2. Compare the output.

[One](https://example.com/1)
[Two](https://example.com/2)
[Three](https://example.com/3)
[Four](https://example.com/4)

Download now for the best app.
'''

        risks = hashnode_automod_risks(content, "https://example.com/original/")

        self.assertIn("body contains more than three external links", risks)
        self.assertIn("body contains promotional call-to-action language", risks)

    def test_hashnode_approval_uses_standard_syndication_approval(self) -> None:
        output_dir = self.root / "generated" / "syndication"
        generate_syndication_drafts(self.topics_path, output_dir, "https://example.com/")
        manifest = output_dir / "manifest.json"

        approved = approve_syndication_draft(
            "TOPIC-0001",
            "hashnode",
            "en",
            "editor",
            manifest,
            now=datetime.fromisoformat("2026-07-20T09:00:00+09:00"),
        )
        self.assertEqual(approved["status"], "approved")

    def test_integrated_publishing_dry_run_report_lists_approved_payloads(self) -> None:
        social_dir = self.root / "generated" / "social"
        syndication_dir = self.root / "generated" / "syndication"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        generate_syndication_drafts(self.topics_path, syndication_dir, "https://example.com/")
        approve_social_post("TOPIC-0001", "x", "en", "editor", social_dir / "manifest.json")
        approve_syndication_draft("TOPIC-0001", "devto", "en", "editor", syndication_dir / "manifest.json")

        report = publishing_dry_run_report(social_dir / "manifest.json", syndication_dir / "manifest.json")

        self.assertIn("Publishing dry-run report", report)
        self.assertIn("approved social posts: 1", report)
        self.assertIn("approved syndication drafts: 1", report)
        self.assertIn("x: not ready, missing=X_CLIENT_ID,X_CLIENT_SECRET,X_REFRESH_TOKEN", report)
        self.assertIn("devto: not ready, missing=DEVTO_API_KEY", report)
        self.assertIn("TOPIC-0001 x en x: text_length=", report)
        self.assertIn("TOPIC-0001 devto en: published=True tags=large-txt-files", report)


if __name__ == "__main__":
    unittest.main()
