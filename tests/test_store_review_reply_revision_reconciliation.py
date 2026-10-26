from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reconcile_store_review_reply_revisions import reconcile


ID = "10b4e93e-b9cd-4ef4-ad91-2726f5256651"
CHECKED = datetime(2026, 10, 26, 1, 26, 37, tzinfo=timezone.utc)
EXPECTED = "Original developer response"
REPLACEMENT = "Approved replacement observed in Google Play"


class StoreObservedRevisionReconciliationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.revisions = self.root / "store_review_reply_revisions.json"
        self.reviews = self.root / "store_reviews.csv"
        self.sync_status = self.root / "store_review_sync_status.json"
        checked = CHECKED.isoformat()
        self.row = {
            "review_id": ID, "app_id": "APP-0002", "app_slug": "tagweaver",
            "platform": "android", "rating": "3", "review_kind": "review",
            "title": "", "body": "The unchanged original review.",
            "app_version": "2.5.5", "developer_reply": REPLACEMENT,
            "status": "replied", "synced_at": checked, "verified_at": checked,
            "verification_source": "google_reviews_get",
        }
        self.record = {
            "revision_id": "revision-test-20261026",
            "review_id": ID, "app_id": "APP-0002", "app_slug": "tagweaver",
            "platform": "android", "rating": 3, "app_version": "2.5.5",
            "expected_review_title": "", "expected_review_body": self.row["body"],
            "expected_current_reply": EXPECTED, "replacement_reply": REPLACEMENT,
            "status": "published_unverified",
            "publication": {
                "attempts": 1, "last_attempt_at": (CHECKED - timedelta(minutes=2)).isoformat(),
                "published_at": "", "workflow_run_id": "40066870095",
                "workflow_run_attempt": "1", "approved_by": "onnellab",
                "approval_channel": "github_owner_workflow_dispatch",
                "store_observed_at": "", "error": "store_observation_not_yet_confirmed",
            },
        }
        self.status = {
            "schema_version": 1, "checked_at": checked, "stores": [{
                "app_id": "APP-0002", "app_slug": "tagweaver", "platform": "android",
                "state": "verified", "checked_at": checked,
                "source": "google_reviews_get_with_full_report_inventory",
            }],
        }
        self.save()

    def save(self):
        with self.reviews.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.row))
            writer.writeheader()
            writer.writerow(self.row)
        self.status["snapshot_sha256"] = hashlib.sha256(self.reviews.read_bytes()).hexdigest()
        self.sync_status.write_text(json.dumps(self.status))
        self.revisions.write_text(json.dumps({"schema_version": 1, "updated_at": "",
                                              "requests": [self.record]}))

    def read_record(self):
        return json.loads(self.revisions.read_text())["requests"][0]

    def run_reconcile(self):
        return reconcile(self.revisions, self.reviews, self.sync_status,
                         now=CHECKED + timedelta(minutes=1))

    def test_exact_fresh_authenticated_observation_only_marks_verified(self):
        self.assertEqual(self.run_reconcile(), 1)
        result = self.read_record()
        self.assertEqual(result["status"], "store_verified")
        publication = result["publication"]
        self.assertEqual(publication["store_observed_at"], self.row["verified_at"])
        self.assertEqual(publication["verification_source"], "google_reviews_get")
        self.assertEqual(publication["verification_snapshot_sha256"],
                         self.status["snapshot_sha256"])
        self.assertEqual(publication["previous_verification_error"],
                         "store_observation_not_yet_confirmed")
        self.assertEqual(publication["error"], "")
        self.assertEqual(publication["attempts"], 1)
        self.assertEqual(publication["workflow_run_id"], "40066870095")
        self.assertEqual(publication["published_at"], "")  # Never invent a publish time.

    def test_idempotent_and_does_not_change_verified_record_again(self):
        self.assertEqual(self.run_reconcile(), 1)
        before = self.revisions.read_bytes()
        self.assertEqual(self.run_reconcile(), 0)
        self.assertEqual(before, self.revisions.read_bytes())

    def test_changed_identity_or_reply_does_not_reconcile(self):
        for field, value in (
            ("developer_reply", EXPECTED),
            ("body", "Reviewer edited the text."),
            ("title", "Changed title"),
            ("rating", "2"),
            ("app_version", "2.5.6"),
            ("review_kind", "rating_only"),
            ("review_id", "report-synthetic-id"),
            ("status", "pending"),
            ("verification_source", "google_reports_csv"),
            ("verified_at", (CHECKED - timedelta(days=1)).isoformat()),
            ("synced_at", (CHECKED - timedelta(days=1)).isoformat()),
        ):
            with self.subTest(field=field):
                original = self.row[field]
                self.row[field] = value
                self.save()
                before = self.revisions.read_bytes()
                self.assertEqual(self.run_reconcile(), 0)
                self.assertEqual(self.revisions.read_bytes(), before)
                self.row[field] = original

    def test_incomplete_or_non_get_store_sync_does_not_verify(self):
        for field, value in (
            ("state", "partial"), ("state", "unavailable"),
            ("source", "google_reports_csv"),
            ("checked_at", (CHECKED - timedelta(days=1)).isoformat()),
        ):
            with self.subTest(field=field):
                original = self.status["stores"][0][field]
                self.status["stores"][0][field] = value
                self.save()
                self.assertEqual(self.run_reconcile(), 0)
                self.status["stores"][0][field] = original

    def test_stale_or_future_snapshot_is_not_live_evidence(self):
        for delta in (timedelta(days=2), -timedelta(minutes=2)):
            with self.subTest(delta=delta):
                self.assertEqual(reconcile(self.revisions, self.reviews, self.sync_status,
                                           now=CHECKED + delta), 0)

    def test_mismatched_checksum_fails_closed_without_writes(self):
        self.reviews.write_bytes(self.reviews.read_bytes() + b"\n")
        original = self.revisions.read_bytes()
        self.assertEqual(self.run_reconcile(), 0)
        self.assertEqual(self.revisions.read_bytes(), original)

    def test_no_dispatch_attempt_or_wrong_owner_never_grants_verification(self):
        for field, value in (
            ("attempts", 0), ("workflow_run_id", ""),
            ("workflow_run_attempt", "2"), ("approved_by", "someone_else"),
            ("approval_channel", "scheduled_worker"),
            ("last_attempt_at", ""),
            ("last_attempt_at", (CHECKED + timedelta(minutes=1)).isoformat()),
        ):
            with self.subTest(field=field):
                original = self.record["publication"][field]
                self.record["publication"][field] = value
                self.save()
                self.assertEqual(self.run_reconcile(), 0)
                self.record["publication"][field] = original

    def test_undispatched_or_already_verified_not_modified(self):
        for status in ("awaiting_owner_dispatch", "store_verified"):
            with self.subTest(status=status):
                self.record["status"] = status
                self.save()
                before = self.revisions.read_bytes()
                self.assertEqual(self.run_reconcile(), 0)
                self.assertEqual(self.revisions.read_bytes(), before)

    def test_missing_app_version_is_not_inferred_from_public_release(self):
        self.row["app_version"] = ""
        self.save()
        self.assertEqual(self.run_reconcile(), 0)


if __name__ == "__main__":
    unittest.main()
