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
