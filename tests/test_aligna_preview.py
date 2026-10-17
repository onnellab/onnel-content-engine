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


    def test_portuguese_revision_detail_wraps_only_at_word_boundaries(self):
        from generate_image_assets import wrap_display_text
        draft = preview.validate_drafts(ROOT / "preview/aligna")["pt-BR"]
        detail = draft["image"]["steps"][3][1]
        lines = wrap_display_text(detail, 142, 15)
        self.assertEqual(detail, "Indica a revisão")
        self.assertEqual(" ".join(lines), detail)
        self.assertLessEqual(len(lines), 3)
        self.assertNotEqual(" ".join(wrap_display_text("Revisões identificadas", 142, 15)),
                            "Revisões identificadas")

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



class NativeOutputProvenance(unittest.TestCase):
    def make_collection(self, stage, output):
        stage.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        candidates = []
        for locale in preview.LOCALES:
            candidates.append({
                "primary_language": locale,
                "canonical_path": f"generated/markdown/{locale}/{preview.CATEGORY}/{preview.SLUG}.md",
            })
        for relative in preview.native_output_paths():
            if "/social-card." in relative:
                continue
            path = stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = ("Native fixture: " + relative + "\n").encode("utf-8")
            path.write_bytes(b"\x89PNG\r\n" + raw if relative.endswith(".png") else raw)
        return candidates

    def collect_fixture(self, stage, output, candidates):
        with patch("check_nine_language_publication.check_reviewed_candidates") as gate, \
                patch("prepare_blog_preview.validate_bundle") as bundle:
            preview.collect(stage, output, candidates, [])
            gate.assert_called_once_with(stage / "data/topics.csv")
            bundle.assert_called_once_with(output / "candidate.json")

    def test_exact_72_retained_bytes_and_git_blob_hashes(self):
        import hashlib
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            stage, output = Path(d) / "stage", Path(d) / "output"
            candidates = self.make_collection(stage, output)
            captured = io.StringIO()
            with redirect_stdout(captured):
                self.collect_fixture(stage, output, candidates)
            self.assertEqual(captured.getvalue(), "")
            manifest = preview.verified_native_manifest(output)
            self.assertEqual(len(manifest["files"]), 72)
            self.assertEqual({entry["path"] for entry in manifest["files"]},
                             set(preview.native_output_paths()))
            self.assertEqual(len(json.loads((output / "candidate.json").read_text())["files"]), 27)
            self.assertEqual(sum(entry["path"].endswith(".png") for entry in manifest["files"]), 18)
            for entry in manifest["files"]:
                self.assertEqual(set(entry), {"path", "byte_length", "sha256", "git_blob_sha1"})
                raw = (output / "artifacts" / entry["path"]).read_bytes()
                self.assertEqual(entry["byte_length"], len(raw))
                self.assertEqual(entry["sha256"], hashlib.sha256(raw).hexdigest())
                header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
                self.assertEqual(entry["git_blob_sha1"],
                                 hashlib.sha1(header + raw, usedforsecurity=False).hexdigest())
                self.assertEqual(raw, (stage / entry["path"]).read_bytes())
            for locale in preview.LOCALES:
                assets = output / "artifacts/generated/assets/blog" / locale / preview.SLUG
                for suffix in ("svg", "png"):
                    self.assertEqual((assets / f"workflow-diagram.{suffix}").read_bytes(),
                                     (assets / f"social-card.{suffix}").read_bytes())
            self.assertEqual(preview.native_entry("fixture", b"hello\n")["git_blob_sha1"],
                             "ce013625030ba8dba906f756967f9e9ca394464a")
            self.assertLess(len(json.dumps(manifest, separators=(",", ":"))), 50_000)

    def test_candidate_count_duplicates_and_unsafe_paths_fail_before_copy(self):
        with tempfile.TemporaryDirectory() as d:
            stage, output = Path(d) / "stage", Path(d) / "output"
            candidates = self.make_collection(stage, output)
            variants = [candidates[:-1], candidates + [candidates[0]],
                        candidates[:-1] + [candidates[0]]]
            for bad_path in ("../escape", "/absolute", "generated/other.md",
                             "generated/markdown/es/../outside.md"):
                altered = copy.deepcopy(candidates)
                altered[-1]["canonical_path"] = bad_path
                variants.append(altered)
            for rows in variants:
                with self.subTest(rows=rows), \
                        patch("check_nine_language_publication.check_reviewed_candidates"), \
                        patch.object(preview.shutil, "copyfile") as copying:
                    with self.assertRaises(ValueError):
                        preview.collect(stage, output, rows, [])
                    copying.assert_not_called()
            with patch.object(preview, "LOCALES", preview.LOCALES[:-1] + ("en",)):
                with self.assertRaisesRegex(ValueError, "72 distinct"):
                    preview.native_output_paths()

    def test_all_paths_preflight_before_any_social_alias_copy(self):
        cases = ("source_leaf", "source_parent", "alias_leaf", "artifact_leaf",
                 "artifact_parent", "manifest_leaf", "missing_last_source",
                 "extra_artifact", "alias_directory", "alias_dangling")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                stage, output = root / "stage", root / "output"
                candidates = self.make_collection(stage, output)
                outside = root / "outside"
                outside.mkdir()
                protected = outside / "protected"
                protected.write_bytes(b"keep external bytes")
                last_markdown = stage / candidates[-1]["canonical_path"]
                if case == "source_leaf":
                    last_markdown.unlink()
                    last_markdown.symlink_to(protected)
                elif case == "source_parent":
                    parent = stage / f"generated/reviews/es/{preview.CATEGORY}/{preview.SLUG}"
                    parent.rename(parent.with_name(parent.name + "-parked"))
                    parent.symlink_to(outside, target_is_directory=True)
                elif case == "alias_leaf":
                    target = stage / f"generated/assets/blog/es/{preview.SLUG}/social-card.png"
                    target.symlink_to(protected)
                elif case == "artifact_leaf":
                    target = output / "artifacts" / preview.native_output_paths()[-1]
                    target.parent.mkdir(parents=True)
                    target.symlink_to(protected)
                elif case == "artifact_parent":
                    (output / "artifacts").mkdir()
                    (output / "artifacts/generated").symlink_to(outside, target_is_directory=True)
                elif case == "manifest_leaf":
                    (output / preview.NATIVE_MANIFEST).symlink_to(protected)
                elif case == "extra_artifact":
                    (output / "artifacts").mkdir()
                    (output / "artifacts/extra.txt").write_text("preserve existing output")
                elif case == "alias_directory":
                    (stage / f"generated/assets/blog/es/{preview.SLUG}/social-card.png").mkdir()
                elif case == "alias_dangling":
                    target = stage / f"generated/assets/blog/es/{preview.SLUG}/social-card.png"
                    target.symlink_to(outside / "does-not-exist")
                else:
                    last_markdown.unlink()
                with patch("check_nine_language_publication.check_reviewed_candidates"), \
                        patch.object(preview.shutil, "copyfile") as copying:
                    with self.assertRaises(ValueError):
                        preview.collect(stage, output, candidates, [])
                    copying.assert_not_called()
                self.assertEqual(protected.read_bytes(), b"keep external bytes")

    def test_path_helper_rejects_noncanonical_and_symlink_roots(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "root"
            root.mkdir()
            for relative in ("", ".", "../escape", "/absolute", "a/../b",
                             "./a", "a//b", "a\\b"):
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    preview.safe_native_path(root, relative)
            alias = Path(d) / "alias"
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                preview.safe_native_path(alias, "candidate.json")

    def test_manifest_rejects_wrong_count_duplicate_path_and_unbounded_fields(self):
        with tempfile.TemporaryDirectory() as d:
            stage, output = Path(d) / "stage", Path(d) / "output"
            candidates = self.make_collection(stage, output)
            self.collect_fixture(stage, output, candidates)
            manifest = preview.verified_native_manifest(output)
            variants = []
            missing = copy.deepcopy(manifest)
            missing["files"].pop()
            variants.append(missing)
            duplicate = copy.deepcopy(manifest)
            duplicate["files"][-1] = duplicate["files"][0]
            variants.append(duplicate)
            for field, value in (("path", "../outside"), ("path", "/absolute"),
                                 ("byte_length", True), ("byte_length", -1),
                                 ("byte_length", preview.MAX_NATIVE_BYTES + 1),
                                 ("sha256", "z" * 64), ("git_blob_sha1", "0" * 39),
                                 ("content", "must never enter a manifest")):
                altered = copy.deepcopy(manifest)
                altered["files"][0][field] = value
                variants.append(altered)
            for altered in variants:
                with self.subTest(manifest=altered), self.assertRaises(ValueError):
                    preview.validate_native_manifest(altered)


    def test_duplicate_manifest_json_keys_and_bounded_reads_fail(self):
        with tempfile.TemporaryDirectory() as d:
            stage, output = Path(d) / "stage", Path(d) / "output"
            candidates = self.make_collection(stage, output)
            self.collect_fixture(stage, output, candidates)
            manifest = preview.verified_native_manifest(output)
            compact = json.dumps(manifest, separators=(",", ":"))
            first_path = '"path":' + json.dumps(manifest["files"][0]["path"])
            malformed = (
                compact.replace('"schema":1', '"schema":1,"schema":1', 1),
                compact.replace(first_path, first_path + "," + first_path, 1),
            )
            path = output / preview.NATIVE_MANIFEST
            for raw in malformed:
                path.write_text(raw, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    preview.verified_native_manifest(output)
            path.write_bytes(b" " * 100_001)
            with self.assertRaisesRegex(ValueError, "size limit"):
                preview.verified_native_manifest(output)
            path.write_bytes(b"four")
            with self.assertRaisesRegex(ValueError, "size limit"):
                preview.read_native_bytes(path, 3)
            self.assertEqual(preview.read_native_bytes(path, 4), b"four")


    def test_retained_artifact_tampering_extra_files_and_symlinks_fail(self):
        for case in ("changed", "missing", "extra", "symlink"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as d:
                stage, output = Path(d) / "stage", Path(d) / "output"
                candidates = self.make_collection(stage, output)
                self.collect_fixture(stage, output, candidates)
                path = output / "artifacts" / preview.native_output_paths()[0]
                if case == "changed":
                    path.write_bytes(b"changed after collection")
                elif case == "missing":
                    path.unlink()
                elif case == "extra":
                    (output / "artifacts/unexpected.txt").write_text("not a native output")
                else:
                    path.unlink()
                    path.symlink_to(stage / preview.native_output_paths()[0])
                with self.assertRaises(ValueError):
                    preview.verified_native_manifest(output)

    def test_prepare_emits_only_verified_manifest_after_integrity_pass(self):
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            source = Path(d).resolve()
            DisposablePreviewBoundaries.make_source(self, source)
            before = preview.source_inventory(source)
            output = source / "preview-evidence/aligna"

            def worker(*args, **kwargs):
                stage = kwargs["cwd"]
                candidates = self.make_collection(stage, output)
                self.collect_fixture(stage, output, candidates)
                return type("Result", (), {"returncode": 0, "stdout": "worker output retained only"})()

            captured = io.StringIO()
            with patch.object(preview.subprocess, "run", side_effect=worker), redirect_stdout(captured):
                preview.prepare(source)
            lines = captured.getvalue().splitlines()
            records = [line.removeprefix(preview.NATIVE_MANIFEST_PREFIX) for line in lines
                       if line.startswith(preview.NATIVE_MANIFEST_PREFIX)]
            self.assertEqual(len(records), 1)
            self.assertEqual(json.loads(records[0]), preview.verified_native_manifest(output))
            self.assertNotIn("worker output retained only", captured.getvalue())
            self.assertNotIn("Native fixture:", captured.getvalue())
            self.assertEqual((output / "generation.log").read_text(), "worker output retained only")
            self.assertTrue(json.loads((output / "source-integrity.json").read_text())["source_unchanged"])
            self.assertEqual(preview.source_inventory(source), before)

    def test_prepare_does_not_emit_on_integrity_or_artifact_failure(self):
        import io
        from contextlib import redirect_stdout
        for case in ("source_changed", "artifact_changed", "manifest_missing", "worker_failed"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as d:
                source = Path(d).resolve()
                DisposablePreviewBoundaries.make_source(self, source)
                output = source / "preview-evidence/aligna"

                def worker(*args, **kwargs):
                    stage = kwargs["cwd"]
                    candidates = self.make_collection(stage, output)
                    self.collect_fixture(stage, output, candidates)
                    if case == "source_changed":
                        (source / "data/topics.csv").write_text("concurrent mutation")
                    elif case == "artifact_changed":
                        target = output / "artifacts" / preview.native_output_paths()[0]
                        target.write_bytes(b"tampered retained artifact")
                    elif case == "manifest_missing":
                        (output / preview.NATIVE_MANIFEST).unlink()
                    return type("Result", (), {"returncode": 1 if case == "worker_failed" else 0,
                                               "stdout": "worker completed"})()

                captured = io.StringIO()
                with patch.object(preview.subprocess, "run", side_effect=worker), \
                        patch("sys.stderr"), redirect_stdout(captured):
                    with self.assertRaises(ValueError):
                        preview.prepare(source)
                self.assertNotIn(preview.NATIVE_MANIFEST_PREFIX, captured.getvalue())

if __name__ == "__main__":
    unittest.main()

