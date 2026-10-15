from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_local_qa_report import assemble
from validate_ai_qa_report import PROFILE_CHECKS, REQUIRED_CHECKS


class QaFixtures:
    def packet(self) -> dict:
        return {
            "task": {"task_id": "finding-1", "repository": "onnellab/sample",
                     "pr_url": "https://github.com/onnellab/sample/pull/1", "commit": "a" * 40},
            "qa_profile": "default", "ios_device_required": False,
            "source_integrity": "passed",
            "command_results": {"flutter_analyze": "passed", "flutter_test": "passed",
                                "performance": "passed"},
            "command_exit_codes": {"flutter_analyze": 0, "flutter_test": 0, "performance": 0},
        }

    def review(self, packet: dict) -> dict:
        report = dict(packet["task"], qa_profile=packet["qa_profile"], tests="passed",
                      static_analysis="passed", performance="passed", build="passed",
                      risk="Fixture reviewed.", rollback="Revert the fixture commit.")
        names = REQUIRED_CHECKS | PROFILE_CHECKS.get(packet["qa_profile"], set())
        report["checks"] = [{"name": name, "status": "PASS", "severity": "LOW",
                             "evidence": f"Fixture evidence for {name}."} for name in sorted(names)]
        return report

class LocalQaReportTests(QaFixtures, unittest.TestCase):
    def test_absent_review_preserves_unknown_build_and_all_stop_checks(self) -> None:
        report = assemble(self.packet())
        self.assertEqual(report["tests"], "passed")
        self.assertEqual(report["build"], "not_run")
        self.assertFalse(report["review_evidence_supplied"])
        self.assertEqual({x["status"] for x in report["checks"]}, {"STOP"})
        self.assertEqual({x["name"] for x in report["checks"]}, REQUIRED_CHECKS)

    def test_local_failures_override_review(self) -> None:
        packet = self.packet()
        for field, command, status in (("tests", "flutter_test", "failed"),
                                       ("static_analysis", "flutter_analyze", "failed"),
                                       ("performance", "performance", "not_configured")):
            with self.subTest(command=command):
                changed = copy.deepcopy(packet)
                changed["command_results"][command] = status
                report = assemble(changed, self.review(packet))
                self.assertEqual(report[field], status)

    def test_review_identity_must_match(self) -> None:
        packet = self.packet()
        for key in ("task_id", "repository", "pr_url", "commit", "qa_profile"):
            with self.subTest(key=key):
                review = self.review(packet)
                review[key] = "different"
                with self.assertRaisesRegex(ValueError, key):
                    assemble(packet, review)

    def test_missing_profile_check_is_stop(self) -> None:
        packet = self.packet()
        packet["qa_profile"] = "flutter_riverpod_firestore_autosave_v1"
        review = self.review(packet)
        review["checks"] = [x for x in review["checks"] if x["name"] != "autosave_flush_integrity"]
        report = assemble(packet, review)
        self.assertEqual(next(x for x in report["checks"] if x["name"] == "autosave_flush_integrity")["status"], "STOP")

    def test_supplied_fail_and_stop_are_not_upgraded(self) -> None:
        packet = self.packet()
        review = self.review(packet)
        review["checks"][0]["status"] = "FAIL"
        review["checks"][1]["status"] = "STOP"
        result = assemble(packet, review)
        self.assertEqual(result["checks"][0]["status"], "FAIL")
        self.assertEqual(result["checks"][1]["status"], "STOP")
        self.assertEqual(review["checks"][0]["status"], "FAIL")

    def test_missing_device_evidence_never_passes(self) -> None:
        packet = self.packet()
        packet["ios_device_required"] = True
        for device in (None, {}, {"status": "FAIL"}, {"status": "STOP"},
                       {"status": "PASS", "task_id": "other", "device_id": "physical", "evidence": "run"}):
            with self.subTest(device=device):
                packet["ios_device_report"] = device
                report = assemble(packet, self.review(packet))
                self.assertEqual(next(x for x in report["checks"] if x["name"] == "ios_device_risk")["status"], "STOP")

    def test_device_pass_does_not_create_missing_source_review(self) -> None:
        packet = self.packet()
        packet.update(ios_device_required=True, ios_device_report={
            "status": "PASS", "task_id": "finding-1", "commit": "a" * 40,
            "device_id": "physical", "evidence": "run"})
        report = assemble(packet)
        self.assertEqual(next(x for x in report["checks"] if x["name"] == "ios_device_risk")["status"], "STOP")
        reviewed = assemble(packet, self.review(packet))
        self.assertEqual(next(x for x in reviewed["checks"] if x["name"] == "ios_device_risk")["status"], "PASS")

    def test_legacy_or_stale_device_pass_stays_stop(self) -> None:
        packet = self.packet()
        packet["ios_device_required"] = True
        for commit in (None, "b" * 40):
            with self.subTest(commit=commit):
                device = {"status": "PASS", "task_id": "finding-1",
                          "device_id": "physical", "evidence": "previous run"}
                if commit is not None:
                    device["commit"] = commit
                packet["ios_device_report"] = device
                report = assemble(packet, self.review(packet))
                self.assertEqual(next(x for x in report["checks"] if x["name"] == "ios_device_risk")["status"], "STOP")

    def test_source_change_blocks_review_pass(self) -> None:
        packet = self.packet()
        packet["source_integrity"] = "unverified"
        report = assemble(packet, self.review(packet))
        self.assertEqual(next(x for x in report["checks"] if x["name"] == "recent_change_compliance")["status"], "STOP")

    def test_malformed_and_duplicate_checks_are_rejected(self) -> None:
        packet = self.packet()
        for checks in (None, [None], [{"name": "x", "status": "PASS", "evidence": ""}],
                       [{"name": "x", "status": "SKIP", "evidence": "text"}],
                       [{"name": "x", "status": "PASS", "evidence": "text"}] * 2):
            with self.subTest(checks=checks):
                review = self.review(packet)
                review["checks"] = checks
                with self.assertRaises(ValueError):
                    assemble(packet, review)


