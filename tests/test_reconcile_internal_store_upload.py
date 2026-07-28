from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reconcile_internal_store_upload.py"


class ReconcileInternalStoreUploadTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "data").mkdir()
        shutil.copy2(SOURCE_SCRIPT, self.root / "scripts" / SOURCE_SCRIPT.name)
        self.write(
            "private_test_orchestrations.json",
            {
                "orchestrations": [
                    {
                        "orchestration_id": "PTO-1",
                        "task_id": "ACT-1",
                        "release_id": "REL-1",
                        "platform": "android",
                        "approver": "first",
                        "status": "failed",
                        "failure": "upload_dispatched_timeout",
                    }
                ]
            },
        )
        self.write(
            "internal_test_readiness.json",
            {
                "records": [
                    {
                        "release_id": "REL-1",
                        "provider": "google_play",
                        "identifier": "com.onnellab.test",
                        "checksum_sha256": "a" * 64,
                        "status": "ready_for_internal_upload",
                    }
                ]
            },
        )
        self.write("internal_store_submissions.json", {"submissions": []})
        self.write("internal_store_upload_reconciliations.json", {"reconciliations": []})

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, name: str, value: object) -> None:
        (self.root / "data" / name).write_text(json.dumps(value), encoding="utf-8")

    def read(self, name: str) -> dict:
        return json.loads((self.root / "data" / name).read_text(encoding="utf-8"))

    def run_script(
        self,
        outcome: str,
        evidence_url: str = "https://play.google.com/console/u/0/developers/1",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(self.root / "scripts" / SOURCE_SCRIPT.name),
                "PTO-1",
                "--outcome",
                outcome,
                "--approver",
                "owner",
                "--evidence-url",
                evidence_url,
                "--run-url",
                "https://github.com/onnellab/ops/actions/runs/1",
            ],
            text=True,
            capture_output=True,
        )

    def test_uploaded_records_audit_and_completes(self) -> None:
        result = self.run_script("uploaded")
        self.assertEqual(result.returncode, 0, result.stderr)
        orchestration = self.read("private_test_orchestrations.json")["orchestrations"][0]
        submission = self.read("internal_store_submissions.json")["submissions"][0]
        self.assertEqual(orchestration["status"], "completed")
        self.assertNotIn("failure", orchestration)
        self.assertEqual(submission["source"], "store_console_reconciliation")
        self.assertEqual(submission["checksum_sha256"], "a" * 64)

    def test_not_uploaded_returns_only_to_upload_stage(self) -> None:
        result = self.run_script("not_uploaded")
        self.assertEqual(result.returncode, 0, result.stderr)
        orchestration = self.read("private_test_orchestrations.json")["orchestrations"][0]
        self.assertEqual(orchestration["status"], "readiness_dispatched")
        self.assertEqual(self.read("internal_store_submissions.json")["submissions"], [])

    def test_rejects_non_console_evidence(self) -> None:
        result = self.run_script("uploaded", "https://example.com/screenshot")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("store-console", result.stderr)
        self.assertEqual(self.read("internal_store_submissions.json")["submissions"], [])

    def test_rejects_non_upload_timeout_failure(self) -> None:
        payload = self.read("private_test_orchestrations.json")
        payload["orchestrations"][0]["failure"] = "private_test_build_failed"
        self.write("private_test_orchestrations.json", payload)
        result = self.run_script("not_uploaded")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("only an upload_dispatched_timeout", result.stderr)

    def test_allows_a_second_not_uploaded_reconciliation_after_another_timeout(self) -> None:
        first = self.run_script("not_uploaded")
        self.assertEqual(first.returncode, 0, first.stderr)
        payload = self.read("private_test_orchestrations.json")
        payload["orchestrations"][0]["status"] = "failed"
        payload["orchestrations"][0]["failure"] = "upload_dispatched_timeout"
        self.write("private_test_orchestrations.json", payload)
        second = self.run_script("not_uploaded")
        self.assertEqual(second.returncode, 0, second.stderr)
        reconciliations = self.read("internal_store_upload_reconciliations.json")["reconciliations"]
        self.assertEqual(len(reconciliations), 2)


if __name__ == "__main__":
    unittest.main()
