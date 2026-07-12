from __future__ import annotations

import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_pipeline import run_pipeline


class GitHubActionsTest(unittest.TestCase):
    def test_workflow_documents_required_stages_and_dry_run(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "publishing.yml").read_text(encoding="utf-8")

        self.assertIn("dry_run", workflow)
        self.assertIn("Validate", workflow)
        self.assertIn("validate_app_release_config.py", workflow)
        self.assertIn("validate_android_store_versions.py", workflow)
        self.assertIn("sync_android_versions_from_repos.py --dry-run", workflow)
        self.assertIn("Generate Markdown", workflow)
        self.assertIn("Create GitHub App Releases", workflow)
        self.assertIn("Check App Store Versions", workflow)
        self.assertIn("Prepare App Release Candidates", workflow)
        self.assertIn("collect_release_artifacts.py", workflow)
        self.assertIn("download_codemagic_artifacts.py", workflow)
        self.assertIn("fill_ready_app_releases.py", workflow)
        self.assertIn("generate_app_release_report.py", workflow)
        self.assertIn("sync_app_release_issue.py", workflow)
        self.assertIn("Generate Image Specifications", workflow)
        self.assertIn("Generate Image Assets", workflow)
        self.assertIn("Generate Internal Links", workflow)
        self.assertIn("Evaluate Articles", workflow)
        self.assertIn("Schedule Ready Articles", workflow)
        self.assertIn("Publish Due Articles", workflow)
        self.assertIn("Build", workflow)
        self.assertIn("Generate Distribution Drafts", workflow)
        self.assertIn("Approve Due Core Distribution", workflow)
        self.assertIn("Deploy", workflow)
        self.assertIn("Post Due Core Distribution", workflow)
        self.assertIn("Fail On Core Distribution Posting Error", workflow)
        self.assertIn('cron: "0 0 * * *"', workflow)
        self.assertIn("--threshold 9.0", workflow)
        self.assertIn("--interval-days 3", workflow)
        self.assertIn("--publication-time 09:00", workflow)
        self.assertIn("ONNELAKIN_GITHUB_PAGES_TOKEN", workflow)
        self.assertNotIn("Blogger", workflow)

    def test_dry_run_pipeline_does_not_modify_repository_topics(self) -> None:
        topics_path = ROOT / "data" / "topics.csv"
        legacy_path = ROOT / "topics" / "topics.csv"
        topics_before = topics_path.read_text(encoding="utf-8")
        legacy_before = legacy_path.read_text(encoding="utf-8")

        run_pipeline(dry_run=True)

        self.assertEqual(topics_path.read_text(encoding="utf-8"), topics_before)
        self.assertEqual(legacy_path.read_text(encoding="utf-8"), legacy_before)

    def test_github_actions_document_exists(self) -> None:
        text = (ROOT / "docs" / "GitHub_Actions.md").read_text(encoding="utf-8")

        self.assertIn("Validate", text)
        self.assertIn("Generate Markdown", text)
        self.assertIn("Create GitHub App Releases", text)
        self.assertIn("Generate image specifications", text)
        self.assertIn("Generate image assets", text)
        self.assertIn("Generate internal link metadata", text)
        self.assertIn("Evaluate articles", text)
        self.assertIn("Schedule ready articles", text)
        self.assertIn("Publish due articles", text)
        self.assertIn("three-day", text)
        self.assertIn("9.0 / 10", text)
        self.assertIn("Build", text)
        self.assertIn("Generate And Approve Distribution", text)
        self.assertIn("Deploy", text)
        self.assertIn("Post Core Distribution", text)
        self.assertIn("Dry-Run Mode", text)


if __name__ == "__main__":
    unittest.main()