class LocalQaRunnerTests(QaFixtures, unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.engine = self.base / "engine"
        self.app = self.base / "app"
        self.binary = self.base / "bin"
        self.tmp = self.base / "tmp"
        for path in (self.engine / "scripts", self.engine / "data", self.app / "tool", self.binary, self.tmp):
            path.mkdir(parents=True, exist_ok=True)
        for name in ("run_codex_qa_report.sh", "assemble_local_qa_report.py", "validate_ai_qa_report.py"):
            shutil.copyfile(ROOT / "scripts" / name, self.engine / "scripts" / name)
        (self.app / "pubspec.yaml").write_text("name: sample\n")
        (self.app / "tool/performance_gate.sh").write_text("#!/bin/sh\nexit ${PERFORMANCE_EXIT:-0}\n")
        for args in (("init", "-q"), ("config", "user.name", "Fixture"),
                     ("config", "user.email", "fixture@example.invalid"), ("add", "."),
                     ("commit", "-qm", "fixture")):
            subprocess.run(["git", "-C", str(self.app), *args], check=True, capture_output=True)
        self.head = subprocess.check_output(["git", "-C", str(self.app), "rev-parse", "HEAD"], text=True).strip()
        self.task = dict(self.packet()["task"], commit=self.head, app_slug="sample", status="draft_pr_created")
        self.write_task()
        (self.engine / "data/local_repositories.csv").write_text(f"app_slug,path,pubspec_path\nsample,{self.app},pubspec.yaml\n")
        (self.engine / "data/apps_registry.csv").write_text("slug,platforms\nsample,android\n")
        for name, body in {
            "flutter": 'printf "flutter %s\\n" "$1" >> "$COMMAND_LOG"\nif [ "${MUTATE_SOURCE:-0}" = 1 ]; then echo changed >> pubspec.yaml; fi\ncase "$1" in analyze) exit ${ANALYZE_EXIT:-0};; test) exit ${TEST_EXIT:-0};; esac\n',
            "codex": 'echo "PAID CODEX INVOKED" >> "$COMMAND_LOG"\nexit 99\n',
        }.items():
            path = self.binary / name
            path.write_text("#!/bin/sh\n" + body)
            path.chmod(0o755)
        self.log = self.base / "commands.log"
        self.environment = dict(os.environ, PATH=f"{self.binary}:{os.environ['PATH']}",
                                COMMAND_LOG=str(self.log), TMPDIR=str(self.tmp))
        self.report_path = self.engine / "data/qa-reports/finding-1.json"

    def write_task(self) -> None:
        (self.engine / "data/ai_coder_tasks.json").write_text(json.dumps({"tasks": [self.task]}))

    def run_runner(self, *, reviewed: bool = False, extra: dict | None = None) -> subprocess.CompletedProcess:
        args = ["bash", str(self.engine / "scripts/run_codex_qa_report.sh"), "finding-1"]
        if reviewed:
            packet = self.packet()
            packet["task"] = self.task
            review_path = self.base / "review.json"
            review_path.write_text(json.dumps(self.review(packet)))
            args.extend(["--review-report", str(review_path)])
        result = subprocess.run(args, env=dict(self.environment, **(extra or {})), text=True,
                                capture_output=True, check=False)
        if self.log.exists():
            self.assertNotIn("CODEX", self.log.read_text())
        self.assertEqual(list(self.tmp.iterdir()), [], "temporary command logs must be cleaned")
        return result

    def test_runner_without_review_writes_stop_without_paid_cli(self) -> None:
        result = self.run_runner()
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(self.report_path.read_text())
        self.assertEqual(report["build"], "not_run")
        self.assertEqual(self.log.read_text().splitlines(), ["flutter analyze", "flutter test"])
        self.assertEqual({x["status"] for x in report["checks"]}, {"STOP"})

    def test_runner_passes_with_matching_review_and_free_commands(self) -> None:
        result = self.run_runner(reviewed=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(self.report_path.read_text())
        self.assertEqual(report["commit"], self.head)
        self.assertEqual(len(report["review_evidence_sha256"]), 64)

    def test_runner_free_command_failure_cannot_be_overridden(self) -> None:
        for var, field in (("ANALYZE_EXIT", "static_analysis"), ("TEST_EXIT", "tests"),
                           ("PERFORMANCE_EXIT", "performance")):
            with self.subTest(var=var):
                result = self.run_runner(reviewed=True, extra={var: "2"})
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(json.loads(self.report_path.read_text())[field], "failed")

    def test_runner_missing_performance_is_not_configured(self) -> None:
        (self.app / "tool/performance_gate.sh").unlink()
        subprocess.run(["git", "-C", str(self.app), "add", "-u"], check=True)
        subprocess.run(["git", "-C", str(self.app), "commit", "-qm", "No performance gate"], check=True)
        self.task["commit"] = subprocess.check_output(["git", "-C", str(self.app), "rev-parse", "HEAD"], text=True).strip()
        self.write_task()
        result = self.run_runner(reviewed=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(self.report_path.read_text())["performance"], "not_configured")

    def test_runner_wrong_commit_stops_before_any_command(self) -> None:
        self.task["commit"] = "b" * 40
        self.write_task()
        result = self.run_runner(reviewed=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HEAD must match", result.stderr)
        self.assertFalse(self.log.exists())

    def test_runner_dirty_checkout_stops_before_any_command(self) -> None:
        (self.app / "pubspec.yaml").write_text("name: modified\n")
        result = self.run_runner(reviewed=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checkout must be clean", result.stderr)
        self.assertFalse(self.log.exists())

    def test_runner_source_mutation_during_checks_is_stop(self) -> None:
        result = self.run_runner(reviewed=True, extra={"MUTATE_SOURCE": "1"})
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(self.report_path.read_text())
        self.assertEqual(next(x for x in report["checks"] if x["name"] == "recent_change_compliance")["status"], "STOP")

    def test_runner_deferred_ios_device_checks_stay_stop(self) -> None:
        (self.engine / "data/apps_registry.csv").write_text("slug,platforms\nsample,ios|android\n")
        result = self.run_runner(reviewed=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(self.report_path.read_text())
        self.assertEqual(next(x for x in report["checks"] if x["name"] == "ios_device_risk")["status"], "STOP")


if __name__ == "__main__":
    unittest.main()
