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

    def test_prioritizes_security_and_data_loss_safety_templates(self) -> None:
        security = generate_reply({
            "app_name": "VaultXT", "rating": "1", "body": "Security breach concern",
            "reviewer_language": "en",
        })
        data_loss = generate_reply({
            "app_name": "VaultXT", "rating": "1", "body": "I lost my data after editing",
            "reviewer_language": "en",
        })
        self.assertEqual(security["reply_category"], "security")
        self.assertIn("security concern", security["suggested_reply"])
        self.assertEqual(data_loss["reply_category"], "data_loss")
        self.assertIn("data may have been affected", data_loss["suggested_reply"])

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


    def test_papira_specific_feedback_gets_grateful_specific_reply_no_debug_request(self) -> None:
        review = {
            "app_slug": "papira",
            "app_name": "Papira",
            "platform": "android",
            "rating": "3",
            "title": "",
            "body": "몇가지만 수정바랍니다 표지가 속표지만 된다는점 표지이미지만사용하게 제목삭제가능 패드로보는데 양쪽 간격이너무넓어서 기록이 너무좁아요",
            "reviewer_language": "ko",
        }
        result = generate_reply(review)
        self.assertEqual(result["reply_category"], "feature")
        reply = result["suggested_reply"]
        self.assertIn("감사합니다", reply)
        self.assertIn("검토", reply)
        self.assertIn("개선 패치", reply)
        self.assertNotIn("표지", reply)
        self.assertNotIn("태블릿", reply)
        self.assertNotIn("두 가지", reply)
        self.assertNotIn("세 가지", reply)
        self.assertNotIn("재현", reply)
        self.assertNotIn("앱 버전", reply)
        self.assertNotIn("발생 과정", reply)
        self.assertFalse(reply.endswith("ONNELLAB"))
        self.assertLessEqual(len(reply), 350)

    def test_store_review_templates_have_no_brand_signoff(self) -> None:
        from store_review_responses import load_templates
        source = load_templates()
        for lang in ("ko", "en"):
            for category, template in source[lang].items():
                with self.subTest(lang=lang, category=category):
                    self.assertNotIn("— ONNELLAB", template)
                    self.assertFalse(template.rstrip().endswith("ONNELLAB"))
        for app, language_map in source["app_overrides"].items():
            for lang, categories in language_map.items():
                for category, template in categories.items():
                    with self.subTest(app=app, lang=lang, category=category):
                        self.assertFalse(template.rstrip().endswith("ONNELLAB"))

    def test_genuine_bug_remains_reproduction_request_not_feature(self) -> None:
        result = generate_reply({
            "app_name": "Papira", "app_slug": "papira", "rating": "1",
            "body": "저장하는 중 오류가 나서 앱이 멈춤",
            "reviewer_language": "ko",
        })
        self.assertEqual(result["reply_category"], "bug")
        self.assertIn("재현", result["suggested_reply"])


if __name__ == "__main__":
    unittest.main()
