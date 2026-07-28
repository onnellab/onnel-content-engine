from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


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


if __name__ == "__main__":
    unittest.main()
