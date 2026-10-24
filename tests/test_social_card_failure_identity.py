from pathlib import Path
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from publishing import Article, PublishingError, social_card_svg, social_card_error_context

class SocialCardFailureIdentity(unittest.TestCase):
    def article(self, **changes):
        values = dict(topic={"id": "TOPIC-0088", "primary_language": "ko",
                             "slug": "source-notes", "category": "research"},
                      markdown_path=Path("fixture.md"), html_path=Path("fixture.html"),
                      url_path="/fixture/", title="짧은 제목", body_html="PRIVATE_BODY",
                      description="짧은 설명", social_image_path="/fixture.png",
                      social_image_url="https://example.test/fixture.png")
        values.update(changes)
        return Article(**values)

    def test_both_layout_failures_remain_fail_closed_without_content_or_writes(self):
        for field in ("title", "description"):
            with self.subTest(field=field), patch("publishing.subprocess.run") as run:
                private = "PRIVATE_CONTENT " * 2000
                with self.assertRaises(PublishingError) as caught:
                    social_card_svg(self.article(**{field: private}))
                message = str(caught.exception)
                self.assertEqual(message, f"Localized social card {field} cannot fit without truncation: TOPIC-0088 (ko, source-notes)")
                self.assertNotIn("PRIVATE_CONTENT", message)
                self.assertNotIn("PRIVATE_BODY", message)
                run.assert_not_called()

    def test_missing_identifiers_do_not_introduce_a_diagnostic_error(self):
        self.assertEqual(social_card_error_context(self.article(topic={})), " (, )")
        with self.assertRaisesRegex(PublishingError, "Localized social card title cannot fit without truncation"):
            social_card_svg(self.article(topic={"primary_language": "ko", "category": "research"}, title="PRIVATE_CONTENT " * 2000))

    def test_error_identity_is_bounded_and_control_characters_are_escaped(self):
        article = self.article(topic={"id": "TOPIC-1\nFORGED",
                                     "primary_language": "ko\r\t",
                                     "slug": "a" * 1000})
        context = social_card_error_context(article)
        self.assertEqual(context, "TOPIC-1?FORGED (ko??, " + "a" * 80 + ")")
        self.assertNotIn("\n", context)
        self.assertNotIn("\r", context)
        self.assertLess(len(context), 250)

if __name__ == "__main__":
    unittest.main()
