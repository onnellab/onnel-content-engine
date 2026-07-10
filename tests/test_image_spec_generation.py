from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_image_spec import ImageSpecError, generate_image_spec
from generate_markdown import generate_markdown
from topic_management import APP_HEADER, TopicStore, write_topics


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


class ImageSpecGenerationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.topics_path = self.root / "data" / "topics.csv"
        self.apps_path = self.root / "data" / "apps_registry.csv"
        self.mirror_path = self.root / "topics" / "topics.csv"
        self.markdown_root = self.root / "generated" / "markdown"
        self.image_root = self.root / "generated" / "images"
        self.template_path = ROOT / "templates" / "blog" / "markdown_draft.md"
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

    def make_markdown_draft(self) -> Path:
        topic = self.store.add(topic_fields())
        self.store.approve(topic["id"])
        return generate_markdown(
            topic["id"],
            topics_path=self.topics_path,
            apps_path=self.apps_path,
            template_path=self.template_path,
            output_root=self.markdown_root,
            legacy_topics_path=self.mirror_path,
        )

    def test_generates_image_spec_from_markdown_draft(self) -> None:
        markdown_path = self.make_markdown_draft()

        spec_path = generate_image_spec(
            markdown_path,
            topics_path=self.topics_path,
            apps_path=self.apps_path,
            output_root=self.image_root,
            legacy_topics_path=self.mirror_path,
        )

        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        rows = self.read_topics()
        self.assertEqual(rows[0]["status"], "image_planning")
        self.assertEqual(spec_path.name, "image_spec.json")
        self.assertEqual(spec["generation_scope"], "specification_only")
        self.assertFalse(spec["image_generation_allowed"])
        self.assertIn("required_infographic_types", spec)
        self.assertIn("screenshot_requirements", spec)
        self.assertIn("workflow_diagrams", spec)
        self.assertIn("comparison_diagrams", spec)
        self.assertEqual(spec["screenshot_requirements"]["applications"], ["VaultXT"])
        self.assertTrue(spec["workflow_diagrams"])
        self.assertTrue(spec["comparison_diagrams"])

    def test_rejects_non_draft_topic(self) -> None:
        topic = self.store.add(topic_fields())
        self.store.approve(topic["id"])
        markdown_path = self.markdown_root / "en" / "reading" / "manual.md"
        markdown_path.parent.mkdir(parents=True)
        markdown_path.write_text('---\ntopic_id: "TOPIC-0001"\n---\n# Manual\n', encoding="utf-8")

        with self.assertRaisesRegex(ImageSpecError, "must be in draft status"):
            generate_image_spec(
                markdown_path,
                topics_path=self.topics_path,
                apps_path=self.apps_path,
                output_root=self.image_root,
                legacy_topics_path=self.mirror_path,
            )


if __name__ == "__main__":
    unittest.main()
