"""Keep repaired source articles aligned with the unchanged publication gate."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_article import find_topic, markdown_path_for, parse_front_matter, score_article


class ContentQualityRegressionsTest(unittest.TestCase):
    def test_large_txt_language_pair_passes_every_readiness_check(self) -> None:
        self.assert_articles_publishable(("TOPIC-0001", "TOPIC-0005"))

    def assert_articles_publishable(self, topic_ids: tuple[str, ...]) -> None:
        topics_path = ROOT / "data" / "topics.csv"
        for topic_id in topic_ids:
            with self.subTest(topic_id=topic_id):
                topic = find_topic(topic_id, topics_path)
                markdown = markdown_path_for(topic, topics_path).read_text(encoding="utf-8")
                metadata, _ = parse_front_matter(markdown)
                self.assertEqual(metadata["primary_keyword"], topic["primary_keyword"])
                review = score_article(
                    topic, markdown, topics_path,
                    ROOT / "generated" / "metadata",
                    ROOT / "generated" / "assets" / "blog",
                )
                failed = [check["name"] for check in review["checks"] if not check["passed"]]
                self.assertEqual(failed, [], f"{topic_id}: {failed}")
                self.assertTrue(review["passed"])
                self.assertGreater(review["score"], review["threshold"])


if __name__ == "__main__":
    unittest.main()
