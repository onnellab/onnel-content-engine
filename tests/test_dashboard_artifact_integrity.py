from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_manual_publish_site import html_document
from validate_manual_publish_site import DashboardArtifactError, validate_dashboard


class DashboardIntegrityTest(unittest.TestCase):
    def validate(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'index.html'
            path.write_text(text)
            validate_dashboard(path)

    def test_real_builder_output_is_valid(self):
        self.validate(html_document([]))

    def test_committed_autostash_conflict_is_rejected(self):
        text = html_document([]) + '\n<<<<<<< Updated upstream\nold\n=======\nnew\n>>>>>>> Stashed changes\n'
        with self.assertRaisesRegex(DashboardArtifactError, 'merge-conflict'):
            self.validate(text)

    def test_duplicate_embedded_payload_without_markers_is_rejected(self):
        text = html_document([]) + '<script id="manual-state-data" type="application/json">{}</script>'
        with self.assertRaisesRegex(DashboardArtifactError, 'duplicate'):
            self.validate(text)

    def test_invalid_json_is_rejected(self):
        text = html_document([]).replace('id="manual-data" type="application/json">[]', 'id="manual-data" type="application/json">broken')
        with self.assertRaisesRegex(DashboardArtifactError, 'invalid JSON'):
            self.validate(text)

    def test_missing_payloads_are_rejected(self):
        with self.assertRaisesRegex(DashboardArtifactError, 'missing'):
            self.validate('<html><body>Incomplete build</body></html>')

    def test_devto_refreshes_main_before_regenerating_and_committing_snapshot(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / '.github/workflows/update-devto-article.yml').read_text()
        commit = text.split('- name: Commit updated publication state', 1)[1].split('- name: Deploy', 1)[0]
        self.assertLess(commit.index('git pull --rebase --autostash origin main'), commit.index('python3 scripts/build_manual_publish_site.py'))
        self.assertLess(commit.index('python3 scripts/build_manual_publish_site.py'), commit.index('git add '))
        self.assertIn('for attempt in 1 2 3', commit)
        self.assertIn('git pull --rebase origin main', commit)
        self.assertNotIn('--force', commit)
        deploy = text.split('- name: Deploy manual publish dashboard', 1)[1]
        self.assertLess(deploy.index('pull --rebase origin main'), deploy.index('cp generated/manual-publish/index.html'))
        self.assertGreater(deploy.rindex('scripts/validate_manual_publish_site.py'), deploy.rindex('pull --rebase origin main'))

    def test_every_direct_deployer_validates_source_and_destination(self):
        root = Path(__file__).resolve().parents[1]
        found = []
        for path in (root / '.github/workflows').glob('*.yml'):
            text = path.read_text()
            if 'cp generated/manual-publish/index.html' not in text:
                continue
            found.append(path.name)
            self.assertIn('python3 scripts/validate_manual_publish_site.py generated/manual-publish/index.html', text, path.name)
            self.assertIn('python3 scripts/validate_manual_publish_site.py "$HOMEPAGE_REPO_PATH/public/manual-publish/index.html"', text, path.name)
            self.assertIn('git -C "$HOMEPAGE_REPO_PATH" diff --check', text, path.name)
        self.assertEqual(len(found), 5)


if __name__ == '__main__':
    unittest.main()
