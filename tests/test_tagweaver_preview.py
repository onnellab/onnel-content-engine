"""Fail-closed tests for the dedicated TagWeaver disposable preview adapter."""
import copy
import hashlib
import io
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
            root = Path(temporary).resolve()
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


class ReviewedTagWeaverSectionHeadings(unittest.TestCase):
    EXPECTED = {
        "en": ("Recommended Workflow", "Where TagWeaver Fits", "Conclusion"),
        "ko": ("권장 작업 순서", "TagWeaver를 활용하는 단계", "결론"),
        "ja": ("推奨する作業手順", "TagWeaverを使う場面", "まとめ"),
        "zh-Hans": ("建议操作流程", "TagWeaver 适合在哪个环节使用", "总结"),
        "zh-Hant": ("建議操作流程", "TagWeaver 適合在哪個階段使用", "結語"),
        "pt-BR": ("Fluxo recomendado", "Onde o TagWeaver se encaixa", "Conclusão"),
        "de": ("Empfohlener Ablauf", "Wo TagWeaver hilft", "Fazit"),
        "fr": ("Méthode recommandée", "Le rôle de TagWeaver", "Conclusion"),
        "es": ("Flujo recomendado", "Dónde encaja TagWeaver", "Conclusión"),
    }

    def drafts(self):
        return {
            locale: json.loads((ROOT / preview.PREVIEW_DIRECTORY / f"{locale}.json").read_text())
            for locale in preview.LOCALES
        }

    def test_all_nine_exact_headings_are_shared_with_native_quality_checks(self):
        from article_localization import (
            TAGWEAVER_REVIEWED_SECTION_HEADINGS, TAGWEAVER_REVIEWED_SECTION_KEYS,
            LOCALIZED_SECTIONS, localized_section_aliases, tagweaver_section_aliases,
        )
        from evaluate_article import (
            SECTION_ALIASES, _h2_heading_positions, _find_section_position,
            find_product_section, has_required_sections, sections,
        )
        self.assertEqual(TAGWEAVER_REVIEWED_SECTION_HEADINGS, self.EXPECTED)
        self.assertEqual(set(self.EXPECTED), set(preview.LOCALES))
        self.assertEqual(TAGWEAVER_REVIEWED_SECTION_KEYS,
                         ("recommended_workflow", "onnellab_application", "conclusion"))
        self.assertNotIn("en", LOCALIZED_SECTIONS)
        self.assertNotIn("ko", LOCALIZED_SECTIONS)
        for locale, draft in self.drafts().items():
            with self.subTest(locale=locale):
                aliases = tagweaver_section_aliases(locale)
                self.assertEqual(aliases, {
                    key: {heading.lower()} for key, heading in zip(
                        TAGWEAVER_REVIEWED_SECTION_KEYS, self.EXPECTED[locale])
                })
                preview.require_reviewed_section_headings(draft["body"], locale)
                found = _h2_heading_positions(draft["body"])
                for key, approved in aliases.items():
                    matching = [heading for heading, _ in found if heading in SECTION_ALIASES[key]]
                    self.assertEqual(len(matching), 1)
                    self.assertIn(matching[0], approved)
                    if locale in LOCALIZED_SECTIONS:
                        self.assertTrue(approved <= localized_section_aliases(locale)[key])
                self.assertTrue(has_required_sections(sections(draft["body"])))
                self.assertGreater(find_product_section(draft["body"]),
                                   _find_section_position(draft["body"], "recommended_workflow"))
        # Recognized section order is not a claim that first product mention passes.

    def test_alias_results_are_fresh_and_do_not_change_source_contract(self):
        from article_localization import (
            TAGWEAVER_REVIEWED_SECTION_HEADINGS, localized_section_aliases,
            tagweaver_section_aliases,
        )
        before = copy.deepcopy(TAGWEAVER_REVIEWED_SECTION_HEADINGS)
        first = tagweaver_section_aliases("ko")
        first["recommended_workflow"].add("arbitrary workflow")
        self.assertEqual(tagweaver_section_aliases("ko")["recommended_workflow"], {"권장 작업 순서"})
        localized = localized_section_aliases("ja")
        localized["recommended_workflow"].add("arbitrary workflow")
        self.assertNotIn("arbitrary workflow", localized_section_aliases("ja")["recommended_workflow"])
        self.assertEqual(TAGWEAVER_REVIEWED_SECTION_HEADINGS, before)
        with self.assertRaises(ValueError):
            tagweaver_section_aliases("zh-hans")

    def test_missing_duplicate_substring_or_fenced_only_workflow_is_rejected(self):
        for locale, draft in self.drafts().items():
            marker = "## " + self.EXPECTED[locale][0]
            body = draft["body"]
            altered = {
                "missing": body.replace(marker + "\n", "## Not a workflow\n", 1),
                "duplicate": body + "\n" + marker + "\n\nDuplicate section.\n",
                "substring": body.replace(marker + "\n", marker + " extra\n", 1),
                "fenced_only": body.replace(marker + "\n", "## Not a workflow\n", 1)
                    + "\n" + chr(96) * 3 + "text\n" + marker + "\n" + chr(96) * 3 + "\n",
                "tilde_fenced_only": body.replace(marker + "\n", "## Not a workflow\n", 1)
                    + "\n~~~text\n" + marker + "\n~~~\n",
            }
            for case, changed in altered.items():
                with self.subTest(locale=locale, case=case), self.assertRaisesRegex(
                        ValueError, "Exactly one reviewed recommended_workflow"):
                    preview.require_reviewed_section_headings(changed, locale)

    def test_workflow_from_wrong_locale_is_not_accepted(self):
        for locale, draft in self.drafts().items():
            heading = self.EXPECTED[locale][0]
            other = next(values[0] for key, values in self.EXPECTED.items()
                         if key != locale and values[0] != heading)
            changed = draft["body"].replace("## " + heading + "\n", "## " + other + "\n", 1)
            with self.subTest(locale=locale), self.assertRaisesRegex(
                    ValueError, "Exactly one reviewed recommended_workflow"):
                preview.require_reviewed_section_headings(changed, locale)

    def test_unreviewed_product_heading_cannot_pass_by_app_name_substring(self):
        for locale, draft in self.drafts().items():
            marker = "## " + self.EXPECTED[locale][1] + "\n"
            for replacement in ("## About TagWeaver\n",
                                "## " + self.EXPECTED[locale][1] + " extra\n",
                                "## Where Another App Fits\n"):
                changed = draft["body"].replace(marker, replacement, 1)
                with self.subTest(locale=locale, heading=replacement), self.assertRaisesRegex(
                        ValueError, "Exactly one reviewed onnellab_application"):
                    preview.require_reviewed_section_headings(changed, locale)

    def test_duplicate_or_missing_app_and_conclusion_are_rejected(self):
        for locale, draft in self.drafts().items():
            for index in (1, 2):
                marker = "## " + self.EXPECTED[locale][index]
                for changed in (draft["body"] + "\n" + marker + "\n",
                                draft["body"].replace(marker + "\n", "## Unapproved heading\n", 1)):
                    with self.subTest(locale=locale, section=index), self.assertRaises(ValueError):
                        preview.require_reviewed_section_headings(changed, locale)

    def test_second_recognized_workflow_alias_is_rejected_as_ambiguous(self):
        from article_localization import LOCALIZED_SECTIONS, localized_section_aliases
        for locale, draft in self.drafts().items():
            canonical = (sorted(localized_section_aliases(locale)["recommended_workflow"])[0]
                         if locale in LOCALIZED_SECTIONS else
                         "recommended workflow" if locale == "en" else "권장 워크플로")
            with self.subTest(locale=locale), self.assertRaisesRegex(
                    ValueError, "Exactly one reviewed recommended_workflow"):
                preview.require_reviewed_section_headings(draft["body"] + "\n## " + canonical + "\n", locale)

    def test_fenced_fake_extra_headings_do_not_count_as_real_sections(self):
        for locale, draft in self.drafts().items():
            fake = "\n".join("## " + heading for heading in self.EXPECTED[locale])
            for opening, closing in ((chr(96) * 3 + "text", chr(96) * 3), ("~~~text", "~~~")):
                body = draft["body"] + "\n" + opening + "\n" + fake + "\n" + closing + "\n"
                with self.subTest(locale=locale, fence=opening):
                    preview.require_reviewed_section_headings(body, locale)

    def test_native_image_insertion_preserves_all_reviewed_body_text_and_is_idempotent(self):
        from generate_image_assets import ensure_markdown_references_asset, markdown_image_line
        for locale, draft in self.drafts().items():
            with self.subTest(locale=locale), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "candidate.md"
                original = draft["body"]
                path.write_text(original, encoding="utf-8")
                ensure_markdown_references_asset(path, locale, preview.SLUG, draft["image"]["title"])
                result = path.read_text(encoding="utf-8")
                image = markdown_image_line(locale, preview.SLUG, draft["image"]["title"])
                self.assertEqual(result.count(image), 1)
                self.assertEqual(result.replace("\n\n" + image, "", 1), original)
                ensure_markdown_references_asset(path, locale, preview.SLUG, draft["image"]["title"])
                self.assertEqual(path.read_text(encoding="utf-8"), result)

    def test_native_image_insertion_rejects_duplicate_workflow_without_writing(self):
        from generate_image_assets import ImageAssetError, ensure_markdown_references_asset
        for locale, draft in self.drafts().items():
            with self.subTest(locale=locale), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "candidate.md"
                original = draft["body"] + "\n## " + self.EXPECTED[locale][0] + "\n"
                path.write_text(original, encoding="utf-8")
                with self.assertRaisesRegex(ImageAssetError, "exactly one reviewed workflow"):
                    ensure_markdown_references_asset(path, locale, preview.SLUG, draft["image"]["title"])
                self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_unrelated_slug_keeps_legacy_insertion_and_does_not_gain_korean_tag_alias(self):
        from generate_image_assets import ImageAssetError, ensure_markdown_references_asset, markdown_image_line
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "legacy.md"
            original = "# Fixture\n\n## 권장 워크플로\n\n1. First.\n\n## 권장 워크플로\n\n2. Second.\n\n## 결론\n\nEnd.\n"
            path.write_text(original, encoding="utf-8")
            slug = "unrelated-legacy-fixture"
            ensure_markdown_references_asset(path, "ko", slug, "Fixture")
            result = path.read_text(encoding="utf-8")
            image = markdown_image_line("ko", slug, "Fixture")
            self.assertEqual(result.count(image), 1)
            self.assertEqual(result.replace("\n\n" + image, "", 1), original)
            ensure_markdown_references_asset(path, "ko", slug, "Fixture")
            self.assertEqual(path.read_text(encoding="utf-8"), result)
            for unrelated in ("unrelated-legacy-fixture", preview.SLUG + "-extra"):
                reviewed = self.drafts()["ko"]["body"]
                path.write_text(reviewed, encoding="utf-8")
                with self.assertRaisesRegex(ImageAssetError, "cannot place workflow image"):
                    ensure_markdown_references_asset(path, "ko", unrelated, "Fixture")
                self.assertEqual(path.read_text(encoding="utf-8"), reviewed)

    def test_last_locale_heading_failure_precedes_all_materialization(self):
        drafts = self.drafts()
        locale = preview.LOCALES[-1]
        marker = "## " + self.EXPECTED[locale][0] + "\n"
        drafts[locale]["body"] = drafts[locale]["body"].replace(marker, "## Unapproved heading\n", 1)
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            with patch("generate_image_spec.generate_image_spec") as spec, \
                 patch("generate_image_assets.generate_image_asset") as asset, \
                 patch("generate_internal_links.generate_internal_links") as links:
                with self.assertRaisesRegex(ValueError, "Exactly one reviewed recommended_workflow"):
                    preview.materialize_candidates(stage, drafts, [], None)
                spec.assert_not_called()
                asset.assert_not_called()
                links.assert_not_called()
            self.assertEqual(list(stage.iterdir()), [])

    def test_product_after_education_formula_threshold_and_points_are_unchanged(self):
        import inspect
        import evaluate_article
        source = inspect.getsource(evaluate_article.score_article)
        self.assertIn(
            '"product_after_education",\n'
            '        not related_apps or (workflow_section >= 0 and app_section > workflow_section and first_app >= app_section),\n'
            '        1.0,',
            source,
        )
        self.assertEqual(evaluate_article.DEFAULT_THRESHOLD, 9.0)
        self.assertEqual(evaluate_article.REVIEW_VERSION, 4)



