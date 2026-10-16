"""Boundary tests for the isolated Aligna native-validation adapter.

These test fixtures never become publication artifacts.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_aligna_preview as preview

class DisposablePreviewBoundaries(unittest.TestCase):
    def make_source(self, root):
        for name in preview.COPY_ROOTS:
            path = root / name
            if name.endswith(".md"):
                path.write_text("fixture", encoding="utf-8")
            else:
                path.mkdir()
                (path / "fixture.txt").write_text(name, encoding="utf-8")
        (root / "data/topics.csv").write_text("live topics must not change\n")
        (root / "topics/topics.csv").write_text("live topics must not change\n")

    def test_copy_is_disposable_and_does_not_copy_git(self):
        with tempfile.TemporaryDirectory() as d:
            source, stage = Path(d) / "source", Path(d) / "stage"
            source.mkdir()
            self.make_source(source)
            (source / ".git").mkdir()
            (source / ".git/config").write_text("must not copy credentials")
            before = preview.source_inventory(source)
            preview.copy_source(source, stage, before)
            self.assertFalse((stage / ".git").exists())
            (stage / "data/topics.csv").write_text("temporary topics")
            (stage / "topics/topics.csv").write_text("temporary topics")
            self.assertEqual(preview.source_inventory(source), before)

    def test_copy_rejects_source_child_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source"
            source.mkdir()
            self.make_source(source)
            inventory = preview.source_inventory(source)
            with self.assertRaises(ValueError):
                preview.copy_source(source, source / "stage", inventory)
            for invalid in ("../escape", "/absolute", ".git/config"):
                with self.subTest(path=invalid), self.assertRaises(ValueError):
                    preview.copy_source(source, Path(d) / "stage", {invalid: "0" * 64})

    def test_source_symlinks_and_changed_bytes_fail(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source"
            source.mkdir()
            self.make_source(source)
            inventory = preview.source_inventory(source)
            (source / "data/topics.csv").write_text("concurrent edit")
            with self.assertRaisesRegex(ValueError, "changed"):
                preview.copy_source(source, Path(d) / "stage", inventory)
            (source / "docs/external").symlink_to(Path(d) / "elsewhere")
            with self.assertRaisesRegex(ValueError, "Symlink"):
                preview.source_inventory(source)

    def test_worker_cannot_run_against_live_checkout(self):
        with patch.object(preview, "ROOT", ROOT):
            with self.assertRaisesRegex(ValueError, "disposable"):
                preview.stage_worker()

    def test_output_collision_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d)
            output = source / "preview-evidence/aligna"
            output.mkdir(parents=True)
            (output / "keep").write_text("keep")
            with self.assertRaisesRegex(ValueError, "collision"):
                preview.prepare(source)
            self.assertEqual((output / "keep").read_text(), "keep")

    def test_symlink_evidence_parent_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source"
            source.mkdir()
            (source / "preview-evidence").symlink_to(Path(d), target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                preview.prepare(source)

    def test_native_gates_are_exact_and_fail_closed(self):
        expected = ("validate_topics.py", "validate_foundation.py",
                    "evaluate_all_articles.py", "check_nine_language_publication.py",
                    "check_content_supply.py")
        self.assertEqual(tuple(g[0] for g in preview.GATES), expected)
        self.assertEqual(preview.GATES[-1][1:], ("--require-healthy", "--minimum-ideas", "8"))
        with tempfile.TemporaryDirectory() as d:
            result = type("Result", (), {"returncode": 1, "stdout": "real gate failure"})()
            with patch.object(preview.subprocess, "run", return_value=result) as run:
                with self.assertRaisesRegex(ValueError, "Native gate failed"):
                    preview.run_gates(Path(d), Path(d))
                self.assertEqual(run.call_count, 1)
                self.assertEqual((Path(d) / "01-validate_topics.py.log").read_text(), "real gate failure")

    def test_nine_complete_authored_drafts_and_changes(self):
        drafts = preview.validate_drafts(ROOT / "preview/aligna")
        self.assertEqual(set(drafts), set(preview.LOCALES))
        for locale, draft in drafts.items():
            self.assertEqual(draft["locale"], locale)
            self.assertGreater(len(draft["body"]), 2000)
            self.assertEqual(len(draft["image"]["steps"]), 4)

    def test_incomplete_or_altered_draft_fails(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            for path in (ROOT / "preview/aligna").glob("*.json"):
                (target / path.name).write_bytes(path.read_bytes())
            (target / "ja.json").unlink()
            with self.assertRaises(FileNotFoundError):
                preview.validate_drafts(target)
            (target / "ja.json").write_bytes((ROOT / "preview/aligna/ja.json").read_bytes())
            value = json.loads((target / "ja.json").read_text())
            value["locale"] = "en"
            (target / "ja.json").write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "locale"):
                preview.validate_drafts(target)

    def test_no_publication_or_paid_execution_entrypoint(self):
        source = (ROOT / "scripts/prepare_aligna_preview.py").read_text()
        for forbidden in ("import publishing", "from publishing", "workflow_dispatch",
                          "git push", "publish_due_articles(", "schedule_articles(",
                          "codex exec", "openai.", "api_key"):
            self.assertNotIn(forbidden, source)

if __name__ == "__main__":
    unittest.main()
