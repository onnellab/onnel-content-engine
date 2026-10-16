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


    def test_os_ancestor_alias_is_canonicalized_but_direct_root_symlink_fails(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d).resolve() / "real"
            real.mkdir()
            alias = Path(d).resolve() / "alias"
            alias.symlink_to(real, target_is_directory=True)
            source = alias / "source"
            source.mkdir()
            self.make_source(source)
            preview.copy_source(source, alias / "stage", preview.source_inventory(source))
            self.assertEqual((real / "stage/data/topics.csv").read_bytes(),
                             (real / "source/data/topics.csv").read_bytes())
            direct = real / "direct"
            direct.symlink_to(real / "source", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Direct"):
                preview.copy_source(direct, real / "other", preview.source_inventory(source))
            direct_stage = real / "direct-stage"
            direct_stage.symlink_to(real / "stage", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Direct"):
                preview.copy_source(source, direct_stage, preview.source_inventory(source))


    def test_internal_symlink_inserted_after_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d).resolve() / "source"
            source.mkdir()
            self.make_source(source)
            before = preview.source_inventory(source)
            target = source / "docs/fixture.txt"
            target.unlink()
            target.symlink_to(source / "data/topics.csv")
            with self.assertRaisesRegex(ValueError, "symlink"):
                preview.copy_source(source, Path(d).resolve() / "stage", before)

    def test_prepare_rejects_direct_source_symlink_before_any_side_effect(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            source = root / "source"
            source.mkdir()
            self.make_source(source)
            before = preview.source_inventory(source)
            paths_before = sorted(p.relative_to(source).as_posix() for p in source.rglob("*"))
            direct = root / "direct"
            direct.symlink_to(source, target_is_directory=True)
            with patch.object(preview.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "Direct source symlink"):
                    preview.prepare(direct)
                run.assert_not_called()
            self.assertFalse((source / "preview-evidence").exists())
            self.assertEqual(preview.source_inventory(source), before)
            self.assertEqual(sorted(p.relative_to(source).as_posix() for p in source.rglob("*")),
                             paths_before)

    def test_worker_failure_is_echoed_and_retained_without_changing_source(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d).resolve()
            self.make_source(source)
            before = preview.source_inventory(source)
            result = type("Result", (), {"returncode": 1, "stdout": "native child traceback"})()
            with patch.object(preview.subprocess, "run", return_value=result), patch("sys.stderr") as stderr:
                with self.assertRaisesRegex(ValueError, "Disposable native validation failed"):
                    preview.prepare(source)
                self.assertIn("native child traceback", "".join(str(call.args[0]) for call in stderr.write.call_args_list))
            evidence = source / "preview-evidence/aligna"
            self.assertEqual((evidence / "generation.log").read_text(), "native child traceback")
            self.assertTrue(json.loads((evidence / "source-integrity.json").read_text())["source_unchanged"])
            self.assertEqual(preview.source_inventory(source), before)

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
            with patch.object(preview.subprocess, "run", return_value=result) as run, patch("sys.stderr") as stderr:
                with self.assertRaisesRegex(ValueError, "Native gate failed"):
                    preview.run_gates(Path(d), Path(d))
                self.assertEqual(run.call_count, 1)
                self.assertIn("real gate failure", "".join(str(call.args[0]) for call in stderr.write.call_args_list))
                self.assertEqual((Path(d) / "01-validate_topics.py.log").read_text(), "real gate failure")

    def test_nine_complete_authored_drafts_and_changes(self):
        drafts = preview.validate_drafts(ROOT / "preview/aligna")
        self.assertEqual(set(drafts), set(preview.LOCALES))
        for locale, draft in drafts.items():
            self.assertEqual(draft["locale"], locale)
            self.assertGreater(len(draft["body"]), 2000)
            self.assertEqual(len(draft["image"]["steps"]), 4)

    def test_all_nine_authored_images_fit_existing_svg_layout(self):
        from generate_image_assets import workflow_svg
        drafts = preview.validate_drafts(ROOT / "preview/aligna")
        for locale, draft in drafts.items():
            with self.subTest(locale=locale):
                image = draft["image"]
                editorial = {
                    "subtitle": image["subtitle"], "message": image["message"],
                    "description": draft["short_answer"], "steps": image["steps"],
                }
                svg = workflow_svg(image["title"], draft["primary_keyword"], locale, editorial)
                self.assertIn('<svg ', svg)

    def test_original_overlong_headings_still_fail_existing_layout_gate(self):
        from generate_image_assets import ImageAssetError, workflow_svg
        drafts = preview.validate_drafts(ROOT / "preview/aligna")
        for locale, index, heading in (("pt-BR", 0, "1. Identidade"),
                                       ("de", 2, "3. Reihenfolge")):
            with self.subTest(locale=locale):
                draft = drafts[locale]
                image = copy.deepcopy(draft["image"])
                image["steps"][index][0] = heading
                editorial = {
                    "subtitle": image["subtitle"], "message": image["message"],
                    "description": draft["short_answer"], "steps": image["steps"],
                }
                with self.assertRaisesRegex(ImageAssetError, "card heading exceeds"):
                    workflow_svg(image["title"], draft["primary_keyword"], locale, editorial)

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
