from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from topic_management import APP_HEADER, TOPIC_HEADER, TopicError, TopicStore, write_topics


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


def topic_fields(slug: str = "read-large-txt-files", related_apps: str = "VaultXT") -> dict[str, str]:
    return {
        "category": "reading",
        "primary_question": "How can I read very large TXT files?",
        "working_title": "How to Read Very Large TXT Files",
        "slug": slug,
        "primary_language": "en",
        "priority": "normal",
        "search_intent": "solve",
        "related_apps": related_apps,
        "primary_keyword": "large TXT files",
        "secondary_keywords": "TXT reader|large text file",
        "evergreen": "true",
        "source_type": "user_question",
        "review_required": "true",
        "notes": "",
    }


class TopicManagementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.topics_path = self.root / "data" / "topics.csv"
        self.apps_path = self.root / "data" / "apps_registry.csv"
        self.mirror_path = self.root / "topics" / "topics.csv"
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

    def rows(self) -> list[dict[str, str]]:
        with self.topics_path.open("r", encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    def test_add_topic_generates_incrementing_ids(self) -> None:
        first = self.store.add(topic_fields("read-large-txt-files"))
        second = self.store.add(topic_fields("organize-large-txt-files"))

        self.assertEqual(first["id"], "TOPIC-0001")
        self.assertEqual(second["id"], "TOPIC-0002")
        self.assertEqual(second["status"], "idea")

    def test_add_rejects_provided_id(self) -> None:
        fields = topic_fields()
        fields["id"] = "TOPIC-9999"

        with self.assertRaisesRegex(TopicError, "generated automatically"):
            self.store.add(fields)

    def test_approve_allows_idea_to_approved(self) -> None:
        topic = self.store.add(topic_fields())
        approved = self.store.approve(topic["id"])

        self.assertEqual(approved["status"], "approved")

    def test_rejects_invalid_status_transition(self) -> None:
        topic = self.store.add(topic_fields())
        self.store.approve(topic["id"])

        with self.assertRaisesRegex(TopicError, "invalid status transition"):
            self.store.archive(topic["id"])

    def test_archive_allows_idea(self) -> None:
        topic = self.store.add(topic_fields())
        archived = self.store.archive(topic["id"])

        self.assertEqual(archived["status"], "archived")

    def test_rejects_duplicated_ids(self) -> None:
        row = {field: "" for field in TOPIC_HEADER}
        row.update(topic_fields())
        row["id"] = "TOPIC-0001"
        row["status"] = "idea"

        with self.assertRaisesRegex(TopicError, "duplicated topic id"):
            self.store.write([row, dict(row)])

    def test_rejects_duplicated_slugs(self) -> None:
        self.store.add(topic_fields("read-large-txt-files"))

        with self.assertRaisesRegex(TopicError, "duplicated topic slug"):
            self.store.add(topic_fields("read-large-txt-files"))

    def test_rejects_unknown_application_names(self) -> None:
        with self.assertRaisesRegex(TopicError, "unknown app"):
            self.store.add(topic_fields(related_apps="MissingApp"))

    def test_edit_updates_topic_and_mirror(self) -> None:
        topic = self.store.add(topic_fields())
        edited = self.store.edit(topic["id"], {"notes": "Reviewed by editor"})

        self.assertEqual(edited["notes"], "Reviewed by editor")
        with self.mirror_path.open("r", encoding="utf-8", newline="") as file:
            mirror_rows = list(csv.DictReader(file))
        self.assertEqual(mirror_rows[0]["notes"], "Reviewed by editor")


if __name__ == "__main__":
    unittest.main()
