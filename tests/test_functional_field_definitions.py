import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evaluate_article import has_clear_definitions, has_functional_field_definition


class FunctionalFieldDefinitionTests(unittest.TestCase):
    def test_actual_named_field_definitions(self):
        cases = [
            ("ko", "**앨범 제목**은 정리하려는 발매판을 식별해요."),
            ("ko", "**트랙 아티스트**는 개별 곡의 크레딧에 표기된 아티스트를 나타내요."),
            ("zh-Hans", "**专辑名称**用于识别你正在整理的发行版本。"),
            ("zh-Hans", "**曲目艺人**表示某一首歌曲的署名艺人。"),
            ("zh-Hant", "**專輯名稱**用於識別你正在整理的發行版本。"),
            ("zh-Hant", "**曲目藝人**表示個別歌曲的署名藝人。"),
        ]
        for language, body in cases:
            with self.subTest(language=language, body=body):
                self.assertTrue(has_clear_definitions(body, language))

    def test_instructions_questions_vague_and_incomplete_are_not_definitions(self):
        cases = [
            ("ko", "앨범 제목을 확인하고 정확한 발매판을 식별해요."),
            ("ko", "정리 방법은 버튼을 눌러 화면에 나타내요."),
            ("ko", "앨범 제목은 정리하려는 발매판을 식별해요?"),
            ("ko", "이것은 정리하려는 발매판을 식별해요."),
            ("ko", "앨범 제목은 식별해요."),
            ("ko", "앨범 제목은 정리하려는 발매판을\n식별해요."),
            ("zh-Hans", "请把专辑名称用于识别你正在整理的发行版本。"),
            ("zh-Hans", "专辑名称用于识别你正在整理的发行版本？"),
            ("zh-Hans", "它用于识别你正在整理的发行版本。"),
            ("zh-Hans", "专辑名称表示艺人。"),
            ("zh-Hans", "专辑名称用于识别\n你正在整理的发行版本。"),
            ("zh-Hant", "請把專輯名稱用於識別你正在整理的發行版本。"),
            ("zh-Hant", "這表示個別歌曲的署名藝人。"),
        ]
        for language, body in cases:
            with self.subTest(language=language, body=body):
                self.assertFalse(has_clear_definitions(body, language))

    def test_code_and_url_do_not_supply_definitions(self):
        text = "专辑名称用于识别你正在整理的发行版本。"
        for body in (f"```text\n{text}\n```", f"`{text}`", f"[source](https://example.org/{text})"):
            self.assertFalse(has_clear_definitions(body, "zh-Hans"))

    def test_other_languages_do_not_use_new_matcher(self):
        self.assertFalse(has_functional_field_definition("专辑名称用于识别你正在整理的发行版本。", "en"))


if __name__ == "__main__":
    unittest.main()
