from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from triage_store_reviews import triage_reviews  # noqa: E402


class TriageStoreReviewsTest(unittest.TestCase):
    def test_operational_dismissal_is_bound_to_review_update(self) -> None:
        row = {
            "review_id": "historical", "updated_at": "2026-07-11T18:07:19+00:00",
            "app_slug": "vaultxt", "rating": "1", "body": "The app crashes",
        }
        with tempfile.TemporaryDirectory() as raw:
            overrides = Path(raw) / "overrides.json"
            overrides.write_text(json.dumps({"reviews": {"historical": {
                "updated_at": row["updated_at"], "operational_status": "dismissed",
                "note": "no verified fix",
            }}}), encoding="utf-8")
            item = triage_reviews([row], (), overrides)["items"][0]
            self.assertEqual(item["category"], "bug")
            self.assertEqual(item["risk_flags"], ["bug"])
            self.assertFalse(item["requires_human_approval"])
            self.assertEqual(item["actions"], {
                "reply": "not_needed", "github_issue": "not_needed",
                "store_copy": "not_needed", "code_change": "not_needed",
            })
            self.assertEqual(item["issue_draft"], "")
            self.assertEqual(item["operational_status"], "dismissed")
            self.assertEqual(item["operational_note"], "no verified fix")

            changed = dict(row, updated_at="2026-09-20T00:00:00+00:00")
            changed_item = triage_reviews([changed], (), overrides)["items"][0]
            self.assertNotIn("operational_status", changed_item)
            self.assertTrue(changed_item["requires_human_approval"])
            self.assertEqual(changed_item["actions"]["code_change"], "investigate")
            self.assertTrue(changed_item["issue_draft"])

    def test_unrelated_bug_remains_active(self) -> None:
        item = triage_reviews([{
            "review_id": "new", "updated_at": "2026-09-20T00:00:00+00:00",
            "app_slug": "vaultxt", "rating": "1", "body": "The app crashes",
        }], ())["items"][0]
        self.assertEqual(item["category"], "bug")
        self.assertNotIn("operational_status", item)

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
