"""Fail-closed tests for the dedicated TagWeaver disposable preview adapter."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_research_preview as research
import prepare_tagweaver_preview as preview


def copy_drafts(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for filename in ("manifest.json", *(f"{locale}.json" for locale in preview.LOCALES)):
        (directory / filename).write_bytes((ROOT / preview.PREVIEW_DIRECTORY / filename).read_bytes())


def make_stage(stage):
    for relative in ("data/topics.csv", "data/apps_registry.csv", "topics/topics.csv"):
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    copy_drafts(stage / preview.PREVIEW_DIRECTORY)
    preview.write_json(stage / preview.PREVIEW_DIRECTORY / "idea_seeds.json",
                       [copy.deepcopy(preview.APPROVED_IDEA_SEED)])
    from topic_management import TopicStore
    return TopicStore(stage / "data/topics.csv", apps_path=stage / "data/apps_registry.csv",
                      mirror_path=stage / "topics/topics.csv")


class ReviewedDrafts(unittest.TestCase):
    def test_exact_nine_reviewed_blobs_are_returned_without_changes(self):
        directory = ROOT / preview.PREVIEW_DIRECTORY
        before = {locale: (directory / f"{locale}.json").read_bytes() for locale in preview.LOCALES}
        drafts = preview.validate_drafts(directory)
        self.assertEqual(list(drafts), list(preview.LOCALES))
        for locale, raw in before.items():
            self.assertEqual(drafts[locale], json.loads(raw))
            expected = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw,
                                    usedforsecurity=False).hexdigest()
            self.assertEqual(expected, preview.REVIEWED_BLOBS[locale])
            self.assertEqual((directory / f"{locale}.json").read_bytes(), raw)
        self.assertEqual(research.SLUG, "separate-source-notes-from-conclusions")
        self.assertEqual(research.CATEGORY, "research")

    def test_any_body_metadata_image_or_whitespace_change_is_rejected(self):
        for case in ("body", "title", "image", "whitespace"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                copy_drafts(directory)
                path = directory / "en.json"
                raw = path.read_bytes()
                draft = json.loads(raw)
                if case == "whitespace":
                    path.write_bytes(raw + b"\n")
                else:
                    if case == "image":
                        draft["image"]["title"] += " changed"
                    else:
                        draft[case] += " changed"
                    preview.write_json(path, draft)
                with self.assertRaisesRegex(ValueError, "Reviewed source blob mismatch"):
                    preview.validate_drafts(directory)

    def test_manifest_identity_state_queue_and_blob_inventory_fail_closed(self):
        changes = [
            ("state", "scheduled"), ("category", "research"),
            ("existing_english_topic_id", "TOPIC-0037"), ("related_apps", []),
            ("queue_modified", True), ("counterpart_topic_ids_reserved", True),
            ("publication_receipt", True), ("scheduled_at", "2026-10-24T00:00:00Z"),
            ("locales", list(reversed(preview.LOCALES))), ("verification", {}),
        ]
        for key, value in changes:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                copy_drafts(directory)
                path = directory / "manifest.json"
                manifest = json.loads(path.read_text())
                manifest[key] = value
                preview.write_json(path, manifest)
                with self.assertRaises(ValueError):
                    preview.validate_drafts(directory)

    def test_symlinks_oversize_missing_and_duplicate_json_keys_are_rejected(self):
        for case in ("symlink", "oversize", "missing", "duplicate"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = root / "drafts"
                copy_drafts(directory)
                path = directory / "en.json"
                if case == "symlink":
                    outside = root / "outside.json"
                    outside.write_bytes(path.read_bytes())
                    path.unlink()
                    path.symlink_to(outside)
                elif case == "oversize":
                    path.write_bytes(b"x" * 100_001)
                elif case == "missing":
                    path.unlink()
                else:
                    path = directory / "manifest.json"
                    text = path.read_text()
                    path.write_text(text.replace("{", '{"schema": "duplicate",', 1))
                with self.assertRaises(ValueError):
                    preview.validate_drafts(directory)

    def test_exact_seed_file_matches_the_reviewed_unassigned_idea(self):
        path = ROOT / preview.PREVIEW_DIRECTORY / "idea_seeds.json"
        self.assertEqual(json.loads(path.read_text()), [preview.APPROVED_IDEA_SEED])
        self.assertNotIn("id", preview.APPROVED_IDEA_SEED)
        self.assertEqual(preview.APPROVED_IDEA_SEED["related_apps"], "")
        self.assertEqual(preview.APPROVED_IDEA_SEED["status"], "idea")

    def test_all_authored_image_copy_passes_the_existing_layout_guard(self):
        from generate_image_assets import workflow_svg
        for locale, draft in preview.validate_drafts(ROOT / preview.PREVIEW_DIRECTORY).items():
            with self.subTest(locale=locale):
                image = draft["image"]
                editorial = {"subtitle": image["subtitle"], "message": image["message"],
                             "description": draft["short_answer"], "steps": image["steps"]}
                self.assertIn("<svg ", workflow_svg(image["title"], draft["primary_keyword"], locale, editorial))


class TopicIsolation(unittest.TestCase):
    def test_nine_candidates_and_one_seed_preserve_live_and_unrelated_rows(self):
        live = {path: (ROOT / path).read_bytes() for path in ("data/topics.csv", "topics/topics.csv")}
        drafts = preview.validate_drafts(ROOT / preview.PREVIEW_DIRECTORY)
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            store = make_stage(stage)
            before = store.read()
            _, candidates, seeds = preview.stage_topics(stage, drafts)
            after = store.read()
            by_id = {row["id"]: row for row in after}
            for row in before:
                if row["id"] != preview.TOPIC_ID:
                    self.assertEqual(by_id[row["id"]], row)
            self.assertEqual(len(after), len(before) + 9)
            self.assertEqual(sum(row["status"] == "idea" for row in after),
                             sum(row["status"] == "idea" for row in before))
            self.assertEqual([row["primary_language"] for row in candidates], list(preview.LOCALES))
            self.assertEqual(candidates[0]["id"], preview.TOPIC_ID)
            for row in candidates:
                self.assertEqual((row["category"], row["slug"], row["related_apps"], row["status"]),
                                 ("music", preview.SLUG, "TagWeaver", "draft"))
                self.assertEqual(row["canonical_path"],
                                 f"generated/markdown/{row['primary_language']}/music/{preview.SLUG}.md")
                self.assertFalse(row["scheduled_at"] or row["published_at"] or row["published_url"])
            self.assertEqual(len(seeds), 1)
            self.assertEqual(seeds[0]["slug"], preview.APPROVED_IDEA_SEED["slug"])
            self.assertEqual(seeds[0]["status"], "idea")
            self.assertEqual(seeds[0]["related_apps"], "")
            self.assertEqual((stage / "data/topics.csv").read_bytes(),
                             (stage / "topics/topics.csv").read_bytes())
        for path, raw in live.items():
            self.assertEqual((ROOT / path).read_bytes(), raw)

    def test_reserved_wrong_or_duplicate_candidate_rejected_before_writes(self):
        from topic_management import next_topic_id
        drafts = preview.validate_drafts(ROOT / preview.PREVIEW_DIRECTORY)
        cases = (("status", "approved"), ("category", "research"),
                 ("primary_language", "ko"), ("related_apps", ""), ("duplicate", ""))
        for key, value in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                stage = Path(temporary)
                store = make_stage(stage)
                rows = store.read()
                candidate = next(row for row in rows if row["id"] == preview.TOPIC_ID)
                if key == "duplicate":
                    rows.append(dict(candidate, id=next_topic_id(rows), primary_language="ko"))
                else:
                    candidate[key] = value
                store.write(rows)
                before = (stage / "data/topics.csv").read_bytes()
                with self.assertRaises(ValueError):
                    preview.stage_topics(stage, drafts)
                self.assertEqual((stage / "data/topics.csv").read_bytes(), before)
                self.assertEqual((stage / "topics/topics.csv").read_bytes(), before)

    def test_changed_seed_or_existing_seed_rejected_before_writes(self):
        drafts = preview.validate_drafts(ROOT / preview.PREVIEW_DIRECTORY)
        for case in ("id", "app", "count", "wording", "existing"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                stage = Path(temporary)
                store = make_stage(stage)
                seeds = [copy.deepcopy(preview.APPROVED_IDEA_SEED)]
                if case == "id":
                    seeds[0]["id"] = "TOPIC-9999"
                elif case == "app":
                    seeds[0]["related_apps"] = "TagWeaver"
                elif case == "count":
                    seeds.append(copy.deepcopy(seeds[0]))
                elif case == "wording":
                    seeds[0]["notes"] = "Unreviewed claim"
                else:
                    store.add(copy.deepcopy(seeds[0]))
                preview.write_json(stage / preview.PREVIEW_DIRECTORY / "idea_seeds.json", seeds)
                before = (stage / "data/topics.csv").read_bytes()
                with self.assertRaises(ValueError):
                    preview.stage_topics(stage, drafts)
                self.assertEqual((stage / "data/topics.csv").read_bytes(), before)
                self.assertEqual((stage / "topics/topics.csv").read_bytes(), before)


class ExecutionBoundaries(unittest.TestCase):
    def test_five_native_gates_keep_minimum_eight_and_stop_on_failure(self):
        expected = (("validate_topics.py",), ("validate_foundation.py",),
                    ("evaluate_all_articles.py",), ("check_nine_language_publication.py",),
                    ("check_content_supply.py", "--require-healthy", "--minimum-ideas", "8"))
        self.assertEqual(preview.GATES, expected)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            results = [SimpleNamespace(returncode=0, stdout="passed") for _ in range(4)]
            results.append(SimpleNamespace(returncode=1, stdout="ideas=7, minimum_ideas=8"))
            with patch.object(preview.subprocess, "run", side_effect=results) as run, patch("sys.stderr"):
                with self.assertRaisesRegex(ValueError, "Native gate failed: check_content_supply.py"):
                    preview.run_gates(root, root)
            self.assertEqual(run.call_count, 5)
            for call, gate in zip(run.call_args_list, expected):
                self.assertEqual(call.args[0], [sys.executable, str(root / "scripts" / gate[0]), *gate[1:]])
                self.assertEqual(call.kwargs["timeout"], 180)
            self.assertIn("ideas=7", (root / "05-check_content_supply.py.log").read_text())

    def test_output_collision_and_symlinks_rejected_before_worker(self):
        for case in ("existing", "parent_symlink", "source_symlink"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "source"
                source.mkdir()
                if case == "existing":
                    output = source / "preview-evidence/tagweaver-album-artists"
                    output.mkdir(parents=True)
                    (output / "keep.txt").write_text("unchanged")
                elif case == "parent_symlink":
                    outside = root / "outside"
                    outside.mkdir()
                    (source / "preview-evidence").symlink_to(outside, target_is_directory=True)
                else:
                    alias = root / "alias"
                    alias.symlink_to(source, target_is_directory=True)
                    source = alias
                with patch.object(preview.subprocess, "run") as run:
                    with self.assertRaises(ValueError):
                        preview.prepare(source)
                    run.assert_not_called()
                if case == "existing":
                    self.assertEqual((output / "keep.txt").read_text(), "unchanged")

    def test_worker_rejects_missing_marker_and_live_source_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(preview, "ROOT", root), patch.object(preview, "stage_topics") as stage:
                with self.assertRaisesRegex(ValueError, "marker"):
                    preview.stage_worker()
                preview.write_json(root / preview.MARKER, {
                    "source": str(root), "output": str(root / "preview-evidence/tagweaver-album-artists")})
                with self.assertRaisesRegex(ValueError, "source checkout"):
                    preview.stage_worker()
                stage.assert_not_called()

    def test_prepare_never_emits_manifest_when_source_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            before = {"data/topics.csv": "a", "topics/topics.csv": "a"}
            before.update({f"{preview.PREVIEW_DIRECTORY}/{locale}.json": "0" * 64
                           for locale in preview.LOCALES})
            after = dict(before, **{"data/topics.csv": "b"})
            with patch.object(preview, "validate_drafts"), \
                 patch.object(preview, "source_inventory", side_effect=[before, after]), \
                 patch.object(preview, "copy_source"), \
                 patch.object(preview.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="worker")) as run, \
                 patch.object(preview, "verified_native_manifest") as verify, patch("builtins.print") as emit:
                with self.assertRaisesRegex(ValueError, "Source checkout changed"):
                    preview.prepare(source)
                self.assertEqual(run.call_args.kwargs["timeout"], 600)
                verify.assert_not_called()
                emit.assert_not_called()
            record = json.loads((source / "preview-evidence/tagweaver-album-artists/source-integrity.json").read_text())
            self.assertFalse(record["source_unchanged"])
            self.assertFalse(record["publication_dates_assigned"])

    def test_no_publication_paid_execution_or_global_patch_entrypoint(self):
        source = (ROOT / "scripts/prepare_tagweaver_preview.py").read_text()
        for forbidden in ("import publishing", "from publishing", "workflow_dispatch", "git push",
                          "publish_due_articles(", "schedule_articles(", "codex exec", "openai.",
                          "api_key", "research.SLUG =", "research.CATEGORY ="):
            self.assertNotIn(forbidden, source)


class NativeProvenance(unittest.TestCase):
    def fixture(self, root):
        stage, output = root / "stage", root / "output"
        stage.mkdir()
        output.mkdir()
        copy_drafts(stage / preview.PREVIEW_DIRECTORY)
        candidates = []
        for locale in preview.LOCALES:
            candidates.append({
                "id": f"fixture-{locale}", "primary_language": locale, "category": "music",
                "slug": preview.SLUG, "related_apps": "TagWeaver", "status": "review",
                "canonical_path": f"generated/markdown/{locale}/music/{preview.SLUG}.md",
                "scheduled_at": "", "published_at": "", "published_url": "",
            })
        for relative in preview.native_output_paths():
            if "/social-card." in relative:
                continue
            path = stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("unit-test fixture only: " + relative).encode())
        return stage, output, candidates

    def collect_fixture(self, stage, output, candidates):
        with patch("check_nine_language_publication.check_reviewed_candidates") as review, \
             patch("prepare_blog_preview.validate_bundle") as bundle:
            preview.collect(stage, output, candidates, [])
            review.assert_called_once_with(stage / "data/topics.csv")
            bundle.assert_called_once_with(output / "candidate.json")

    def test_exact_72_native_files_and_27_bundle_items_have_rechecked_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage, output, candidates = self.fixture(Path(temporary))
            self.collect_fixture(stage, output, candidates)
            manifest = preview.verified_native_manifest(output)
            self.assertEqual(len(manifest["files"]), 72)
            self.assertEqual({entry["path"] for entry in manifest["files"]}, set(preview.native_output_paths()))
            for entry in manifest["files"]:
                raw = (output / "artifacts" / entry["path"]).read_bytes()
                self.assertEqual(entry, preview.native_entry(entry["path"], raw))
            bundle = json.loads((output / "candidate.json").read_text())
            self.assertEqual(len(bundle["files"]), 27)
            self.assertEqual(bundle["state"], "UNSCHEDULED_PREVIEW_ONLY")
            rows = json.loads((output / "candidate-topic-rows.json").read_text())
            self.assertIs(rows["ids_reserved"], False)
            self.assertIs(rows["live_queue_modified"], False)
            with self.assertRaises(ValueError):
                self.collect_fixture(stage, output, candidates)

    def test_actual_review_failure_prevents_any_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage, output, candidates = self.fixture(Path(temporary))
            with patch("check_nine_language_publication.check_reviewed_candidates",
                       side_effect=ValueError("stale native fingerprint")):
                with self.assertRaisesRegex(ValueError, "stale native fingerprint"):
                    preview.collect(stage, output, candidates, [])
            self.assertEqual(list(output.iterdir()), [])

    def test_late_missing_source_fails_before_any_alias_or_evidence_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage, output, candidates = self.fixture(Path(temporary))
            late = stage / f"generated/reviews/es/music/{preview.SLUG}/review.json"
            late.unlink()
            with patch("check_nine_language_publication.check_reviewed_candidates"):
                with self.assertRaises(ValueError):
                    preview.collect(stage, output, candidates, [])
            self.assertEqual(list(output.iterdir()), [])
            self.assertFalse((stage / f"generated/assets/blog/en/{preview.SLUG}/social-card.svg").exists())

    def test_tampered_extra_missing_or_symlink_artifacts_fail_closed(self):
        for case in ("tampered", "extra", "missing", "symlink"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                stage, output, candidates = self.fixture(root)
                self.collect_fixture(stage, output, candidates)
                path = output / "artifacts" / preview.native_output_paths()[0]
                if case == "tampered":
                    path.write_bytes(path.read_bytes() + b"changed")
                elif case == "extra":
                    (output / "artifacts/extra.txt").write_text("extra")
                elif case == "missing":
                    path.unlink()
                else:
                    outside = root / "outside.md"
                    outside.write_bytes(path.read_bytes())
                    path.unlink()
                    path.symlink_to(outside)
                with self.assertRaises(ValueError):
                    preview.verified_native_manifest(output)

    def test_native_manifest_wrong_identity_duplicate_path_and_unbounded_size_fail(self):
        manifest = {"schema": 1, "slug": preview.SLUG, "locales": list(preview.LOCALES),
                    "files": [preview.native_entry(path, b"fixture") for path in preview.native_output_paths()]}
        self.assertEqual(preview.validate_native_manifest(manifest), manifest)
        for case in ("identity", "duplicate", "size", "hash"):
            broken = copy.deepcopy(manifest)
            if case == "identity":
                broken["slug"] = research.SLUG
            elif case == "duplicate":
                broken["files"][1] = copy.deepcopy(broken["files"][0])
            elif case == "size":
                broken["files"][0]["byte_length"] = preview.MAX_NATIVE_BYTES + 1
            else:
                broken["files"][0]["sha256"] = "z" * 64
            with self.subTest(case=case), self.assertRaises(ValueError):
                preview.validate_native_manifest(broken)


if __name__ == "__main__":
    unittest.main()
