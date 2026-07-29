from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_incidents
import prepare_ai_doctor_context
import record_ai_doctor_diagnosis


class AiDoctorAutomationTest(unittest.TestCase):
    def init_app(self, root: Path) -> Path:
        app = root / "app"
        (app / "lib").mkdir(parents=True)
        (app / "test").mkdir()
        (app / "pubspec.yaml").write_text("name: sample\n", encoding="utf-8")
        (app / "lib" / "large_file_reader.dart").write_text(
            "class LargeFileReader { void openDocument() {} }\n", encoding="utf-8"
        )
        (app / "test" / "large_file_reader_test.dart").write_text(
            "void main() { /* openDocument regression */ }\n", encoding="utf-8"
        )
        (app / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(app)], check=True)
        subprocess.run(["git", "-C", str(app), "config", "user.name", "test"], check=True)
        subprocess.run(["git", "-C", str(app), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(app), "add", "."], check=True)
        subprocess.run(["git", "-C", str(app), "commit", "-qm", "Add large file reader"], check=True)
        return app

    def test_context_contains_recent_commit_rules_and_candidate_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            app = self.init_app(root)
            (data / "ai_doctor_findings.json").write_text(
                json.dumps(
                    {
                        "findings": [
                            {
                                "finding_id": "github-sample-1",
                                "app_slug": "sample",
                                "diagnosis_status": "pending",
                                "github_issue": {"title": "openDocument large file failure"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (data / "local_repositories.csv").write_text(
                "app_id,app_slug,repository_name,path,pubspec_path,source_priority,notes\n"
                f"APP-1,sample,sample,{app},pubspec.yaml,primary,test\n",
                encoding="utf-8",
            )
            with patch.object(prepare_ai_doctor_context, "DATA", data):
                packet = prepare_ai_doctor_context.prepare("github-sample-1")

        self.assertEqual(packet["entry_rules"], ["AGENTS.md"])
        self.assertEqual(len(packet["recent_commits"]), 1)
        self.assertIn("lib/large_file_reader.dart", packet["candidate_files"])
        self.assertIn("test/large_file_reader_test.dart", packet["candidate_files"])

    def test_context_rejects_unsafe_finding_id(self) -> None:
        with self.assertRaisesRegex(SystemExit, "finding ID is invalid"):
            prepare_ai_doctor_context.prepare("../finding")

    def test_analyzer_creates_github_finding_and_preserves_diagnosis(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            (data / "store_reviews.csv").write_text("review_id,app_slug,app_version\n", encoding="utf-8")
            (data / "store_review_triage.json").write_text('{"items":[]}', encoding="utf-8")
            (data / "github_issues.json").write_text(
                json.dumps(
                    {
                        "issues": [
                            {
                                "app_slug": "sample",
                                "number": 7,
                                "title": "Crash when opening a large file",
                                "labels": ["bug"],
                                "status": "open",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (data / "ai_doctor_findings.json").write_text(
                json.dumps(
                    {
                        "findings": [
                            {
                                "finding_id": "github-sample-7",
                                "diagnosis_status": "STOP",
                                "diagnosis": {"status": "STOP"},
                                "diagnosed_at": "2026-07-27T00:00:00+00:00",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(analyze_incidents, "ROOT", root):
                self.assertEqual(analyze_incidents.main(), 0)
            finding = json.loads((data / "ai_doctor_findings.json").read_text())["findings"][0]

        self.assertEqual(finding["origin"], "github_issue")
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["diagnosis_status"], "STOP")

    def test_records_only_evidence_backed_diagnosis(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            (data / "ai_doctor_findings.json").write_text(
                '{"findings":[{"finding_id":"finding-1","diagnosis_status":"pending"}]}',
                encoding="utf-8",
            )
            report = root / "report.json"
            report.write_text(
                json.dumps(
                    {
                        "finding_id": "finding-1",
                        "status": "DIAGNOSED",
                        "hypotheses": ["Parser retains the entire input"],
                        "evidence": ["lib/parser.dart:Parser.open"],
                        "reproduction": "test/parser_large_file_test.dart",
                        "expected_result": "Large files open without retaining the entire input.",
                        "recommended_scope": ["lib/parser.dart"],
                        "verification_commands": ["flutter test test/parser_large_file_test.dart"],
                        "performance_baseline": "Parser memory benchmark must not regress.",
                        "completion_criteria": "Regression test and existing parser tests pass.",
                        "risk_class": "YELLOW",
                        "risk": "memory pressure",
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(record_ai_doctor_diagnosis, "ROOT", root), patch.object(
                sys, "argv", ["record_ai_doctor_diagnosis.py", "finding-1", "--report", str(report)]
            ):
                self.assertEqual(record_ai_doctor_diagnosis.main(), 0)
            finding = json.loads((data / "ai_doctor_findings.json").read_text())["findings"][0]
            audit = data / "ai_doctor_diagnoses" / "finding-1.json"
            audit_exists = audit.is_file()

        self.assertEqual(finding["diagnosis_status"], "DIAGNOSED")
        self.assertTrue(audit_exists)

    def test_local_cycle_runs_doctor_read_only_before_coder_generation(self) -> None:
        script = (ROOT / "scripts" / "run_local_ai_scout_cycle.sh").read_text()
        doctor = (ROOT / "scripts" / "run_codex_doctor.sh").read_text()

        self.assertIn('run_codex_doctor.sh "$finding_id" --execute', script)
        self.assertLess(script.index("run_codex_doctor.sh"), script.index("generate_ai_coder_tasks.py"))
        self.assertIn("git ls-files --others --exclude-standard", script)
        self.assertIn("codex exec -s read-only", doctor)
        self.assertNotIn("git commit", doctor)
        self.assertNotIn("git push", doctor)


if __name__ == "__main__":
    unittest.main()
