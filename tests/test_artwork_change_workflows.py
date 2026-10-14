import re
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
STATUS = ROOT / '.github/workflows/sync-app-operational-status.yml'
PUBLISH = ROOT / '.github/workflows/publish-ready-app-releases.yml'


def steps(text):
    return [block for block in text.split('      - name: ')[1:]]


class ArtworkChangeWorkflowTests(unittest.TestCase):
    def test_no_schedule_or_new_secret_binding_before_runtime_proof(self):
        status = STATUS.read_text()
        self.assertNotIn('\n  schedule:', status)
        self.assertEqual(status.count('secrets.ONNELLAB_RELEASE_TOKEN'), 3)
        self.assertEqual(status.count('secrets.ONNELLAB_GITHUB_PAGES_TOKEN'), 4)
        self.assertIn('group: onnellab-manual-dashboard-writer', status)
        self.assertIn('cancel-in-progress: false', status)
        self.assertIn('artwork_check_only:', status)
        self.assertIn('default: false', status)

    def test_docker_trial_is_explicit_readonly_and_has_no_private_read_fallback(self):
        text = STATUS.read_text()
        blocks = steps(text)
        self.assertTrue(blocks[0].startswith('Validate read-only isolation diagnostic inputs'))
        self.assertIn('inputs.artwork_docker_trial == true', blocks[0])
        self.assertIn('inputs.artwork_read_only', blocks[0])
        self.assertIn('exit 1', blocks[0])
        self.assertIn("(inputs.artwork_read_only || inputs.artwork_docker_trial || inputs.artwork_profile_inspection || inputs.artwork_docker_profile_trial) && 'Read-only artwork access probe'", text)
        install = next(b for b in blocks if b.startswith('Install isolated'))
        self.assertIn('inputs.artwork_docker_trial != true', install)
        guard = next(b for b in blocks if b.startswith('Sync GitHub main'))
        self.assertIn('/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -B scripts/check_artwork_docker_isolation.py', guard)
        self.assertLess(guard.index('check_artwork_docker_isolation.py'), guard.index('elif [ "${{ inputs.artwork_read_only }}"'))
        self.assertNotIn('|| python', guard)
        production = (ROOT / 'scripts/isolated_vendored_artwork.py').read_text()
        self.assertNotIn('check_artwork_docker_isolation', production)
        self.assertNotIn('docker', production.lower())

    def test_profile_inspection_is_standalone_readonly_and_never_resumes_docker(self):
        text = STATUS.read_text()
        blocks = steps(text)
        self.assertIn('artwork_profile_inspection:', text)
        self.assertIn('inputs.artwork_profile_inspection == true', blocks[0])
        self.assertIn('Choose one standalone isolation diagnostic', blocks[0])
        self.assertIn('inputs.artwork_read_only', blocks[0])
        install = next(b for b in blocks if b.startswith('Install isolated'))
        self.assertIn('inputs.artwork_profile_inspection != true', install)
        guard = next(b for b in blocks if b.startswith('Sync GitHub main'))
        self.assertIn('/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B scripts/check_artwork_apparmor_profile.py', guard)
        self.assertLess(guard.index('check_artwork_apparmor_profile.py'), guard.index('elif [ "${{ inputs.artwork_docker_trial }}"'))
        self.assertNotIn('|| python', guard)
        self.assertNotIn('check_artwork_apparmor_profile', (ROOT / 'scripts/isolated_vendored_artwork.py').read_text())

    def test_combined_trial_is_explicit_and_fresh_without_changing_standalone_probe(self):
        text = STATUS.read_text()
        blocks = steps(text)
        self.assertIn('artwork_docker_profile_trial:', text)
        self.assertIn('diagnostic_count', blocks[0])
        self.assertIn('"$diagnostic_count" -ne 1', blocks[0])
        self.assertIn('inputs.artwork_docker_profile_trial', blocks[0])
        install = next(b for b in blocks if b.startswith('Install isolated'))
        self.assertIn('inputs.artwork_docker_profile_trial != true', install)
        guard = next(b for b in blocks if b.startswith('Sync GitHub main'))
        self.assertIn('/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -B scripts/check_artwork_docker_isolation.py --inspect-profile-readonly', guard)
        self.assertLess(guard.index('--inspect-profile-readonly'), guard.index('elif [ "${{ inputs.artwork_profile_inspection }}"'))
        self.assertNotIn('sudo', guard)
        self.assertNotIn('check_artwork_apparmor_profile', (ROOT / 'scripts/isolated_vendored_artwork.py').read_text())

    def test_existing_bound_read_step_prepares_full_local_evidence_before_probe(self):
        block = next(b for b in steps(STATUS.read_text()) if b.startswith('Sync GitHub main'))
        names = ['sync_flutter_plugin_versions.py', 'sync_android_versions_from_repos.py',
                 'check_store_versions.py', 'prepare_app_release_rows.py',
                 'fill_ready_app_releases.py', 'check_homepage_artwork_changes.py stage']
        indices = [block.index(name) for name in names]
        self.assertEqual(indices, sorted(indices))
        self.assertIn('--run-attempt "$GITHUB_RUN_ATTEMPT"', block)
        self.assertIn('--github-output "$GITHUB_OUTPUT"', block)
        self.assertNotIn('git push', block)
        self.assertNotIn('create_github_releases', block)

    def test_all_later_status_operations_skip_automatic_no_change_but_preserve_manual(self):
        blocks = steps(STATUS.read_text())
        guard = next(i for i,b in enumerate(blocks) if b.startswith('Sync GitHub main'))
        for block in blocks[guard+1:]:
            with self.subTest(step=block.splitlines()[0]):
                self.assertIn("env.ARTWORK_CHECK_ONLY != 'true' || steps.artwork_guard.outputs.changed == 'true'", block)
                self.assertIn('inputs.artwork_read_only != true', block)
        commit = next(b for b in blocks if b.startswith('Commit operational'))
        self.assertIn('if [ "$ARTWORK_CHECK_ONLY" = "true" ]; then\n            git add data/artwork-change-trigger.json', commit)

    def test_automatic_publisher_checks_latest_exact_run_and_attempt(self):
        text = PUBLISH.read_text()
        self.assertLess(text.index('git pull --ff-only origin main'), text.index('Gate automatic artwork checks'))
        blocks = steps(text)
        gate = next(i for i,b in enumerate(blocks) if b.startswith('Gate automatic artwork'))
        self.assertIn('SOURCE_RUN_ATTEMPT: ${{ github.event.workflow_run.run_attempt }}', blocks[gate])
        self.assertIn('--source-run-attempt "$SOURCE_RUN_ATTEMPT"', blocks[gate])
        self.assertIn('else\n            echo "authorized=true"', blocks[gate])
        for block in blocks[gate+1:]:
            with self.subTest(step=block.splitlines()[0]):
                self.assertIn("steps.artwork_run.outputs.authorized == 'true'", block)
        self.assertIn("github.event.workflow_run.display_title != 'Read-only artwork access probe'", text)

if __name__ == '__main__': unittest.main()
