"""Validate documented queue semantics not yet known to pinned actionlint.

No network calls or workflow dispatches. All shared writers stay serialized.
"""
from __future__ import annotations

from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GROUP = "onnellab-manual-dashboard-writer"
WRITERS = {
    "collect-github-issues.yml", "collect-os-updates.yml",
    "collect-private-test-build-status.yml", "collect-sentry-crashes.yml",
    "collect-store-policy-updates.yml", "deploy-ops-dashboard.yml",
    "generate-ai-manager-report.yml", "generate-chatgpt-monitor.yml",
    "publish-ready-app-releases.yml", "publish-store-review-reply.yml",
    "reconcile-remote-browser-publications.yml", "refresh-ai-operations.yml",
    "retry-devto-article.yml", "sync-app-operational-status.yml",
    "sync-internal-store-processing-status.yml", "sync-public-release-notes.yml",
    "sync-store-funnel.yml", "sync-store-reviews.yml", "sync-store-sales.yml",
    "update-devto-article.yml", "verify-manual-publications.yml",
}
LINT_COMPATIBILITY = (
    "^unexpected key .queue. for .concurrency. section[.] "
    "expected one of .cancel-in-progress., .group.$"
)


def validate_queue(concurrency):
    if not isinstance(concurrency, dict) or "queue" not in concurrency:
        return
    if concurrency["queue"] not in ("single", "max"):
        raise ValueError("concurrency.queue must be the literal single or max")
    if concurrency["queue"] == "max" and concurrency.get("cancel-in-progress", False) is not False:
        raise ValueError("queue max must not cancel in-progress writers")


class OpsWorkflowConcurrency(unittest.TestCase):
    def test_all_shared_writers_preserve_pending_and_running_work(self):
        found = set()
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            config = yaml.safe_load(path.read_text(encoding="utf-8"))
            scopes = [config, *config.get("jobs", {}).values()]
            for scope in scopes:
                concurrency = scope.get("concurrency")
                with self.subTest(workflow=path.name):
                    validate_queue(concurrency)
                    if isinstance(concurrency, dict) and concurrency.get("group") == GROUP:
                        found.add(path.name)
                        self.assertEqual({"group": GROUP, "cancel-in-progress": False, "queue": "max"}, concurrency)
            if path.name in WRITERS:
                with self.subTest(required_writer=path.name):
                    self.assertEqual({"group": GROUP, "cancel-in-progress": False, "queue": "max"}, config.get("concurrency"))
        self.assertEqual(WRITERS, found)

    def test_queue_values_and_cancel_policy_are_strict(self):
        for value in ("single", "max"):
            validate_queue({"queue": value, "cancel-in-progress": False})
        for value in (True, False, 100, None, "many", "MAX", "${{ inputs.queue }}"):
            with self.subTest(queue=value), self.assertRaises(ValueError):
                validate_queue({"queue": value})
        for cancel in (True, "false", "${{ inputs.cancel }}", 0, None):
            with self.subTest(cancel=cancel), self.assertRaises(ValueError):
                validate_queue({"queue": "max", "cancel-in-progress": cancel})

    def test_native_linter_remains_enabled_with_only_exact_schema_compatibility(self):
        text = (ROOT / ".github/workflows/validate-workflows.yml").read_text(encoding="utf-8")
        config = yaml.safe_load(text)
        steps = config["jobs"]["actionlint"]["steps"]
        lint = next(s for s in steps if s.get("uses") == "docker://rhysd/actionlint:1.7.7")
        check = next(s for s in steps if s.get("run") == "python -m unittest tests.test_ops_workflow_concurrency")
        self.assertLess(steps.index(check), steps.index(lint))
        self.assertEqual(f'-color -ignore "{LINT_COMPATIBILITY}"', lint["with"]["args"])
        self.assertNotIn("continue-on-error", text)
        self.assertNotIn("|| true", text)
        self.assertEqual({"contents": "read"}, config["permissions"])


if __name__ == "__main__":
    unittest.main()
