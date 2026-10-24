from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from publishing import Article, PublishingError, social_card_svg, social_card_error_context

from render_social_card_regression import complete_wrapped_text

class WrappedTextCompleteness(unittest.TestCase):
    def test_character_and_word_wrapping_preserves_source(self):
        self.assertTrue(complete_wrapped_text(["研究ノート", "を整理する"], "研究ノートを整理する"))
        self.assertTrue(complete_wrapped_text(["Keep source", "notes intact."], "Keep source notes intact."))
        self.assertTrue(complete_wrapped_text(["source notes", " remain"], "source notes\nremain"))

    def test_missing_reordered_changed_or_extra_text_is_rejected(self):
        for lines in (["Keep source"], ["notes intact.", "Keep source"],
                      ["Keep sauce", "notes intact."], ["Keep source", "notes intact. extra"],
                      ["Keep source", "", "notes intact."]):
            with self.subTest(lines=lines):
                self.assertFalse(complete_wrapped_text(lines, "Keep source notes intact."))
        self.assertFalse(complete_wrapped_text(["研究ノート", "整理する"], "研究ノートを整理する"))

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

    def test_german_four_line_description_preserves_every_word_and_bounds(self):
        article = self.article(topic={"id": "TOPIC-0093", "primary_language": "de",
                                      "slug": "separate-source-notes-from-conclusions", "category": "research"},
                               title="Quellennotizen und eigene Schlussfolgerungen klar trennen", description="Halten Sie Zitate, Paraphrasen und eigene Interpretationen auseinander: mit genauen Fundstellen, einer praktischen Vergleichstabelle und einem Ablauf in fünf Schritten für Forschungsnotizen.")
        root = ET.fromstring(social_card_svg(article))
        ns = {"s": "http://www.w3.org/2000/svg"}
        title_node = root.find("s:text[@font-weight='760']", ns)
        description = root.find("s:text[@fill='#5f5b54']", ns)
        lines = description.findall("s:tspan", ns)
        self.assertEqual(" ".join(line.text for line in lines), article.description)
        self.assertEqual([int(line.attrib["y"]) for line in lines], [390, 422, 454, 486])
        self.assertEqual(int(description.attrib["font-size"]), 22)
        self.assertGreaterEqual(int(lines[0].attrib["y"]) - int(title_node.findall("s:tspan", ns)[-1].attrib["y"]), 44)
        self.assertLessEqual(int(lines[-1].attrib["y"]), 490)

    def test_existing_short_card_keeps_original_position_and_font(self):
        root = ET.fromstring(social_card_svg(self.article()))
        ns = {"s": "http://www.w3.org/2000/svg"}
        node = root.find("s:text[@fill='#5f5b54']", ns)
        self.assertEqual(node.attrib["font-size"], "24")
        self.assertEqual(node.find("s:tspan", ns).attrib["y"], "410")


    def test_english_card_preserves_complete_title_and_description(self):
        article = self.article(topic={"id": "TOPIC-0037", "primary_language": "en",
                                     "slug": "source-notes", "category": "research"},
                               title="How to Separate Source Notes from Your Conclusions",
                               description="Keep quotations, paraphrases, and your own interpretations distinct with source locators, a practical comparison table, and a five-step research-note workflow.")
        root = ET.fromstring(social_card_svg(article))
        ns = {"s": "http://www.w3.org/2000/svg"}
        for selector, expected in (("s:text[@font-weight='760']", article.title),
                                   ("s:text[@fill='#5f5b54']", article.description)):
            lines = root.find(selector, ns).findall("s:tspan", ns)
            self.assertEqual(" ".join(line.text for line in lines), expected)
        title_lines = root.find("s:text[@font-weight='760']", ns).findall("s:tspan", ns)
        self.assertNotEqual(title_lines[0].text, "How to Separate Source Notes from")
        description = root.find("s:text[@fill='#5f5b54']", ns).findall("s:tspan", ns)
        self.assertLessEqual(int(description[-1].attrib["y"]), 490)
        self.assertGreaterEqual(int(description[0].attrib["y"]) - int(title_lines[-1].attrib["y"]), 44)

    def test_english_oversized_text_fails_instead_of_truncating(self):
        for field in ("title", "description"):
            with self.subTest(field=field), patch("publishing.subprocess.run") as run:
                with self.assertRaises(PublishingError):
                    social_card_svg(self.article(topic={"primary_language": "en", "category": "research"},
                                                 **{field: "Long complete text " * 2000}))
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
