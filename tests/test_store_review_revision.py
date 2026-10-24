from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from store_review_revision import apply_revision, process_revision, google_review_url
from publish_store_review_reply import json_request


ID = "10b4e93e-b9cd-4ef4-ad91-2726f5256651"
BODY = "Some tags aren't removed correctly when the file is saved. When the X next to URL is pressed, for example, saving doesn't actually retain the change."
ORIGINAL = "Previously posted reply"
REPLACEMENT = "The Android 2.5.6 fix is under review by Google Play."
OWNER = {"actor": "onnellab", "triggering_actor": "onnellab",
         "repository": "onnellab/onnel-content-engine",
         "event": "workflow_dispatch", "run_id": "123456", "run_attempt": "1"}


def live(reply=ORIGINAL, *, body=BODY, rating=3, version="2.5.5", rid=ID):
    return {"reviewId": rid, "comments": [
        {"userComment": {"text": body, "starRating": rating, "appVersionName": version}},
        {"developerComment": {"text": reply}},
    ]}


def review():
    return {"review_id": ID, "app_id": "APP-0002", "app_slug": "tagweaver",
            "platform": "android", "review_kind": "review", "title": "", "body": BODY,
            "rating": "3", "app_version": "2.5.5", "status": "replied",
            "developer_reply": ORIGINAL}


