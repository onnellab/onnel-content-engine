"""Daily Aether orchestration tests. No local production or network execution."""
from datetime import datetime
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_daily_local as module


KST = ZoneInfo("Asia/Seoul")


class CompilationSlot(unittest.TestCase):
    def test_asset_registration_failure_blocks_before_compilation_worker(self):
        report = {"blockers": [], "steps": []}
        blocked = json.dumps({
            "status": "blocked",
            "error": "aether_asset_approval_incomplete",
        })
        now = datetime(2026, 9, 27, 6, 20, tzinfo=KST)
        with patch.object(module, "run_step", return_value=(2, blocked, "")) as run:
            module.run_compilation_slot(report, now)

        self.assertEqual("aether_asset_approval_incomplete", report["compilation_slot"]["error"])
        self.assertEqual(["aether_asset_approval_incomplete"], report["blockers"])
        self.assertEqual(1, run.call_count)
        self.assertTrue(any(
            str(arg).endswith("aether_compilation_assets.py")
            for arg in run.call_args.args[2]
        ))


class RepositoryFreshness(unittest.TestCase):
    def test_initial_fetch_failure_blocks_before_cached_divergence_check(self):
        report = {"blockers": [], "steps": []}
        with patch.object(module, "run_step", side_effect=[
            (0, "", ""),
            (1, "", "offline"),
        ]) as run:
            self.assertFalse(module.repo_sync(report))

        self.assertEqual(["repo_fetch_failed"], report["blockers"])
        self.assertEqual(2, run.call_count)

    def test_ops_prewrite_fetch_failure_blocks_before_generators(self):
        report = {"blockers": [], "steps": [], "warnings": []}
        with patch.object(module, "run_step", side_effect=[
            (0, "", ""),
            (1, "", "offline"),
        ]) as run:
            module.publish_local_ops_sources(report)

        self.assertEqual(["ops_snapshot_fetch_failed"], report["blockers"])
        self.assertEqual(2, run.call_count)


class SingleSlotBoundary(unittest.TestCase):
    def report(self):
        return {"blockers": [], "steps": []}

    def test_exact_0900_blocks_without_worker_call(self):
        report = self.report()
        now = datetime(2026, 9, 29, 9, 0, tzinfo=KST)
        with patch.object(module, "now_kst", return_value=now), \
             patch.object(module, "run_step") as run:
            module.run_single_slot(report, {"status": "idle"})

        self.assertEqual(
            {"status": "blocked", "error": "aether_single_publish_time_stale"},
            report["single_slot"],
        )
        self.assertEqual(["aether_single_publish_time_stale"], report["blockers"])
        run.assert_not_called()

    def test_crossing_0900_stops_before_second_backlog_publish_call(self):
        report = self.report()
        times = [
            datetime(2026, 9, 29, 8, 59, 58, tzinfo=KST),
            datetime(2026, 9, 29, 8, 59, 59, tzinfo=KST),
            datetime(2026, 9, 29, 9, 0, 0, tzinfo=KST),
        ]

        first = json.dumps({"status": "already_public"})
        with patch.object(module, "now_kst", side_effect=times), \
             patch.object(module, "run_step", return_value=(0, first, "")) as run:
            module.run_single_slot(report, {"status": "idle"})

        self.assertEqual(1, run.call_count)
        self.assertEqual("aether_single_publish_time_stale", report["single_slot"]["error"])
        self.assertEqual(["aether_single_publish_time_stale"], report["blockers"])

    def test_fresh_slot_date_is_passed_to_backlog_worker(self):
        report = self.report()
        now = datetime(2026, 9, 29, 8, 30, tzinfo=KST)
        payload = json.dumps({"status": "scheduled", "video_id": "test-video"})
        with patch.object(module, "now_kst", return_value=now), \
             patch.object(module, "sync_playlists_after_upload"), \
             patch.object(module, "run_step", return_value=(0, payload, "")) as run:
            module.run_single_slot(report, {"status": "idle"})

        args = run.call_args.args[2]
        self.assertIn("--slot", args)
        self.assertEqual("2026-09-29", args[args.index("--slot") + 1])
        self.assertEqual("scheduled", report["single_slot"]["status"])


if __name__ == "__main__":
    unittest.main()
