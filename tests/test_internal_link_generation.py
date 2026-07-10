from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_internal_links import InternalLinkError, generate_internal_links
from topic_management import APP_HEADER, TOPIC_HEADER, write_topics


APP_ROWS = [
    {
        "app_id": "APP-0001",
        "app_name": "VaultXT",
        "slug": "vaultxt",
        "status": "released",
        "product_group": "apps",
        "primary_category": "reading",
        "platforms": "ios|android",
        "pricing_model": "one_time_purchase",
        "content_eligible": "true",
        "official_site_path": "/apps/vaultxt/",
        "app_store_url": "",
        "play_store_url": "",
        "docs_path": "sources/vaultxt/",
        "one_line_description": "A text editor and viewer designed for working with large plain-text files.",
        "primary_language": "ko",
        "notes": "",
    },
    {
        "app_id": "APP-0002",
        "app_name": "TagWeaver",
        "slug": "tagweaver",
        "status": "released",
        "product_group": "apps",
        "primary_category": "music",
        "platforms": "ios|android",
        "pricing_model": "one_time_purchase",
        "content_eligible": "true",
        "official_site_path": "/apps/tagweaver/",
        "app_store_url": "",
        "play_store_url": "",
        "docs_path": "sources/tagweaver/",
        "one_line_description": "A local MP3 metadata editor designed for focused tag management.",
        "primary_language": "ko",
        "notes": "",
    },
]


def topic_row(
    topic_id: str,
    category: str,
    title: str,
    slug: str,
    keyword: str,
    secondary: str,
    related_apps: str,
    status: str = "draft",
    intent: str = "solve",
) -> dict[str, str]:
    return {
        "id": topic_id,
        "status": status,
        "category": category,
        "primary_question": f"How should I understand {keyword}?",
        "working_title": title,
        "slug": slug,
        "primary_language": "en",
        "priority": "normal",
        "search_intent": intent,
        "related_apps": related_apps,
        "primary_keyword": keyword,
        "secondary_keywords": secondary,
        "evergreen": "true",
        "source_type": "user_question",
        "canonical_path": f"generated/markdown/en/{category}/{slug}.md",
        "published_url": "",
        "scheduled_at": "",
        "published_at": "",
        "updated_at": "",
        "review_required": "true",
        "notes": "",
    }


class InternalLinkGenerationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.topics_path = self.root / "data" / "topics.csv"
        self.apps_path = self.root / "data" / "apps_registry.csv"
        self.output_root = self.root / "generated" / "metadata"
        self.markdown_path = self.root / "generated" / "markdown" / "en" / "reading" / "read-large-txt-files.md"
        self.topics_path.parent.mkdir(parents=True)
        self.apps_path.parent.mkdir(parents=True, exist_ok=True)
        self.markdown_path.parent.mkdir(parents=True)
        self.markdown_path.write_text("# Existing article\n\nDo not edit this text.\n", encoding="utf-8")
        with self.apps_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=APP_HEADER, lineterminator="\n")
            writer.writeheader()
            writer.writerows(APP_ROWS)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_topic_rows(self, rows: list[dict[str, str]]) -> None:
        write_topics(self.topics_path, rows)

    def test_generates_recommendation_metadata_without_editing_markdown(self) -> None:
        before = self.markdown_path.read_text(encoding="utf-8")
        self.write_topic_rows(
            [
                topic_row(
                    "TOPIC-0001",
                    "reading",
                    "How to Read Large TXT Files",
                    "read-large-txt-files",
                    "large TXT files",
                    "TXT reader|file performance|encoding",
                    "VaultXT",
                ),
                topic_row(
                    "TOPIC-0002",
                    "reading",
                    "TXT Reader Performance Basics",
                    "txt-reader-performance",
                    "TXT reader performance",
                    "large TXT files|virtual rendering",
                    "VaultXT",
                    status="published",
                    intent="learn",
                ),
                topic_row(
                    "TOPIC-0003",
                    "media",
                    "File Metadata Basics",
                    "file-metadata-basics",
                    "file metadata",
                    "metadata|file formats",
                    "TagWeaver",
                    status="draft",
                    intent="learn",
                ),
            ]
        )

        path = generate_internal_links(
            "TOPIC-0001",
            topics_path=self.topics_path,
            apps_path=self.apps_path,
            output_root=self.output_root,
        )

        metadata = json.loads(path.read_text(encoding="utf-8"))
        after = self.markdown_path.read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertEqual(path.name, "internal_links.json")
        self.assertEqual(metadata["generation_scope"], "metadata_only")
        self.assertFalse(metadata["article_text_modified"])
        self.assertEqual(metadata["recommendations"]["related_apps"][0]["app_name"], "VaultXT")
        self.assertEqual(metadata["recommendations"]["related_articles"][0]["topic_id"], "TOPIC-0002")
        self.assertTrue(metadata["recommendations"]["related_guides"])

    def test_rejects_unknown_application_name(self) -> None:
        self.write_topic_rows(
            [
                topic_row(
                    "TOPIC-0001",
                    "reading",
                    "How to Read Large TXT Files",
                    "read-large-txt-files",
                    "large TXT files",
                    "TXT reader|file performance|encoding",
                    "MissingApp",
                )
            ]
        )

        with self.assertRaisesRegex(InternalLinkError, "unknown app"):
            generate_internal_links(
                "TOPIC-0001",
                topics_path=self.topics_path,
                apps_path=self.apps_path,
                output_root=self.output_root,
            )


if __name__ == "__main__":
    unittest.main()
