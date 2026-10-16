"""Regression tests for narrowly recognized conversational Korean definitions."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_article import has_clear_definitions

class ConversationalKoreanDefinitions(unittest.TestCase):
    def test_meaningful_definition_endings(self):
        for text in (
            "파일명 규칙은 어떤 항목을 어떤 순서로 쓰고, 무엇으로 구분할지 정한 약속이에요.",
            "날짜 규칙은 날짜의 뜻과 표기 순서를 고정하는 규칙이에요.",
            "필드는 파일명에서 하나의 뜻을 맡는 부분이에요.",
            "파일명 규칙은 이름에 넣을 항목과 순서를 정하는 규칙입니다.",
        ):
            with self.subTest(text=text):
                self.assertTrue(has_clear_definitions(text, "ko"))

    def test_generic_statements_do_not_count(self):
        for text in (
            "파일명은 간단해서 좋아요.",
            "이것은 파일명을 쉽게 읽게 하는 약속이에요.",
            "그것은 파일명에서 날짜를 나타내는 부분이에요.",
            "이름을 짧게 쓰면 좋아요.",
            "규칙이에요.",
            "파일명은 내일 다시 살펴볼 약속이에요.",
            "내일 다시 만나는 약속이에요.",
            "파일명은 아주 좋은 부분이에요.",
            "`파일명 규칙은 이름의 순서를 정하는 약속이에요.`",
            "```text\n파일명 규칙은 이름의 순서를 정하는 약속이에요.\n```",
            "[참고](https://example.invalid/파일명은_순서를_정하는_약속이에요)",
        ):
            with self.subTest(text=text):
                self.assertFalse(has_clear_definitions(text, "ko"))

    def test_existing_english_definition_unchanged(self):
        self.assertTrue(has_clear_definitions("A field is one part of a filename.", "en"))
        self.assertFalse(has_clear_definitions("This is a convenient filename.", "en"))

if __name__ == "__main__":
    unittest.main()
