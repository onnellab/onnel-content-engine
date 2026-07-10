from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_markdown import MarkdownGenerationError, generate_markdown
from topic_management import APP_HEADER, TOPIC_HEADER, TopicStore, write_topics


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
]


def topic_fields() -> dict[str, str]:
    return {
        "category": "reading",
        "primary_question": "How can I read very large TXT files?",
        "working_title": "How to Read Very Large TXT Files",
        "slug": "read-large-txt-files",
        "primary_language": "en",
        "priority": "normal",
        "search_intent": "solve",
        "related_apps": "VaultXT",
        "primary_keyword": "large TXT files",
        "secondary_keywords": "TXT reader|large text file|file performance",
        "evergreen": "true",
        "source_type": "user_question",
        "review_required": "true",
        "notes": "",
    }


class MarkdownGenerationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.topics_path = self.root / "data" / "topics.csv"
        self.apps_path = self.root / "data" / "apps_registry.csv"
        self.mirror_path = self.root / "topics" / "topics.csv"
        self.template_path = ROOT / "templates" / "blog" / "markdown_draft.md"
        self.output_root = self.root / "generated" / "markdown"
        self.topics_path.parent.mkdir(parents=True)
        self.apps_path.parent.mkdir(parents=True, exist_ok=True)
        self.mirror_path.parent.mkdir(parents=True)
        write_topics(self.topics_path, [])
        write_topics(self.mirror_path, [])
        with self.apps_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=APP_HEADER, lineterminator="\n")
            writer.writeheader()
            writer.writerows(APP_ROWS)
        self.store = TopicStore(self.topics_path, self.apps_path, self.mirror_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def read_topics(self) -> list[dict[str, str]]:
        with self.topics_path.open("r", encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    def test_generates_markdown_draft_from_approved_topic(self) -> None:
        topic = self.store.add(topic_fields())
        self.store.approve(topic["id"])

        path = generate_markdown(
            topic["id"],
            topics_path=self.topics_path,
            apps_path=self.apps_path,
            template_path=self.template_path,
            output_root=self.output_root,
            legacy_topics_path=self.mirror_path,
        )

        content = path.read_text(encoding="utf-8")
        rows = self.read_topics()
        self.assertEqual(rows[0]["status"], "draft")
        self.assertEqual(rows[0]["canonical_path"], "generated/markdown/en/reading/read-large-txt-files.md")
        self.assertIn('card_title: "Read Very Large TXT Files"', content)
        self.assertIn('description: "Learn how to evaluate large TXT files', content)
        self.assertIn('image_specs: "Workflow diagram for large TXT files', content)
        self.assertIn("# How to Read Very Large TXT Files", content)
        self.assertIn("## Question", content)
        self.assertIn("## Short Answer", content)
        self.assertIn("## What Makes This Problem Feel Worse", content)
        self.assertIn("## Recommended Workflow", content)
        self.assertIn("![Workflow diagram placeholder](/blog-assets/en/read-large-txt-files/workflow-diagram.svg", content)
        self.assertIn("## ONNELLAB Application", content)
        self.assertIn("## References", content)
        self.assertIn("## Conclusion", content)
        self.assertIn("[VaultXT](/apps/vaultxt/)", content)
        self.assertLess(content.index("## Recommended Workflow"), content.index("## ONNELLAB Application"))
        self.assertNotIn("image generation", content.lower())

    def test_rejects_unapproved_topic(self) -> None:
        topic = self.store.add(topic_fields())

        with self.assertRaisesRegex(MarkdownGenerationError, "must be approved"):
            generate_markdown(
                topic["id"],
                topics_path=self.topics_path,
                apps_path=self.apps_path,
                template_path=self.template_path,
                output_root=self.output_root,
                legacy_topics_path=self.mirror_path,
            )

    def test_rejects_ineligible_related_app(self) -> None:
        APP_ROWS[0]["content_eligible"] = "false"
        try:
            with self.apps_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=APP_HEADER, lineterminator="\n")
                writer.writeheader()
                writer.writerows(APP_ROWS)
            topic = self.store.add(topic_fields())
            self.store.approve(topic["id"])

            with self.assertRaisesRegex(MarkdownGenerationError, "not eligible"):
                generate_markdown(
                    topic["id"],
                    topics_path=self.topics_path,
                    apps_path=self.apps_path,
                    template_path=self.template_path,
                    output_root=self.output_root,
                    legacy_topics_path=self.mirror_path,
                )
        finally:
            APP_ROWS[0]["content_eligible"] = "true"


if __name__ == "__main__":
    unittest.main()
