from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from triage_store_reviews import triage_reviews  # noqa: E402


class TriageStoreReviewsTest(unittest.TestCase):
    def test_pricing_pattern_is_grouped_and_grounded(self) -> None:
        rows = [
            {"review_id": str(index), "app_slug": "tagweaver", "rating": "1", "body": "not free as stated"}
            for index in range(3)
        ]
        root = Path(__file__).resolve().parents[1]
        result = triage_reviews(rows, (root / "docs/operations/APP_FACTS.md", root / "docs/operations/PRICING_FACTS.md"))
        item = result["items"][0]
        self.assertEqual(item["category"], "pricing_confusion")
        self.assertEqual(item["similar_reviews"], 3)
        self.assertEqual(item["actions"]["store_copy"], "review_recommended")
        self.assertTrue(item["facts"])

    def test_bug_only_creates_an_issue_draft(self) -> None:
        result = triage_reviews([{"review_id": "1", "app_slug": "vaultxt", "rating": "1", "body": "The app crashes"}], ())
        item = result["items"][0]
        self.assertEqual(item["actions"]["github_issue"], "approval_required")
        self.assertIn("unverified", item["issue_draft"])


if __name__ == "__main__":
    unittest.main()
