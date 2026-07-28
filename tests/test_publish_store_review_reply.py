from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publish_store_review_reply import publish  # noqa: E402


class StoreReviewPublisherTest(unittest.TestCase):
    def test_google_post_uses_reply_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stores = Path(temp) / "stores.csv"
            stores.write_text("app_id,platform,store_url\nAPP-1,android,https://play.google.com/store/apps/details?id=com.example.app\n", encoding="utf-8")
            calls = []
            response_id = publish({"platform": "android", "app_id": "APP-1", "review_id": "review-1", "reply": "Thank you."}, "", "token", stores, lambda *args: calls.append(args) or {"result": {"lastEdited": {"seconds": "7"}}})
        self.assertEqual(response_id, "7")
        self.assertIn("reviews/review-1:reply", calls[0][0])
        self.assertEqual(calls[0][3], {"replyText": "Thank you."})


if __name__ == "__main__":
    unittest.main()