def revision():
    return {"revision_id": "revision-tagweaver-test", "review_id": ID,
            "app_id": "APP-0002", "app_slug": "tagweaver", "platform": "android",
            "app_version": "2.5.5", "rating": 3,
            "expected_review_title": "", "expected_review_body": BODY,
            "expected_current_reply": ORIGINAL,
            "replacement_reply": REPLACEMENT, "status": "awaiting_owner_dispatch",
            "expected_public_store_version": "2.5.5", "target_version_under_review": "2.5.6",
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
        for changes in ({"actor": "someone_else"}, {"triggering_actor": "collaborator"},
                        {"repository": "different/repo"}, {"event": "schedule"},
                        {"run_id": ""}, {"run_attempt": "0"}):
            with self.subTest(changes=changes):
                calls = []
                owner = {**OWNER, **changes}
                with self.assertRaisesRegex(ValueError, "Exact GitHub owner"):
                    apply_revision(revision(), review(), package="com.onnellab.tagweaver2",
                                   google_token="private", getter=lambda *_: live(),
                                   poster=lambda *args: calls.append(args), **owner)
                self.assertEqual(calls, [])

    def test_rerun_may_not_originate_a_store_post(self):
        calls = []
        with self.assertRaisesRegex(ValueError, "rerun cannot"):
            apply_revision(revision(), review(), package="com.onnellab.tagweaver2",
                           google_token="private", getter=lambda *_: live(ORIGINAL),
                           poster=lambda *args: calls.append(args),
                           **{**OWNER, "run_attempt": "2"})
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
            stores.write_text(
                "app_id,platform,store_url,version,checked_at\n"
                "APP-0002,android,https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2,2.5.5,"
                + datetime.now(timezone.utc).isoformat() + "\n",
                encoding="utf-8")
            revisions = root / "revisions.json"
            revisions.write_text(json.dumps({"schema_version": 1, "requests": [revision()]}))
            env = {"GITHUB_ACTOR": "onnellab", "GITHUB_REPOSITORY": "onnellab/onnel-content-engine",
                   "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ID": "99",
                   "REPLY_TRIGGERING_ACTOR": "onnellab", "REPLY_RUN_ATTEMPT": "1"}
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


    def test_uses_canonical_original_text_when_google_returns_translation(self):
        """The stored review sync prefers originalText over translated text."""
        before = live()
        before["comments"][0]["userComment"]["text"] = "Machine-translated replacement text"
        before["comments"][0]["userComment"]["originalText"] = BODY
        calls = []
        responses = iter([before, live(REPLACEMENT)])
        state = apply_revision(revision(), review(), package="com.onnellab.tagweaver2",
                               google_token="private", getter=lambda *_: next(responses),
                               poster=lambda *args: calls.append(args), **OWNER)
        self.assertEqual(state, "store_verified")
        self.assertEqual(len(calls), 1)

    def test_canonical_tab_separated_title_and_body_are_compared_separately(self):
        """A genuine title is not misidentified as a changed body."""
        r = revision()
        r["expected_review_title"] = "Title from reviewer"
        saved = {**review(), "title": "Title from reviewer"}
        before = live()
        after = live(REPLACEMENT)
        for raw in (before, after):
            raw["comments"][0]["userComment"]["text"] = "Title from reviewer\t" + BODY
        # Python source should have a tab escape, not a literal backslash+t.
        calls = []
        responses = iter([before, after])
        state = apply_revision(r, saved, package="com.onnellab.tagweaver2",
                               google_token="private", getter=lambda *_: next(responses),
                               poster=lambda *args: calls.append(args), **OWNER)
        self.assertEqual(state, "store_verified")
        self.assertEqual(len(calls), 1)

    def test_rejects_changed_title_and_original_review_without_post(self):
        scenarios = [
            ("live_review_title_mismatch", "Injected title\t" + BODY, None),
            ("live_review_body_mismatch", "Altered user body", None),
            ("live_review_body_mismatch", "Unrelated translation", "Changed original"),
            ("live_review_rating_mismatch", BODY, None, 4),
            ("live_review_version_mismatch", BODY, None, 3, "2.5.4"),
        ]
        for code, body, original, *optional in scenarios:
            with self.subTest(code=code, original=original):
                changed = live(body=body)
                user = changed["comments"][0]["userComment"]
                if original is not None:
                    user["originalText"] = original
                if optional:
                    user["starRating"] = optional[0]
                if len(optional) > 1:
                    user["appVersionName"] = optional[1]
                calls = []
                with self.assertRaisesRegex(ValueError, "^" + code + "$"):
                    apply_revision(revision(), review(), package="com.onnellab.tagweaver2",
                                   google_token="private", getter=lambda *_: changed,
                                   poster=lambda *args: calls.append(args), **OWNER)
                self.assertEqual(calls, [])

    def test_missing_google_version_is_distinct_and_fails_closed(self):
        """Google documents appVersionName as optional; do not guess a version."""
        payload = live()
        payload["comments"][0]["userComment"].pop("appVersionName")
        calls = []
        with self.assertRaisesRegex(ValueError, "live_review_version_unavailable"):
            apply_revision(revision(), review(), package="com.onnellab.tagweaver2",
                           google_token="private", getter=lambda *_: payload,
                           poster=lambda *args: calls.append(args), **OWNER)
        self.assertEqual(calls, [])

    def test_preflight_mismatch_records_only_constant_code_and_no_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviews = root / "store_reviews.csv"
            with reviews.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(review().keys()))
                writer.writeheader()
                writer.writerow(review())
            stores = root / "stores.csv"
            stores.write_text(
                "app_id,platform,store_url,version,checked_at\n"
                "APP-0002,android,https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2,2.5.5,"
                + datetime.now(timezone.utc).isoformat() + "\n",
                encoding="utf-8")
            path = root / "revisions.json"
            path.write_text(json.dumps({"schema_version": 1, "requests": [revision()]}))
            env = {"GITHUB_ACTOR": "onnellab", "GITHUB_REPOSITORY": "onnellab/onnel-content-engine",
                   "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ID": "99",
                   "REPLY_TRIGGERING_ACTOR": "onnellab", "REPLY_RUN_ATTEMPT": "1"}
            live_bad = live(body="VERY_PRIVATE_DIFFERENT_TEXT")
            calls = []
            with self.assertRaisesRegex(ValueError, "live_review_body_mismatch"):
                process_revision("revision-tagweaver-test", reviews_path=reviews,
                                 stores_path=stores, token="private",
                                 poster=lambda *args: calls.append(args),
                                 getter=lambda *_: live_bad,
                                 revisions_path=path, environment=env)
            audit = json.loads(path.read_text())["requests"][0]
            self.assertEqual(audit["status"], "awaiting_owner_dispatch")
            self.assertEqual(audit["publication"]["attempts"], 0)
            self.assertEqual(audit["diagnostic"]["code"], "live_review_body_mismatch")
            self.assertEqual(audit["diagnostic"]["workflow_run_id"], "99")
            self.assertNotIn("VERY_PRIVATE", path.read_text())
            self.assertEqual(calls, [])

    def test_store_review_write_has_no_transient_transport_retry(self):
        """An accepted-but-timed-out API POST cannot be attempted twice."""
        with patch("publish_store_review_reply.urlopen_with_retry") as opener:
            opener.return_value.__enter__.return_value.read.return_value = b'{"result": {}}'
            json_request("https://example.test/reviews/uuid:reply", "private", "POST", {"replyText": REPLACEMENT})
            self.assertEqual(opener.call_args.kwargs["max_attempts"], 1)
        with patch("publish_store_review_reply.urlopen_with_retry") as opener:
            opener.return_value.__enter__.return_value.read.return_value = b'{}'
            json_request("https://example.test/reviews/uuid", "private", "GET", {})
            self.assertEqual(opener.call_args.kwargs["max_attempts"], 5)


if __name__ == "__main__":
    unittest.main()
