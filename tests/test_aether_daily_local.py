"""Daily Aether orchestration tests. No local production or network execution."""
import copy
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
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



class CompilationMaterializationRetry(unittest.TestCase):
    def test_transient_mybox_failure_only_retries_asset_stage_before_single_publish(self):
        now = datetime(2026, 10, 11, 6, 25, tzinfo=KST)
        report = {"blockers": [], "steps": []}
        failed = json.dumps({"status": "blocked", "error": "aether_asset_source_materialization_failed"})
        ready = json.dumps({"status": "ready"})
        published = json.dumps({"status": "published", "job_id": "kept-job", "video_id": "kept-video"})
        with patch.object(module, "run_step", side_effect=[
            (2, failed, ""), (0, ready, ""), (0, published, "")
        ]) as run, patch.object(module.time, "sleep") as sleep, \
                patch.object(module, "save"):
            module.run_compilation_slot(report, now)

        self.assertEqual(3, run.call_count)
        self.assertEqual("aether_compilation_assets", run.call_args_list[0].args[1])
        self.assertEqual("aether_compilation_assets_retry_1", run.call_args_list[1].args[1])
        self.assertEqual("aether_compilation_slot", run.call_args_list[2].args[1])
        sleep.assert_called_once_with(module.COMPILATION_ASSET_RETRY_DELAYS[0])
        self.assertEqual("published", report["compilation_slot"]["status"])
        self.assertEqual([], report["blockers"])

    def test_exhausted_mybox_retries_never_start_publication(self):
        now = datetime(2026, 10, 11, 6, 25, tzinfo=KST)
        report = {"blockers": [], "steps": []}
        failed = json.dumps({"status": "blocked", "error": "aether_asset_source_materialization_failed"})
        with patch.object(module, "run_step", return_value=(2, failed, "")) as run, \
                patch.object(module.time, "sleep") as sleep, \
                patch.object(module, "save"):
            module.run_compilation_slot(report, now)

        self.assertEqual(3, run.call_count)
        self.assertEqual(2, sleep.call_count)
        self.assertTrue(all("assets" in call.args[1] for call in run.call_args_list))
        self.assertEqual("blocked", report["compilation_slot"]["status"])
        self.assertEqual(["aether_asset_source_materialization_failed"], report["blockers"])

    def test_any_other_approval_error_never_retries_or_publishes(self):
        now = datetime(2026, 10, 11, 6, 25, tzinfo=KST)
        report = {"blockers": [], "steps": []}
        failed = json.dumps({"status": "blocked", "error": "aether_asset_approval_incomplete"})
        with patch.object(module, "run_step", return_value=(2, failed, "")) as run, \
                patch.object(module.time, "sleep") as sleep:
            module.run_compilation_slot(report, now)

        self.assertEqual(1, run.call_count)
        sleep.assert_not_called()
        self.assertEqual(["aether_asset_approval_incomplete"], report["blockers"])


