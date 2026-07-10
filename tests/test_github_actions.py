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
        self.assertIn("Generate Markdown", workflow)
        self.assertIn("Generate Image Specifications", workflow)
        self.assertIn("Build", workflow)
        self.assertIn("Deploy", workflow)
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
        self.assertIn("Generate image specifications", text)
        self.assertIn("Build", text)
        self.assertIn("Deploy", text)
        self.assertIn("Dry-Run Mode", text)


if __name__ == "__main__":
    unittest.main()
