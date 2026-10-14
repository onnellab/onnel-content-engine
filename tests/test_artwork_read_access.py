import csv
import io
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
from pathlib import Path
import tempfile
import urllib.error
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

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
        self.assertEqual(len(result), 3)
        self.assertEqual(len(self.calls), 6)
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

    def test_each_repository_reports_and_http_status_is_safe(self):
        messages = []
        def mixed(path, token):
            if path == 'onnellab/app':
                raise urllib.error.HTTPError('https://secret.invalid', 404, 'secret-body', {}, None)
            return self.fetch(path, token)
        with self.assertRaisesRegex(ValueError, 'HTTP 404') as caught:
            probe.check(self.config, 'release', 'pages', mixed, emit=messages.append)
        self.assertEqual(len(messages), 3)
        self.assertEqual(sum('READ VERIFIED' in line for line in messages), 2)
        self.assertNotIn('secret', str(caught.exception))
        self.assertNotIn('flutter-template', ' '.join(messages))

    def test_http_status_cannot_inject_nonnumeric_diagnostics(self):
        def denied(path, token):
            raise urllib.error.HTTPError('https://secret.invalid', 'secret-status', 'secret-body', {}, None)
        with self.assertRaises(ValueError) as caught:
            probe.check(self.config, 'release', 'pages', denied, emit=lambda _: None)
        self.assertNotIn('secret', str(caught.exception))
        self.assertNotIn('HTTP secret', str(caught.exception))

    def test_fresh_bundle_probe_never_executes_app_code(self):
        self.config.write_text('repository,app_slug\nonnellab/app,app\nonnellab/app,other\n')
        messages = []
        with patch('sync_homepage_release_artwork.checkout', return_value=Path('/fresh')) as clone, \
             patch('sync_homepage_release_artwork.locate_project', side_effect=[Path('/fresh'), ValueError('custom inventory')]), \
             patch('isolated_vendored_artwork.validate_vendored_bundle', return_value=SimpleNamespace(source_commit='a'*40)) as validate, \
             patch('isolated_vendored_artwork.run_verified_gate') as execute:
            probe.check_bundles(self.config, emit=messages.append)
        clone.assert_called_once()
        validate.assert_called_once_with(Path('/fresh'))
        execute.assert_not_called()
        self.assertIn('BUNDLE VERIFIED', messages[0])
        self.assertIn('ARTWORK UNSUPPORTED', messages[1])

    def test_bundle_checkout_failure_is_not_reported_as_success_or_retried(self):
        self.config.write_text('repository,app_slug\nonnellab/app,app\nonnellab/app,other\n')
        messages = []
        with patch('sync_homepage_release_artwork.checkout', side_effect=OSError('secret value')) as clone:
            with self.assertRaisesRegex(ValueError, 'Fresh app checkout failed') as caught:
                probe.check_bundles(self.config, emit=messages.append)
        clone.assert_called_once()
        self.assertEqual(len(messages), 1)
        self.assertNotIn('secret value', str(caught.exception))

    def test_docker_probe_executes_only_verified_canonical_bundles(self):
        self.config.write_text('repository,app_slug\nonnellab/app,app\nonnellab/app,custom\nonnellab/app,bad\n')
        messages = []
        with patch('sync_homepage_release_artwork.checkout', return_value=Path('/fresh')), \
             patch('sync_homepage_release_artwork.locate_project', return_value=Path('/fresh')), \
             patch('isolated_vendored_artwork.validate_vendored_bundle', side_effect=[
                 SimpleNamespace(source_commit='a'*40),
                 ValueError('Unsupported custom root artwork gate; a separately reviewed bridge is required'),
                 ValueError('private malformed metadata')]), \
             patch('isolated_vendored_artwork.run_verified_gate') as execute:
            result = probe.check_bundles(self.config, emit=messages.append, verify_backend='docker-readonly')
        execute.assert_called_once_with(Path('/fresh'), 'verify-site', backend='docker-readonly')
        self.assertEqual(result, dict(registered=3, bundles_verified=1, gates_verified=1, unsupported=1, blocked=1))
        self.assertIn('ARTWORK VERIFIED', ' '.join(messages))
        self.assertIn('reason=custom_root_gate', ' '.join(messages))
        self.assertIn('reason=canonical_bundle_unverified', ' '.join(messages))
        self.assertNotIn('private', ' '.join(messages))

    def test_missing_or_malformed_inventory_is_blocked_not_custom_unsupported(self):
        self.config.write_text('repository,app_slug\nonnellab/app,app\n')
        messages = []
        with patch('sync_homepage_release_artwork.checkout', return_value=Path('/fresh')), \
             patch('sync_homepage_release_artwork.locate_project', side_effect=ValueError('private malformed JSON')), \
             patch('isolated_vendored_artwork.run_verified_gate') as execute:
            result = probe.check_bundles(self.config, emit=messages.append, verify_backend='docker-readonly')
        self.assertEqual(result['blocked'], 1)
        self.assertEqual(result['unsupported'], 0)
        self.assertIn('reason=inventory_unverified', ' '.join(messages))
        self.assertNotIn('private', ' '.join(messages))
        execute.assert_not_called()

    def test_generic_nonzero_or_bootstrap_failure_stops_remaining_apps(self):
        self.config.write_text('repository,app_slug\nonnellab/app,app\nonnellab/app,second\n')
        messages = []
        with patch('sync_homepage_release_artwork.checkout', return_value=Path('/fresh')), \
             patch('sync_homepage_release_artwork.locate_project', return_value=Path('/fresh')), \
             patch('isolated_vendored_artwork.validate_vendored_bundle', return_value=SimpleNamespace(source_commit='a'*40)), \
             patch('isolated_vendored_artwork.run_verified_gate', side_effect=[ValueError('Docker artwork verification blocked: readonly_artwork_gate_failed'), None]) as execute:
            with self.assertRaisesRegex(ValueError, 'remaining probes stopped'):
                probe.check_bundles(self.config, emit=messages.append, verify_backend='docker-readonly')
        self.assertEqual(execute.call_count, 1)
        self.assertIn('runtime_or_gate_unverified', ' '.join(messages))
        self.assertIn('"registered": 2', ' '.join(messages))
        self.assertNotIn('ARTWORK VERIFIED', ' '.join(messages))

    def test_runtime_or_cleanup_failure_stops_without_retry(self):
        self.config.write_text('repository,app_slug\nonnellab/app,app\nonnellab/app,second\n')
        messages = []
        with patch('sync_homepage_release_artwork.checkout', return_value=Path('/fresh')), \
             patch('sync_homepage_release_artwork.locate_project', return_value=Path('/fresh')), \
             patch('isolated_vendored_artwork.validate_vendored_bundle', return_value=SimpleNamespace(source_commit='a'*40)), \
             patch('isolated_vendored_artwork.run_verified_gate', side_effect=ValueError('private cleanup detail')) as execute:
            with self.assertRaisesRegex(ValueError, 'remaining probes stopped') as caught:
                probe.check_bundles(self.config, emit=messages.append, verify_backend='docker-readonly')
        execute.assert_called_once()
        self.assertNotIn('private', str(caught.exception) + ' '.join(messages))

    def test_backend_arguments_rejected_before_checkout(self):
        with patch('sync_homepage_release_artwork.checkout') as checkout:
            with self.assertRaises(ValueError): probe.check_bundles(self.config, verify_backend='unisolated')
        checkout.assert_not_called()

    def test_explicit_docker_main_requires_actual_complete_gate_coverage(self):
        for summary, expected in [
            (dict(registered=1, bundles_verified=1, gates_verified=1, unsupported=0, blocked=0), 0),
            (dict(registered=1, bundles_verified=0, gates_verified=0, unsupported=1, blocked=0), 1),
            (dict(registered=2, bundles_verified=2, gates_verified=1, unsupported=0, blocked=1), 1),
            (dict(registered=0, bundles_verified=0, gates_verified=0, unsupported=0, blocked=0), 1)]:
            with self.subTest(summary=summary), patch.object(probe, 'check'), \
                 patch('check_artwork_docker_isolation.run_trial', return_value={'status':'passed','cleanup':'verified'}) as trial, \
                 patch.object(probe, 'check_bundles', return_value=summary) as bundles, \
                 patch('isolated_vendored_artwork.sandbox_preflight') as old, redirect_stdout(io.StringIO()):
                self.assertEqual(probe.main(['--docker-verify']), expected)
                trial.assert_called_once_with(inspect_profile_readonly=True)
                bundles.assert_called_once_with(probe.ROOT / 'data/app_release_config.csv', verify_backend='docker-readonly')
                old.assert_not_called()

    def test_docker_main_stops_before_app_reads_after_failed_synthetic_proof(self):
        with patch.object(probe, 'check'), patch('check_artwork_docker_isolation.run_trial', return_value={'status':'blocked'}), \
             patch.object(probe, 'check_bundles') as bundles, redirect_stderr(io.StringIO()):
            self.assertEqual(probe.main(['--docker-verify']), 1)
        bundles.assert_not_called()

    def test_interrupted_synthetic_trial_restores_signal_handler_and_stops_apps(self):
        handlers = []
        original = object()
        def install(signum, handler):
            handlers.append(handler)
            return original
        def interrupted_trial(**kwargs):
            handlers[0](None, None)
        with patch.object(probe.signal, 'signal', side_effect=install), patch.object(probe, 'check'), \
             patch('check_artwork_docker_isolation.run_trial', side_effect=interrupted_trial), \
             patch.object(probe, 'check_bundles') as bundles, redirect_stderr(io.StringIO()) as output:
            self.assertEqual(probe.main(['--docker-verify']), 1)
        self.assertEqual(len(handlers), 2)
        self.assertIs(handlers[-1], original)
        self.assertIn('interrupted', output.getvalue())
        bundles.assert_not_called()

    def test_main_rejects_arbitrary_args_before_credentials(self):
        with patch.object(probe, 'check') as check, redirect_stderr(io.StringIO()):
            self.assertEqual(probe.main(['--site', '/private']), 1)
        check.assert_not_called()

    def test_redirects_do_not_forward_credentials(self):
        with self.assertRaisesRegex(ValueError, 'redirect'):
            probe.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')

    def test_existing_status_dry_run_reuses_binding_and_skips_mutation(self):
        text = (FILE.parents[1] / '.github/workflows/sync-app-operational-status.yml').read_text()
        self.assertIn('artwork_read_only:', text)
        self.assertIn('python3 scripts/check_artwork_read_access.py', text)
        self.assertIn("run-name: ${{ (inputs.artwork_read_only || inputs.artwork_docker_trial || inputs.artwork_profile_inspection || inputs.artwork_docker_profile_trial || inputs.artwork_docker_app_probe) && 'Read-only artwork access probe'", text)
        publisher = (FILE.parents[1] / '.github/workflows/publish-ready-app-releases.yml').read_text()
        self.assertIn("github.event.workflow_run.display_title != 'Read-only artwork access probe'", publisher)
        self.assertNotIn('ARTWORK_READ_TOKEN:', text)
        self.assertNotIn('ARTWORK_PAGES_TOKEN:', text)
        self.assertEqual(text.count('if: inputs.artwork_read_only != true'), 11)
        self.assertIn("inputs.artwork_read_only != true && env.DEPLOY_DASHBOARD == 'true'", text)

if __name__ == '__main__': unittest.main()
