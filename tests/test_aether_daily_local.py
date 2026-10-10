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

    def test_lyria_fallback_only_after_all_backlog_tracks_confirmed_public(self):
        report = self.report()
        now = datetime(2026, 10, 13, 6, 35, tzinfo=KST)
        concept = {
            "title": "Sails Above the Silver Cloud Sea",
            "style": "Skybound travel with warm strings",
            "lane": "skybound_flight",
        }
        calls = []
        def fake_step(_report, name, args, **kwargs):
            calls.append((name, args))
            if name.startswith("backlog_"):
                return 0, json.dumps({"status": "already_public"}), ""
            self.assertEqual("new_lyria_single", name)
            return 0, json.dumps({
                "status": "scheduled", "source_kind": "new_lyria",
                "title": concept["title"], "video_id": "existing-private-id",
                "estimated_cost_usd": 0.08, "generation_count": 1,
            }), ""
        with patch.object(module, "now_kst", return_value=now), \
             patch.object(module, "choose_approved_new_single", return_value=concept) as choose, \
             patch.object(module, "sync_playlists_after_upload") as playlists, \
             patch.object(module, "run_step", side_effect=fake_step):
            module.run_single_slot(report, {"status": "idle"})
        choose.assert_called_once_with()
        self.assertEqual(len(module.BACKLOG) + 1, len(calls))
        self.assertEqual("worker", calls[-1][1][3])
        self.assertEqual("2026-10-13", calls[-1][1][calls[-1][1].index("--slot") + 1])
        self.assertIn("--publish", calls[-1][1])
        self.assertEqual("scheduled", report["single_slot"]["status"])
        self.assertEqual(0.08, report["single_slot"]["estimated_cost_usd"])
        playlists.assert_called_once()
        self.assertEqual([], report["blockers"])

    def test_backlog_remains_canonical_without_lyria_fallback(self):
        report = self.report()
        now = datetime(2026, 10, 13, 6, 30, tzinfo=KST)
        with patch.object(module, "now_kst", return_value=now), \
             patch.object(module, "run_step", return_value=(2, json.dumps({
                 "status": "blocked", "error": "aether_single_cover_approval_missing"
             }), "")) as run, \
             patch.object(module, "choose_approved_new_single") as choose:
            module.run_single_slot(report, {"status": "idle"})
        self.assertEqual(1, run.call_count)
        choose.assert_not_called()
        self.assertEqual("aether_single_cover_approval_missing", report["single_slot"]["error"])

    def test_paid_lyria_window_closes_at_0800_even_if_0900_has_not_passed(self):
        report = self.report()
        now = datetime(2026, 10, 13, 8, 0, tzinfo=KST)
        with patch.object(module, "now_kst", return_value=now), \
             patch.object(module, "run_step", return_value=(0, json.dumps({
                 "status": "already_public"
             }), "")) as run, \
             patch.object(module, "choose_approved_new_single") as choose:
            module.run_single_slot(report, {"status": "idle"})
        self.assertEqual(len(module.BACKLOG), run.call_count)
        choose.assert_not_called()
        self.assertEqual("aether_lyria_generation_window_closed", report["single_slot"]["error"])

    def test_same_day_scheduled_reconcile_is_reused_without_backlog_attempt(self):
        report = self.report()
        now = datetime(2026, 9, 29, 8, 30, tzinfo=KST)
        reconciled = {
            "profile": "aether_inn",
            "status": "scheduled",
            "slot": "2026-09-29",
            "job_id": "durable-job",
            "video_id": "durable-video",
            "title": "Beyond the Road of Falling Petals",
            "source_kind": "backlog_wav",
        }
        with patch.object(module, "now_kst", return_value=now), \
             patch.object(module, "run_step") as run:
            module.run_single_slot(report, reconciled)

        run.assert_not_called()
        self.assertEqual("durable-job", report["single_slot"]["job_id"])
        self.assertEqual("durable-video", report["single_slot"]["video_id"])
        self.assertTrue(report["single_slot"]["reused_existing_job"])
        self.assertEqual([], report["blockers"])

    def test_other_day_scheduled_reconcile_blocks_without_new_job(self):
        report = self.report()
        now = datetime(2026, 9, 29, 8, 30, tzinfo=KST)
        reconciled = {
            "status": "scheduled",
            "slot": "2026-09-27",
            "job_id": "old-job",
            "video_id": "old-video",
        }
        with patch.object(module, "now_kst", return_value=now), \
             patch.object(module, "run_step") as run:
            module.run_single_slot(report, reconciled)

        run.assert_not_called()
        self.assertEqual("aether_single_existing_job_unsettled", report["single_slot"]["error"])
        self.assertEqual("old-video", report["single_slot"]["video_id"])
        self.assertEqual(["aether_single_existing_job_unsettled"], report["blockers"])


if __name__ == "__main__":
    unittest.main()
