from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_article import evaluate_article
from publish_due_articles import publish_due_articles
from schedule_ready_articles import schedule_ready_articles
from topic_management import TOPIC_HEADER, write_topics


KST = timezone(timedelta(hours=9))


def topic_row(status: str, topic_id: str = "TOPIC-0001", language: str = "en") -> dict[str, str]:
    path = f"generated/markdown/{language}/reading/read-large-txt-files.md"
    return {
        "id": topic_id,
        "status": status,
        "category": "reading",
        "primary_question": "How can I read very large TXT files?",
        "working_title": "How to Read Very Large TXT Files",
        "slug": "read-large-txt-files",
        "primary_language": language,
        "priority": "high",
        "search_intent": "solve",
        "related_apps": "",
        "primary_keyword": "large TXT file reader",
        "secondary_keywords": "TXT reader|large text file|virtual rendering",
        "evergreen": "true",
        "source_type": "user_question",
        "canonical_path": path,
        "published_url": "",
        "scheduled_at": "",
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
description: "Learn how to choose a large TXT file reader without unnecessary lag."
status: "review"
topic_id: "TOPIC-0001"
search_intent: "solve"
primary_keyword: "large TXT file reader"
secondary_keywords: "TXT reader|large text file|virtual rendering"
related_apps: ""
canonical_url: "https://example.com/blog/en/read-large-txt-files/"
published_at: "2026-07-14T09:00:00+09:00"
updated_at: "2026-07-14T09:00:00+09:00"
tags: "large TXT file reader|TXT reader|plain text"
---

# How to Read Very Large TXT Files

## Question

How can I read very large TXT files?

## Short Answer

Use a reader workflow that separates file size, encoding, search behavior, and virtual rendering before choosing an app.

## Why This Problem Happens

Encoding is the rule an app uses to turn bytes into readable characters. Virtual rendering is a technique that renders only the visible portion of a document.

## What To Check First

- Confirm the file is plain text.
- Check the encoding.
- Avoid rich text conversion.

## Recommended Workflow

1. Open a copy of the file.
2. Check the encoding.
3. Use search before repeated scrolling.
4. Choose a large TXT file reader only after the workflow is clear.

![Workflow diagram](/blog-assets/en/read-large-txt-files/workflow-diagram.svg "Workflow diagram")

## Loading the Whole File vs Rendering What You Need

| Approach | Best for |
| --- | --- |
| Render visible text | Very large TXT files |

## ONNELLAB Application

No ONNELLAB application is required to understand this workflow.

## References

- [The Unicode Standard](https://www.unicode.org/versions/latest/) for encoding references.

## Conclusion

Start with the reading task, confirm encoding, and choose the simplest workflow that solves the problem.

## FAQ

### Can a large TXT file damage my device?

No. The usual risk is that an app may become slow or unresponsive.
"""


class PublicationAutomationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.topics_path = self.root / "data" / "topics.csv"
        self.legacy_path = self.root / "topics" / "topics.csv"
        self.markdown_path = self.root / "generated" / "markdown" / "en" / "reading" / "read-large-txt-files.md"
        self.ko_markdown_path = self.root / "generated" / "markdown" / "ko" / "reading" / "read-large-txt-files.md"
        self.asset_path = self.root / "generated" / "assets" / "blog" / "en" / "read-large-txt-files" / "workflow-diagram.svg"
        self.ko_asset_path = self.root / "generated" / "assets" / "blog" / "ko" / "read-large-txt-files" / "workflow-diagram.svg"
        self.metadata_path = self.root / "generated" / "metadata" / "en" / "reading" / "read-large-txt-files" / "internal_links.json"
        self.review_root = self.root / "generated" / "reviews"
        self.topics_path.parent.mkdir(parents=True)
        self.legacy_path.parent.mkdir(parents=True)
        self.markdown_path.parent.mkdir(parents=True)
        self.ko_markdown_path.parent.mkdir(parents=True)
        self.asset_path.parent.mkdir(parents=True)
        self.ko_asset_path.parent.mkdir(parents=True)
        self.metadata_path.parent.mkdir(parents=True)
        self.markdown_path.write_text(MARKDOWN, encoding="utf-8")
        self.ko_markdown_path.write_text(
            MARKDOWN.replace('language: "en"', 'language: "ko"').replace('/blog-assets/en/', '/blog-assets/ko/'),
            encoding="utf-8",
        )
        self.asset_path.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n", encoding="utf-8")
        self.ko_asset_path.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n", encoding="utf-8")
        self.metadata_path.write_text(
            json.dumps({"recommendations": {"related_articles": [{"topic_id": "TOPIC-0002"}]}}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def read_rows(self) -> list[dict[str, str]]:
        with self.topics_path.open("r", encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    def test_evaluates_article_above_publication_threshold(self) -> None:
        write_topics(self.topics_path, [topic_row("review")])
        write_topics(self.legacy_path, [topic_row("review")])

        path = evaluate_article(
            "TOPIC-0001",
            topics_path=self.topics_path,
            metadata_root=self.root / "generated" / "metadata",
            assets_root=self.root / "generated" / "assets" / "blog",
            review_root=self.review_root,
        )

        review = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreater(review["score"], 9.0)
        self.assertTrue(review["passed"])

    def test_schedules_only_reviewed_articles_above_threshold_every_three_days(self) -> None:
        published = topic_row("published", "TOPIC-0002")
        published["slug"] = "already-published"
        published["canonical_path"] = "generated/markdown/en/reading/already-published.md"
        published["published_url"] = "https://example.com/blog/en/already-published/"
        published["published_at"] = "2026-07-11T09:00:00+09:00"
        review_en = topic_row("review", "TOPIC-0001", "en")
        review_ko = topic_row("review", "TOPIC-0003", "ko")
        write_topics(self.topics_path, [published, review_en, review_ko])
        write_topics(self.legacy_path, [published, review_en, review_ko])
        for language in ["en", "ko"]:
            review_path = self.review_root / language / "reading" / "read-large-txt-files" / "review.json"
            review_path.parent.mkdir(parents=True)
            review_path.write_text(json.dumps({"score": 9.2}), encoding="utf-8")

        scheduled = schedule_ready_articles(
            self.topics_path,
            self.review_root,
            self.legacy_path,
            now=datetime(2026, 7, 12, 9, tzinfo=KST),
        )

        self.assertEqual(len(scheduled), 2)
        self.assertEqual(scheduled[0]["status"], "scheduled")
        self.assertEqual(scheduled[0]["scheduled_at"], "2026-07-14T09:00:00+09:00")
        self.assertEqual(scheduled[1]["scheduled_at"], "2026-07-14T09:00:00+09:00")

    def test_publishes_due_article_only_when_review_score_exceeds_threshold(self) -> None:
        en = topic_row("scheduled", "TOPIC-0001", "en")
        ko = topic_row("scheduled", "TOPIC-0002", "ko")
        en["scheduled_at"] = "2026-07-14T09:00:00+09:00"
        ko["scheduled_at"] = "2026-07-14T09:00:00+09:00"
        write_topics(self.topics_path, [en, ko])
        write_topics(self.legacy_path, [en, ko])
        for language in ["en", "ko"]:
            review_path = self.review_root / language / "reading" / "read-large-txt-files" / "review.json"
            review_path.parent.mkdir(parents=True)
            review_path.write_text(json.dumps({"score": 9.4}), encoding="utf-8")

        published = publish_due_articles(
            self.topics_path,
            self.review_root,
            self.legacy_path,
            site_url="https://example.com/",
            now=datetime(2026, 7, 14, 9, tzinfo=KST),
        )

        self.assertEqual(len(published), 2)
        rows = self.read_rows()
        self.assertEqual(rows[0]["status"], "published")
        self.assertEqual(rows[0]["published_url"], "https://example.com/blog/en/read-large-txt-files/")
        self.assertEqual(rows[1]["status"], "published")
        self.assertEqual(rows[1]["published_url"], "https://example.com/blog/ko/read-large-txt-files/")
        content = self.markdown_path.read_text(encoding="utf-8")
        self.assertIn('status: "published"', content)
        self.assertIn('published_at: "2026-07-14T09:00:00+09:00"', content)
        ko_content = self.ko_markdown_path.read_text(encoding="utf-8")
        self.assertIn('status: "published"', ko_content)


if __name__ == "__main__":
    unittest.main()
