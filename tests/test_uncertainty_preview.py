"""Closed uncertainty preview and unchanged native publication gates."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_uncertainty_preview as preview
import prepare_blog_preview as overlay
import select_blog_preview as selector
import evaluate_article as evaluator
from generate_image_assets import workflow_svg

class DraftContract(unittest.TestCase):
    def fixture(self, root):
        source = ROOT / preview.DRAFT_DIRECTORY
        target = root / "draft"
        shutil.copytree(source, target)
        return target

    def test_all_nine_reviewed_drafts_and_native_text_contracts(self):
        drafts = preview.validate_drafts(ROOT / preview.DRAFT_DIRECTORY)
        self.assertEqual(set(drafts), set(preview.LOCALES))
        for locale, draft in drafts.items():
            with self.subTest(locale=locale):
                self.assertTrue(evaluator.has_required_sections(evaluator.sections(draft["body"])))
                self.assertTrue(evaluator.has_clear_definitions(draft["body"], locale))
                self.assertIn(draft["primary_keyword"].lower(), draft["body"].lower())
                self.assertTrue(draft["question"].endswith(("?", "？")))
                self.assertEqual(len(draft["image"]["steps"]), 4)
                svg = workflow_svg(draft["image"]["title"], draft["primary_keyword"], locale,
                    dict(subtitle=draft["image"]["subtitle"], message=draft["image"]["message"],
                         description=draft["short_answer"], steps=draft["image"]["steps"]))
                self.assertIn('viewBox="0 0 1200 675"', svg)
                self.assertTrue(evaluator.svg_arrows_avoid_cards(svg))
                self.assertNotIn("...", svg)

    def test_every_markdown_and_svg_pin_rejects_mutation(self):
        for locale in preview.LOCALES:
            for relative in (locale + ".md", "assets/" + locale + "/workflow-diagram.svg"):
                with self.subTest(path=relative), tempfile.TemporaryDirectory() as tmp:
                    root = self.fixture(Path(tmp))
                    p = root / relative
                    p.write_bytes(p.read_bytes() + b"\n")
                    with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
                        preview.validate_drafts(root)

    def test_missing_and_symlink_sources_rejected(self):
        for mode in ("missing", "symlink"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = self.fixture(Path(tmp))
                p = root / "es.md"
                p.unlink()
                if mode == "symlink":
                    p.symlink_to(root / "en.md")
                with self.assertRaises(ValueError):
                    preview.validate_drafts(root)

    def test_manifest_lifecycle_cannot_authorize_queue_or_dates(self):
        for field, value in (("state", "review"), ("queue_modified", True),
                             ("new_topic_ids_allocated", True),
                             ("scheduled_at", "2026-11-05T09:00:00+09:00"),
                             ("published_at", "2026-11-05T09:00:00+09:00")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = self.fixture(Path(tmp))
                path = root / "manifest.json"
                value_map = json.loads(path.read_text())
                value_map[field] = value
                path.write_text(json.dumps(value_map))
                with self.assertRaises(ValueError):
                    preview.validate_drafts(root)

    def test_native_gate_threshold_and_path_set_unchanged(self):
        self.assertEqual(evaluator.DEFAULT_THRESHOLD, 9.0)
        self.assertEqual(preview.GATES, (
            ("validate_topics.py",), ("validate_foundation.py",),
            ("evaluate_all_articles.py",), ("check_nine_language_publication.py",),
            ("check_content_supply.py", "--require-healthy", "--minimum-ideas", "8")))
        paths = preview.native_output_paths()
        self.assertEqual(len(paths), 72)
        self.assertEqual(len(set(paths)), 72)
        self.assertTrue(all(preview.SLUG in p and p.startswith("generated/") for p in paths))
        self.assertFalse(any("privacy" in p or "social/manifest" in p for p in paths))

    def test_unknown_duplicate_traversal_and_bad_hash_outputs_rejected(self):
        manifest = dict(schema=1, slug=preview.SLUG, locales=list(preview.LOCALES),
                        files=[preview.native_entry(p, b"test") for p in preview.native_output_paths()])
        preview.validate_native_manifest(manifest)
        for mode in ("unknown", "duplicate", "traversal", "hash", "missing"):
            candidate = copy.deepcopy(manifest)
            if mode == "unknown": candidate["files"][0]["path"] = "generated/other.md"
            elif mode == "duplicate": candidate["files"][-1] = candidate["files"][0]
            elif mode == "traversal": candidate["files"][0]["path"] = "../outside"
            elif mode == "hash": candidate["files"][0]["sha256"] = "invalid"
            else: candidate["files"].pop()
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                preview.validate_native_manifest(candidate)

    def test_stage_and_output_path_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError): preview.safe_native_path(root, "../outside")
            with self.assertRaises(ValueError): preview.safe_native_path(root, "/absolute")
            with self.assertRaises(ValueError): preview.safe_native_path(root, "a/../b")
            (root / "link").symlink_to(root)
            with self.assertRaises(ValueError): preview.safe_native_path(root, "link/file")

    def test_staging_preserves_unrelated_live_rows_and_allocates_nine_only_in_stage(self):
        original = (ROOT / "data/topics.csv").read_bytes()
        drafts = preview.validate_drafts(ROOT / preview.DRAFT_DIRECTORY)
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            for relative in ("data/topics.csv", "topics/topics.csv", "data/apps_registry.csv",
                             "preview/research-uncertainty/idea_seeds.json"):
                p = stage / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes((ROOT / relative).read_bytes())
            store, candidates, seeds = preview.stage_topics(stage, drafts)
            self.assertEqual(len(candidates), 9)
            self.assertEqual(len(seeds), 1)
            self.assertEqual({r["primary_language"] for r in candidates}, set(preview.LOCALES))
            self.assertTrue(all(r["status"] == "draft" and not r["scheduled_at"] for r in candidates))
            self.assertEqual((stage / "data/topics.csv").read_bytes(), (stage / "topics/topics.csv").read_bytes())
        self.assertEqual((ROOT / "data/topics.csv").read_bytes(), original)

    def test_closed_profile_has_no_product_or_unreviewed_links(self):
        profile = overlay.candidate_profile(preview.SLUG)
        self.assertIsNone(profile["app_path"])
        self.assertEqual(profile["store_urls"], [])
        self.assertEqual(profile["source_urls"], ["https://library.leeds.ac.uk/info/1401/academic-skills/85/note-making"])
        self.assertEqual(profile["faq_count"], 3)
        self.assertTrue(all(v == 3 for v in profile["table_rows"].values()))
        for locale in preview.LOCALES:
            allowed = overlay.allowed_candidate_links(preview.SLUG, locale)
            self.assertEqual(len(allowed), 4)
            self.assertNotIn("https://example.com/", allowed)
        with self.assertRaises(ValueError): overlay.candidate_profile(preview.SLUG + "-extra")

class Selection(unittest.TestCase):
    def idea(self):
        return dict(id="TOPIC-0086", slug=preview.SLUG, category="research",
                    primary_language="en", status="idea", review_required="true",
                    scheduled_at="", published_at="", published_url="")

    def test_only_exact_undated_idea_selects_new_preview(self):
        row = self.idea()
        before = copy.deepcopy(row)
        self.assertEqual(selector.select_candidate([row]), "research-uncertainty")
        self.assertEqual(row, before)
        self.assertIn("UNCERTAINTY_PREVIEW=true", selector.environment_lines("research-uncertainty"))

    def test_invalid_identity_duplicates_or_date_rejected(self):
        for key, value in (("id", "TOPIC-9999"), ("category", "media"),
                           ("primary_language", "ko"), ("status", "draft"),
                           ("scheduled_at", "2026-11-05T09:00:00+09:00")):
            row = self.idea()
            row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                selector.select_candidate([row])
        with self.assertRaises(ValueError): selector.select_candidate([self.idea(), self.idea()])

    def test_registered_mixed_slot_is_rejected(self):
        rows=[]
        for locale, topic_id in selector.REGISTERED_IDS["research-uncertainty"].items():
            rows.append(dict(id=topic_id, slug=preview.SLUG, category="research",
                primary_language=locale, status="scheduled", review_required="true",
                canonical_path=f"generated/markdown/{locale}/research/{preview.SLUG}.md",
                scheduled_at="2026-11-05T09:00:00+09:00", published_at="", published_url=""))
        self.assertEqual(selector.uncertainty_state(rows), "scheduled")
        rows[-1]["scheduled_at"]="2026-11-06T09:00:00+09:00"
        with self.assertRaises(ValueError): selector.uncertainty_state(rows)

    def test_workflow_uses_isolated_existing_preview_and_no_dispatch_publish(self):
        workflow=(ROOT/".github/workflows/blog-preview.yml").read_text()
        self.assertIn("python3 scripts/prepare_uncertainty_preview.py", workflow)
        self.assertIn("--bundle preview-evidence/research-uncertainty/candidate.json", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("publish_due_articles.py", workflow)
        self.assertNotIn("deploy_github_pages.py", workflow)

if __name__ == "__main__":
    unittest.main()
