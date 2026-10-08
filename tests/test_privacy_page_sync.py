from pathlib import Path
import sys
import tempfile
import subprocess
import shutil
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sync_app_privacy_pages import PrivacySyncError, assert_no_canonical_shadows, sync_privacy_pages, write_staging_manifest, stage_synced_paths


class PrivacyPageSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'generated'
        self.home = self.root / 'homepage'
        self.source.mkdir(); self.home.mkdir()
        self.contents = {}
        for language, suffix in [('en', ''), ('ko', 'ko/')]:
            body = f'<html lang="{language}">Original official policy – 2026-07-30</html>\n'.encode()
            for route in [f'privacy/segra/{suffix}index.html', f'apps/segra/privacy/{suffix}index.html', f'segra/privacy/{suffix}index.html']:
                path = self.source / route; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
                self.contents[route] = body

    def tearDown(self):
        self.tmp.cleanup()

    def own(self):
        for language in ['en', 'ko']:
            path = self.home / f'src/content/privacy-policies/{language}/segra.json'
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text('{}\n')
        for route, body in self.contents.items():
            if not route.startswith('privacy/'):
                target = self.home / 'public' / route
                target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(body)

    def test_owned_canonical_is_skipped_and_four_aliases_keep_exact_bytes(self):
        self.own()
        result = sync_privacy_pages(self.source, self.home)
        self.assertEqual(sum(x.action == 'skip-astro-owned' for x in result), 2)
        for route, content in self.contents.items():
            target = self.home / 'public' / route
            if route.startswith('privacy/'):
                self.assertFalse(target.exists())
            else:
                self.assertEqual(target.read_bytes(), content)
        self.assertEqual(sum(x.action == 'preserve-homepage-owned-alias' for x in sync_privacy_pages(self.source, self.home)), 4)
        assert_no_canonical_shadows(self.home)

    def test_legacy_owner_keeps_all_six_generated_paths(self):
        result = sync_privacy_pages(self.source, self.home)
        self.assertEqual(len(result), 6)
        for route, content in self.contents.items():
            self.assertEqual((self.home / 'public' / route).read_bytes(), content)

    def test_dry_run_does_not_create_public_files(self):
        self.own()
        self.assertEqual(len(sync_privacy_pages(self.source, self.home, dry_run=True)), 6)
        self.assertFalse((self.home / 'public/privacy').exists())

    def test_existing_collision_is_rejected_without_deleting_it_or_copying_aliases(self):
        self.own()
        collision = self.home / 'public/privacy/segra/index.html'
        collision.parent.mkdir(parents=True); collision.write_bytes(b'preserve')
        with self.assertRaises(PrivacySyncError):
            sync_privacy_pages(self.source, self.home)
        self.assertEqual(collision.read_bytes(), b'preserve')
        self.assertEqual((self.home / 'public/apps/segra/privacy/index.html').read_bytes(), self.contents['apps/segra/privacy/index.html'])

    def test_partial_migration_fails_before_any_copy(self):
        self.own()
        (self.home / 'src/content/privacy-policies/ko/segra.json').unlink()
        with self.assertRaises(PrivacySyncError):
            sync_privacy_pages(self.source, self.home)
        self.assertFalse((self.home / 'public/privacy').exists())

    def test_rebase_ownership_check_rejects_new_canonical_shadow(self):
        sync_privacy_pages(self.source, self.home)
        self.own()
        with self.assertRaises(PrivacySyncError):
            assert_no_canonical_shadows(self.home)

    def test_owned_alias_branding_is_preserved_even_if_legacy_generator_differs(self):
        self.own()
        alias = self.home / 'public/apps/segra/privacy/index.html'
        alias.write_bytes(b'<html>Homepage-owned branding and original policy</html>')
        sync_privacy_pages(self.source, self.home)
        self.assertEqual(alias.read_bytes(), b'<html>Homepage-owned branding and original policy</html>')

    def test_missing_owned_alias_fails_before_writes(self):
        self.own()
        (self.home / 'public/segra/privacy/index.html').unlink()
        with self.assertRaises(PrivacySyncError):
            sync_privacy_pages(self.source, self.home)
        self.assertFalse((self.home / 'public/privacy').exists())

    @unittest.skipUnless(shutil.which('git'), 'git is required for shell staging integration')
    def test_all_owned_staging_handles_absent_public_privacy_directory(self):
        self.own()
        sync_privacy_pages(self.source, self.home)
        self.assertFalse((self.home / 'public/privacy').exists())
        subprocess.run(['git', 'init', '-q', str(self.home)], check=True, capture_output=True)
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/publish-app-privacy-policies.yml').read_text()
        manifest = self.root / 'staging.json'
        write_staging_manifest(manifest, self.home, sync_privacy_pages(self.source, self.home))
        self.assertEqual(stage_synced_paths(manifest, self.home), [])
        staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=self.home, check=True, capture_output=True, text=True).stdout.splitlines()
        self.assertEqual(staged, [])

    def test_explicit_owner_list_protects_non_json_app(self):
        registry = self.home / 'src/lib/privacy-policy-documents.ts'
        registry.parent.mkdir(parents=True); registry.write_text("export const allPrivacyAppSlugs = ['papira', 'lunary'] as const;\n")
        shadow = self.home / 'public/privacy/papira/index.html'
        shadow.parent.mkdir(parents=True); shadow.write_text('preserve')
        with self.assertRaises(PrivacySyncError):
            assert_no_canonical_shadows(self.home)

    @unittest.skipUnless(shutil.which('git'), 'git is required for shell staging integration')
    def test_manifest_stages_only_changed_policy_files(self):
        plan = sync_privacy_pages(self.source, self.home)
        unrelated = self.home / 'public/other.txt'; unrelated.write_text('keep untracked')
        subprocess.run(['git', 'init', '-q', str(self.home)], check=True, capture_output=True)
        manifest = self.root / 'staging.json'; write_staging_manifest(manifest, self.home, plan)
        staged = stage_synced_paths(manifest, self.home)
        self.assertEqual(set(staged), {f'public/{p}' for p in self.contents})
        actual = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=self.home, check=True, capture_output=True, text=True).stdout.splitlines()
        self.assertEqual(set(actual), set(staged))
        self.assertNotIn('public/other.txt', actual)

    def test_workflow_uses_guarded_sync_and_rechecks_after_rebase(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/publish-app-privacy-policies.yml').read_text()
        self.assertNotIn('cp -R', workflow)
        self.assertIn('python3 scripts/sync_app_privacy_pages.py', workflow)
        self.assertLess(workflow.index('git pull --rebase origin main'), workflow.index('--check-ownership'))
        self.assertLess(workflow.index('--check-ownership'), workflow.index('git push origin main'))

    def test_escaping_destination_symlink_is_rejected(self):
        outside = self.root / 'outside'; outside.mkdir()
        (self.home / 'public').mkdir()
        (self.home / 'public/apps').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(PrivacySyncError):
            sync_privacy_pages(self.source, self.home)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