class BoundedReviewFailureDiagnostics(unittest.TestCase):
    EXPECTED_CHECKS = (
        "metadata_complete", "card_title_consistent", "brand_spelling",
        "required_sections", "short_answer_ready", "structured_answer",
        "clear_definitions", "primary_keyword", "external_reference",
        "product_after_education", "publish_ready_image", "social_card_source",
        "image_quality", "internal_links", "readability_depth", "translation_quality",
    )

    def native_report(self):
        # Synthetic schema fixture; never depend on live generated review state.
        return {
            "version": 4, "type": "article_review", "topic_id": "TOPIC-0039",
            "title": "Synthetic review fixture", "input_fingerprint": "0" * 64,
            "score": 8.8, "threshold": 9.0, "passed": False,
            "checks": [
                {"name": name, "passed": name != "product_after_education",
                 "points": 0.0 if name == "product_after_education" else 1.0,
                 "max_points": 1.0, "note": "Synthetic test fixture only."}
                for name in self.EXPECTED_CHECKS
            ],
        }

    def review_path(self, stage, locale):
        return stage / f"generated/reviews/{locale}/{preview.CATEGORY}/{preview.SLUG}/review.json"

    def write_reviews(self, stage):
        for index, locale in enumerate(preview.LOCALES):
            report = self.native_report()
            report["topic_id"] = preview.TOPIC_ID if locale == "en" else f"TOPIC-{100 + index:04d}"
            report["passed"] = False
            report["score"] = 9.26
            report["title"] = "DO_NOT_LOG_TITLE_OR_SECRET"
            report["body"] = "DO_NOT_LOG_ARTICLE_BODY"
            report["checks"][9]["passed"] = False
            for check in report["checks"]:
                check["note"] = "DO_NOT_LOG_REVIEW_NOTE"
            preview.write_json(self.review_path(stage, locale), report)

    def diagnostic_lines(self, captured):
        return [line for line in captured.getvalue().splitlines()
                if line.startswith("TAGWEAVER_REVIEW_DIAGNOSTIC")]

    def assert_unavailable(self, lines):
        self.assertEqual(lines, [
            preview.REVIEW_DIAGNOSTIC_UNAVAILABLE_PREFIX + locale
            for locale in preview.LOCALES
        ])

    def test_native_schema_and_closed_check_whitelist_select_only_safe_fields(self):
        self.assertEqual(preview.REVIEW_DIAGNOSTIC_CHECK_NAMES, self.EXPECTED_CHECKS)
        report = self.native_report()
        before = copy.deepcopy(report)
        self.assertEqual({check["name"] for check in report["checks"]}, set(self.EXPECTED_CHECKS))
        summary = preview.review_diagnostic_summary(report, "en")
        self.assertEqual(set(summary), {"locale", "topic_id", "passed", "score", "checks"})
        self.assertEqual(summary["topic_id"], report["topic_id"])
        self.assertEqual(summary["score"], report["score"])
        self.assertIs(summary["passed"], report["passed"])
        self.assertEqual(summary["checks"], [
            {"name": name, "passed": next(check["passed"] for check in report["checks"]
                                        if check["name"] == name)}
            for name in self.EXPECTED_CHECKS
        ])
        self.assertEqual(report, before)
        for invalid in ("EN", "zh-hans", "en" + chr(10) + "SECRET", "", None):
            with self.subTest(locale=invalid), self.assertRaises(ValueError):
                preview.review_diagnostic_summary(report, invalid)

    def test_all_nine_summaries_are_bounded_and_do_not_log_unused_report_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            self.write_reviews(stage)
            before = {path: path.read_bytes() for path in stage.rglob("review.json")}
            captured = io.StringIO()
            with patch("sys.stderr", captured):
                preview.emit_failed_review_diagnostics(stage)
            lines = self.diagnostic_lines(captured)
            self.assertEqual(len(lines), 9)
            for locale, line in zip(preview.LOCALES, lines):
                self.assertLessEqual(len(line.encode("utf-8")), 2_048)
                summary = json.loads(line.removeprefix(preview.REVIEW_DIAGNOSTIC_PREFIX))
                self.assertEqual(summary["locale"], locale)
                self.assertIs(summary["passed"], False)
                self.assertEqual(summary["score"], 9.26)
                self.assertEqual([check["name"] for check in summary["checks"]], list(self.EXPECTED_CHECKS))
                self.assertEqual([check for check in summary["checks"] if not check["passed"]],
                                 [{"name": "product_after_education", "passed": False}])
            self.assertNotIn("DO_NOT_LOG", captured.getvalue())
            self.assertNotIn("note", captured.getvalue())
            self.assertNotIn("title", captured.getvalue().replace("card_title_consistent", ""))
            self.assertEqual({path: path.read_bytes() for path in stage.rglob("review.json")}, before)

    def test_malformed_schema_emits_only_fixed_unavailable_markers(self):
        reports = [None, [], {}]
        for key, values in (
            ("version", (True, 3, "4")),
            ("type", ("article_review" + chr(10) + "SECRET", None)),
            ("topic_id", ("TOPIC-1", "TOPIC-00000", "TOPIC-0039" + chr(10) + "SECRET", "TOPIC-１２３４", None)),
            ("passed", (0, 1, "false", None)),
            ("score", (True, "9.26", None, float("nan"), float("inf"), -1, 11)),
        ):
            for value in values:
                report = self.native_report()
                report[key] = value
                reports.append(report)
        for case in ("missing", "duplicate", "unknown", "non_dict", "non_bool", "many"):
            report = self.native_report()
            if case == "missing":
                report["checks"].pop()
            elif case == "duplicate":
                report["checks"][1] = copy.deepcopy(report["checks"][0])
            elif case == "unknown":
                report["checks"][0]["name"] = "DO_NOT_LOG_ARBITRARY_NAME"
            elif case == "non_dict":
                report["checks"][0] = None
            elif case == "non_bool":
                report["checks"][0]["passed"] = 1
            else:
                report["checks"] *= 1000
            reports.append(report)
        for index, report in enumerate(reports):
            captured = io.StringIO()
            with self.subTest(case=index), patch.object(preview, "bounded_json", return_value=report), \
                 patch("sys.stderr", captured):
                preview.emit_failed_review_diagnostics(Path("unused-stage"))
            self.assert_unavailable(self.diagnostic_lines(captured))
            self.assertNotIn("SECRET", captured.getvalue())
            self.assertNotIn("DO_NOT_LOG", captured.getvalue())

    def test_bounded_reader_rejects_bad_bytes_missing_files_and_symlinks(self):
        self.assertEqual(preview.MAX_REVIEW_DIAGNOSTIC_BYTES, 65_536)
        self.assertEqual(preview.MAX_REVIEW_DIAGNOSTIC_LINE, 2_048)
        cases = ("oversize", "invalid_utf8", "invalid_json", "duplicate_key",
                 "deep_json", "missing", "file_symlink", "parent_symlink")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                stage = root / "stage"
                stage.mkdir()
                self.write_reviews(stage)
                path = self.review_path(stage, "en")
                if case == "oversize":
                    path.write_bytes(b"x" * 65_537)
                elif case == "invalid_utf8":
                    path.write_bytes(bytes([0xFF]))
                elif case == "invalid_json":
                    path.write_text("DO_NOT_LOG_BROKEN_JSON")
                elif case == "duplicate_key":
                    raw = path.read_text()
                    path.write_text(raw.replace("{", '{"score": 1,', 1))
                elif case == "deep_json":
                    path.write_text("[" * 2000 + "0" + "]" * 2000)
                elif case == "missing":
                    path.unlink()
                elif case == "file_symlink":
                    outside = root / "outside.json"
                    outside.write_bytes(path.read_bytes())
                    path.unlink()
                    path.symlink_to(outside)
                else:
                    parent = path.parent
                    outside = root / "outside"
                    parent.rename(outside)
                    parent.symlink_to(outside, target_is_directory=True)
                captured = io.StringIO()
                with patch.object(preview, "read_native_bytes", wraps=preview.read_native_bytes) as read, \
                     patch("sys.stderr", captured):
                    preview.emit_failed_review_diagnostics(stage)
                lines = self.diagnostic_lines(captured)
                self.assertEqual(len(lines), 9)
                self.assertEqual(lines[0], preview.REVIEW_DIAGNOSTIC_UNAVAILABLE_PREFIX + "en")
                self.assertTrue(all(line.startswith(preview.REVIEW_DIAGNOSTIC_PREFIX) for line in lines[1:]))
                self.assertTrue(all(call.args[1] == 65_536 for call in read.call_args_list))
                self.assertNotIn("DO_NOT_LOG", captured.getvalue())

    def test_line_limit_and_read_error_never_expose_arbitrary_error_text(self):
        for case in ("line_limit", "read_error"):
            captured = io.StringIO()
            kwargs = ({"return_value": self.native_report()} if case == "line_limit" else
                      {"side_effect": OSError("DO_NOT_LOG_ERROR")})
            with self.subTest(case=case), patch.object(preview, "bounded_json", **kwargs), \
                 patch.object(preview, "MAX_REVIEW_DIAGNOSTIC_LINE", 1), patch("sys.stderr", captured):
                preview.emit_failed_review_diagnostics(Path("unused-stage"))
            self.assert_unavailable(self.diagnostic_lines(captured))
            self.assertNotIn("DO_NOT_LOG", captured.getvalue())

    def test_failed_gate_aborts_before_supply_without_topic_or_queue_writes(self):
        from topic_management import TopicStore
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage, output = root / "stage", root / "output"
            stage.mkdir()
            output.mkdir()
            make_stage(stage)
            self.write_reviews(stage)
            before = {path.relative_to(stage): path.read_bytes()
                      for path in stage.rglob("*") if path.is_file()}
            live_before = {relative: (ROOT / relative).read_bytes()
                           for relative in ("data/topics.csv", "topics/topics.csv")}
            results = [SimpleNamespace(returncode=0, stdout="passed") for _ in range(3)]
            results.append(SimpleNamespace(returncode=1, stdout="persisted review did not pass"))
            captured = io.StringIO()
            with patch.object(preview.subprocess, "run", side_effect=results) as run, \
                 patch.object(TopicStore, "write") as write, patch("sys.stderr", captured):
                with self.assertRaisesRegex(ValueError, "^Native gate failed: check_nine_language_publication.py"):
                    preview.run_gates(stage, output)
                write.assert_not_called()
            self.assertEqual(run.call_count, 4)
            self.assertTrue(all(call.kwargs["timeout"] == 180 for call in run.call_args_list))
            self.assertEqual({path.relative_to(stage): path.read_bytes()
                              for path in stage.rglob("*") if path.is_file()}, before)
            for relative, raw in live_before.items():
                self.assertEqual((ROOT / relative).read_bytes(), raw)
            self.assertEqual({path.name for path in output.iterdir()},
                             {f"{index:02d}-{gate[0]}.log" for index, gate in enumerate(preview.GATES[:4], 1)}
                             | {"failed-candidate-reviews"})
            self.assertEqual((output / "04-check_nine_language_publication.py.log").read_text(),
                             "persisted review did not pass")
            self.assertEqual(len(self.diagnostic_lines(captured)), 9)
            for locale in preview.LOCALES:
                self.assertEqual((output / "failed-candidate-reviews" / f"{locale}.json").read_bytes(),
                                 self.review_path(stage, locale).read_bytes())
            self.assertNotIn("DO_NOT_LOG", captured.getvalue())

    def test_artifact_retention_is_bounded_and_never_overwrites_or_follows_symlinks(self):
        for case in ("existing", "file_symlink", "parent_symlink", "oversize", "malformed"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                stage, output = root / "stage", root / "output"
                stage.mkdir()
                output.mkdir()
                self.write_reviews(stage)
                diagnostics = output / "failed-candidate-reviews"
                outside = root / "outside"
                outside.mkdir()
                sentinel = outside / "en.json"
                sentinel.write_bytes(b"existing evidence")
                target = diagnostics / "en.json"
                if case == "parent_symlink":
                    diagnostics.symlink_to(outside, target_is_directory=True)
                elif case in ("existing", "file_symlink"):
                    diagnostics.mkdir()
                    if case == "existing":
                        target.write_bytes(b"existing evidence")
                    else:
                        target.symlink_to(sentinel)
                elif case == "oversize":
                    self.review_path(stage, "en").write_bytes(b"x" * 65_537)
                else:
                    self.review_path(stage, "en").write_bytes(b"DO_NOT_LOG_BROKEN_REPORT")
                captured = io.StringIO()
                with patch.object(preview.subprocess, "run",
                                  return_value=SimpleNamespace(returncode=1, stdout="native failure")), \
                     patch("sys.stderr", captured):
                    with self.assertRaisesRegex(ValueError, "Native gate failed: validate_topics.py"):
                        preview.run_gates(stage, output)
                self.assertEqual(sentinel.read_bytes(), b"existing evidence")
                self.assertEqual({path.name for path in outside.iterdir()}, {"en.json"})
                if case in ("existing", "file_symlink", "parent_symlink"):
                    self.assertEqual(target.read_bytes(), b"existing evidence")
                elif case == "oversize":
                    self.assertFalse(target.exists())
                else:
                    self.assertEqual(target.read_bytes(), b"DO_NOT_LOG_BROKEN_REPORT")
                self.assertEqual(len(self.diagnostic_lines(captured)), 9)
                self.assertNotIn("DO_NOT_LOG", captured.getvalue())

    def test_malformed_reports_do_not_mask_original_gate_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            captured = io.StringIO()
            with patch.object(preview.subprocess, "run",
                              return_value=SimpleNamespace(returncode=7, stdout="native failure")) as run, \
                 patch.object(preview, "bounded_json", side_effect=ValueError("DO_NOT_LOG_ERROR")), \
                 patch("sys.stderr", captured):
                with self.assertRaisesRegex(ValueError, "^Native gate failed: validate_topics.py \\(see retained log\\)$"):
                    preview.run_gates(root, root)
            self.assertEqual(run.call_count, 1)
            self.assert_unavailable(self.diagnostic_lines(captured))
            self.assertNotIn("DO_NOT_LOG", captured.getvalue())

    def test_unexpected_diagnostic_or_logging_exception_cannot_replace_native_failure(self):
        for case in ("diagnostic_error", "stderr_error"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with patch.object(preview.subprocess, "run",
                                  return_value=SimpleNamespace(returncode=2, stdout="native failure")), \
                     patch.object(preview, "emit_failed_review_diagnostics") as diagnostics, \
                     patch("sys.stderr") as stderr:
                    if case == "diagnostic_error":
                        diagnostics.side_effect = RuntimeError("DO_NOT_LOG_DIAGNOSTIC_ERROR")
                    else:
                        stderr.write.side_effect = OSError("DO_NOT_LOG_STDERR_ERROR")
                    with self.assertRaisesRegex(ValueError, "^Native gate failed: validate_topics.py"):
                        preview.run_gates(root, root)

    def test_success_keeps_all_five_gates_and_never_reads_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(preview.subprocess, "run",
                              return_value=SimpleNamespace(returncode=0, stdout="passed")) as run, \
                 patch.object(preview, "emit_failed_review_diagnostics") as diagnostics:
                preview.run_gates(root, root)
            self.assertEqual(run.call_count, 5)
            diagnostics.assert_not_called()
            self.assertEqual(run.call_args_list[-1].args[0][-3:],
                             ["--require-healthy", "--minimum-ideas", "8"])

    def test_worker_never_collects_or_reserves_queue_after_native_failure(self):
        from topic_management import TopicStore
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage, source = root / "stage", root / "source"
            stage.mkdir()
            source.mkdir()
            output = source / "preview-evidence/tagweaver-album-artists"
            output.mkdir(parents=True)
            preview.write_json(stage / preview.MARKER, {"source": str(source), "output": str(output)})
            with patch.object(preview, "ROOT", stage), patch.object(preview, "validate_drafts", return_value={}), \
                 patch.object(preview, "stage_topics", return_value=(None, [], [])), \
                 patch.object(preview, "materialize_candidates", return_value=[]), \
                 patch.object(preview.subprocess, "run",
                              return_value=SimpleNamespace(returncode=1, stdout="native failure")), \
                 patch.object(TopicStore, "write") as write, patch.object(preview, "collect") as collect, \
                 patch("sys.stderr"):
                with self.assertRaisesRegex(ValueError, "Native gate failed"):
                    preview.stage_worker()
                write.assert_not_called()
                collect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
