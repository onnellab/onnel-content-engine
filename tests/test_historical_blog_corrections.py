import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
import os
import subprocess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from historical_blog_corrections import prepare_historical_corrections, CorrectionError, blob_sha
import publishing
import publication_transaction as transaction


class HistoricalCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = Path(self.temp.name) / "engine"
        self.site = Path(self.temp.name) / "site"
        self.engine.mkdir(); self.site.mkdir()
        self.config = json.loads((ROOT / "data/historical_blog_corrections.json").read_text())
        self.entry = self.config["corrections"][0]
        self.proposal = json.loads((ROOT / self.entry["proposal_path"]).read_text())
        self.before = {}
        for row in self.proposal["corrections"]:
            corrected = (ROOT / f'preview/tagweaver-multidisc-ios-save/{row["locale"]}.md').read_bytes()
            original = corrected.replace(row["replacement_text"].encode(), row["old_sentence"].encode())
            self.assertEqual(blob_sha(original), row["source_blob_sha"])
            root = self.site if row["repository"].endswith("github.io") else self.engine
            target = root / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original if root == self.site else corrected)
            self.before[target] = target.read_bytes()
        self.save_config()

    def save_config(self):
        path = self.engine / "data/historical_blog_corrections.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(self.config))

    def prepare(self):
        return prepare_historical_corrections(self.engine, self.site, ROOT)

    def assert_site_unchanged(self):
        for p, data in self.before.items():
            if p.is_relative_to(self.site):
                self.assertEqual(p.read_bytes(), data)

    def export(self, dry_run=False, articles=()):
        with patch.object(publishing, "ROOT", ROOT), \
             patch.object(publishing, "validate_homepage_repository"), \
             patch.object(publishing, "prepare_site_icon_updates", return_value={}), \
             patch.object(publishing, "load_publishable_articles", return_value=articles), \
             patch.object(publishing, "homepage_approved_blog_mark", return_value=None):
            return publishing.export_markdown_to_homepage(self.engine / "data/topics.csv", self.site, dry_run)

    def test_restart_after_engine_commit_before_site_commit(self):
        updates, observed = self.prepare()
        self.assertEqual(len(updates), 9)
        self.assertEqual(len(observed), 9)
        self.assert_site_unchanged()
        self.assertEqual(len(self.export()), 9)
        for path, data in updates.items():
            self.assertEqual(path.read_bytes(), data)

    def test_repeat_is_idempotent(self):
        self.export()
        first = {p: p.read_bytes() for p in self.site.glob("src/content/blog/*/*.md")}
        result = self.export()
        self.assertTrue(all(r.action == "unchanged" for r in result))
        self.assertEqual(first, {p: p.read_bytes() for p in first})

    def test_dry_run_no_writes(self):
        self.assertEqual(len(self.export(True)), 9)
        self.assert_site_unchanged()

    def test_stale_one_locale_prevents_all_writes(self):
        target = next(self.site.glob("src/content/blog/es/*.md"))
        target.write_bytes(target.read_bytes() + b"concurrent content")
        with patch.object(publishing, "prepare_site_icon_updates") as icons:
            with self.assertRaises(publishing.PublishingError): self.export()
        self.assertFalse(icons.called)
        for p, before in self.before.items():
            if p.is_relative_to(self.site) and p != target: self.assertEqual(p.read_bytes(), before)

    def test_changed_engine_source_blocks_site(self):
        target = next(self.engine.glob("generated/markdown/en/music/*.md"))
        target.write_bytes(b"stale")
        with self.assertRaises(CorrectionError): self.prepare()
        self.assert_site_unchanged()

    def test_unrelated_concurrent_file_preserved(self):
        unrelated = self.site / "unrelated-worker.txt"
        unrelated.write_text("new worker changes")
        self.export()
        self.assertEqual(unrelated.read_text(), "new worker changes")

    def test_changed_target_between_preflight_and_commit(self):
        updates, expected = self.prepare()
        target = next(iter(expected))
        target.write_bytes(b"concurrent edit")
        with self.assertRaises(publishing.PublishingError):
            publishing.commit_homepage_updates(self.site, updates, expected)
        self.assertEqual(target.read_bytes(), b"concurrent edit")
        for p in expected:
            if p != target: self.assertEqual(p.read_bytes(), expected[p])

    def test_atomic_replace_failure_rolls_back_nine(self):
        updates, expected = self.prepare()
        replace = transaction.os.replace
        count = 0
        def fail_third_destination(source, destination):
            nonlocal count
            if Path(destination) in updates:
                count += 1
                if count == 3: raise OSError("injected replacement failure")
            return replace(source, destination)
        with patch.object(transaction.os, "replace", side_effect=fail_third_destination):
            with self.assertRaises(OSError): publishing.commit_homepage_updates(self.site, updates, expected)
        self.assert_site_unchanged()
        self.assertFalse((self.site / "data/.publication-transaction").exists())

    def test_swapped_parent_symlink_after_preflight(self):
        updates, expected = self.prepare()
        parent = self.site / "src/content/blog/es"
        alternate = self.site / "alternate"
        parent.rename(alternate)
        parent.symlink_to(alternate, target_is_directory=True)
        with self.assertRaises(publishing.PublishingError):
            publishing.commit_homepage_updates(self.site, updates, expected)
        for path, observed in expected.items():
            self.assertEqual(path.read_bytes(), observed)

    def test_bad_manuscript_hash(self):
        self.entry["manuscript_blob_shas"]["es"] = "0" * 40
        self.save_config()
        with self.assertRaises(CorrectionError): self.prepare()

    def test_missing_locale_hash(self):
        del self.entry["manuscript_blob_shas"]["es"]
        self.save_config()
        with self.assertRaises(publishing.PublishingError): self.export()
        self.assert_site_unchanged()

    def test_unsafe_manuscript_path(self):
        self.entry["manuscript_directory"] = "../outside"
        self.save_config()
        with self.assertRaises(CorrectionError): self.prepare()

    def test_symlink_destination(self):
        target = next(self.site.glob("src/content/blog/es/*.md"))
        outside = Path(self.temp.name) / "outside"
        outside.write_bytes(target.read_bytes())
        target.unlink(); target.symlink_to(outside)
        with self.assertRaises(CorrectionError): self.prepare()

    def test_unapproved_entry(self):
        self.entry["state"] = "draft"
        self.save_config()
        with self.assertRaises(CorrectionError): self.prepare()

    def test_duplicate_destination(self):
        self.config["corrections"].append(copy.deepcopy(self.entry))
        self.save_config()
        with self.assertRaises(CorrectionError): self.prepare()

    def test_no_registry_unchanged_legacy_behavior(self):
        (self.engine / "data/historical_blog_corrections.json").unlink()
        self.assertEqual(self.prepare(), ({}, {}))

    def normal_articles(self):
        return [SimpleNamespace(topic={"id": "historical-" + locale, "primary_language": locale,
                    "slug": self.entry["slug"], "category": "music"},
                    markdown_path=self.engine / f'generated/markdown/{locale}/music/{self.entry["slug"]}.md',
                    social_image_path=f'/blog-assets/{locale}/{self.entry["slug"]}/social-card.png') for locale in ("en", "ko")]

    def test_normal_export_two_canonical_plus_seven_site_only_relative_path(self):
        articles = self.normal_articles()
        asset = self.engine / "stub.svg"; asset.write_bytes(b"fixture")
        cwd = Path.cwd()
        original_site = self.site
        try:
            os.chdir(self.temp.name)
            self.site = Path("site")
            with patch.object(publishing, "write_social_card", return_value=asset), \
                 patch.object(publishing, "social_card_source_for", return_value=asset), \
                 patch.object(publishing, "prepare_blog_asset_updates", return_value={}), \
                 patch.object(publishing, "branded_export_bytes", side_effect=lambda data, *_: data):
                exports = self.export(articles=articles)
        finally:
            os.chdir(cwd); self.site = original_site
        self.assertEqual(len(exports), 9)
        self.assertEqual(len({e.destination.resolve() for e in exports}), 9)
        for target, content in self.prepare()[0].items(): self.assertEqual(target.read_bytes(), content)

    def test_conflicting_normal_export_has_no_partial_writes(self):
        articles = self.normal_articles()
        bad = self.engine / "conflict.md"; bad.write_text("unapproved bytes")
        articles[0].markdown_path = bad
        asset = self.engine / "stub.svg"; asset.write_bytes(b"fixture")
        with patch.object(publishing, "write_social_card", return_value=asset), \
             patch.object(publishing, "social_card_source_for", return_value=asset), \
             patch.object(publishing, "prepare_blog_asset_updates", return_value={}), \
             patch.object(publishing, "branded_export_bytes", side_effect=lambda data, *_: data):
            with self.assertRaises(publishing.PublishingError): self.export(articles=articles)
        self.assert_site_unchanged()

    def deploy(self, dry_run, fail_build=False, staged_extra=False):
        (self.site / "package.json").write_text(json.dumps({"scripts": {"check:i18n-quality": "check", "build": "build"}}))
        calls = []
        staged = [str(p.relative_to(self.site)) for p in self.before if p.is_relative_to(self.site)]
        if staged_extra: staged.append("public/privacy.html")
        def command(args, _):
            calls.append(args)
            if args == ["npm", "run", "build"] and fail_build: raise RuntimeError("injected build failure")
        with patch.object(publishing, "ROOT", ROOT), \
             patch.object(publishing, "validate_homepage_repository"), \
             patch.object(publishing, "run_homepage_command", side_effect=command), \
             patch.object(publishing.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, ("\0".join(staged) + "\0").encode())), \
             patch.object(publishing, "export_markdown_to_homepage", side_effect=AssertionError("normal export forbidden")), \
             patch.object(publishing, "export_privacy_pages_to_homepage", side_effect=AssertionError("privacy forbidden")):
            result = publishing.deploy_github_pages(topics_path=self.engine / "data/topics.csv",
                homepage_repo=self.site, dry_run=dry_run, historical_corrections_only=True)
        return calls, result

    def test_correction_dryrun_builds_restores_and_cannot_push(self):
        calls, result = self.deploy(True)
        self.assertEqual(len(result), 9)
        self.assert_site_unchanged()
        self.assertEqual(calls, [["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"],
            ["npm", "run", "check:i18n-quality"], ["npm", "run", "build"]])

    def test_correction_build_failure_restores(self):
        with self.assertRaises(RuntimeError): self.deploy(False, fail_build=True)
        self.assert_site_unchanged()

    def test_correction_real_add_exact_nine_paths(self):
        calls, _ = self.deploy(False)
        add = next(c for c in calls if c[:2] == ["git", "add"])
        self.assertEqual(len(add[3:]), 9)
        self.assertTrue(all(p.startswith("src/content/blog/") and p.endswith(self.entry["slug"] + ".md") for p in add[3:]))
        self.assertEqual(calls[-1], ["git", "push", "origin", "main"])
        self.assertEqual(sum(c[:2] == ["git", "pull"] for c in calls), 1)

    def test_unexpected_staged_path_aborts_commit(self):
        with self.assertRaises(publishing.PublishingError): self.deploy(False, staged_extra=True)


if __name__ == "__main__": unittest.main()
