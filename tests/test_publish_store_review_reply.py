from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from store_review_approvals import approve_review
from publish_store_review_reply import publish  # noqa: E402


class StoreReviewPublisherTest(unittest.TestCase):
    def approved(self, review):
        review = {"status": "pending", "review_kind": "review", "body": "Feedback", **review}
        record = approve_review({review["review_id"]: review}, {"approvals": []},
                                review["review_id"], review["reply"], "owner",
                                approval_reference="Sentinel_11111111111111111111111111111111")
        return record, review

    def test_google_post_uses_reply_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stores = Path(temp) / "stores.csv"
            stores.write_text("app_id,platform,store_url\nAPP-1,android,https://play.google.com/store/apps/details?id=com.example.app\n", encoding="utf-8")
            calls = []
            record, review = self.approved({
                    "platform": "android",
                    "app_id": "APP-1",
                    "review_id": "review-1",
                    "reply": "Gracias por avisarnos.",
                    "review_translation_ko": "파일을 열 수 없습니다.",
                    "reply_translation_ko": "알려주셔서 감사합니다.",
                })
            response_id = publish(record,
                "",
                "token",
                stores,
                lambda *args: calls.append(args)
                or {"result": {"lastEdited": {"seconds": "7"}}}, review=review,
            )
        self.assertEqual(response_id, "7")
        self.assertIn("reviews/review-1:reply", calls[0][0])
        self.assertEqual(calls[0][3], {"replyText": "Gracias por avisarnos."})

    def test_google_report_only_id_requires_manual_play_console_reply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stores = Path(temp) / "stores.csv"
            stores.write_text(
                "app_id,platform,store_url\n"
                "APP-1,android,https://play.google.com/store/apps/details?id=com.example.app\n",
                encoding="utf-8",
            )
            record, review = self.approved({"platform": "android", "app_id": "APP-1",
                                           "review_id": "report-generated-id", "reply": "Thanks for the feedback."})
            with self.assertRaisesRegex(ValueError, "manual Play Console reply"):
                publish(record, "", "token", stores, review=review)


if __name__ == "__main__":
    unittest.main()
