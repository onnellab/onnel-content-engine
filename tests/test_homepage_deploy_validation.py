import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publishing import deploy_github_pages


class HomepageDeployValidationTest(unittest.TestCase):
    def deploy(self, homepage, runner):
        with patch("publishing.validate_homepage_repository"), patch("publishing.export_markdown_to_homepage", return_value=[]), patch("publishing.export_privacy_pages_to_homepage", return_value=[]), patch("publishing.run_homepage_command", side_effect=runner), patch("publishing.subprocess.run", return_value=subprocess.CompletedProcess([], 0)):
            return deploy_github_pages(homepage_repo=homepage)

    def test_localization_failure_stops_before_build_commit_and_push(self):
        with tempfile.TemporaryDirectory() as directory:
            homepage = Path(directory)
            (homepage / "package.json").write_text(json.dumps({"scripts": {"check:i18n-quality": "node scripts/check-localization-quality.mjs"}}))
            calls = []

            def run(command, _root):
                calls.append(command)
                if command == ["npm", "run", "check:i18n-quality"]:
                    raise subprocess.CalledProcessError(1, command)

            with self.assertRaises(subprocess.CalledProcessError):
                self.deploy(homepage, run)
            self.assertEqual(calls, [["git", "pull", "--rebase", "origin", "main"], ["npm", "run", "check:i18n-quality"]])

    def test_available_localization_check_precedes_build(self):
        with tempfile.TemporaryDirectory() as directory:
            homepage = Path(directory)
            (homepage / "package.json").write_text(json.dumps({"scripts": {"check:i18n-quality": "node check.mjs"}}))
            calls = []
            self.deploy(homepage, lambda command, _root: calls.append(command))
            self.assertLess(calls.index(["npm", "run", "check:i18n-quality"]), calls.index(["npm", "run", "build"]))

    def test_other_homepage_without_script_keeps_existing_build(self):
        with tempfile.TemporaryDirectory() as directory:
            homepage = Path(directory)
            (homepage / "package.json").write_text(json.dumps({"scripts": {"build": "astro build"}}))
            calls = []
            self.deploy(homepage, lambda command, _root: calls.append(command))
            self.assertIn(["npm", "run", "build"], calls)
            self.assertNotIn(["npm", "run", "check:i18n-quality"], calls)


if __name__ == "__main__":
    unittest.main()
