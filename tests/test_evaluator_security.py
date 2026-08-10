from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_article import (
    _find_section_position,
    has_clear_definitions,
    human_readable_prose,
    score_article,
    sections,
    translation_quality_passes,
)
from topic_management import TOPIC_HEADER, write_topics


class EvaluatorSecurityTest(unittest.TestCase):
    def test_input_fingerprint_tracks_all_evaluator_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata_root = root / "metadata"
            assets_root = root / "assets"
            links_path = metadata_root / "en" / "research" / "fingerprint" / "internal_links.json"
            asset_path = assets_root / "en" / "fingerprint" / "diagram.bin"
            links_path.parent.mkdir(parents=True)
            asset_path.parent.mkdir(parents=True)
            links_path.write_bytes(b'{"recommendations":{"related_articles":[]}}')
            asset_path.write_bytes(b"asset-v1")
            topic = {
                "id": "TOPIC-FINGERPRINT",
                "working_title": "Fingerprint Inputs",
                "primary_question": "How are evaluator inputs tracked?",
                "primary_language": "en",
                "category": "research",
                "slug": "fingerprint",
                "primary_keyword": "input fingerprint",
                "secondary_keywords": "review dependency",
                "related_apps": "",
                "search_intent": "learn",
                "source_type": "user_question",
                "canonical_path": "generated/markdown/en/research/fingerprint.md",
                "notes": "initial",
                "status": "review",
                "scheduled_at": "",
                "published_at": "",
                "published_url": "",
                "updated_at": "2026-08-10T09:00:00+09:00",
            }
            markdown = "Input fingerprint prose.\n\n![Diagram](/blog-assets/en/fingerprint/diagram.bin)\n"

            def fingerprint(current_topic: dict[str, str] = topic, current_markdown: str = markdown) -> str:
                with patch("evaluate_article.translation_quality_passes", return_value=(True, "valid")):
                    review = score_article(current_topic, current_markdown, root / "topics.csv", metadata_root, assets_root)
                self.assertEqual(review["version"], 2)
                return str(review["input_fingerprint"])

            baseline = fingerprint()
            self.assertEqual(fingerprint(), baseline)

            lifecycle_topic = dict(topic)
            lifecycle_topic.update(
                {
                    "status": "scheduled",
                    "scheduled_at": "2026-08-13T09:00:00+09:00",
                    "published_at": "2026-08-16T09:00:00+09:00",
                    "published_url": "https://example.com/article",
                    "updated_at": "2026-08-11T09:00:00+09:00",
                    "notes": "operational note",
                }
            )
            self.assertEqual(fingerprint(current_topic=lifecycle_topic), baseline)

            changed_topic = dict(topic)
            changed_topic["primary_question"] = "Which evaluator inputs are tracked?"
            changed_prose = fingerprint(current_markdown=markdown.replace("prose", "updated prose"))
            changed_topic_fingerprint = fingerprint(current_topic=changed_topic)
            links_path.write_bytes(b'{"recommendations": {"related_articles": []}}')
            changed_links = fingerprint()
            links_path.write_bytes(b'{"recommendations":{"related_articles":[]}}')
            asset_path.write_bytes(b"asset-v2")
            changed_asset = fingerprint()

            for changed in [changed_prose, changed_topic_fingerprint, changed_links, changed_asset]:
                self.assertNotEqual(changed, baseline)

    def translation_result(self, source_body: str, target_body: str) -> tuple[bool, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topics_path = root / "data" / "topics.csv"
            rows = []
            for topic_id, language in [("TOPIC-EN", "en"), ("TOPIC-KO", "ko")]:
                row = {field: "" for field in TOPIC_HEADER}
                row.update(
                    {
                        "id": topic_id,
                        "category": "research",
                        "slug": "visible-terminology",
                        "primary_language": language,
                        "canonical_path": f"generated/markdown/{language}/research/visible-terminology.md",
                    }
                )
                rows.append(row)
            write_topics(topics_path, rows)
            counterpart_path = root / rows[0]["canonical_path"]
            counterpart_path.parent.mkdir(parents=True)
            counterpart_path.write_text(
                f'---\nslug: "visible-terminology"\n---\n\n{source_body}',
                encoding="utf-8",
            )
            return translation_quality_passes(
                rows[1],
                {"slug": "visible-terminology"},
                target_body,
                sections(target_body),
                topics_path,
            )

    def test_malformed_link_with_many_escapes_is_processed_in_linear_time(self) -> None:
        markdown = "[표준](https://example.com/" + "\\" * 100_000

        started = time.monotonic()
        prose = human_readable_prose(markdown)
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 2.0)
        self.assertEqual(prose, markdown)

    def test_link_destinations_and_escaped_parentheses_are_excluded(self) -> None:
        markdown = (
            "[인코딩 표준](https://encoding.spec.whatwg.org/a\\)b)과 "
            "[다른 표준]\\(https://encoding.example/)을 참고합니다."
        )

        prose = human_readable_prose(markdown)

        self.assertIn("인코딩 표준", prose)
        self.assertNotIn("https://", prose)

    def test_unmatched_markdown_preserves_later_visible_terms(self) -> None:
        examples = [
            "` unmatched inline marker\nvisible encoding",
            "```text\nunmatched fence\nvisible encoding",
            "[표준](https://example.com/" + "\\" * 20 + "\nvisible encoding",
        ]

        for markdown in examples:
            with self.subTest(markdown=markdown[:20]):
                self.assertIn("visible encoding", human_readable_prose(markdown))

    def test_section_order_ignores_fenced_fake_headings(self) -> None:
        fake_product = "## Recommended Workflow\n\n```markdown\n## Where ONNELLAB Fits\n```"
        fake_workflow = "```markdown\n## Recommended Workflow\n```\n\n## Where ONNELLAB Fits"

        self.assertGreaterEqual(_find_section_position(fake_product, "recommended_workflow"), 0)
        self.assertEqual(_find_section_position(fake_product, "onnellab_application"), -1)
        self.assertEqual(_find_section_position(fake_workflow, "recommended_workflow"), -1)
        self.assertGreaterEqual(_find_section_position(fake_workflow, "onnellab_application"), 0)

    def test_terminology_uses_only_visible_source_and_target_text(self) -> None:
        source_only_in_nonprose = "`encoding`\n\n[표준](https://encoding.example/)\n\nreencoding"
        passed, note = self.translation_result(source_only_in_nonprose, "용어를 일관되게 사용합니다.")
        self.assertTrue(passed, note)

        source_visible = "Encoding is a rule for interpreting bytes."
        target_only_in_nonprose = "`인코딩`\n\n[표준](https://example.com/인코딩)"
        passed, note = self.translation_result(source_visible, target_only_in_nonprose)
        self.assertFalse(passed)
        self.assertIn("인코딩", note)

        passed, note = self.translation_result(source_visible, "인코딩은 바이트를 해석하는 규칙입니다.")
        self.assertTrue(passed, note)

    def test_code_does_not_count_as_a_definition(self) -> None:
        self.assertFalse(has_clear_definitions("`Codec is a media representation method.`"))
        self.assertFalse(has_clear_definitions("```text\nEncoding is a byte conversion rule.\n```"))

    def test_bold_technical_terms_count_as_definitions(self) -> None:
        self.assertTrue(has_clear_definitions("**Codec** is a method for representing media data."))
        self.assertTrue(has_clear_definitions("**인코딩**은 바이트를 문자로 바꾸는 규칙입니다."))

    def test_generic_pronouns_do_not_count_as_definitions(self) -> None:
        for prose in [
            "This is a method for representing media data.",
            "It is a rule for reading bytes.",
            "이것은 바이트를 문자로 바꾸는 규칙입니다.",
            "그것은 미디어를 표현하는 방법입니다.",
        ]:
            with self.subTest(prose=prose):
                self.assertFalse(has_clear_definitions(prose))


if __name__ == "__main__":
    unittest.main()
