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
        self.assertIn("validate_app_pricing.py", workflow)
        validate_block = workflow.split("- name: Validate", 1)[1].split("- name: Check App Store Versions", 1)[0]
        self.assertNotIn("sync_android_versions_from_repos.py --dry-run", validate_block)
        self.assertIn("Generate Markdown", workflow)
        self.assertIn("Create GitHub App Releases", workflow)
        self.assertIn("scripts/create_github_releases.py --publish", workflow)
        self.assertIn("Check App Store Versions", workflow)
        self.assertIn("Prepare App Release Candidates", workflow)
        self.assertIn("collect_release_artifacts.py", workflow)
        self.assertIn("sync_codemagic_artifact_urls.py", workflow)
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
        self.assertIn("Validate Distribution Supply", workflow)
        self.assertIn("scripts/check_distribution_supply.py", workflow)
        self.assertIn("--minimum-score 9.5", workflow)
        self.assertIn("Approve Due Core Distribution", workflow)
        self.assertIn("Deploy", workflow)
        self.assertIn("Post Due Core Distribution", workflow)
        self.assertIn("Fail On Core Distribution Posting Error", workflow)
        self.assertIn('cron: "0 0 * * *"', workflow)
        self.assertIn("--threshold 9.0", workflow)
        self.assertIn("--interval-days 3", workflow)
        self.assertIn("--publication-time 09:00", workflow)
        self.assertIn("--require-ready-when-due", workflow)
        self.assertIn("ONNELLAB_GITHUB_PAGES_TOKEN", workflow)
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

    def test_manual_publication_verification_refreshes_store_snapshots(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "verify-manual-publications.yml").read_text(encoding="utf-8")

        self.assertIn("Check store homepage versions", workflow)
        self.assertIn("scripts/check_store_versions.py", workflow)
        self.assertIn("Prepare app release candidates", workflow)
        self.assertIn("scripts/prepare_app_release_rows.py", workflow)
        self.assertIn("Fill ready app release rows", workflow)
        self.assertIn("scripts/fill_ready_app_releases.py", workflow)
        self.assertIn("Validate app pricing", workflow)
        self.assertIn("scripts/validate_app_pricing.py", workflow)
        self.assertIn("Sync AI provider pricing assumptions", workflow)
        self.assertIn("scripts/sync_ai_provider_pricing.py", workflow)
        self.assertIn("git pull --rebase --autostash origin main", workflow)

    def test_ready_app_release_workflow_is_release_only(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "publish-ready-app-releases.yml").read_text(encoding="utf-8")

        self.assertIn("scripts/create_github_releases.py --publish", workflow)
        self.assertIn("scripts/sync_github_release_status.py --allow-missing-token", workflow)
        self.assertIn("scripts/sync_ai_provider_pricing.py", workflow)
        self.assertIn("scripts/build_manual_publish_site.py", workflow)
        self.assertNotIn("post_core_distribution.py", workflow)
        self.assertNotIn("verify_manual_publications.py --visual-public-pages", workflow)
        self.assertIn("data/app_releases.csv", workflow)
        self.assertIn("data/ai_provider_pricing.csv", workflow)
        self.assertIn("data/melivra_ai_credit_policy.csv", workflow)
        self.assertIn("generated/manual-publish/index.html", workflow)
        self.assertIn("generated/manual-publish/sw.js", workflow)
        self.assertIn("public/manual-publish/sw.js", workflow)

    def test_devto_update_workflow_deploys_rebuilt_dashboard(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "update-devto-article.yml").read_text(encoding="utf-8")

        self.assertIn("repository: onnellab/onnellab.github.io", workflow)
        self.assertIn("scripts/sync_ai_provider_pricing.py", workflow)
        self.assertIn("scripts/build_manual_publish_site.py --homepage-repo", workflow)
        self.assertIn("data/ai_provider_pricing.csv", workflow)
        self.assertIn("data/melivra_ai_credit_policy.csv", workflow)
        self.assertIn("generated/manual-publish/sw.js", workflow)
        self.assertIn("public/manual-publish/sw.js", workflow)
        self.assertIn("Refresh manual publish dashboard", workflow)

    def test_store_review_workflow_syncs_and_deploys_dashboard(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "sync-store-reviews.yml").read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch", workflow)
        self.assertIn('cron: "20 0 * * *"', workflow)
        self.assertIn("APP_STORE_CONNECT_PRIVATE_KEY_BASE64", workflow)
        self.assertIn("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64", workflow)
        self.assertIn("scripts/sync_store_reviews.py", workflow)
        self.assertIn("scripts/build_manual_publish_site.py", workflow)
        self.assertIn("data/store_reviews.csv", workflow)
        self.assertIn("public/manual-publish/", workflow)


if __name__ == "__main__":
    unittest.main()
