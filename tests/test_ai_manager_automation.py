from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_ai_manager_report
import publish_ai_manager_issue


class AiManagerAutomationTest(unittest.TestCase):
    def test_report_surfaces_coder_and_performance_qa_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            (data / "qa-reports").mkdir(parents=True)
            (data / "ai_coder_tasks.json").write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "approved-1", "status": "approved_for_draft_pr"},
                            {"task_id": "draft-1", "status": "draft_pr_created"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (data / "qa-reports" / "draft-1.json").write_text(
                json.dumps(
                    {
                        "task_id": "draft-1",
                        "tests": "passed",
                        "build": "passed",
                        "static_analysis": "passed",
                        "performance": "not_configured",
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(generate_ai_manager_report, "ROOT", root):
                self.assertEqual(generate_ai_manager_report.main(), 0)
            report = json.loads((data / "ai_manager_daily_report.json").read_text())

        self.assertEqual(report["summary"]["coder_tasks_approved_pending"], 1)
        self.assertEqual(report["summary"]["qa_reports_blocked"], 1)
        self.assertIn("qa_blocked", {item["category"] for item in report["requires_attention"]})

    def test_issue_body_has_stable_ids_and_human_workflow_links(self) -> None:
        report = {
            "generated_at": "2026-07-28T00:00:00+00:00",
            "summary": {"qa_reports_blocked": 1},
            "requires_attention": [{"task_id": "draft-1", "category": "qa_blocked"}],
        }
        result = publish_ai_manager_issue.body(report, "onnellab/onnel-content-engine")

        self.assertIn("`draft-1` — qa_blocked", result)
        self.assertIn("approve-ai-coder-task.yml", result)
        self.assertIn("merge-approved-app-pr.yml", result)
        self.assertIn("This report is informational", result)

    def test_public_repo_issue_and_external_webhook_stay_disabled(self) -> None:
        issue = json.loads((ROOT / "data" / "ai_manager_notification_config.json").read_text())
        webhook = json.loads((ROOT / "data" / "ai_manager_webhook_config.json").read_text())

        self.assertFalse(issue["enabled"])
        self.assertEqual(issue["repository"], "onnellab/onnel-content-engine")
        self.assertFalse(webhook["enabled"])


if __name__ == "__main__":
    unittest.main()
