from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from store_review_revision import apply_revision, process_revision, google_review_url


ID = "10b4e93e-b9cd-4ef4-ad91-2726f5256651"
BODY = "Some tags aren't removed correctly when the file is saved. When the X next to URL is pressed, for example, saving doesn't actually retain the change."
ORIGINAL = "Previously posted reply"
REPLACEMENT = "The Android 2.5.6 fix is under review by Google Play."
OWNER = {"actor": "onnellab", "repository": "onnellab/onnel-content-engine",
         "event": "workflow_dispatch", "run_id": "123456"}


def live(reply=ORIGINAL, *, body=BODY, rating=3, version="2.5.5", rid=ID):
    return {"reviewId": rid, "comments": [
        {"userComment": {"text": body, "starRating": rating, "appVersionName": version}},
        {"developerComment": {"text": reply}},
    ]}


def review():
    return {"review_id": ID, "app_id": "APP-0002", "app_slug": "tagweaver",
            "platform": "android", "review_kind": "review", "body": BODY,
            "rating": "3", "app_version": "2.5.5", "status": "replied",
            "developer_reply": ORIGINAL}


def revision():
    return {"revision_id": "revision-tagweaver-test", "review_id": ID,
            "app_id": "APP-0002", "app_slug": "tagweaver", "platform": "android",
            "app_version": "2.5.5", "rating": 3,
            "expected_review_body": BODY, "expected_current_reply": ORIGINAL,
            "replacement_reply": REPLACEMENT, "status": "awaiting_owner_dispatch",
            "publication": {"attempts": 0, "store_observed_at": ""}}


class PublishedReplyRevisionTest(unittest.TestCase):
    def test_manual_dispatch_verifies_live_original_then_replacement(self):
        r = revision()
        calls = []
        outcomes = iter([live(ORIGINAL), live(REPLACEMENT)])
        def post(url, token, method, body):
            calls.append((url, method, body))
            return {"result": {"lastEdited": {"seconds": "1"}}}
        state = apply_revision(r, review(), package="com.onnellab.tagweaver2",
                               google_token="private", getter=lambda *_: next(outcomes),
                               poster=post, **OWNER)
        self.assertEqual(state, "store_verified")
        self.assertEqual(r["publication"]["attempts"], 1)
        self.assertTrue(r["publication"]["store_observed_at"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], ("POST", {"replyText": REPLACEMENT}))
        self.assertTrue(calls[0][0].endswith("/reviews/" + ID + ":reply"))

    def test_already_updated_does_not_post(self):
        r = revision()
        calls = []
        state = apply_revision(r, review(), package="com.onnellab.tagweaver2",
                               google_token="private", getter=lambda *_: live(REPLACEMENT),
                               poster=lambda *args: calls.append(args), **OWNER)
        self.assertEqual(state, "store_verified")
        self.assertEqual(calls, [])
        self.assertEqual(r["publication"]["attempts"], 0)

    def test_after_uncertain_post_a_retry_only_observes(self):
        r = revision()
        outcomes = iter([live(ORIGINAL), live(ORIGINAL)])
        calls = []
        state = apply_revision(r, review(), package="com.onnellab.tagweaver2",
                               google_token="private", getter=lambda *_: next(outcomes),
                               poster=lambda *args: calls.append(args), **OWNER)
        self.assertEqual(state, "published_unverified")
        self.assertEqual(len(calls), 1)
        with self.assertRaisesRegex(ValueError, "no duplicate POST"):
            apply_revision(r, review(), package="com.onnellab.tagweaver2",
                           google_token="private", getter=lambda *_: live(ORIGINAL),
                           poster=lambda *args: calls.append(args), **OWNER)
        self.assertEqual(len(calls), 1)

    def test_rejects_wrong_owner_channel_or_run_without_post(self):
        for changes in ({"actor": "someone_else"}, {"repository": "different/repo"},
                        {"event": "schedule"}, {"run_id": ""}):
            with self.subTest(changes=changes):
                calls = []
                owner = {**OWNER, **changes}
                with self.assertRaisesRegex(ValueError, "Exact GitHub owner"):
                    apply_revision(revision(), review(), package="com.onnellab.tagweaver2",
                                   google_token="private", getter=lambda *_: live(),
                                   poster=lambda *args: calls.append(args), **owner)
                self.assertEqual(calls, [])

    def test_stale_or_unknown_live_review_rejected_before_post(self):
        cases = [live(body="Edited user review"), live(reply="Another reply"),
                 live(rid="another-id"), live(version="2.5.4"), live(rating=2)]
        for result in cases:
            with self.subTest(result=result):
                calls = []
                with self.assertRaises(ValueError):
                    apply_revision(revision(), review(), package="com.onnellab.tagweaver2",
                                   google_token="private", getter=lambda *_: result,
                                   poster=lambda *args: calls.append(args), **OWNER)
                self.assertEqual(calls, [])

    def test_no_pending_text_review_or_synthetic_id_can_be_revised(self):
        for mutation in ({"status": "pending"}, {"review_kind": "rating_only"},
                         {"developer_reply": ""}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                apply_revision(revision(), {**review(), **mutation},
                               package="com.onnellab.tagweaver2", google_token="private",
                               getter=lambda *_: live(), poster=lambda *_: None, **OWNER)
        with self.assertRaises(ValueError):
            google_review_url("com.onnellab.tagweaver2", "report-fake-id")

    def test_revision_record_is_observed_only_after_store_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviews = root / "store_reviews.csv"
            with reviews.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(review().keys()))
                writer.writeheader()
                writer.writerow(review())
            stores = root / "stores.csv"
            stores.write_text("app_id,platform,store_url\n"
                              "APP-0002,android,https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2\n",
                              encoding="utf-8")
            revisions = root / "revisions.json"
            revisions.write_text(json.dumps({"schema_version": 1, "requests": [revision()]}))
            env = {"GITHUB_ACTOR": "onnellab", "GITHUB_REPOSITORY": "onnellab/onnel-content-engine",
                   "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ID": "99"}
            responses = iter([live(ORIGINAL), live(ORIGINAL)])
            outcome = process_revision("revision-tagweaver-test", reviews_path=reviews,
                                       stores_path=stores, token="private",
                                       poster=lambda *_: {}, getter=lambda *_: next(responses),
                                       revisions_path=revisions, environment=env)
            self.assertEqual(outcome, 2)
            saved = json.loads(revisions.read_text())["requests"][0]
            self.assertEqual(saved["status"], "published_unverified")
            self.assertFalse(saved["publication"]["store_observed_at"])
            self.assertEqual(saved["publication"]["attempts"], 1)


if __name__ == "__main__":
    unittest.main()
