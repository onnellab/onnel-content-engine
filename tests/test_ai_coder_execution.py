from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dispatch_ai_coder_qa


class AiCoderExecutionTest(unittest.TestCase):
    def test_approval_workflow_is_disabled_until_runner_is_configured(self) -> None:
        path = ROOT / ".github" / "workflows" / "approve-ai-coder-task.yml"
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        execute = parsed["jobs"]["execute-draft-pr"]

        self.assertEqual(execute["if"], "vars.AI_CODER_RUNNER_ENABLED == 'true'")
        self.assertEqual(execute["runs-on"], ["self-hosted", "onnellab-ai-coder"])
        self.assertEqual(execute["timeout-minutes"], 90)

    def test_execution_requires_dedicated_token_and_records_draft_pr(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "approve-ai-coder-task.yml").read_text()

        self.assertIn("secrets.AI_CODER_GITHUB_TOKEN", workflow)
        self.assertIn("preflight_ai_coder_runner.sh", workflow)
        self.assertIn('run_codex_approved_coder_task.sh "$TASK_ID" --execute', workflow)
        self.assertIn("git add data/ai_coder_tasks.json", workflow)
        self.assertIn("git pull --rebase origin main", workflow)
        self.assertIn("dispatch_ai_coder_qa.py", workflow)
        self.assertNotIn('approve_ai_coder_task.py "${{ inputs.task_id }}"', workflow)

    def test_preflight_fails_before_cli_checks_without_token(self) -> None:
        result = subprocess.run(
            ["bash", str(ROOT / "scripts" / "preflight_ai_coder_runner.sh")],
            cwd=ROOT,
            env={key: value for key, value in os.environ.items() if key != "AI_CODER_GITHUB_TOKEN"},
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("AI_CODER_GITHUB_TOKEN is required", result.stderr)

    def test_qa_dispatch_uses_recorded_commit_and_pr(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "data").mkdir()
            (root / "data" / "ai_coder_tasks.json").write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "finding-1",
                                "status": "draft_pr_created",
                                "repository": "onnellab/sample",
                                "commit": "a" * 40,
                                "pr_url": "https://github.com/onnellab/sample/pull/1",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(dispatch_ai_coder_qa, "ROOT", root), patch.dict(
                os.environ, {"GITHUB_REPOSITORY": "onnellab/onnel-content-engine"}
            ), patch.object(subprocess, "run") as run, patch.object(
                sys, "argv", ["dispatch_ai_coder_qa.py", "finding-1", "--execute"]
            ):
                self.assertEqual(dispatch_ai_coder_qa.main(), 0)

        command = run.call_args.args[0]
        self.assertIn("ref=" + "a" * 40, command)
        self.assertIn("pr_url=https://github.com/onnellab/sample/pull/1", command)

    def test_portable_qa_requires_app_performance_gate(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "run-app-qa.yml").read_text()
        validator = (ROOT / "scripts" / "validate_ai_qa_report.py").read_text()

        self.assertIn("tool/performance_gate.sh", workflow)
        self.assertIn('performance=2', workflow)
        self.assertIn("steps.qa.outputs.performance != '0'", workflow)
        self.assertIn('"performance"', validator)

        valid = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "validate_ai_qa_report.py"),
                str(ROOT / "docs" / "operations" / "QA_REPORT_EXAMPLE.json"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)

        with tempfile.TemporaryDirectory() as raw:
            report = json.loads(
                (ROOT / "docs" / "operations" / "QA_REPORT_EXAMPLE.json").read_text()
            )
            report.pop("performance")
            path = Path(raw) / "qa.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            missing = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validate_ai_qa_report.py"), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(missing.returncode, 1)
        self.assertIn("performance", missing.stderr)


if __name__ == "__main__":
    unittest.main()
