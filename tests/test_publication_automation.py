from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_article import REVIEW_VERSION, evaluate_article, has_clear_definitions, score_article, sections, translation_quality_passes
from build_manual_publish_site import compose_url
from publish_due_articles import DuePublicationError, publish_due_articles
from schedule_ready_articles import SchedulingError, schedule_ready_articles
from check_content_supply import content_supply_report
from topic_management import TOPIC_HEADER, write_topics
import run_pipeline as pipeline_module
from publication_locales import PUBLICATION_LOCALES
from article_localization import LOCALIZED_SECTIONS, WORKFLOW_LABELS
from generate_image_assets import workflow_svg


KST = timezone(timedelta(hours=9))


def topic_row(status: str, topic_id: str = "TOPIC-0001", language: str = "en") -> dict[str, str]:
    path = f"generated/markdown/{language}/reading/read-large-txt-files.md"
    return {
        "id": topic_id,
        "status": status,
        "category": "reading",
        "primary_question": "How can I read very large TXT files?",
        "working_title": "How to Read Very Large TXT Files",
        "slug": "read-large-txt-files",
        "primary_language": language,
        "priority": "high",
        "search_intent": "solve",
        "related_apps": "",
        "primary_keyword": "large TXT file reader",
        "secondary_keywords": "TXT reader|large text file|virtual rendering",
        "evergreen": "true",
        "source_type": "user_question",
        "canonical_path": path,
        "published_url": "",
        "scheduled_at": "",
        "published_at": "",
        "updated_at": "",
        "review_required": "true",
        "notes": "",
    }


MARKDOWN = """---
title: "How to Read Very Large TXT Files"
card_title: "How to Read Very Large TXT Files"
slug: "read-large-txt-files"
category: "reading"
language: "en"
description: "Learn how to choose a large TXT file reader without unnecessary lag."
status: "review"
topic_id: "TOPIC-0001"
search_intent: "solve"
primary_keyword: "large TXT file reader"
secondary_keywords: "TXT reader|large text file|virtual rendering"
related_apps: ""
canonical_url: "https://example.com/blog/en/read-large-txt-files/"
published_at: "2026-07-14T09:00:00+09:00"
updated_at: "2026-07-14T09:00:00+09:00"
tags: "large TXT file reader|TXT reader|plain text"
---

# How to Read Very Large TXT Files

## Question

How can I read very large TXT files?

## Short Answer

Use a reader workflow that separates file size, encoding, search behavior, and virtual rendering before choosing an app.

## Why This Problem Happens

Encoding is the rule an app uses to turn bytes into readable characters. Virtual rendering is a technique that renders only the visible portion of a document.

## What To Check First

- Confirm the file is plain text.
- Check the encoding.
- Avoid rich text conversion.

## Recommended Workflow

1. Open a copy of the file.
2. Check the encoding.
3. Use search before repeated scrolling.
4. Choose a large TXT file reader only after the workflow is clear.

![Workflow diagram](/blog-assets/en/read-large-txt-files/workflow-diagram.svg "Workflow diagram")

## Loading the Whole File vs Rendering What You Need

| Approach | Best for |
| --- | --- |
| Render visible text | Very large TXT files |

## ONNELLAB Application

No ONNELLAB application is required to understand this workflow.

## References

- [The Unicode Standard](https://www.unicode.org/versions/latest/) for encoding references.

## Conclusion

Start with the reading task, confirm encoding, and choose the simplest workflow that solves the problem.

## FAQ

### Can a large TXT file damage my device?

No. The usual risk is that an app may become slow or unresponsive.
"""


def korean_markdown() -> str:
    content = MARKDOWN
    replacements = [
        ('language: "en"', 'language: "ko"'),
        ('topic_id: "TOPIC-0001"', 'topic_id: "TOPIC-0002"'),
        ("/blog-assets/en/", "/blog-assets/ko/"),
        ("## Question", "## 질문"),
        ("## Short Answer", "## 요약 답변"),
        ("## Recommended Workflow", "## 권장 워크플로"),
        ("## ONNELLAB Application", "## ONNELLAB 앱"),
        ("## References", "## 참고 자료"),
        ("## Conclusion", "## 결론"),
        ("## FAQ", "## 자주 묻는 질문"),
        ("plain text", "일반 텍스트"),
        ("Plain text", "일반 텍스트"),
        ("rich text", "서식 있는 텍스트"),
        ("Rich text", "서식 있는 텍스트"),
        ("virtual rendering", "가상 렌더링"),
        ("Virtual rendering", "가상 렌더링"),
        ("encoding", "인코딩"),
        ("Encoding", "인코딩"),
    ]
    for source, localized in replacements:
        content = content.replace(source, localized)
    return content


def minimal_article_body(language: str, include_product: bool = False) -> str:
    headings = (
        ["Question", "Short Answer", "Recommended Workflow"]
        if language == "en"
        else ["질문", "요약 답변", "권장 워크플로"]
    )
    if include_product:
        headings.append("ONNELLAB Application" if language == "en" else "ONNELLAB 앱")
    headings.extend(["References", "Conclusion", "FAQ"] if language == "en" else ["참고 자료", "결론", "자주 묻는 질문"])
    return "\n\n".join(f"## {heading}\n\nSection content." for heading in headings) + "\n"


