from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_chatgpt_monitor_snapshot import build
from validate_ai_qa_report import REQUIRED_CHECKS


class ChatGptMonitorTest(unittest.TestCase):
    def test_snapshot_contains_actionable_state_without_ticket_body(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            reports = data / "qa-reports"
            reports.mkdir(parents=True)
            (data / "chatgpt_monitor_config.json").write_text(
                json.dumps(
                    {
                        "repository": "onnellab/onnel-content-engine",
                        "notify_states": ["draft_pr_ready"],
                    }
                ),
                encoding="utf-8",
            )
            (data / "ai_coder_tasks.json").write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "fix-1",
                                "app_slug": "sample",
                                "repository": "onnellab/sample",
                                "status": "draft_pr_created",
                                "risk_class": "GREEN",
                                "pr_url": "https://github.com/onnellab/sample/pull/3",
                                "commit": "a" * 40,
                                "ticket": {"observed_symptom": "private user report"},
                                "verification": {"status": "passed"},
                                "security_scan": "passed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (reports / "fix-1.json").write_text(
                json.dumps(
                    {
                        "task_id": "fix-1",
                        "repository": "onnellab/sample",
                        "pr_url": "https://github.com/onnellab/sample/pull/3",
                        "tests": "passed",
                        "build": "passed",
                        "static_analysis": "passed",
                        "performance": "passed",
                        "qa_profile": "default",
                        "risk": "Bounded GREEN patch.",
                        "rollback": "Revert the patch commit.",
                        "checks": [
                            {
                                "name": name,
                                "status": "PASS",
                                "severity": "LOW",
                                "evidence": f"objective evidence for {name}",
                            }
                            for name in REQUIRED_CHECKS
                        ],
                    }
                ),
                encoding="utf-8",
            )

            snapshot = build(root)

        self.assertEqual(snapshot["items"][0]["state"], "draft_pr_ready")
        self.assertIn("notification_key", snapshot["items"][0])
        self.assertIn("rework-ai-coder-task.yml", snapshot["items"][0]["action_urls"]["rework"])
        self.assertNotIn("private user report", json.dumps(snapshot))

    def test_notification_key_changes_with_qa_state(self) -> None:
        base = {"task_id": "fix-1", "state": "draft_pr_qa_pending"}
        from generate_chatgpt_monitor_snapshot import notification_key

        self.assertNotEqual(notification_key(base), notification_key({**base, "state": "draft_pr_ready"}))

    def test_workflows_refresh_snapshot_and_telegram_delivery_is_absent(self) -> None:
        required = (
            "approve-ai-coder-task.yml",
            "run-app-qa.yml",
            "merge-approved-app-pr.yml",
            "rework-ai-coder-task.yml",
            "discard-ai-coder-task.yml",
            "generate-ai-manager-report.yml",
        )
        for name in required:
            workflow = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("generate_chatgpt_monitor_snapshot.py", workflow, name)
        manager = (ROOT / ".github/workflows/generate-ai-manager-report.yml").read_text(encoding="utf-8")
        self.assertNotIn("publish_ai_manager_telegram.py", manager)


if __name__ == "__main__":
    unittest.main()
