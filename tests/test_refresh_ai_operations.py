from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import refresh_ai_operations  # noqa: E402


class RefreshAiOperationsTest(unittest.TestCase):
    def test_runs_allowlisted_steps_in_order_and_continues_after_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "data").mkdir()
            (root / "data/private_test_build_requests.json").write_text('{"requests": []}', encoding="utf-8")
            calls = []

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                if command[-1].endswith("generate_ai_manager_report.py"):
                    seen = json.loads((root / "data/ai_operations_refresh_status.json").read_text(encoding="utf-8"))
                    (root / "data/manager_seen.json").write_text(json.dumps(seen), encoding="utf-8")
                return SimpleNamespace(returncode=1 if len(calls) == 1 else 0, stdout="SECRET-OUTPUT", stderr="SECRET-ERROR")

            with patch.dict(os.environ, {
                "GMAIL_POLICY_REFRESH_DEVELOPER": "developer-secret",
                "GMAIL_POLICY_REFRESH_OFFICIAL": "official-secret",
            }, clear=False):
                result = refresh_ai_operations.run_refresh(root, runner)
            payload = json.loads((root / "data/ai_operations_refresh_status.json").read_text(encoding="utf-8"))
            seen = json.loads((root / "data/manager_seen.json").read_text(encoding="utf-8"))

        self.assertEqual(result, 1)
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(len(payload["steps"]), len(refresh_ai_operations.STEPS))
        self.assertEqual([item["script"] for item in payload["steps"]], list(refresh_ai_operations.STEPS))
        self.assertEqual(payload["steps"][0]["status"], "failed")
        self.assertEqual(payload["steps"][-1]["status"], "ok")
        self.assertEqual(payload["steps"][10]["status"], "not_applicable")
        self.assertNotIn("SECRET", json.dumps(payload))
        self.assertEqual(seen["steps"][-1]["status"], "ok")
        self.assertTrue(all(call[0][0] == sys.executable for call in calls))
        self.assertTrue(all("shell" not in call[1] for call in calls))

    def test_missing_gmail_tokens_are_unavailable_without_running_or_overwriting_sync(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "data").mkdir()
            (root / "data/private_test_build_requests.json").write_text('{"requests": []}', encoding="utf-8")
            calls = []

            def runner(command, **kwargs):
                calls.append(command[-1])
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.dict(os.environ, {}, clear=True):
                result = refresh_ai_operations.run_refresh(root, runner)
            payload = json.loads((root / "data/ai_operations_refresh_status.json").read_text(encoding="utf-8"))

        self.assertEqual(result, 1)
        gmail_steps = [item for item in payload["steps"] if item["script"] == "collect_gmail_policy_alerts.py"]
        self.assertEqual([item["status"] for item in gmail_steps], ["unavailable", "unavailable"])
        self.assertNotIn("collect_gmail_policy_alerts.py", calls)

    def test_store_version_manual_check_is_preserved_as_manual_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            (data / "store_versions.csv").write_text(
                "app_id,status\nAPP-0008,manual_check\n",
                encoding="utf-8",
            )
            self.assertEqual(
                refresh_ai_operations.semantic_status("check_store_versions.py", root),
                "manual_only",
            )
            (data / "store_versions.csv").write_text(
                "app_id,status\nAPP-0008,manual_check\nAPP-0007,failed\n",
                encoding="utf-8",
            )
            self.assertEqual(
                refresh_ai_operations.semantic_status("check_store_versions.py", root),
                "failed",
            )

    def test_manual_only_source_keeps_partial_audit_without_failing_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "data").mkdir()
            (root / "data/private_test_build_requests.json").write_text(
                '{"requests": []}',
                encoding="utf-8",
            )

            def runner(command, **kwargs):
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.dict(
                os.environ,
                {
                    "GMAIL_POLICY_REFRESH_DEVELOPER": "developer-secret",
                    "GMAIL_POLICY_REFRESH_OFFICIAL": "official-secret",
                },
                clear=False,
            ), patch.object(
                refresh_ai_operations,
                "semantic_status",
                side_effect=lambda script, root: "manual_only" if script == "check_store_versions.py" else "ok",
            ):
                result = refresh_ai_operations.run_refresh(root, runner)

            payload = json.loads(
                (root / "data/ai_operations_refresh_status.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result, 0)
        self.assertEqual(payload["status"], "partial")
        store_step = next(
            item for item in payload["steps"] if item["script"] == "check_store_versions.py"
        )
        self.assertEqual(store_step["status"], "manual_only")

    def test_semantic_ledgers_distinguish_not_released_and_failed_or_missing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            (data / "store_review_sync_status.json").write_text(json.dumps({"stores": [{"state": "not_released"}]}), encoding="utf-8")
            self.assertEqual(refresh_ai_operations.semantic_status("sync_store_reviews.py", root), "ok")
            (data / "os_update_watchlist.json").write_text(json.dumps({"sources": [{"status": "failed"}]}), encoding="utf-8")
            self.assertEqual(refresh_ai_operations.semantic_status("collect_os_updates.py", root), "failed")
            (data / "os_update_watchlist.json").unlink()
            self.assertEqual(refresh_ai_operations.semantic_status("collect_os_updates.py", root), "unavailable")


if __name__ == "__main__":
    unittest.main()
