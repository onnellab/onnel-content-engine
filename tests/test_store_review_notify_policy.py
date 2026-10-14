import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_daily_local as daily
from publish_store_review_reply import publish, main as publish_main
from queue_standing_store_review_replies import acknowledge_notification, prepare_notifications, queue_replies
from store_review_approvals import approve_review
from store_review_policy import approval_fingerprint, require_owner_approval


class OwnerReviewPolicy(unittest.TestCase):
    def review(self, platform="ios"):
        return {"review_id": "review-1", "app_id": "APP-1", "app_slug": "test",
                "app_name": "Test", "platform": platform, "status": "pending", "review_kind": "review",
                "rating": "2", "title": "A suggestion", "body": "Please improve this.",
                "updated_at": "2026-10-14T06:00:00Z"}

    def approval(self, review):
        return approve_review({"review-1": review}, {"approvals": []}, "review-1", "Thank you for the feedback.",
                              "owner_explicit_chat_approval", approval_reference="Sentinel_11111111111111111111111111111111")

    def test_missing_evidence_cannot_create_approval(self):
        with self.assertRaisesRegex(ValueError, "reference"):
            approve_review({"review-1": self.review()}, {"approvals": []}, "review-1", "Thanks.", "owner")

    def test_both_stores_fail_closed_before_request(self):
        for platform in ("ios", "android"):
            review = self.review(platform)
            valid = self.approval(review)
            for changes in ({"approval_type": "standing"}, {"approval_reference": ""},
                            {"approved_by": "owner_standing_scheduled_policy_2026-09-24"},
                            {"reply": "Changed text"}, {"review_id": "different"},
                            {"approved_at": "2026-10-13T00:00:00Z"},
                            {"status": "failed"}, {"status": "published"}):
                with self.subTest(platform=platform, changes=changes):
                    requester = Mock(side_effect=AssertionError("must not send"))
                    with self.assertRaises(ValueError):
                        publish({**valid, **changes}, "apple", "google", Path("missing"), requester, review=review)
                    requester.assert_not_called()

    def test_current_review_edit_or_reply_invalidates_approval(self):
        review = self.review()
        record = self.approval(review)
        for changes in ({"body": "Edited review"}, {"rating": "1"}, {"developer_reply": "Already replied"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                require_owner_approval(record, {**review, **changes})

    def test_explicit_owner_approval_can_publish_one_ios_reply(self):
        review = self.review()
        record = self.approval(review)
        requester = Mock(return_value={"data": {"id": "mock-response"}})
        self.assertEqual("mock-response", publish(record, "mock", "", Path("missing"), requester, review=review))
        self.assertEqual(1, requester.call_count)
        self.assertEqual(record["reply"], requester.call_args.args[3]["data"]["attributes"]["responseBody"])

    def test_scheduled_queue_never_consumes_explicit_approval(self):
        review = self.review()
        record = self.approval(review)
        self.assertEqual(([], False), queue_replies({"review-1": review}, {"approvals": [record]}))

    def test_published_history_remains_byte_equivalent(self):
        record = {"status": "published", "approved_by": "old-standing", "publication": {"attempts": 1}}
        payload = {"approvals": [record]}
        original = copy.deepcopy(payload)
        self.assertEqual(([], False), queue_replies({}, payload))
        self.assertEqual(original, payload)

    def test_notification_dedup_and_receipt_are_separate_from_approval(self):
        reviews = {"review-1": self.review()}
        state = {"notifications": []}
        pending, changed = prepare_notifications(reviews, state)
        self.assertTrue(changed)
        self.assertEqual(1, len(pending))
        self.assertEqual("Please improve this.", pending[0]["body"])
        identity = pending[0]["notification_id"]
        self.assertFalse(prepare_notifications(reviews, state)[1])
        acknowledge_notification(state, identity, "Sentinel_22222222222222222222222222222222")
        self.assertEqual(([], False), prepare_notifications(reviews, state))
        acknowledge_notification(state, identity, "Sentinel_22222222222222222222222222222222")
        self.assertNotIn("approvals", state)
        reviews["review-1"]["body"] = "Updated suggestion"
        pending, changed = prepare_notifications(reviews, state)
        self.assertTrue(changed)
        self.assertEqual(1, len(pending))
        self.assertNotEqual(identity, pending[0]["notification_id"])

    def test_unconfirmed_delivery_is_not_acknowledged(self):
        state = {"notifications": []}
        pending, _ = prepare_notifications({"review-1": self.review()}, state)
        with self.assertRaises(ValueError):
            acknowledge_notification(state, pending[0]["notification_id"], "")
        self.assertEqual("pending", pending[0]["status"])

    def test_disappeared_review_not_notified(self):
        state = {"notifications": []}
        prepare_notifications({"review-1": self.review()}, state)
        self.assertEqual([], prepare_notifications({}, state)[0])
        self.assertEqual("superseded", state["notifications"][0]["status"])

    def test_notification_reappears_without_prior_delivery(self):
        reviews = {"review-1": self.review()}
        state = {"notifications": []}
        original_id = prepare_notifications(reviews, state)[0][0]["notification_id"]
        prepare_notifications({}, state)
        pending, changed = prepare_notifications(reviews, state)
        self.assertTrue(changed)
        self.assertEqual(original_id, pending[0]["notification_id"])
        self.assertEqual(1, len(state["notifications"]))

    def test_local_log_and_workflow_ids_are_not_owner_evidence(self):
        state = {"notifications": []}
        pending, _ = prepare_notifications({"review-1": self.review()}, state)
        for reference in ("log-created", "123456789", "workflow-run-123", "/tmp/receipt.json", "owner-message-test"):
            with self.subTest(reference=reference):
                with self.assertRaisesRegex(ValueError, "message reference"):
                    acknowledge_notification(state, pending[0]["notification_id"], reference)
                with self.assertRaisesRegex(ValueError, "message reference"):
                    approve_review({"review-1": self.review()}, {"approvals": []}, "review-1", "Thanks.",
                                   "owner", approval_reference=reference)
        with self.assertRaisesRegex(ValueError, "actor"):
            approve_review({"review-1": self.review()}, {"approvals": []}, "review-1", "Thanks.", "", 
                           approval_reference="Sentinel_" + "1" * 32)

    def test_recomputed_hash_cannot_bind_another_review_target(self):
        review = self.review()
        record = self.approval(review)
        for field in ("review_id", "app_id", "platform"):
            changed = {**record, field: "android" if field == "platform" else "another"}
            changed["approval_sha256"] = approval_fingerprint(changed)
            requester = Mock()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "target"):
                publish(changed, "apple", "google", Path("missing"), requester, review=review)
            requester.assert_not_called()

    def test_daily_report_preserves_notifications_never_dispatches_writer(self):
        report = {"blockers": []}
        payload = {"mode": "notify_only", "queued": [], "publication_allowed": False,
                   "changed": False, "notifications": [{"review_id": "review-1", "body": "Feedback"}]}
        with patch.object(daily, "run_step", return_value=(0, json.dumps(payload), "")) as run:
            daily.run_store_review_auto_replies(report)
        self.assertEqual(1, run.call_count)
        self.assertEqual(payload, report["store_review_notifications"])
        self.assertEqual([], report["store_review_auto_replies"]["queued"])
        self.assertFalse(report["blockers"])

    def test_daily_rejects_legacy_queue_contract_without_any_dispatch(self):
        report = {"blockers": []}
        with patch.object(daily, "run_step", return_value=(0, '{"queued":[{"approval_id":"old"}]}', "")) as run:
            daily.run_store_review_auto_replies(report)
        self.assertEqual(1, run.call_count)
        self.assertIn("store_review_notification_contract_invalid", report["blockers"])


if __name__ == "__main__":
    unittest.main()
