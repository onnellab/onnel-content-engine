import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).parents[1] / 'scripts/check_artwork_read_access.py'
spec = importlib.util.spec_from_file_location('access_probe', FILE)
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)

class ReadAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'apps.csv'
        self.config.write_text('repository\nonnellab/app\nonnellab/app\n')
        self.calls = []

    def fetch(self, path, token):
        self.calls.append((path, token))
        if '/git/trees/' in path:
            return {'sha': 'a' * 40, 'tree': []}
        return {'full_name': path, 'private': path not in {'onnellab/onnel-content-engine', 'onnellab/onnellab.github.io'}, 'default_branch': 'main'}

    def test_deduplicated_exact_repo_reads_and_credential_separation(self):
        result = probe.check(self.config, 'release', 'pages', self.fetch)
        self.assertEqual(len(result), 4)
        self.assertEqual(len(self.calls), 8)
        self.assertTrue(all(token == ('pages' if path.startswith(('onnellab/onnellab.github.io', 'onnellab/onnel-content-engine')) else 'release') for path, token in self.calls))

    def test_missing_credentials_or_invalid_repo_block_before_network(self):
        with self.assertRaises(ValueError): probe.check(self.config, '', 'pages', self.fetch)
        self.config.write_text('repository\nother/app\n')
        with self.assertRaises(ValueError): probe.check(self.config, 'release', 'pages', self.fetch)
        self.assertEqual(self.calls, [])

    def test_private_publisher_blocks_and_error_body_is_not_logged(self):
        def private(path, token):
            value = self.fetch(path, token)
            value['private'] = True
            return value
        with self.assertRaisesRegex(ValueError, 'cannot verify'): probe.check(self.config, 'release', 'pages', private)
        def denied(path, token): raise OSError('secret-token-value')
        with self.assertRaises(ValueError) as error: probe.check(self.config, 'release', 'pages', denied)
        self.assertNotIn('secret-token-value', str(error.exception))

    def test_redirects_do_not_forward_credentials(self):
        with self.assertRaisesRegex(ValueError, 'redirect'):
            probe.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')

    def test_existing_status_dry_run_reuses_binding_and_skips_mutation(self):
        text = (FILE.parents[1] / '.github/workflows/sync-app-operational-status.yml').read_text()
        self.assertIn('artwork_read_only:', text)
        self.assertIn('python3 scripts/check_artwork_read_access.py', text)
        self.assertIn("run-name: ${{ inputs.artwork_read_only && 'Read-only artwork access probe'", text)
        publisher = (FILE.parents[1] / '.github/workflows/publish-ready-app-releases.yml').read_text()
        self.assertIn("github.event.workflow_run.display_title != 'Read-only artwork access probe'", publisher)
        self.assertNotIn('ARTWORK_READ_TOKEN:', text)
        self.assertNotIn('ARTWORK_PAGES_TOKEN:', text)
        self.assertEqual(text.count('if: inputs.artwork_read_only != true'), 11)
        self.assertIn("inputs.artwork_read_only != true && env.DEPLOY_DASHBOARD == 'true'", text)

if __name__ == '__main__': unittest.main()
