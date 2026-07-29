from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_ai_manager_report
import publish_ai_manager_issue
import publish_ai_manager_telegram


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

    def test_private_ops_issue_enabled_and_external_webhook_stays_disabled(self) -> None:
        issue = json.loads((ROOT / "data" / "ai_manager_notification_config.json").read_text())
        webhook = json.loads((ROOT / "data" / "ai_manager_webhook_config.json").read_text())
        telegram = json.loads((ROOT / "data" / "ai_manager_telegram_config.json").read_text())

        self.assertTrue(issue["enabled"])
        self.assertEqual(issue["repository"], "onnellab/onnellab-ops")
        self.assertFalse(webhook["enabled"])
        self.assertFalse(telegram["enabled"])

    def test_telegram_report_is_informational_and_links_to_approval_workflows(self) -> None:
        report = {
            "generated_at": "2026-07-29T00:00:00+00:00",
            "summary": {"coder_tasks_approved_pending": 1, "qa_reports_passed": 2},
            "requires_attention": [
                {"task_id": "coder-1", "category": "coder_approved_pending"}
            ],
        }

        text = publish_ai_manager_telegram.message(report)
        buttons = publish_ai_manager_telegram.keyboard("onnellab/onnel-content-engine")

        self.assertIn("coder-1", text)
        self.assertIn("Informational only", text)
        urls = [
            button["url"]
            for row in buttons["inline_keyboard"]
            for button in row
        ]
        self.assertTrue(any("approve-ai-coder-task.yml" in url for url in urls))
        self.assertTrue(any("merge-approved-app-pr.yml" in url for url in urls))
        self.assertNotIn("callback_data", json.dumps(buttons))

    def test_telegram_error_does_not_expose_bot_token(self) -> None:
        token = "123456:secret-token"
        error = HTTPError(
            f"https://api.telegram.org/bot{token}/sendMessage",
            401,
            "Unauthorized",
            {},
            None,
        )
        with patch.object(publish_ai_manager_telegram, "urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401") as raised:
                publish_ai_manager_telegram.send(token, {"chat_id": "1", "text": "test"})

        self.assertNotIn(token, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
