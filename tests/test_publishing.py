from __future__ import annotations

import tempfile
import unittest
import json
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
from approve_social_post import approve_social_post
from generate_syndication_drafts import generate_syndication_drafts
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
        self.assertTrue((self.site_dir / "favicon.svg").exists())
        self.assertTrue((self.site_dir / "favicon-32x32.png").exists())
        self.assertTrue((self.site_dir / "apple-touch-icon.png").exists())
        self.assertTrue((self.site_dir / "site.webmanifest").exists())
        html = article_html.read_text(encoding="utf-8")
        self.assertIn("<h1>How to Read Very Large TXT Files</h1>", html)
        self.assertIn('content="A practical guide to reading very large TXT files without unnecessary lag."', html)
        self.assertIn('<link rel="icon" href="/favicon.svg?v=20260712-transparent" type="image/svg+xml">', html)
        self.assertIn('<link rel="apple-touch-icon" href="/apple-touch-icon.png?v=20260712-transparent">', html)
        self.assertIn('<link rel="manifest" href="/site.webmanifest?v=20260712-transparent">', html)
        self.assertIn("<blockquote>Treat the file as a reference document before editing it.</blockquote>", html)
        self.assertIn("<table>", html)
        self.assertIn('<img src="/blog-assets/en/read-large-txt-files/workflow-diagram.svg"', html)
        self.assertIn('<meta property="og:title" content="How to Read Very Large TXT Files">', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
        self.assertIn(
            '<meta name="twitter:image" content="https://example.com/blog-assets/en/read-large-txt-files/social-card.png">',
            html,
        )
        self.assertTrue((self.root / "generated" / "assets" / "blog" / "en" / "read-large-txt-files" / "social-card.svg").exists())
        self.assertTrue((self.root / "generated" / "assets" / "blog" / "en" / "read-large-txt-files" / "social-card.png").exists())
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", (self.site_dir / "feed.xml").read_text(encoding="utf-8"))
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", (self.site_dir / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn('"short_name": "ONNELLAB"', (self.site_dir / "site.webmanifest").read_text(encoding="utf-8"))
        self.assertIn('/favicon.svg?v=20260712-transparent', (self.site_dir / "site.webmanifest").read_text(encoding="utf-8"))

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
        self.assertIn('/favicon.svg?v=20260712-transparent', manifest_destination.read_text(encoding="utf-8"))
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

        self.assertEqual(len(posts), 6)
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
        self.assertLessEqual(len(bluesky_text), 300)
        self.assertIn("How to Read Very Large TXT Files", x_text)
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", x_text)
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", bluesky_text)
        self.assertIn("Identify the file size.", linkedin_text)
        self.assertIn("Check the encoding.", linkedin_text)
        self.assertNotIn("{{", linkedin_text)
        self.assertIn("Read the full article:", linkedin_text)
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", linkedin_text)
        manifest = (social_dir / "manifest.json").read_text(encoding="utf-8")
        self.assertIn('"status": "draft"', manifest)
        self.assertIn('"status": "variant"', manifest)
        self.assertIn('"template_id": "x"', manifest)
        self.assertIn('"template_id": "x_question"', manifest)
        self.assertIn('"template_id": "bluesky"', manifest)
        self.assertIn('"template_id": "bluesky_question"', manifest)
        self.assertIn('"card_asset_path":', manifest)
        self.assertIn('"approved_by": ""', manifest)
        self.assertIn('"post_id": ""', manifest)
        self.assertIn('"error_type": ""', manifest)
        self.assertIn('"retry_count": 0', manifest)
        self.assertIn('"impressions": 0', manifest)
        self.assertEqual(validate_social_posts(social_dir / "manifest.json", self.root), 12)

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
        self.assertIn("X_BEARER_TOKEN", missing_credentials("x", {}))
        self.assertIn("BLUESKY_HANDLE", missing_credentials("bluesky", {}))
        self.assertIn("bluesky: not ready", credential_report("bluesky"))
        with self.assertRaises(AdapterError):
            require_adapter_ready("bluesky", "social", {})

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
            "X_BEARER_TOKEN": "x-token",
            "HASHNODE_TOKEN": "hashnode-token",
            "HASHNODE_PUBLICATION_ID": "pub123",
            "BLUESKY_HANDLE": "onnel.test",
            "BLUESKY_APP_PASSWORD": "app-password",
        }
        with patch.dict("os.environ", env):
            with patch("check_publishing_credentials.json_request", fake_json_request):
                self.assertEqual(credential_status("devto", live=True)["identity"], "dev-user")
                self.assertEqual(credential_status("x", live=True)["identity"], "x-user")
                hashnode_status = credential_status("hashnode", live=True)
                self.assertFalse(hashnode_status["implemented"])
                self.assertFalse(hashnode_status["live_checked"])
                self.assertEqual(credential_status("bluesky", live=True)["identity"], "did:plc:test")

        self.assertIn(("https://dev.to/api/users/me", "GET", None, {"api-key": "devto-key"}), calls)
        self.assertIn(("https://api.x.com/2/users/me", "GET", None, {"Authorization": "Bearer x-token"}), calls)
        self.assertNotIn(("https://gql.hashnode.com", "POST", {"query": "query Viewer { me { id username } }"}, {"Authorization": "hashnode-token"}), calls)

    def test_x_adapter_creates_post_payload(self) -> None:
        social_dir = self.root / "generated" / "social"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        approve_social_post("TOPIC-0001", "x", "en", "editor", social_dir / "manifest.json")
        calls: list[tuple[str, dict[str, object], dict[str, str] | None]] = []

        def fake_json_post(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
            calls.append((url, payload, headers))
            return {"data": {"id": "1234567890", "text": str(payload["text"])}}

        with patch.dict("os.environ", {"X_BEARER_TOKEN": "x-token"}):
            with patch("post_social_drafts.json_post", fake_json_post):
                posted = post_social_drafts(social_dir / "manifest.json", platform="x", adapter="x")

        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]["status"], "posted")
        self.assertEqual(posted[0]["post_id"], "1234567890")
        self.assertEqual(posted[0]["posted_url"], "https://x.com/i/web/status/1234567890")
        self.assertEqual(calls[0][0], "https://api.x.com/2/tweets")
        self.assertEqual(calls[0][2]["Authorization"], "Bearer x-token")
        self.assertIn("How to Read Very Large TXT Files", calls[0][1]["text"])
        self.assertIn("https://example.com/blog/en/read-large-txt-files/", calls[0][1]["text"])

    def test_social_posting_failure_records_error_type(self) -> None:
        social_dir = self.root / "generated" / "social"
        manifest_path = social_dir / "manifest.json"
        generate_social_posts(self.topics_path, social_dir, "https://example.com/")
        approve_social_post("TOPIC-0001", "x", "en", "editor", manifest_path)

        def fake_json_post(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
            raise SocialPostingError("HTTP 429 from https://api.x.com/2/tweets: rate limit")

        with patch.dict("os.environ", {"X_BEARER_TOKEN": "x-token"}):
            with patch("post_social_drafts.json_post", fake_json_post):
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
        self.assertIn("How to Read Very Large TXT Files", record["text"])
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

        self.assertEqual(len(drafts), 6)
        devto_path = output_dir / "devto" / "en" / "reading" / "read-large-txt-files.md"
        hashnode_path = output_dir / "hashnode" / "en" / "reading" / "read-large-txt-files.md"
        medium_path = output_dir / "medium" / "en" / "reading" / "read-large-txt-files.md"
        self.assertTrue(devto_path.exists())
        self.assertTrue(hashnode_path.exists())
        self.assertTrue(medium_path.exists())
        content = devto_path.read_text(encoding="utf-8")
        self.assertIn('canonical_url: "https://example.com/blog/en/read-large-txt-files/"', content)
        self.assertIn('tags: "large-txt-files"', content)
        self.assertIn("Originally published at https://example.com/blog/en/read-large-txt-files/", content)
        self.assertIn("# How to Read Very Large TXT Files", content)
        self.assertIn('cover_image: "https://example.com/blog-assets/en/read-large-txt-files/social-card.png"', hashnode_path.read_text(encoding="utf-8"))
        manifest = (output_dir / "manifest.json").read_text(encoding="utf-8")
        self.assertIn('"platform": "devto"', manifest)
        self.assertIn('"platform": "hashnode"', manifest)
        self.assertIn('"platform": "medium"', manifest)
        self.assertIn('"last_attempt_at": ""', manifest)
        self.assertIn('"error_type": ""', manifest)
        self.assertIn('"retry_count": 0', manifest)
        evaluation = evaluate_syndication_drafts(output_dir / "manifest.json", self.root)
        self.assertGreaterEqual(evaluation["average_score"], 9.0)
        self.assertEqual(validate_syndication_drafts(output_dir / "manifest.json", self.root), 6)

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

    def test_devto_adapter_posts_unpublished_draft_payload(self) -> None:
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
        article = calls[0][1]["article"]
        self.assertEqual(article["title"], "How to Read Very Large TXT Files")
        self.assertFalse(article["published"])
        self.assertEqual(article["canonical_url"], "https://example.com/blog/en/read-large-txt-files/")
        self.assertEqual(article["tags"], "large-txt-files")
        self.assertIn("Originally published at https://example.com/blog/en/read-large-txt-files/", article["body_markdown"])

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
        self.assertEqual(input_payload["tags"], [{"slug": "large-txt-files", "name": "large-txt-files"}])
        with self.assertRaises(SyndicationPostingError):
            post_syndication_drafts(output_dir / "manifest.json", platform="hashnode", adapter="hashnode")
        self.assertEqual(
            input_payload["coverImageOptions"]["coverImageURL"],
            "https://example.com/blog-assets/en/read-large-txt-files/social-card.png",
        )
        self.assertFalse(input_payload["settings"]["activateNewsletter"])

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
        self.assertIn("x: not ready, missing=X_BEARER_TOKEN", report)
        self.assertIn("devto: not ready, missing=DEVTO_API_KEY", report)
        self.assertIn("TOPIC-0001 x en x: text_length=", report)
        self.assertIn("TOPIC-0001 devto en: published=False tags=large-txt-files", report)


if __name__ == "__main__":
    unittest.main()