def passing_review(
    topic_id: str,
    score: float = 9.4,
    input_fingerprint: str | None = None,
) -> dict[str, object]:
    return {
        "version": REVIEW_VERSION,
        "type": "article_review",
        "topic_id": topic_id,
        "title": "How to Read Very Large TXT Files",
        "input_fingerprint": input_fingerprint or f"fingerprint-{topic_id}",
        "score": score,
        "threshold": 9.0,
        "passed": True,
        "checks": [
            {
                "name": name,
                "passed": True,
                "points": 1.0,
                "max_points": 1.0,
                "note": "Current article passed the required check.",
            }
            for name in (
                "metadata_complete", "card_title_consistent", "brand_spelling",
                "required_sections", "short_answer_ready", "structured_answer",
                "clear_definitions", "primary_keyword", "external_reference",
                "product_after_education", "publish_ready_image", "social_card_source",
                "image_quality", "internal_links", "readability_depth", "translation_quality",
            )
        ],
    }


class PublicationAutomationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.topics_path = self.root / "data" / "topics.csv"
        self.legacy_path = self.root / "topics" / "topics.csv"
        self.markdown_path = self.root / "generated" / "markdown" / "en" / "reading" / "read-large-txt-files.md"
        self.ko_markdown_path = self.root / "generated" / "markdown" / "ko" / "reading" / "read-large-txt-files.md"
        self.asset_path = self.root / "generated" / "assets" / "blog" / "en" / "read-large-txt-files" / "workflow-diagram.svg"
        self.ko_asset_path = self.root / "generated" / "assets" / "blog" / "ko" / "read-large-txt-files" / "workflow-diagram.svg"
        self.metadata_path = self.root / "generated" / "metadata" / "en" / "reading" / "read-large-txt-files" / "internal_links.json"
        self.review_root = self.root / "generated" / "reviews"
        self.topics_path.parent.mkdir(parents=True)
        self.legacy_path.parent.mkdir(parents=True)
        self.markdown_path.parent.mkdir(parents=True)
        self.ko_markdown_path.parent.mkdir(parents=True)
        self.asset_path.parent.mkdir(parents=True)
        self.ko_asset_path.parent.mkdir(parents=True)
        self.metadata_path.parent.mkdir(parents=True)
        self.markdown_path.write_text(MARKDOWN, encoding="utf-8")
        self.ko_markdown_path.write_text(
            MARKDOWN.replace('language: "en"', 'language: "ko"').replace('/blog-assets/en/', '/blog-assets/ko/'),
            encoding="utf-8",
        )
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675">
<title>ONNELLAB Blog workflow diagram</title>
<desc>ONNELLAB workflow diagram for reading large TXT files.</desc>
<g transform="translate(100 210)"><rect width="200" height="170"/><text><tspan>Check file</tspan></text></g>
<path d="M330 295H470"/>
<g transform="translate(500 210)"><rect width="200" height="170"/><text><tspan>Read safely</tspan></text></g>
</svg>
"""
        self.asset_path.write_text(svg, encoding="utf-8")
        self.ko_asset_path.write_text(svg.replace("Check file", "파일 확인").replace("Read safely", "안전하게 읽기"), encoding="utf-8")
        self.metadata_path.write_text(
            json.dumps({"recommendations": {"related_articles": [{"topic_id": "TOPIC-0002"}]}}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pipeline_requests_prepublication_distribution_drafts_in_live_and_dry_runs(self) -> None:
        stage_names = (
            "validate",
            "create_github_releases",
            "generate_all_markdown",
            "generate_all_image_specs",
            "generate_all_image_assets",
            "generate_all_internal_links",
            "evaluate_all_articles",
            "schedule_ready_articles",
            "publish_due_articles",
            "build_site",
            "quality_gate",
            "distribution_gate",
            "approve_due_distribution",
            "deploy_github_pages",
        )
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                patches = [patch.object(pipeline_module, name) for name in stage_names]
                patches.append(patch.object(pipeline_module, "copy_for_dry_run"))
                mocks = [item.start() for item in patches]
                self.addCleanup(lambda active=patches: [item.stop() for item in active])
                with patch.object(pipeline_module, "generate_social_posts") as generate_social, patch.object(
                    pipeline_module, "generate_syndication_drafts"
                ) as generate_syndication:
                    pipeline_module.run_pipeline(dry_run=dry_run)
                self.assertTrue(generate_social.call_args.kwargs["include_prepublication"])
                self.assertTrue(generate_syndication.call_args.kwargs["include_prepublication"])
                for item in patches:
                    item.stop()

    def test_quality_gate_cleans_first_temp_when_second_temp_creation_fails(self) -> None:
        social_manifest = self.root / "generated" / "social" / "manifest.json"
        syndication_manifest = self.root / "generated" / "syndication" / "manifest.json"
        social_manifest.parent.mkdir(parents=True, exist_ok=True)
        syndication_manifest.parent.mkdir(parents=True, exist_ok=True)
        social_manifest.write_text('{"posts": []}\n', encoding="utf-8")
        syndication_manifest.write_text('{"drafts": []}\n', encoding="utf-8")

        with patch.object(pipeline_module, "syndication_gate_manifest", side_effect=RuntimeError("injected")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                pipeline_module.quality_gate(social_manifest, syndication_manifest)

        self.assertEqual(list(social_manifest.parent.glob(".published-social-*.json")), [])
        self.assertEqual(list(syndication_manifest.parent.glob(".published-syndication-*.json")), [])

    def test_distribution_gate_cleans_all_temps_when_intermediate_creation_fails(self) -> None:
        social_manifest = self.root / "generated" / "social" / "manifest.json"
        syndication_manifest = self.root / "generated" / "syndication" / "manifest.json"
        social_manifest.parent.mkdir(parents=True, exist_ok=True)
        syndication_manifest.parent.mkdir(parents=True, exist_ok=True)
        social_manifest.write_text('{"posts": []}\n', encoding="utf-8")
        syndication_manifest.write_text('{"drafts": []}\n', encoding="utf-8")
        original = pipeline_module.syndication_gate_manifest
        calls = 0

        def fail_second(path: Path, actionable_only: bool) -> Path:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected intermediate failure")
            return original(path, actionable_only)

        with patch.object(pipeline_module, "syndication_gate_manifest", side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, "injected intermediate failure"):
                pipeline_module.distribution_gate(self.topics_path, social_manifest, syndication_manifest)

        self.assertEqual(list(social_manifest.parent.glob(".published-social-*.json")), [])
        self.assertEqual(list(syndication_manifest.parent.glob(".published-syndication-*.json")), [])

    def read_rows(self) -> list[dict[str, str]]:
        with self.topics_path.open("r", encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    def write_review_report(self, language: str, report: dict[str, object]) -> None:
        path = self.review_root / language / "reading" / "read-large-txt-files" / "review.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report), encoding="utf-8")

    def prepare_bundle(self, status: str, score: float = 9.4, history=()) -> list[dict[str, str]]:
        """Synthetic structural fixtures only, not publishable editorial copy.

        EN/KO retain the original language regression fixtures; the remaining
        locales use the localized structure also exercised by the contract suite.
        Every locale has its own topic, article, image, metadata and review.
        """
        definitions = {
            "ja": "文字コードとは文字を表す規則です。",
            "zh-Hans": "文本编码是指字符与字节之间的对应规则。",
            "zh-Hant": "文字編碼是指字元與位元組之間的對應規則。",
            "pt-BR": "Codificação é uma regra para representar caracteres.",
            "de": "Zeichenkodierung ist eine Regel zur Darstellung von Zeichen.",
            "fr": "Un encodage est une règle de représentation des caractères.",
            "es": "La codificación es una regla para representar caracteres.",
        }
        rows = [topic_row(status, f"TOPIC-{i:04d}", language)
                for i, language in enumerate(PUBLICATION_LOCALES, 1)]
        for row in rows:
            language = row["primary_language"]
            if status == "scheduled":
                row["scheduled_at"] = "2026-07-14T09:00:00+09:00"
            if language == "en":
                markdown = MARKDOWN
            elif language == "ko":
                markdown = korean_markdown()
            else:
                row["primary_keyword"] = "TXT"
                body = "\n\n".join(f"## {h}\n\nTXT {definitions[language]}" for h in LOCALIZED_SECTIONS[language])
                body += "\n\n" + (definitions[language] + " ") * 65
                body += "\n\n1. TXT\n2. TXT\n\n| A | B |\n| --- | --- |\n| TXT | TXT |\n\nhttps://www.w3.org/\n"
                body += f'\n![{WORKFLOW_LABELS[language][3]}](/blog-assets/{language}/{row["slug"]}/workflow-diagram.svg)\n'
                metadata = {"title": "TXT", "card_title": "TXT", "slug": row["slug"],
                            "description": "TXT", "status": status, "language": language,
                            "topic_id": row["id"], "search_intent": "solve", "primary_keyword": "TXT", "tags": "TXT"}
                markdown = "---\n" + "\n".join(f'{k}: "{v}"' for k, v in metadata.items()) + "\n---\n" + body
            path = self.root / row["canonical_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(markdown, encoding="utf-8")
            asset = self.root / "generated/assets/blog" / language / row["slug"] / "workflow-diagram.svg"
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_text(workflow_svg("TXT", "TXT", language), encoding="utf-8")
            links = self.root / "generated/metadata" / language / "reading" / row["slug"] / "internal_links.json"
            links.parent.mkdir(parents=True, exist_ok=True)
            links.write_text(json.dumps({"recommendations": {"related_articles": []}}), encoding="utf-8")
            self.write_review_report(language, passing_review(row["id"], score))
        write_topics(self.topics_path, [*history, *rows])
        write_topics(self.legacy_path, [*history, *rows])
        return rows

    def test_supply_requires_current_complete_reviews_even_for_scheduled_bundles(self) -> None:
        for status in ("review", "scheduled"):
            for invalid in ({"score": 9.9}, {**passing_review("TOPIC-0001"), "input_fingerprint": "old"}, []):
                with self.subTest(status=status, invalid=invalid):
                    self.prepare_bundle(status)
                    self.write_review_report("en", invalid)
                    self.write_review_report("ko", passing_review("TOPIC-0002"))
                    with patch("schedule_ready_articles.score_article", side_effect=lambda topic, *_: passing_review(topic["id"])):
                        report = content_supply_report(self.topics_path, self.review_root)
                    self.assertEqual(report["qualified_pair_count"], 0)

    def test_supply_accepts_current_bundle_without_mutating_content(self) -> None:
        for status in ("review", "scheduled"):
            self.prepare_bundle(status)
            before = self.topics_path.read_bytes()
            with patch("schedule_ready_articles.score_article", side_effect=lambda topic, *_: passing_review(topic["id"])):
                report = content_supply_report(self.topics_path, self.review_root)
            self.assertEqual(report["qualified_pair_count"], 1)
            self.assertEqual(report["qualified_bundle_count"], 1)
            self.assertEqual(set(report["qualified_pairs"][0]["scores"]), set(PUBLICATION_LOCALES))
            self.assertEqual(self.topics_path.read_bytes(), before)

    def test_evaluates_article_above_publication_threshold(self) -> None:
        write_topics(self.topics_path, [topic_row("review"), topic_row("review", "TOPIC-0002", "ko")])
        write_topics(self.legacy_path, [topic_row("review"), topic_row("review", "TOPIC-0002", "ko")])

        path = evaluate_article(
            "TOPIC-0001",
            topics_path=self.topics_path,
            metadata_root=self.root / "generated" / "metadata",
            assets_root=self.root / "generated" / "assets" / "blog",
            review_root=self.review_root,
        )

        review = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreater(review["score"], 9.0)
        self.assertTrue(review["passed"])
        check_names = {check["name"] for check in review["checks"]}
        self.assertIn("short_answer_ready", check_names)
        self.assertIn("card_title_consistent", check_names)
        self.assertIn("brand_spelling", check_names)
        self.assertIn("social_card_source", check_names)
        self.assertIn("image_quality", check_names)
        self.assertIn("translation_quality", check_names)

    def test_review_passed_requires_every_check_to_pass(self) -> None:
        en = topic_row("review")
        ko = topic_row("review", "TOPIC-0002", "ko")
        write_topics(self.topics_path, [en, ko])
        self.asset_path.write_text(self.asset_path.read_text(encoding="utf-8").replace("Check file", "Check file…"), encoding="utf-8")

        review = score_article(
            en,
            MARKDOWN,
            self.topics_path,
            self.root / "generated" / "metadata",
            self.root / "generated" / "assets" / "blog",
        )
        checks = {check["name"]: check for check in review["checks"]}

        self.assertGreater(review["score"], 9.0)
        self.assertFalse(checks["image_quality"]["passed"])
        self.assertFalse(review["passed"])

    def test_clear_definitions_accept_topic_independent_prose(self) -> None:
        examples = {
            "reading": "A line ending is a marker that separates one line from the next.",
            "media": "A codec is a method for encoding and decoding media data.",
            "research": "Provenance refers to the recorded origin and history of evidence.",
        }

        for topic, prose in examples.items():
            with self.subTest(topic=topic):
                self.assertTrue(has_clear_definitions(prose))

    def test_product_neutral_article_does_not_require_a_product_section(self) -> None:
        en = topic_row("review")
        ko = topic_row("review", "TOPIC-0002", "ko")
        write_topics(self.topics_path, [en, ko])
        product_neutral_markdown = MARKDOWN.replace(
            "\n## ONNELLAB Application\n\nNo ONNELLAB application is required to understand this workflow.\n",
            "",
        )

        review = score_article(
            en,
            product_neutral_markdown,
            self.topics_path,
            self.root / "generated" / "metadata",
            self.root / "generated" / "assets" / "blog",
        )
        checks = {check["name"]: check for check in review["checks"]}

        self.assertTrue(checks["required_sections"]["passed"])
        self.assertTrue(checks["product_after_education"]["passed"])

    def test_app_linked_article_accepts_generated_product_heading_after_workflow(self) -> None:
        en = topic_row("review")
        en["related_apps"] = "VaultXT"
        ko = topic_row("review", "TOPIC-0002", "ko")
        ko["related_apps"] = "VaultXT"
        write_topics(self.topics_path, [en, ko])
        markdown = MARKDOWN.replace("## ONNELLAB Application", "## Where ONNELLAB Fits").replace(
            "No ONNELLAB application is required to understand this workflow.",
            "VaultXT can support the workflow after the reader understands the process.",
        )

        review = score_article(
            en,
            markdown,
            self.topics_path,
            self.root / "generated" / "metadata",
            self.root / "generated" / "assets" / "blog",
        )
        checks = {check["name"]: check for check in review["checks"]}

        self.assertTrue(checks["required_sections"]["passed"])
        self.assertTrue(checks["product_after_education"]["passed"])

        product_section = """## Where ONNELLAB Fits

