from __future__ import annotations

import unittest
import json
import tempfile

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from store_review_responses import (  # noqa: E402
    classify_review,
    generate_reply,
    requires_korean_approval_translation,
)
from validate_store_review_drafts import validate  # noqa: E402


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

    def test_uses_fact_approved_app_override_for_pricing_confusion(self) -> None:
        result = generate_reply({"app_name": "TagWeaver", "app_slug": "tagweaver", "rating": "1", "body": "not free as stated", "reviewer_language": "en"})
        self.assertEqual(result["reply_category"], "pricing_confusion")
        self.assertIn("batch editing", result["suggested_reply"])

    def test_foreign_review_requires_korean_approval_translation(self) -> None:
        self.assertTrue(
            requires_korean_approval_translation(
                {"body": "No puedo abrir el archivo.", "reviewer_language": "es"}
            )
        )
        self.assertFalse(
            requires_korean_approval_translation(
                {"body": "파일을 열 수 없습니다.", "reviewer_language": "ko-KR"}
            )
        )

    def test_foreign_draft_requires_both_korean_translations(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviews = root / "reviews.csv"
            drafts = root / "drafts.json"
            reviews.write_text(
                "review_id,app_slug,app_name,rating,title,body,reviewer_language,status,developer_reply\n"
                "review-es,vaultxt,VaultXT,1,,No puedo abrir el archivo.,es,pending,\n",
                encoding="utf-8",
            )
            payload = {
                "schema_version": 1,
                "drafts": [
                    {
                        "review_id": "review-es",
                        "reply": "Gracias por avisarnos.",
                        "source": "codex",
                        "facts": [],
                    }
                ],
            }
            drafts.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            errors = validate(drafts, reviews)
            self.assertTrue(any("review_translation_ko" in error for error in errors))
            self.assertTrue(any("reply_translation_ko" in error for error in errors))

            payload["drafts"][0]["review_translation_ko"] = "파일을 열 수 없습니다."
            payload["drafts"][0]["reply_translation_ko"] = "알려주셔서 감사합니다."
            drafts.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(validate(drafts, reviews), [])


if __name__ == "__main__":
    unittest.main()
