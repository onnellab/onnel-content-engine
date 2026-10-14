from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from queue_standing_store_review_replies import eligible, queue_replies  # noqa: E402


class StandingStoreReviewRepliesTest(unittest.TestCase):
    def review(self, **overrides):
        row = {
            "review_id": "real-review-1",
            "app_id": "APP-0002",
            "app_slug": "tagweaver",
            "app_name": "TagWeaver",
            "platform": "ios",
            "rating": "5",
            "review_kind": "review",
            "title": "Simple and useful",
            "body": "It just works",
            "reviewer_language": "en",
            "developer_reply": "",
            "status": "pending",
        }
        row.update(overrides)
        return row

    def test_eligible_requires_real_pending_text_review(self):
        self.assertTrue(eligible(self.review()))
        self.assertTrue(eligible(self.review(review_id="report-synthetic")))
        self.assertFalse(eligible(self.review(review_kind="rating_only", title="", body="")))
        self.assertFalse(eligible(self.review(developer_reply="Thanks", status="replied")))

    def test_new_review_never_creates_approval(self):
        review = self.review()
        payload = {"approvals": []}
        queued, changed = queue_replies({review["review_id"]: review}, payload)
        self.assertEqual([], queued)
        self.assertFalse(changed)
        self.assertEqual([], payload["approvals"])

    def test_standing_and_legacy_records_quarantined_without_retry(self):
        for status in ("queued", "failed"):
            with self.subTest(status=status):
                existing = {"approval_id": "old-id", "review_id": "real-review-1",
                            "reply": "Old draft", "status": status,
                            "approved_by": "owner_standing_scheduled_policy_2026-09-24",
                            "publication": {"attempts": 1, "error": "uncertain"}}
                payload = {"approvals": [existing]}
                queued, changed = queue_replies({}, payload)
                self.assertEqual([], queued)
                self.assertTrue(changed)
                self.assertEqual("awaiting_owner_approval", existing["status"])
                self.assertEqual(status, existing["previous_status"])
                self.assertEqual({"attempts": 1, "error": "uncertain"}, existing["publication"])
                self.assertEqual(([], False), queue_replies({}, payload))

    def test_published_or_rating_only_review_is_not_queued(self):
        review = self.review(developer_reply="Already replied", status="replied")
        payload = {"schema_version": 1, "updated_at": "", "approvals": []}
        queued, changed = queue_replies({review["review_id"]: review}, payload)
        self.assertEqual(queued, [])
        self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()

