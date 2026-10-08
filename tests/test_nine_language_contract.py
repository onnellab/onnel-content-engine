from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publication_locales import PUBLICATION_LOCALES, require_publication_bundle, public_locale_segment
from schedule_ready_articles import schedule_ready_articles, SchedulingError
from publish_due_articles import publish_due_articles, DuePublicationError, public_url
from topic_management import TOPIC_HEADER, write_topics, read_csv
from publishing import homepage_destination_for, article_url_path, validate_publishable_language_pairs
from article_localization import LOCALIZED_SECTIONS, DEFINITION_PATTERNS, WORKFLOW_LABELS
from evaluate_article import has_clear_definitions, has_required_sections, has_short_answer
from generate_image_assets import workflow_svg, ensure_markdown_references_asset
from article_localization import localized_section_aliases
from evaluate_article import evaluate_article
import json
import os
from publication_transaction import publication_guard, atomic_replace_files
from generate_image_spec import build_spec
from publishing import Article, social_card_svg
from xml.etree import ElementTree


class NineLanguageContract(unittest.TestCase):
    def rows(self, status="review"):
        rows = []
        for i, language in enumerate(PUBLICATION_LOCALES, 1):
            row = dict.fromkeys(TOPIC_HEADER, "")
            row.update(id=f"TOPIC-{i:04d}", status=status, category="reading", primary_question="How to read?", working_title="Read clearly", slug="read-clearly", primary_language=language, priority="normal", search_intent="workflow", primary_keyword="read", evergreen="true", source_type="editorial", review_required="true", canonical_path=f"generated/markdown/{language}/reading/read-clearly.md", scheduled_at="2026-10-07T09:00:00+09:00" if status == "scheduled" else "")
            rows.append(row)
        return rows

    def workspace(self, root, rows):
        topics = root / "data/topics.csv"
        write_topics(topics, rows)
        for row in rows:
            p = root / row["canonical_path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('---\nstatus: "scheduled"\n---\nBody\n')
        return topics

    def test_registry_matches_verified_homepage(self):
        self.assertEqual(set(PUBLICATION_LOCALES), {"en", "ko", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es"})

    def test_transaction_supports_aliased_repository_root(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "real"
            root.mkdir()
            alias = parent / "alias"
            alias.symlink_to(root, target_is_directory=True)
            destination = alias / "data/topics.csv"
            with publication_guard(alias):
                atomic_replace_files(alias, {destination: b"new\n"})
            self.assertEqual((root / "data/topics.csv").read_bytes(), b"new\n")
            with publication_guard(alias):
                with self.assertRaisesRegex(ValueError, "duplicate canonical"):
                    atomic_replace_files(alias, {destination: b"one", root / "data/topics.csv": b"two"})
            linked_file = root / "data/linked.csv"
            linked_file.symlink_to(root / "data/topics.csv")
            with publication_guard(alias):
                with self.assertRaisesRegex(ValueError, "stay within"):
                    atomic_replace_files(alias, {linked_file: b"unsafe"})
            self.assertEqual(destination.read_bytes(), b"new\n")

    def test_requires_all_nine_exactly_once(self):
        self.assertEqual(len(require_publication_bundle(self.rows())), 9)
        for i in range(9):
            with self.assertRaises(ValueError):
                require_publication_bundle(self.rows()[:i] + self.rows()[i+1:])
        with self.assertRaises(ValueError):
            require_publication_bundle(self.rows() + [self.rows()[0]])

    def test_bilingual_only_cannot_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topics = self.workspace(root, self.rows()[:2])
            before = topics.read_bytes()
            with self.assertRaises(SchedulingError):
                schedule_ready_articles(topics, root / "reviews", None)
            self.assertEqual(before, topics.read_bytes())

    def test_nine_share_single_schedule(self):
        with tempfile.TemporaryDirectory() as tmp, patch("topic_management.load_app_names", return_value=set()), patch("schedule_ready_articles.current_review_score", return_value=10.0):
            root = Path(tmp)
            topics = self.workspace(root, self.rows())
            output = schedule_ready_articles(topics, root / "reviews", None)
            self.assertEqual(len(output), 9)
            self.assertEqual(len({r["scheduled_at"] for r in output}), 1)

    def test_one_failed_quality_blocks_every_locale(self):
        with tempfile.TemporaryDirectory() as tmp, patch("schedule_ready_articles.current_review_score", side_effect=lambda row, *args: 9.0 if row["primary_language"] == "es" else 10.0):
            root = Path(tmp)
            topics = self.workspace(root, self.rows())
            before = topics.read_bytes()
            self.assertEqual(schedule_ready_articles(topics, root / "reviews", None), [])
            self.assertEqual(before, topics.read_bytes())

    def test_publish_nine_or_none(self):
        with tempfile.TemporaryDirectory() as tmp, patch("topic_management.load_app_names", return_value=set()), patch("publish_due_articles.current_review_score", return_value=10.0):
            root = Path(tmp)
            topics = self.workspace(root, self.rows("scheduled"))
            output = publish_due_articles(topics, root / "reviews", None, now=datetime(2026, 10, 8, tzinfo=timezone.utc))
            self.assertEqual(len(output), 9)
            self.assertTrue(all(r["status"] == "published" for r in read_csv(topics, TOPIC_HEADER)))

    def test_middle_replace_failure_restores_markdown_topics_and_mirror(self):
        with tempfile.TemporaryDirectory() as tmp, patch("topic_management.load_app_names", return_value=set()), patch("publish_due_articles.current_review_score", return_value=10.0):
            root = Path(tmp)
            rows = self.rows("scheduled")
            topics = self.workspace(root, rows)
            mirror = root / "topics/topics.csv"
            write_topics(mirror, rows)
            paths = [topics, mirror, *(root / row["canonical_path"] for row in rows)]
            before = {p: p.read_bytes() for p in paths}
            replace = os.replace
            attempts = 0
            def fail_fifth(source, destination):
                nonlocal attempts
                if Path(destination).suffix == ".md":
                    attempts += 1
                    if attempts == 5:
                        raise OSError("injected fifth locale replacement failure")
                return replace(source, destination)
            with patch("publication_transaction.os.replace", side_effect=fail_fifth):
                with self.assertRaisesRegex(OSError, "injected fifth"):
                    publish_due_articles(topics, root / "reviews", mirror, now=datetime(2026, 10, 8, tzinfo=timezone.utc))
            self.assertEqual(before, {p: p.read_bytes() for p in paths})
            self.assertFalse((root / "data/.publication-transaction").exists())
            output = publish_due_articles(topics, root / "reviews", mirror, now=datetime(2026, 10, 8, tzinfo=timezone.utc))
            self.assertEqual(len(output), 9)

    def test_uncommitted_journal_recovers_before_next_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "data/topics.csv"
            target.parent.mkdir()
            target.write_bytes(b"partial new state")
            journal = root / "data/.publication-transaction"
            journal.mkdir()
            (journal / "0.before").write_bytes(b"original bytes")
            (journal / "manifest.json").write_text(json.dumps([{"path": "data/topics.csv", "existed": True, "backup": "0.before"}]))
            with publication_guard(root):
                self.assertEqual(target.read_bytes(), b"original bytes")
            self.assertFalse(journal.exists())

    def test_different_slot_blocks_publication_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = self.rows("scheduled")
            rows[-1]["scheduled_at"] = "2026-10-06T09:00:00+09:00"
            topics = self.workspace(root, rows)
            before = topics.read_bytes()
            with self.assertRaises(DuePublicationError):
                publish_due_articles(topics, root / "reviews", None, now=datetime(2026, 10, 8, tzinfo=timezone.utc))
            self.assertEqual(before, topics.read_bytes())

    def test_lowercase_routes_preserve_source_locale_identity(self):
        for row in self.rows():
            language = row["primary_language"]
            self.assertIn(f"/blog/{language.lower()}/", public_url("https://onnellab.com/", row))
            self.assertIn(f"blog/{language.lower()}/", article_url_path(row))
            self.assertEqual(homepage_destination_for(row, Path("/test")).parent.name, language)

    def test_past_bilingual_publications_remain_valid(self):
        rows = self.rows("published")[:2]
        validate_publishable_language_pairs(rows)

    def test_localized_sections_short_answers_and_images(self):
        for language, headings in LOCALIZED_SECTIONS.items():
            with self.subTest(language=language):
                found = {h.lower() for h in headings}
                self.assertTrue(has_required_sections(found))
                self.assertTrue(has_short_answer({}, found, f"## {headings[1]}\n\nAnswer."))
                svg = workflow_svg("Title", "Keyword", language)
                self.assertIn(WORKFLOW_LABELS[language][3], svg)
                self.assertNotIn(">4. Result<", svg)

    def test_localized_definitions(self):
        definitions = {"ja": "文字コードとは文字を表す規則です。", "zh-Hans": "文本编码是指字符与字节之间的对应规则。", "zh-Hant": "文字編碼是指字元與位元組之間的對應規則。", "pt-BR": "Codificação é uma regra para representar caracteres.", "de": "Zeichenkodierung ist eine Regel zur Darstellung von Zeichen.", "fr": "Un encodage est une règle de représentation des caractères.", "es": "La codificación es una regla para representar caracteres."}
        for language, body in definitions.items():
            self.assertTrue(has_clear_definitions(body, language), language)
            self.assertFalse(has_clear_definitions("No definition here.", language), language)

    def test_reviewed_chinese_definition_form_does_not_accept_incidental_indicates(self):
        for language, body in [('zh-Hans', '来源的可追溯性，指位置改变后仍能识别资料。'), ('zh-Hant', '來源的可追溯性，指位置改變後仍能辨識資料。')]:
            self.assertTrue(has_clear_definitions(body, language))
            self.assertFalse(has_clear_definitions('如果无法解释这些证据，表示记录尚未准备好。', language))
            self.assertFalse(has_clear_definitions('这个链接，指向出版社首页。', language))

    def test_localized_image_specs_do_not_invent_english_titles(self):
        for row in self.rows():
            if row["primary_language"] not in LOCALIZED_SECTIONS:
                continue
            spec = build_spec(Path(row["canonical_path"]), "## Section\n", row)
            self.assertNotIn(" Workflow", spec["workflow_diagrams"][0]["title"])
            self.assertNotIn(" Comparison", spec["comparison_diagrams"][0]["title"])

    def test_asset_insertion_accepts_every_reviewed_workflow_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.md"
            for language in LOCALIZED_SECTIONS:
                for heading in localized_section_aliases(language)["recommended_workflow"]:
                    with self.subTest(language=language, heading=heading):
                        prefix = f"```markdown\n## {heading}\nNot an actual section.\n```\n\n"
                        path.write_text(prefix + f"## {heading}\n\n1. A step.\n\n## Next\n\nConclusion.\n")
                        ensure_markdown_references_asset(path, language, "sample", "A title")
                        result = path.read_text()
                        image = f"/blog-assets/{language}/sample/workflow-diagram.svg"
                        self.assertEqual(result.count(image), 1)
                        self.assertTrue(result.startswith(prefix))
                        self.assertGreater(result.index(image), result.index("1. A step."))
                        self.assertLess(result.index(image), result.index("## Next"))

    def test_localized_social_card_keeps_complete_copy(self):
        for row in self.rows():
            language = row["primary_language"]
            if language not in LOCALIZED_SECTIONS:
                continue
            title = LOCALIZED_SECTIONS[language][2] + " TXT EPUB " + LOCALIZED_SECTIONS[language][5]
            description = LOCALIZED_SECTIONS[language][1] + " TXT EPUB. " + LOCALIZED_SECTIONS[language][4]
            article = Article(row, Path("draft.md"), Path("page.html"), "blog/", title, "", description, "", "")
            svg = social_card_svg(article)
            tree = ElementTree.fromstring(svg)
            self.assertEqual(tree.find("{http://www.w3.org/2000/svg}title").text, title)
            self.assertEqual(tree.find("{http://www.w3.org/2000/svg}desc").text, description)
            self.assertNotIn("…", svg)

    def test_real_nine_locale_review_schedule_publish_lifecycle(self):
        # Synthetic structural fixture, not publishable editorial copy.
        from test_publication_automation import MARKDOWN, korean_markdown
        definitions = {"ja": "文字コードとは文字を表す規則です。", "zh-Hans": "文本编码是指字符与字节之间的对应规则。", "zh-Hant": "文字編碼是指字元與位元組之間的對應規則。", "pt-BR": "Codificação é uma regra para representar caracteres.", "de": "Zeichenkodierung ist eine Regel zur Darstellung von Zeichen.", "fr": "Un encodage est une règle de représentation des caractères.", "es": "La codificación es una regla para representar caracteres."}
        with tempfile.TemporaryDirectory() as tmp, patch("topic_management.load_app_names", return_value=set()):
            root = Path(tmp)
            rows = self.rows()
            for row in rows:
                row["slug"] = "read-large-txt-files"
                row["canonical_path"] = f"generated/markdown/{row['primary_language']}/reading/read-large-txt-files.md"
                row["primary_keyword"] = "TXT"
            topics = self.workspace(root, rows)
            assets_root = root / "generated/assets/blog"
            metadata_root = root / "generated/metadata"
            for row in rows:
                language = row["primary_language"]
                if language == "en":
                    markdown = MARKDOWN
                elif language == "ko":
                    markdown = korean_markdown()
                else:
                    labels = LOCALIZED_SECTIONS[language]
                    body = "\n\n".join(f"## {h}\n\nTXT {definitions[language]}" for h in labels)
                    body += "\n\n" + (definitions[language] + " ") * 65
                    body += '\n\n1. TXT\n2. TXT\n\n| A | B |\n| --- | --- |\n| TXT | TXT |\n\nhttps://www.w3.org/\n'
                    body += f'\n![{WORKFLOW_LABELS[language][3]}](/blog-assets/{language}/{row["slug"]}/workflow-diagram.svg)\n'
                    metadata = {"title": "TXT", "card_title": "TXT", "slug": row["slug"], "description": "TXT", "status": "review", "language": language, "topic_id": row["id"], "search_intent": "workflow", "primary_keyword": "TXT", "tags": "TXT"}
                    markdown = "---\n" + "\n".join(f'{k}: "{v}"' for k, v in metadata.items()) + "\n---\n" + body
                (root / row["canonical_path"]).write_text(markdown)
                asset = assets_root / language / row["slug"] / "workflow-diagram.svg"
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_text(workflow_svg("TXT", "TXT", language))
                links = metadata_root / language / "reading" / row["slug"] / "internal_links.json"
                links.parent.mkdir(parents=True, exist_ok=True)
                links.write_text(json.dumps({"recommendations": {"related_articles": []}}))
            review_root = root / "generated/reviews"
            for row in rows:
                result = json.loads(evaluate_article(row["id"], topics, metadata_root, assets_root, review_root).read_text())
                self.assertTrue(result["passed"], (row["primary_language"], result["checks"]))
            scheduled = schedule_ready_articles(topics, review_root, None, now=datetime(2026, 10, 8, tzinfo=timezone.utc))
            self.assertEqual(len(scheduled), 9)
            published = publish_due_articles(topics, review_root, None, now=datetime(2026, 10, 12, tzinfo=timezone.utc))
            self.assertEqual(len(published), 9)


if __name__ == "__main__":
    unittest.main()
