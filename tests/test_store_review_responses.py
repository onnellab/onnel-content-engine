from __future__ import annotations

import unittest

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from store_review_responses import classify_review, generate_reply  # noqa: E402


class StoreReviewResponsesTest(unittest.TestCase):
    def test_generates_korean_bug_reply_without_requesting_personal_data(self) -> None:
        result = generate_reply(
            {
                "app_name": "Quivra",
                "rating": "2",
                "title": "변환 오류",
                "body": "파일을 고르면 앱이 멈춤",
                "reviewer_language": "ko-KR",
            }
        )

        self.assertEqual(result["reply_category"], "bug")
        self.assertEqual(result["reply_language"], "ko")
        self.assertIn("개인정보를 리뷰에 남기지 말고", result["suggested_reply"])
        self.assertNotIn("이메일", result["suggested_reply"])

    def test_prioritizes_billing_over_rating(self) -> None:
        review = {
            "app_name": "Aligna",
            "rating": "5",
            "title": "Restore purchase failed",
            "body": "Please help",
            "reviewer_language": "en-US",
        }

        self.assertEqual(classify_review(review), "billing")
        self.assertIn("order numbers", generate_reply(review)["suggested_reply"])

    def test_uses_positive_and_no_text_templates(self) -> None:
        positive = generate_reply(
            {
                "app_name": "TagWeaver",
                "rating": "5",
                "body": "Simple and useful",
                "reviewer_language": "en",
            }
        )
        no_text = generate_reply(
            {
                "app_name": "TagWeaver",
                "rating": "3",
                "body": "",
                "reviewer_language": "ko",
            }
        )

        self.assertEqual(positive["reply_category"], "positive")
        self.assertEqual(no_text["reply_category"], "no_text")
        self.assertEqual(positive["human_review_required"], "true")


if __name__ == "__main__":
    unittest.main()
