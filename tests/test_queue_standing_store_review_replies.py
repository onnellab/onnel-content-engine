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
        self.assertFalse(eligible(self.review(review_id="report-synthetic")))
        self.assertFalse(eligible(self.review(review_kind="rating_only", title="", body="")))
        self.assertFalse(eligible(self.review(developer_reply="Thanks", status="replied")))

    def test_new_review_gets_owner_standing_approval(self):
        review = self.review()
        payload = {"schema_version": 1, "updated_at": "", "approvals": []}
        queued, changed = queue_replies({review["review_id"]: review}, payload)
        self.assertTrue(changed)
        self.assertEqual(len(queued), 1)
        record = payload["approvals"][0]
        self.assertEqual(record["status"], "queued")
        self.assertEqual(record["approved_by"], "owner_standing_scheduled_policy_2026-09-24")
        self.assertIn("Thank you", record["reply"])

    def test_failed_review_reuses_same_durable_record(self):
        review = self.review()
        existing = {
            "approval_id": "review-real-review-1",
            "review_id": "real-review-1",
            "app_id": "APP-0002",
            "app_slug": "tagweaver",
            "platform": "ios",
            "reply": "Thanks for the feedback.",
            "approved_at": "2026-09-24T00:00:00+00:00",
            "approved_by": "owner_standing_scheduled_policy_2026-09-24",
            "note": "standing",
            "status": "failed",
            "publication": {"attempts": 1, "error": "temporary"},
        }
        payload = {"schema_version": 1, "updated_at": "", "approvals": [existing]}
        queued, changed = queue_replies({review["review_id"]: review}, payload)
        self.assertTrue(changed)
        self.assertEqual(len(payload["approvals"]), 1)
        self.assertEqual(payload["approvals"][0]["approval_id"], "review-real-review-1")
        self.assertEqual(payload["approvals"][0]["status"], "queued")
        self.assertEqual(payload["approvals"][0]["publication"]["attempts"], 1)
        self.assertEqual(queued[0]["source"], "existing_durable_record")

    def test_published_or_rating_only_review_is_not_queued(self):
        review = self.review(developer_reply="Already replied", status="replied")
        payload = {"schema_version": 1, "updated_at": "", "approvals": []}
        queued, changed = queue_replies({review["review_id"]: review}, payload)
        self.assertEqual(queued, [])
        self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
