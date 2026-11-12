"""Offline regression tests for the isolated ONNELLAB Blogger channel."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from blogger_weekly import (
    BLOG_HOST, BLOG_ID, BloggerGuardError, read_ledger, record_draft,
    record_published, reserve, validate, verify_public_post, week_key,
)


class BloggerWeekTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "drafts/blogger/en").mkdir(parents=True)
        (self.root / "generated/markdown/en/music").mkdir(parents=True)
        self.ledger = self.root / "data/blogger_publications.json"
        self.source_path = self.root / "generated/markdown/en/music/main.md"
        self.source_path.write_text("# How to Edit MP3 Metadata Correctly\n\n" + ("This article teaches metadata fundamentals. " * 30), encoding="utf-8")
        self.url = "https://onnellab.com/blog/en/music/mp3-metadata/"
        self.references = (
            "https://www.loc.gov/preservation/digital/formats/",
            "https://www.w3.org/TR/html52/",
        )
        self.slug = "why-album-art-is-missing"
        self.meta_path = self.root / f"drafts/blogger/en/{self.slug}.json"
        self.body_path = self.root / f"drafts/blogger/en/{self.slug}.html"
        # A large real-form article sample. The generated prose is a fixture,
        # not editorial content; only safety, distinction, and ledger are tested.
        paragraphs = "".join(
            f"<p>Step {i}: inspect the file properties in your music library, "
            "compare the image dimensions with your player capabilities, "
            "save a backup before changing artwork, then test on a second device. "
            "A consistent repeatable check helps you isolate why an album cover is missing.</p>"
            for i in range(21)
        )
        self.body = (
            "<h2>Understand the symptom</h2><p>Album art may be embedded or stored beside a file.</p>"
            "<h2>Check the original file</h2><ol><li>Make a copy before editing.</li></ol>"
            "<h2>Test your result</h2><p>Use a second player for comparison.</p>"
            + paragraphs
            + f'<p>For related technical foundations, see <a href="{self.url}">the ONNELLAB original guide</a>.</p>'
            + "".join(f'<p>Technical reference: <a href="{u}">read the original documentation</a>.</p>' for u in self.references)
        )
        self.body_path.write_text(self.body, encoding="utf-8")
        self.meta = {
            "language": "en", "week": week_key(), "slug": self.slug,
            "title": "Why Music Album Artwork Vanishes Across Different Players",
            "primary_question": "Why do album covers disappear when files move between players?",
            "source_title": "How to Edit MP3 Metadata Correctly",
            "source_url": self.url,
            "source_path": "generated/markdown/en/music/main.md",
            "body_path": f"drafts/blogger/en/{self.slug}.html",
            "fact_sources": [
                {"url": u, "supports": "Compare interoperability and accessibility details carefully."}
                for u in self.references
            ],
            "new_examples": [
                "A folder-art versus embedded-thumbnail troubleshooting case.",
                "A second-player compatibility check with a backup-first workflow.",
            ],
            "review": {
                "technically_verified": True, "distinct_search_intent": True,
                "original_examples": True, "sources_checked": True,
                "links_checked": True, "rights_checked": True,
                "english_proofread": True,
            },
        }
        self.write_meta()

    def write_meta(self):
        self.meta_path.write_text(json.dumps(self.meta), encoding="utf-8")

    def test_valid_brief_and_reservation_idempotence(self):
        info = validate(self.meta_path, root=self.root)
        self.assertGreaterEqual(info["word_count"], 650)
        row, new = reserve(info, self.ledger)
        self.assertTrue(new)
        again, new = reserve(info, self.ledger)
        self.assertFalse(new)
        self.assertEqual(row["sha256"], again["sha256"])
        self.assertEqual(read_ledger(self.ledger)["blog_id"], BLOG_ID)
        self.assertEqual(len(read_ledger(self.ledger)["entries"]), 1)

    def test_no_second_article_same_week(self):
        info = validate(self.meta_path, root=self.root)
        reserve(info, self.ledger)
        extra = dict(info, slug="different-article", sha256="abc123")
        with self.assertRaisesRegex(BloggerGuardError, "already reserved"):
            reserve(extra, self.ledger)

    def test_distinctness_and_fact_sources_required(self):
        self.meta["title"] = self.meta["source_title"]
        self.write_meta()
        with self.assertRaisesRegex(BloggerGuardError, "too close"):
            validate(self.meta_path, root=self.root)
        self.meta["title"] = "Why Music Album Artwork Vanishes Across Different Players"
        self.meta["fact_sources"] = []
        self.write_meta()
        with self.assertRaisesRegex(BloggerGuardError, "research sources"):
            validate(self.meta_path, root=self.root)

    def test_safety_and_english_gate(self):
        self.body_path.write_text(self.body + '<a href="https://example.com:bad">broken</a>', encoding="utf-8")
        with self.assertRaisesRegex(BloggerGuardError, "HTTPS"):
            validate(self.meta_path, root=self.root)
        self.body_path.write_text(self.body + '<script>alert("x")</script>', encoding="utf-8")
        with self.assertRaisesRegex(BloggerGuardError, "unsafe"):
            validate(self.meta_path, root=self.root)
        self.body_path.write_text(self.body, encoding="utf-8")
        self.meta["language"] = "ko"
        self.write_meta()
        with self.assertRaisesRegex(BloggerGuardError, "English"):
            validate(self.meta_path, root=self.root)

    def test_cannot_claim_publication_before_draft(self):
        info = validate(self.meta_path, root=self.root)
        with self.assertRaisesRegex(BloggerGuardError, "reserve"):
            record_draft(info, "1234567890123", self.ledger)
        reserve(info, self.ledger)
        with self.assertRaisesRegex(BloggerGuardError, "must first"):
            record_published(info, "1234567890123", f"https://{BLOG_HOST}/2026/11/test.html", self.ledger)

    def test_exact_id_and_public_url_verified_before_recording(self):
        info = validate(self.meta_path, root=self.root)
        reserve(info, self.ledger)
        record_draft(info, "1234567890123", self.ledger)
        bad_url = "https://other.blogspot.com/2026/11/test.html"
        with self.assertRaisesRegex(BloggerGuardError, "permalink"):
            record_published(info, "1234567890123", bad_url, self.ledger, fetch=lambda _: "ignored")
        self.assertEqual(read_ledger(self.ledger)["entries"][0]["status"], "draft")
        good_url = f"https://{BLOG_HOST}/2026/11/test.html"
        page = "<html><body>" + ("Hello world " * 30) + "<h1>" + info["title"] + "</h1>" + "".join(f"<h2>{s}</h2>" for s in info["sections"]) + "</body></html>"
        row = record_published(info, "1234567890123", good_url, self.ledger, fetch=lambda _: page)
        self.assertEqual(row["posted_url"], good_url)
        self.assertEqual(row["status"], "published")
        with self.assertRaisesRegex(BloggerGuardError, "already published"):
            record_draft(info, "1234567890123", self.ledger)

    def test_disallow_copied_canonical_passage(self):
        longpass = " ".join(f"identical phrase word number {i}" for i in range(28))
        self.source_path.write_text("# How to Edit MP3 Metadata Correctly\n" + longpass, encoding="utf-8")
        self.body_path.write_text(self.body.replace("<h2>Test your result</h2>", "<h2>Test your result</h2><p>" + longpass + "</p>"), encoding="utf-8")
        with self.assertRaisesRegex(BloggerGuardError, "copies a long exact passage"):
            validate(self.meta_path, root=self.root)


if __name__ == "__main__":
    unittest.main()
