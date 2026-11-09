"""Durable daily-result regressions; all commands are mocked, state is temporary."""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_daily_local as worker


class DailyResultTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.result = self.root / "result.json"
        for name, value in (("STATE", self.root), ("RESULT", self.result),
                            ("LOCK", self.root / "worker.lock")):
            self.stack.enter_context(patch.object(worker, name, value))
        self.run = self.stack.enter_context(patch.object(
            worker.subprocess, "run", side_effect=AssertionError("external execution forbidden")))
        self.stack.enter_context(patch.object(sys, "argv", ["aether_daily_local.py"]))

    def report(self, mode="daily"):
        return {"schema_version": 1, "kind": "onnellab_aether_local_daily_result",
                "mode": mode, "local_date": "2026-09-28", "state": "running",
                "started_at": "2026-09-28T06:20:05+09:00",
                "steps": [], "blockers": [], "warnings": []}

    def test_timeout_bytes_are_serializable_and_preserve_prior_evidence(self):
        report = self.report()
        report["video_id"] = "test-only-video"
        self.run.side_effect = subprocess.TimeoutExpired(
            ["never-executed"], 1, output=b'{"job_id":"test-job"}\n\xff')
        code, stdout, stderr = worker.run_step(report, "fixture", ["never-executed"])
        self.assertEqual(124, code)
        self.assertIsInstance(stdout, str)
        self.assertIn("test-job", stdout)
        self.assertEqual("local_worker_timeout", stderr)
        saved = json.loads(self.result.read_text())
        self.assertEqual("test-only-video", saved["video_id"])
        self.assertEqual(124, saved["steps"][-1]["exit_code"])

    def test_unstartable_command_records_safe_failure_without_retry(self):
        self.run.side_effect = FileNotFoundError("sensitive-exception-payload")
        code, _, stderr = worker.run_step(self.report(), "fixture", ["never-executed"])
        self.assertEqual(127, code)
        self.assertEqual("local_worker_start_failed:FileNotFoundError", stderr)
        self.assertNotIn("sensitive-exception-payload", self.result.read_text())
        self.assertEqual(1, self.run.call_count)

    def test_active_step_is_durable_before_command_starts(self):
        def inspect_checkpoint(*args, **kwargs):
            saved = json.loads(self.result.read_text())
            self.assertEqual("fixture", saved["active_step"]["name"])
            return subprocess.CompletedProcess(args[0], 0, "ok", "")
        self.run.side_effect = inspect_checkpoint
        worker.run_step(self.report(), "fixture", ["never-executed"])
        saved = json.loads(self.result.read_text())
        self.assertNotIn("active_step", saved)
        self.assertEqual("fixture", saved["steps"][-1]["name"])

    def test_probe_cannot_overwrite_authoritative_daily_result(self):
        worker.save(self.report())
        original = self.result.read_bytes()
        worker.save(self.report("probe"))
        self.assertEqual(original, self.result.read_bytes())
        probe = json.loads((self.root / "probe-result.json").read_text())
        self.assertEqual("probe", probe["mode"])
        self.assertEqual(0o600, (self.result.stat().st_mode & 0o777))
        self.assertEqual(0o600, ((self.root / "probe-result.json").stat().st_mode & 0o777))

    def test_sleep_continuation_cannot_overwrite_authoritative_daily_result(self):
        worker.save(self.report())
        original = self.result.read_bytes()
        sleep_report = self.report("sleep")
        sleep_report.update(kind="onnellab_aether_local_sleep_result",
                            sleep_slot={"job_id": "fixture-sleep", "status": "blocked"})
        worker.save(sleep_report)
        self.assertEqual(original, self.result.read_bytes())
        separate = self.root / "sleep-result.json"
        saved = json.loads(separate.read_text())
        self.assertEqual("fixture-sleep", saved["sleep_slot"]["job_id"])
        self.assertEqual(0o600, separate.stat().st_mode & 0o777)

    def test_json_stdout_accepts_only_objects(self):
        for value in ("[]", "null", '"text"', "7", "true", None):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                worker.json_stdout(value)
        self.assertEqual({}, worker.json_stdout("not-json"))
        self.assertEqual({"status": "ok"}, worker.json_stdout('{"status":"ok"}'))

    def test_exception_retains_ids_steps_blockers_and_original_date(self):
        evidence = {
            "hosted_workflows": {"store_reviews": {"run_id": "123456"}},
            "store_review_auto_replies": {"queued": [{"approval_id": "test-approval",
                                                       "review_id": "test-review"}]},
            "single_slot": {"job_id": "test-job", "video_id": "test-video"},
            "active_step": {"name": "fixture"},
        }
        started = {}
        def fail_after_evidence(report):
            started.update({k: report[k] for k in ("started_at", "local_date", "mode")})
            report.update(evidence)
            report["steps"].append({"name": "fixture_done", "exit_code": 0})
            report["blockers"].append("fixture_existing_blocker")
            report["warnings"].append("fixture_warning")
            raise RuntimeError("sensitive-exception-payload")
        with patch.object(worker, "repo_sync", return_value=True), \
             patch.object(worker, "run_reconcile", return_value={"status": "idle"}), \
             patch.object(worker, "run_single_slot"), \
             patch.object(worker, "run_sleep_slot"), \
             patch.object(worker, "run_compilation_slot"), \
             patch.object(worker, "run_youtube_reports", side_effect=fail_after_evidence), \
             patch.object(worker, "publish_local_ops_sources") as publish, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(2, worker.main())
        saved = json.loads(self.result.read_text())
        for key, value in {**evidence, **started}.items():
            self.assertEqual(value, saved[key], key)
        self.assertEqual("failed", saved["state"])
        self.assertEqual(["fixture_existing_blocker", "local_worker_exception:RuntimeError"], saved["blockers"])
        self.assertEqual(["fixture_warning"], saved["warnings"])
        self.assertEqual("fixture_done", saved["steps"][0]["name"])
        self.assertNotIn("sensitive-exception-payload", self.result.read_text())
        publish.assert_not_called()
        self.run.assert_not_called()

    def scheduled_pass(self, *, hosted_success=True, repo_ready=True, probe=False):
        """Run real orchestration/slot selection with fictional time and workers.

        subprocess.run is already forbidden by setUp; no queue, provider,
        credential, renderer, real clock or daily result is touched.
        """
        from datetime import datetime
        from zoneinfo import ZoneInfo
        clock = [datetime(2026, 11, 7, 6, 20, tzinfo=ZoneInfo("Asia/Seoul"))]
        events = []
        concept = {"title": "Fixture Sailing", "lane": "open_sea_voyage", "style": "Fixture only"}

        def repo(report):
            events.append("repo")
            if not repo_ready:
                report["blockers"].append("repo_fetch_failed")
            return repo_ready

        def step(report, name, argv, **kwargs):
            events.append(name)
            if name.startswith("backlog_"):
                return 0, json.dumps({"status": "already_public"}), ""
            if name == "new_lyria_single":
                self.assertLess(clock[0].hour, 8)
                self.assertEqual("2026-11-07", argv[argv.index("--slot") + 1])
                return 0, json.dumps({"status": "scheduled", "job_id": "fixture-job",
                    "video_id": "fixture-video", "slot": "2026-11-07", "publication_complete": False,
                    "publish_at": "2026-11-07T00:00:00Z"}), ""
            if name == "post_ops_repo_status":
                return 0, "", ""
            if name in {"single_readiness_probe", "compilation_readiness_probe"}:
                return 0, json.dumps({"dry_run": True}), ""
            self.fail("Unexpected side effect: " + name)

        def hosted(report):
            events.append("hosted")
            # Even a queue delay lasting past the publishing boundary must not
            # prevent the already finished time-critical production stage.
            clock[0] = clock[0].replace(hour=10)
            if not hosted_success:
                report["blockers"].append("fixture_hosted_unavailable")
            return hosted_success

        def reports(report):
            events.append("reports")
            if not probe:
                self.assertEqual("fixture-video", report["single_slot"]["video_id"])

        def reconcile(report):
            events.append("reconcile")
            return {"status": "idle"}

        def compilation(report, now):
            events.append("compilation")
            report["compilation_slot"] = {"status": "not_scheduled_today"}

        with patch.object(worker, "now_kst", side_effect=lambda: clock[0]), \
             patch.object(worker, "repo_sync", side_effect=repo), \
             patch.object(worker, "run_step", side_effect=step), \
             patch.object(worker, "run_reconcile", side_effect=reconcile), \
             patch.object(worker, "run_compilation_slot", side_effect=compilation), \
             patch.object(worker, "check_new_single_inputs", return_value={"provider_base_price_usd": "0.08"}), \
             patch.object(worker, "choose_approved_new_single", return_value=concept), \
             patch.object(worker, "sync_playlists_after_upload", side_effect=lambda r: events.append("playlists")), \
             patch.object(worker, "run_youtube_reports", side_effect=reports), \
             patch.object(worker, "publish_local_ops_sources", side_effect=lambda r: events.append("snapshot")), \
             patch.object(worker, "run_hosted_ops_workflows", side_effect=hosted), \
             patch.object(worker, "run_store_review_auto_replies", side_effect=lambda r: events.append("reviews")), \
             patch.object(worker, "run_ops_dashboard_deploy", side_effect=lambda r: events.append("deploy")), \
             patch.object(sys, "argv", ["aether_daily_local.py"] + (["--probe"] if probe else [])), \
             redirect_stdout(io.StringIO()):
            code = worker.main()
        path = self.root / "probe-result.json" if probe else self.result
        self.run.assert_not_called()
        return code, events, json.loads(path.read_text())

    def test_hosted_delay_cannot_consume_music_deadline_and_snapshot_is_after_music(self):
        code, events, result = self.scheduled_pass()
        self.assertEqual(0, code)
        self.assertEqual("scheduled", result["single_slot"]["status"])
        self.assertFalse(result["single_slot"]["publication_complete"])
        self.assertEqual(1, events.count("new_lyria_single"))
        order = ["reconcile", "new_lyria_single", "playlists", "compilation", "reports", "snapshot", "hosted", "reviews", "deploy"]
        self.assertEqual(sorted(events.index(x) for x in order), [events.index(x) for x in order])
        self.assertEqual("aether_before_reporting_and_hosted_ops", result["execution_order"])

    def test_hosted_failure_preserves_music_ids_without_second_attempt(self):
        code, events, result = self.scheduled_pass(hosted_success=False)
        self.assertEqual(2, code)
        self.assertEqual("partial", result["state"])
        self.assertEqual("fixture-video", result["single_slot"]["video_id"])
        self.assertEqual(1, events.count("new_lyria_single"))
        self.assertNotIn("reviews", events)
        self.assertNotIn("deploy", events)
        self.assertEqual(["fixture_hosted_unavailable"], result["blockers"])
        original = self.result.read_bytes()
        # Same-day relaunch must not repeat either production or hosted work.
        code, events, again = self.scheduled_pass(hosted_success=False)
        self.assertEqual(2, code)
        self.assertEqual([], events)
        self.assertEqual(original, self.result.read_bytes())

    def test_priority_does_not_bypass_repository_check(self):
        code, events, result = self.scheduled_pass(repo_ready=False)
        self.assertEqual(2, code)
        self.assertEqual(["repo"], events)
        self.assertEqual(["repo_fetch_failed"], result["blockers"])

    def test_probe_remains_nonproducing_after_reorder(self):
        code, events, result = self.scheduled_pass(probe=True)
        self.assertEqual(0, code)
        self.assertEqual(["repo", "reports", "single_readiness_probe", "compilation_readiness_probe"], events)
        self.assertFalse(self.result.exists())
        self.assertNotIn("single_slot", result)

    def test_lock_failure_does_not_clobber_existing_result(self):
        worker.save(self.report())
        original = self.result.read_bytes()
        with patch.object(worker.os, "fchmod", side_effect=PermissionError("fixture")), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(2, worker.main())
        self.assertEqual(original, self.result.read_bytes())
        self.run.assert_not_called()

    def test_busy_lock_preserves_result_without_replacement_worker(self):
        worker.save(self.report())
        original = self.result.read_bytes()
        with patch.object(worker.fcntl, "flock", side_effect=BlockingIOError()), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(3, worker.main())
        self.assertEqual(original, self.result.read_bytes())
        self.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()