VaultXT can support the workflow after the reader understands the process.

"""
        before_workflow = markdown.replace(product_section, "").replace(
            "## Recommended Workflow",
            f"{product_section}## Recommended Workflow",
        )
        early_review = score_article(
            en,
            before_workflow,
            self.topics_path,
            self.root / "generated" / "metadata",
            self.root / "generated" / "assets" / "blog",
        )
        early_checks = {check["name"]: check for check in early_review["checks"]}

        self.assertFalse(early_checks["product_after_education"]["passed"])

    def test_korean_terminology_is_derived_from_counterpart_content(self) -> None:
        for category, slug, definition in [
            ("media", "understand-codecs", "A codec is a method for representing media data."),
            ("research", "track-provenance", "Provenance refers to the recorded origin of evidence."),
        ]:
            with self.subTest(category=category):
                en = topic_row("review", "TOPIC-0001", "en")
                ko = topic_row("review", "TOPIC-0002", "ko")
                for row in (en, ko):
                    row["category"] = category
                    row["slug"] = slug
                    row["primary_question"] = definition
                    row["working_title"] = definition
                    row["primary_keyword"] = slug.replace("-", " ")
                    row["secondary_keywords"] = ""
                    row["canonical_path"] = f"generated/markdown/{row['primary_language']}/{category}/{slug}.md"
                write_topics(self.topics_path, [en, ko])
                counterpart_path = self.root / en["canonical_path"]
                counterpart_path.parent.mkdir(parents=True, exist_ok=True)
                counterpart_path.write_text(
                    f'---\nslug: "{slug}"\n---\n\n{definition}\n\n{minimal_article_body("en")}',
                    encoding="utf-8",
                )
                korean_body = minimal_article_body("ko")

                passed, note = translation_quality_passes(
                    ko,
                    {"slug": slug},
                    korean_body,
                    sections(korean_body),
                    self.topics_path,
                )

                self.assertTrue(passed, note)

    def test_korean_translation_requires_only_terms_present_in_reading_counterpart(self) -> None:
        en = topic_row("review", "TOPIC-0001", "en")
        ko = topic_row("review", "TOPIC-0002", "ko")
        write_topics(self.topics_path, [en, ko])
        korean_body = minimal_article_body("ko", include_product=True)

        passed, note = translation_quality_passes(
            ko,
            {"slug": ko["slug"]},
            korean_body,
            sections(korean_body),
            self.topics_path,
        )

        self.assertFalse(passed)
        self.assertIn("일반 텍스트", note)
        self.assertIn("인코딩", note)
        self.assertIn("가상 렌더링", note)

    def test_korean_mixed_terms_ignore_urls_but_reject_visible_prose(self) -> None:
        en = topic_row("review", "TOPIC-0001", "en")
        ko = topic_row("review", "TOPIC-0002", "ko")
        write_topics(self.topics_path, [en, ko])
        localized_body = (
            minimal_article_body("ko", include_product=True)
            + "일반 텍스트의 인코딩과 가상 렌더링을 확인합니다.\n\n"
            + "[WHATWG 표준](https://encoding.spec.whatwg.org/)을 참고합니다.\n"
        )

        passed, note = translation_quality_passes(
            ko,
            {"slug": ko["slug"]},
            localized_body,
            sections(localized_body),
            self.topics_path,
        )
        self.assertTrue(passed, note)

        mixed_body = localized_body + "Visible encoding guidance should be localized.\n"
        passed, note = translation_quality_passes(
            ko,
            {"slug": ko["slug"]},
            mixed_body,
            sections(mixed_body),
            self.topics_path,
        )
        self.assertFalse(passed)
        self.assertIn("encoding", note)

    def test_schedules_only_reviewed_articles_above_threshold_every_three_days(self) -> None:
        published = topic_row("published", "TOPIC-1000")
        published["slug"] = "already-published"
        published["canonical_path"] = "generated/markdown/en/reading/already-published.md"
        published["published_url"] = "https://example.com/blog/en/already-published/"
        published["published_at"] = "2026-07-11T09:00:00+09:00"
        self.prepare_bundle("review", score=9.2, history=[published])

        with patch(
            "schedule_ready_articles.score_article",
            side_effect=lambda topic, *_: passing_review(topic["id"], 9.2),
        ):
            scheduled = schedule_ready_articles(
                self.topics_path,
                self.review_root,
                self.legacy_path,
                now=datetime(2026, 7, 12, 9, tzinfo=KST),
            )

        self.assertEqual(len(scheduled), 9)
        self.assertEqual(scheduled[0]["status"], "scheduled")
        self.assertEqual(scheduled[0]["scheduled_at"], "2026-07-14T09:00:00+09:00")
        self.assertEqual({row["scheduled_at"] for row in scheduled}, {"2026-07-14T09:00:00+09:00"})

    def test_scheduling_catches_up_an_overdue_slot_immediately(self) -> None:
        published = topic_row("published", "TOPIC-1000")
        published["slug"] = "already-published"
        published["canonical_path"] = "generated/markdown/en/reading/already-published.md"
        published["published_url"] = "https://example.com/blog/en/already-published/"
        published["published_at"] = "2026-07-14T09:00:00+09:00"
        self.prepare_bundle("review", score=9.2, history=[published])

        with patch(
            "schedule_ready_articles.score_article",
            side_effect=lambda topic, *_: passing_review(topic["id"], 9.2),
        ):
            scheduled = schedule_ready_articles(
                self.topics_path,
                self.review_root,
                self.legacy_path,
                now=datetime(2026, 7, 20, 10, tzinfo=KST),
            )

        self.assertEqual(len(scheduled), 9)
        self.assertEqual(scheduled[0]["scheduled_at"], "2026-07-20T10:00:00+09:00")
        self.assertEqual({row["scheduled_at"] for row in scheduled}, {"2026-07-20T10:00:00+09:00"})

    def test_real_evaluation_schedule_and_publish_lifecycle_preserves_review_fingerprint(self) -> None:
        bundle = self.prepare_bundle("review")
        metadata_root = self.root / "generated" / "metadata"
        assets_root = self.root / "generated" / "assets" / "blog"

        review_paths = [
            evaluate_article(
                topic["id"],
                topics_path=self.topics_path,
                metadata_root=metadata_root,
                assets_root=assets_root,
                review_root=self.review_root,
            )
            for topic in bundle
        ]
        fingerprints = {}
        for review_path in review_paths:
            review = json.loads(review_path.read_text(encoding="utf-8"))
            self.assertEqual(review["version"], REVIEW_VERSION)
            self.assertTrue(review["input_fingerprint"])
            fingerprints[review["topic_id"]] = review["input_fingerprint"]
            self.assertTrue(review["passed"])
            self.assertTrue(all(check["passed"] for check in review["checks"]))

        scheduled = schedule_ready_articles(
            self.topics_path,
            self.review_root,
            self.legacy_path,
            now=datetime(2026, 7, 14, 8, tzinfo=KST),
        )

        self.assertEqual(len(scheduled), 9)
        self.assertEqual({row["status"] for row in scheduled}, {"scheduled"})
        self.assertEqual({row["scheduled_at"] for row in scheduled}, {"2026-07-17T09:00:00+09:00"})

        for row in self.read_rows():
            current = score_article(row, (self.root / row["canonical_path"]).read_text(encoding="utf-8"), self.topics_path, metadata_root, assets_root)
            self.assertEqual(current["input_fingerprint"], fingerprints[row["id"]])

        published = publish_due_articles(
            self.topics_path,
            self.review_root,
            self.legacy_path,
            site_url="https://example.com/",
            now=datetime(2026, 7, 17, 9, tzinfo=KST),
            metadata_root=metadata_root,
        )

        self.assertEqual(len(published), 9)
        self.assertEqual({row["status"] for row in published}, {"published"})
        self.assertEqual(
            {row["published_at"] for row in published},
            {"2026-07-17T09:00:00+09:00"},
        )

    def test_schedule_rejects_incomplete_mismatched_stale_and_changed_reviews(self) -> None:
        valid = passing_review("TOPIC-0001")
        failed_current = passing_review("TOPIC-0001", 8.0)
        failed_current["passed"] = False
        failed_current["checks"][0]["passed"] = False
        without_fingerprint = {key: value for key, value in valid.items() if key != "input_fingerprint"}
        cases = {
            "score_only": ({"score": 9.4}, valid),
            "legacy_version": ({**valid, "version": REVIEW_VERSION - 1}, valid),
            "missing_fingerprint": (without_fingerprint, valid),
            "topic_mismatch": ({**valid, "topic_id": "TOPIC-9999"}, valid),
            "report_failed": ({**valid, "passed": False}, valid),
            "check_failed": ({**valid, "checks": [{**valid["checks"][0], "passed": False}]}, valid),
            "at_threshold": ({**valid, "score": 9.0}, {**valid, "score": 9.0}),
            "empty_checks": ({**valid, "checks": []}, valid),
            "stale_score": ({**valid, "score": 9.3}, valid),
            "input_changed_same_score": (
                valid,
                passing_review("TOPIC-0001", input_fingerprint="fingerprint-after-prose-or-topic-change"),
            ),
            "article_changed": (valid, failed_current),
        }

        for name, (persisted_en, current_en) in cases.items():
            with self.subTest(name=name):
                bundle = self.prepare_bundle("review")
                before = {self.root / row["canonical_path"]: (self.root / row["canonical_path"]).read_bytes() for row in bundle}
                csv_before = {path: path.read_bytes() for path in (self.topics_path, self.legacy_path)}
                self.write_review_report("en", persisted_en)
                self.write_review_report("ko", passing_review("TOPIC-0002"))

                def current_report(topic: dict[str, str], *_: object) -> dict[str, object]:
                    return current_en if topic["id"] == "TOPIC-0001" else passing_review(topic["id"])

                with patch("schedule_ready_articles.score_article", side_effect=current_report) as evaluator:
                    scheduled = schedule_ready_articles(
                        self.topics_path,
                        self.review_root,
                        self.legacy_path,
                        now=datetime(2026, 7, 12, 9, tzinfo=KST),
                    )

                self.assertEqual(scheduled, [])
                self.assertEqual([row["status"] for row in self.read_rows()], ["review"] * 9)
                self.assertEqual({path: path.read_bytes() for path in before}, before)
                self.assertEqual({path: path.read_bytes() for path in csv_before}, csv_before)
                evaluator.assert_called()

    def test_due_cadence_fails_when_ideas_exist_but_no_review_pair_is_ready(self) -> None:
        published = topic_row("published", "TOPIC-0001", "en")
        published["published_at"] = "2026-07-14T09:00:00+09:00"
        idea = topic_row("idea", "TOPIC-0002", "en")
        idea["slug"] = "next-idea"
        write_topics(self.topics_path, [published, idea])
        write_topics(self.legacy_path, [published, idea])

        with self.assertRaisesRegex(SchedulingError, "ideas=1, paired_ideas=0"):
            schedule_ready_articles(
                self.topics_path,
                self.review_root,
                self.legacy_path,
                now=datetime(2026, 7, 20, 10, tzinfo=KST),
                require_ready_when_due=True,
            )

    def test_publishes_due_article_only_when_review_score_exceeds_threshold(self) -> None:
        bundle = self.prepare_bundle("scheduled")

        with patch(
            "schedule_ready_articles.score_article",
            side_effect=lambda topic, *_: passing_review(topic["id"]),
        ) as evaluate:
            published = publish_due_articles(
                self.topics_path,
                self.review_root,
                self.legacy_path,
                site_url="https://example.com/",
                now=datetime(2026, 7, 14, 9, tzinfo=KST),
            )

        for call in evaluate.call_args_list:
            self.assertEqual(call.args[3], self.root.resolve() / "generated" / "metadata")
        self.assertEqual(len(published), 9)
        self.assertEqual(len(evaluate.call_args_list), 9)
        rows = self.read_rows()
        for row in rows:
            self.assertEqual(row["status"], "published")
            self.assertEqual(row["published_url"], f'https://example.com/blog/{row["primary_language"].lower()}/read-large-txt-files/')
            self.assertIn('status: "published"', (self.root / row["canonical_path"]).read_text(encoding="utf-8"))
        self.assertEqual(rows[0]["status"], "published")
        self.assertEqual(rows[0]["published_url"], "https://example.com/blog/en/read-large-txt-files/")
        self.assertEqual(rows[1]["status"], "published")
        self.assertEqual(rows[1]["published_url"], "https://example.com/blog/ko/read-large-txt-files/")
        content = self.markdown_path.read_text(encoding="utf-8")
        self.assertIn('status: "published"', content)
        self.assertIn('published_at: "2026-07-14T09:00:00+09:00"', content)
        ko_content = self.ko_markdown_path.read_text(encoding="utf-8")
        self.assertIn('status: "published"', ko_content)

    def test_publish_rejects_incomplete_mismatched_stale_and_changed_reviews_before_mutation(self) -> None:
        valid = passing_review("TOPIC-0001")
        failed_current = passing_review("TOPIC-0001", 8.0)
        failed_current["passed"] = False
        failed_current["checks"][0]["passed"] = False
        without_fingerprint = {key: value for key, value in valid.items() if key != "input_fingerprint"}
        cases = {
            "score_only": ({"score": 9.4}, valid),
            "legacy_version": ({**valid, "version": REVIEW_VERSION - 1}, valid),
            "missing_fingerprint": (without_fingerprint, valid),
            "topic_mismatch": ({**valid, "topic_id": "TOPIC-9999"}, valid),
            "report_failed": ({**valid, "passed": False}, valid),
            "check_failed": ({**valid, "checks": [{**valid["checks"][0], "passed": False}]}, valid),
            "at_threshold": ({**valid, "score": 9.0}, {**valid, "score": 9.0}),
            "empty_checks": ({**valid, "checks": []}, valid),
            "stale_score": ({**valid, "score": 9.3}, valid),
            "input_changed_same_score": (
                valid,
                passing_review("TOPIC-0001", input_fingerprint="fingerprint-after-prose-or-topic-change"),
            ),
            "article_changed": (valid, failed_current),
        }

        for name, (persisted_en, current_en) in cases.items():
            with self.subTest(name=name):
                bundle = self.prepare_bundle("scheduled")
                before = {self.root / row["canonical_path"]: (self.root / row["canonical_path"]).read_bytes() for row in bundle}
                csv_before = {path: path.read_bytes() for path in (self.topics_path, self.legacy_path)}
                self.write_review_report("en", persisted_en)
                self.write_review_report("ko", passing_review("TOPIC-0002"))

                def current_report(topic: dict[str, str], *_: object) -> dict[str, object]:
                    return current_en if topic["id"] == "TOPIC-0001" else passing_review(topic["id"])

                with patch("schedule_ready_articles.score_article", side_effect=current_report) as evaluator:
                    with self.assertRaises(DuePublicationError):
                        publish_due_articles(
                            self.topics_path,
                            self.review_root,
                            self.legacy_path,
                            site_url="https://example.com/",
                            now=datetime(2026, 7, 14, 9, tzinfo=KST),
                        )

                self.assertEqual([row["status"] for row in self.read_rows()], ["scheduled"] * 9)
                self.assertEqual({path: path.read_bytes() for path in before}, before)
                self.assertEqual({path: path.read_bytes() for path in csv_before}, csv_before)
                evaluator.assert_called()

    def test_publish_injects_public_same_language_related_articles_into_frontmatter(self) -> None:
        bundle = self.prepare_bundle("scheduled")

        ko_metadata_path = self.root / "generated" / "metadata" / "ko" / "reading" / "read-large-txt-files" / "internal_links.json"
        ko_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.write_text(
            json.dumps(
                {
                    "recommendations": {
                        "related_articles": [
                            {
                                "title": "Already Published TXT Guide",
                                "language": "en",
                                "status": "published",
                                "url": "https://example.com/blog/en/already-published-txt-guide/",
                            },
                            {
                                "title": "Draft TXT Follow-up",
                                "language": "en",
                                "status": "review",
                                "url": "generated/markdown/en/reading/draft-txt-follow-up.md",
                            },
                            {
                                "title": "Korean TXT Guide",
                                "language": "ko",
                                "status": "published",
                                "url": "https://example.com/blog/ko/korean-txt-guide/",
                            },
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        ko_metadata_path.write_text(
            json.dumps(
                {
                    "recommendations": {
                        "related_articles": [
                            {
                                "title": "이미 공개된 TXT 가이드",
                                "language": "ko",
                                "status": "published",
                                "url": "https://example.com/blog/ko/already-published-txt-guide/",
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch(
            "schedule_ready_articles.score_article",
            side_effect=lambda topic, *_: passing_review(topic["id"]),
        ):
            publish_due_articles(
                self.topics_path,
                self.review_root,
                self.legacy_path,
                site_url="https://example.com/",
                now=datetime(2026, 7, 14, 9, tzinfo=KST),
                metadata_root=self.root / "generated" / "metadata",
            )

        content = self.markdown_path.read_text(encoding="utf-8")
        self.assertIn(
            'related_articles: "Already Published TXT Guide => https://example.com/blog/en/already-published-txt-guide/"',
            content,
        )
        self.assertNotIn("Draft TXT Follow-up", content)
        self.assertNotIn("Korean TXT Guide", content)
        ko_content = self.ko_markdown_path.read_text(encoding="utf-8")
        self.assertIn(
            'related_articles: "이미 공개된 TXT 가이드 => https://example.com/blog/ko/already-published-txt-guide/"',
            ko_content,
        )

    def test_each_locale_at_threshold_blocks_schedule_and_publication_without_mutation(self) -> None:
        for status in ("review", "scheduled"):
            for blocked_language in PUBLICATION_LOCALES:
                with self.subTest(status=status, language=blocked_language):
                    bundle = self.prepare_bundle(status)
                    blocked = next(row for row in bundle if row["primary_language"] == blocked_language)
                    self.write_review_report(blocked_language, passing_review(blocked["id"], 9.0))
                    paths = [self.topics_path, self.legacy_path, *(self.root / row["canonical_path"] for row in bundle)]
                    before = {path: path.read_bytes() for path in paths}

                    def current_report(topic, *_):
                        return passing_review(topic["id"], 9.0 if topic["primary_language"] == blocked_language else 9.4)

                    with patch("schedule_ready_articles.score_article", side_effect=current_report) as evaluator:
                        if status == "review":
                            self.assertEqual(schedule_ready_articles(
                                self.topics_path, self.review_root, self.legacy_path,
                                now=datetime(2026, 7, 12, 9, tzinfo=KST)), [])
                        else:
                            with self.assertRaises(DuePublicationError):
                                publish_due_articles(
                                    self.topics_path, self.review_root, self.legacy_path,
                                    now=datetime(2026, 7, 14, 9, tzinfo=KST))
                    self.assertIn(blocked["id"], [call.args[0]["id"] for call in evaluator.call_args_list])
                    self.assertEqual({path: path.read_bytes() for path in paths}, before)

    def test_manual_syndication_open_urls_use_current_editor_routes(self) -> None:
        self.assertEqual(compose_url("hashnode", "", "https://example.com/article"), "")
        self.assertEqual(compose_url("medium", "", "https://example.com/article"), "")


if __name__ == "__main__":
    unittest.main()