class SameDayCompilationRecovery(unittest.TestCase):
    @staticmethod
    def prior(now):
        error = "aether_asset_source_materialization_failed"
        return {
            "kind": "onnellab_aether_local_daily_result",
            "mode": "daily",
            "local_date": now.date().isoformat(),
            "state": "partial",
            "started_at": "2026-10-11T06:20:05+09:00",
            "finished_at": "2026-10-11T06:25:15+09:00",
            "blockers": [error],
            "steps": [
                {"name": "dispatch_app_operational_status", "exit_code": 0},
                {"name": "aether_compilation_assets", "exit_code": 2},
            ],
            "ops_snapshot_commit": {"sha": "immutable-ops-id", "pushed": True},
            "hosted_workflows": {"store_reviews": {"run_id": "original-workflow-id"}},
            "aether_compilation_reconcile": {"status": "idle", "created_new_job": False},
            "aether_playlists": {"state": "synced"},
            "aether_compilation_assets": {"status": "blocked", "error": error},
            "compilation_slot": {"status": "blocked", "theme": "lantern_towns", "error": error},
        }

    def test_eligible_failed_assets_can_resume_exact_same_slot(self):
        now = datetime(2026, 10, 11, 8, 0, tzinfo=KST)
        report = self.prior(now)
        self.assertTrue(module.compilation_resume_allowed(report, now))

        def fake_compilation(data, observed, *, recovery):
            self.assertTrue(recovery)
            self.assertEqual(now, observed)
            data["compilation_slot"] = {
                "status": "published", "job_id": "durable-job", "video_id": "durable-video",
                "publication_complete": True,
            }

        with patch.object(module, "repo_sync", return_value=True) as repo, \
                patch.object(module, "run_compilation_slot", side_effect=fake_compilation) as production, \
                patch.object(module, "run_youtube_reports") as youtube, \
                patch.object(module, "run_hosted_ops_workflows") as ops, \
                patch.object(module, "run_store_review_auto_replies") as reviews, \
                patch.object(module, "save"):
            success = module.resume_compilation(report, now)

        self.assertTrue(success)
        repo.assert_called_once()
        production.assert_called_once()
        youtube.assert_not_called()
        ops.assert_not_called()
        reviews.assert_not_called()
        self.assertEqual("complete", report["state"])
        self.assertEqual("immutable-ops-id", report["ops_snapshot_commit"]["sha"])
        self.assertEqual("original-workflow-id", report["hosted_workflows"]["store_reviews"]["run_id"])
        self.assertEqual("durable-video", report["compilation_slot"]["video_id"])
        self.assertEqual(2, len(report["steps"]))
        self.assertEqual(1, len(report["compilation_recovery_attempts"]))
        self.assertEqual([], report["blockers"])

    def test_recovery_repo_failure_preserves_original_blocker(self):
        now = datetime(2026, 10, 11, 8, 0, tzinfo=KST)
        report = self.prior(now)
        def fail_sync(data):
            data["blockers"].append("repo_fetch_failed")
            return False
        with patch.object(module, "repo_sync", side_effect=fail_sync), \
                patch.object(module, "run_compilation_slot") as prod, \
                patch.object(module, "save"):
            self.assertFalse(module.resume_compilation(report, now))
        prod.assert_not_called()
        self.assertIn("aether_asset_source_materialization_failed", report["blockers"])
        self.assertIn("repo_fetch_failed", report["blockers"])
        self.assertEqual("partial", report["state"])

    def test_never_retry_on_other_day_or_uncertain_video_or_policy_blocker(self):
        now = datetime(2026, 10, 11, 8, 0, tzinfo=KST)
        originals = self.prior(now)
        cases = {
            "yesterday": {"local_date": "2026-10-10"},
            "different_error": {"blockers": ["aether_asset_approval_incomplete"]},
            "running": {"state": "running"},
            "already_completed": {"state": "complete"},
            "wrong_theme": {"compilation_slot": {"status": "blocked", "theme": "open_roads", "error": "aether_asset_source_materialization_failed"}},
            "video_id_exists": {"compilation_slot": {"status": "blocked", "theme": "lantern_towns", "error": "aether_asset_source_materialization_failed", "video_id": "possible-upload-id"}},
            "recovery_limit": {"compilation_recovery_attempts": [{}, {}]},
            "worker_was_started": {"steps": [{"name": "aether_compilation_slot", "exit_code": 124}]},
            "reconcile_unsettled": {"aether_compilation_reconcile": {"status": "processing"}},
            "wrong_kind": {"kind": "another_kind"},
            "not_synced": {"aether_playlists": {"state": "blocked"}},
        }
        for label, changes in cases.items():
            with self.subTest(label=label):
                candidate = copy.deepcopy(originals)
                candidate.update(changes)
                self.assertFalse(module.compilation_resume_allowed(candidate, now))

    def test_monday_never_resumes_sunday_compilation(self):
        now = datetime(2026, 10, 12, 6, 25, tzinfo=KST)
        report = self.prior(datetime(2026, 10, 11, 6, 25, tzinfo=KST))
        report["local_date"] = now.date().isoformat()
        self.assertFalse(module.compilation_resume_allowed(report, now))

    def test_main_never_dispatches_full_ops_again_for_same_day_partial(self):
        now = datetime(2026, 10, 11, 8, 0, tzinfo=KST)
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            result = state / "result.json"
            previous = self.prior(now)
            previous["blockers"] = ["different_unresolved_error"]
            result.write_text(json.dumps(previous), encoding="utf-8")
            with patch.object(module, "STATE", state), \
                    patch.object(module, "RESULT", result), \
                    patch.object(module, "LOCK", state / "worker.lock"), \
                    patch.object(module, "now_kst", return_value=now), \
                    patch.object(module, "run_youtube_reports") as youtube, \
                    patch.object(module, "run_hosted_ops_workflows") as ops, \
                    patch.object(module, "run_compilation_slot") as compilation, \
                    patch.object(sys, "argv", ["aether_daily_local.py"]):
                self.assertEqual(2, module.main())
            youtube.assert_not_called()
            ops.assert_not_called()
            compilation.assert_not_called()
            self.assertEqual(previous, json.loads(result.read_text()))


if __name__ == "__main__":
    unittest.main()
