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
import approve_ai_coder_task
from ai_coder_task_contract import contract_errors, path_is_allowed


class AiCoderExecutionTest(unittest.TestCase):
    def complete_task(self, risk_class: str) -> dict:
        return {
            "task_id": "finding-1",
            "app_slug": "sample",
            "repository": "onnellab/sample",
            "status": "proposed",
            "risk_class": risk_class,
            "ticket": {
                "observed_symptom": "Parser crashes on a large file.",
                "reproduction": "flutter test test/parser_large_file_test.dart",
                "expected_result": "The file opens without a crash.",
                "allowed_paths": ["lib/parser", "test/parser_large_file_test.dart"],
                "prohibited_paths": ["authentication", "billing"],
                "verification_commands": ["flutter test test/parser_large_file_test.dart"],
                "performance_baseline": "Parser benchmark must not regress.",
                "completion_criteria": "Regression and existing parser tests pass.",
            },
        }

    def test_task_contract_enforces_bounded_paths(self) -> None:
        task = self.complete_task("GREEN")

        self.assertEqual(contract_errors(task), [])
        self.assertTrue(path_is_allowed("lib/parser/reader.dart", task["ticket"]["allowed_paths"]))
        self.assertFalse(path_is_allowed("lib/auth/session.dart", task["ticket"]["allowed_paths"]))

    def test_red_task_is_never_approved_and_yellow_requires_plan(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "data").mkdir()
            path = root / "data" / "ai_coder_tasks.json"
            for risk, extra, expected in (
                ("RED", [], "RED tasks cannot"),
                ("YELLOW", [], "require --approve-plan"),
            ):
                path.write_text(json.dumps({"tasks": [self.complete_task(risk)]}), encoding="utf-8")
                with patch.object(approve_ai_coder_task, "ROOT", root), patch.object(
                    sys,
                    "argv",
                    ["approve_ai_coder_task.py", "finding-1", "--approver", "owner", "--confirm", *extra],
                ):
                    with self.assertRaisesRegex(SystemExit, expected):
                        approve_ai_coder_task.main()

            path.write_text(json.dumps({"tasks": [self.complete_task("YELLOW")]}), encoding="utf-8")
            with patch.object(approve_ai_coder_task, "ROOT", root), patch.object(
                sys,
                "argv",
                [
                    "approve_ai_coder_task.py",
                    "finding-1",
                    "--approver",
                    "owner",
                    "--confirm",
                    "--approve-plan",
                ],
            ):
                self.assertEqual(approve_ai_coder_task.main(), 0)
            approved = json.loads(path.read_text())["tasks"][0]

        self.assertEqual(approved["status"], "approved_for_draft_pr")
        self.assertIn("plan_approved_at", approved)

    def test_approval_workflow_is_disabled_until_runner_is_configured(self) -> None:
        path = ROOT / ".github" / "workflows" / "approve-ai-coder-task.yml"
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        execute = parsed["jobs"]["execute-draft-pr"]

        self.assertEqual(execute["if"], "vars.AI_CODER_RUNNER_ENABLED == 'true'")
        self.assertEqual(execute["runs-on"], ["self-hosted", "onnellab-ai-coder"])
        self.assertEqual(execute["timeout-minutes"], 90)
        self.assertEqual(execute["concurrency"]["group"], "ai-coder-global")

    def test_execution_requires_dedicated_token_and_records_draft_pr(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "approve-ai-coder-task.yml").read_text()

        self.assertIn("secrets.AI_CODER_GITHUB_TOKEN", workflow)
        self.assertIn("preflight_ai_coder_runner.sh", workflow)
        self.assertIn('run_codex_approved_coder_task.sh "$TASK_ID" --execute', workflow)
        self.assertIn("git add data/ai_coder_tasks.json", workflow)
        self.assertIn("git pull --rebase origin main", workflow)
        self.assertIn("dispatch_ai_coder_qa.py", workflow)
        self.assertIn("AI_CODER_SECURITY_SCAN_ENABLED", workflow)
        self.assertIn("--approve-plan", workflow)
        self.assertNotIn('approve_ai_coder_task.py "${{ inputs.task_id }}"', workflow)

    def test_runner_uses_disposable_clone_and_optional_security_diff_gate(self) -> None:
        runner = (ROOT / "scripts" / "run_codex_approved_coder_task.sh").read_text()

        self.assertIn('workspace="$(mktemp -d', runner)
        self.assertIn('git clone --filter=blob:none --no-tags', runner)
        self.assertIn('--working-tree', runner)
        self.assertIn('--fail-on-severity high', runner)
        self.assertIn('AI_CODER_SECURITY_SCAN_ENABLED', runner)
        self.assertIn('ls-files --others --exclude-standard', runner)
        self.assertNotIn("local_repositories.csv", runner)

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

    def test_firestore_autosave_profile_requires_specialized_checks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            report = json.loads(
                (ROOT / "docs" / "operations" / "QA_REPORT_EXAMPLE.json").read_text()
            )
            report["qa_profile"] = "flutter_riverpod_firestore_autosave_v1"
            path = Path(raw) / "qa.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            missing = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validate_ai_qa_report.py"), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(missing.returncode, 1)
            self.assertIn("autosave_flush_integrity", missing.stderr)

            for name in (
                "architecture_state_boundary",
                "riverpod_listener_lifecycle",
                "autosave_flush_integrity",
                "resource_disposal",
                "firestore_query_index",
                "firestore_security_rules",
                "quiet_sync_ux",
                "localization_tone",
            ):
                report["checks"].append(
                    {
                        "name": name,
                        "status": "PASS",
                        "severity": "LOW",
                        "evidence": f"{name} objective test evidence",
                    }
                )
            path.write_text(json.dumps(report), encoding="utf-8")
            valid = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validate_ai_qa_report.py"), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(valid.returncode, 0, valid.stderr)


if __name__ == "__main__":
    unittest.main()
