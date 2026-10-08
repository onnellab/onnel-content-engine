import sys
from pathlib import Path
import unittest
import csv
import tempfile
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_nine_language_publication import LANGUAGES, check_rows, check_reviewed_candidates


class NineLanguagePublicationGuardTest(unittest.TestCase):
    def rows(self, status="review"):
        return [{"category": "reading", "slug": "example", "primary_language": language,
                 "status": status, "scheduled_at": "2026-10-09T09:00:00+09:00"}
                for language in sorted(LANGUAGES)]

    def test_complete_review_bundle_passes(self):
        check_rows(self.rows())

    def test_complete_scheduled_bundle_passes(self):
        check_rows(self.rows("scheduled"))

    def test_every_missing_locale_holds(self):
        for language in LANGUAGES:
            with self.subTest(language=language), self.assertRaises(ValueError):
                check_rows([r for r in self.rows() if r["primary_language"] != language])

    def test_historical_bilingual_and_ideas_are_preserved(self):
        check_rows([r for r in self.rows("published") if r["primary_language"] in {"en", "ko"}])
        check_rows(self.rows("idea")[:1])
        check_rows([])

    def test_english_korean_only_holds(self):
        with self.assertRaises(ValueError):
            check_rows([r for r in self.rows() if r["primary_language"] in {"en", "ko"}])

    def test_duplicates_and_unknown_locales_hold(self):
        with self.assertRaises(ValueError):
            check_rows(self.rows() + [self.rows()[0]])
        rows = self.rows()
        rows[0]["primary_language"] = "it"
        with self.assertRaises(ValueError):
            check_rows(rows)

    def test_mixed_stages_hold(self):
        rows = self.rows()
        rows[0]["status"] = "draft"
        with self.assertRaises(ValueError):
            check_rows(rows)

    def test_mismatched_and_naive_publication_instants_hold(self):
        for slot in ("2026-10-10T09:00:00+09:00", "2026-10-09T09:00:00"):
            rows = self.rows("scheduled")
            rows[0]["scheduled_at"] = slot
            with self.assertRaises(ValueError):
                check_rows(rows)

    def test_same_instant_different_offsets_passes(self):
        rows = self.rows("scheduled")
        rows[0]["scheduled_at"] = "2026-10-09T00:00:00+00:00"
        check_rows(rows)

    def test_every_locale_uses_existing_current_quality_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            topics = Path(tmp) / "data/topics.csv"
            topics.parent.mkdir()
            rows = self.rows()
            with topics.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
            with patch("schedule_ready_articles.current_review_score", return_value=10.0) as gate:
                self.assertEqual(check_reviewed_candidates(topics), 1)
                self.assertEqual(gate.call_count, 9)
                self.assertEqual({call.args[0]["primary_language"] for call in gate.call_args_list}, LANGUAGES)
                self.assertTrue(all(call.args[3] == 9.0 for call in gate.call_args_list))
            with patch("schedule_ready_articles.current_review_score", side_effect=ValueError("stale review")):
                with self.assertRaisesRegex(ValueError, "stale review"):
                    check_reviewed_candidates(topics)

    def test_workflow_checks_before_schedule_and_publish(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/publishing.yml").read_text()
        for name, next_name, command in (("Schedule Ready Articles", "Schedule Ready Articles Dry Run", "schedule_ready_articles.py"), ("Publish Due Articles", "Publish Due Articles Dry Run", "publish_due_articles.py")):
            block = workflow.split(f"- name: {name}\n", 1)[1].split(f"- name: {next_name}\n", 1)[0]
            self.assertIn("if: env.DRY_RUN != 'true'", block)
            self.assertLess(block.index("check_nine_language_publication.py"), block.index(command))


if __name__ == "__main__":
    unittest.main()
