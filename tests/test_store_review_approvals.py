from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from store_review_approvals import approve_review  # noqa: E402


class StoreReviewApprovalsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reviews = {"review-1": {"review_id": "review-1", "app_id": "APP-1", "app_slug": "demo", "platform": "android", "status": "pending", "developer_reply": ""}}

    def test_approval_creates_a_queued_audit_record(self) -> None:
        payload = {"schema_version": 1, "approvals": []}
        record = approve_review(self.reviews, payload, "review-1", "Thanks for the feedback.", "owner")
        self.assertEqual(record["status"], "queued")
        self.assertEqual(payload["approvals"][0]["reply"], "Thanks for the feedback.")

    def test_rejects_unverified_fix_promise(self) -> None:
        with self.assertRaisesRegex(ValueError, "prohibited"):
            approve_review(self.reviews, {"schema_version": 1, "approvals": []}, "review-1", "It will be fixed next update.", "owner")


if __name__ == "__main__":
    unittest.main()
