"""Cover supply regression tests: fixed fixtures, no APIs or production workers."""
from contextlib import ExitStack
import copy
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_daily_local as daily
import aether_existing_cover as covers
import aether_planner as planner
import aether_single as singles
from short_video_pipeline import VideoError

KST = ZoneInfo("Asia/Seoul")


class CoverSelectionDiagnostics(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        (root / "data").mkdir()
        (root / "data/aether_single_lanes.json").write_text(json.dumps({"lanes": [
            {"id": "frontier_surge", "energy": "high_motion", "traversal": True}
        ]}), encoding="utf-8")
        self.state = {"schema_version": 1, "jobs": {}}
        self.queue = MagicMock()
        self.queue._read.return_value = self.state
        self.stack.enter_context(patch.object(daily, "REPO", root))
        self.stack.enter_context(patch.object(daily, "TITLE_BANK", {
            "frontier_surge": ["Reserved Road", "Fresh Ridge", "Fresh Gate"]
        }))
        self.stack.enter_context(patch.object(singles, "SingleQueue", return_value=self.queue))
        self.rotation = self.stack.enter_context(patch.object(singles, "enforce_lane_rotation"))
        self.stack.enter_context(patch.object(planner, "read_catalog", return_value=[]))
        self.metadata = self.stack.enter_context(patch.object(planner, "inspect_candidate", return_value={"metadata_gate": "accepted"}))
        self.cover = self.stack.enter_context(patch.object(covers, "approved_cover", side_effect=VideoError("aether_single_cover_approval_missing")))
        self.run = self.stack.enter_context(patch.object(daily, "run_step", side_effect=AssertionError("no execution")))

    def inspect(self):
        details = {}
        selected = daily.choose_approved_new_single(diagnostics=details, materialize_staged=False, scan_all=True)
        self.run.assert_not_called()
        return selected, details

    def test_depleted_inventory_explains_next_title_without_reviving_rejected_job(self):
        self.state["jobs"]["fixture"] = {"title": " RESERVED ROAD ", "status": "rejected"}
        before = copy.deepcopy(self.state)
        selected, details = self.inspect()
        self.assertIsNone(selected)
        self.assertEqual(before, self.state)
        self.assertEqual("reserved", details["candidates"][0]["status"])
        self.assertEqual("Fresh Ridge", details["next_cover_request"]["title"])
        self.assertFalse(details["next_cover_request"]["approval_granted"])
        self.assertEqual(0, details["ready_count"])
        self.assertTrue(details["scan_complete"])
        self.assertEqual(2, self.cover.call_count)
        self.assertTrue(all(c.kwargs == {"materialize_staged": False} for c in self.cover.call_args_list))
        self.queue._write.assert_not_called()

    def test_corrupt_cover_reason_survives_and_only_valid_title_is_selected(self):
        self.cover.side_effect = [VideoError("aether_asset_hash_mismatch"), (Path("fixture"), {}, "hash"), VideoError("aether_asset_rights_unconfirmed")]
        selected, details = self.inspect()
        self.assertEqual("Fresh Ridge", selected["title"])
        self.assertEqual("ready", details["status"])
        self.assertEqual(1, details["ready_count"])
        self.assertEqual("aether_asset_hash_mismatch", details["candidates"][0]["error"])
        self.assertEqual("aether_asset_rights_unconfirmed", details["candidates"][2]["error"])

    def test_lane_rotation_block_is_not_misreported_as_missing_art(self):
        self.rotation.side_effect = VideoError("aether_single_high_motion_rotation_required")
        selected, details = self.inspect()
        self.assertIsNone(selected)
        self.assertEqual("aether_single_high_motion_rotation_required", details["lane_blockers"][0]["error"])
        self.assertIsNone(details["next_cover_request"])
        self.cover.assert_not_called()

    def test_metadata_rejections_never_reach_cover_import(self):
        self.metadata.return_value = {"metadata_gate": "rejected"}
        selected, details = self.inspect()
        self.assertIsNone(selected)
        self.assertTrue(all(c["status"] == "metadata_rejected" for c in details["candidates"]))
        self.cover.assert_not_called()

    def test_unsettled_upload_blocks_selection_without_altering_ids(self):
        self.state["jobs"]["fixture"] = {"id": "durable-job", "title": "Old", "status": "processing", "upload": {"video_id": "durable-video"}}
        before = copy.deepcopy(self.state)
        with self.assertRaisesRegex(VideoError, "existing_job_unsettled"):
            self.inspect()
        self.assertEqual(before, self.state)
        self.cover.assert_not_called()

    def test_error_payloads_are_not_exposed_in_diagnostics(self):
        self.cover.side_effect = VideoError("private/path: private fixture data")
        _, details = self.inspect()
        self.assertNotIn("private fixture", json.dumps(details))
        self.assertEqual("aether_cover_validation_failed", details["candidates"][0]["error"])

    def test_reused_diagnostics_do_not_keep_a_stale_failure(self):
        details = {}
        self.assertIsNone(daily.choose_approved_new_single(diagnostics=details))
        self.assertIn("error", details)
        self.cover.side_effect = None
        selected = daily.choose_approved_new_single(diagnostics=details)
        self.assertEqual("Reserved Road", selected["title"])
        self.assertEqual("ready", details["status"])
        self.assertNotIn("error", details)
        self.assertIsNone(details["next_cover_request"])
        self.assertEqual(1, details["ready_count"])

    def test_production_selection_still_materializes_only_first_ready_title(self):
        self.cover.side_effect = None
        selected = daily.choose_approved_new_single()
        self.assertEqual("Reserved Road", selected["title"])
        self.cover.assert_called_once_with("Reserved Road", covers.ASSETS_ROOT, materialize_staged=True)
        self.run.assert_not_called()


class UpcomingCoverAdvisory(unittest.TestCase):
    def test_next_slot_and_warning_exist_on_non_publication_days(self):
        def depleted(**kwargs):
            self.assertFalse(kwargs["materialize_staged"])
            self.assertTrue(kwargs["scan_all"])
            kwargs["diagnostics"].update(status="blocked", ready_count=0, scan_complete=True)
            return None
        for day, expected in ((13, 14), (14, 17), (15, 17), (16, 17), (17, 21)):
            with self.subTest(day=day):
                report = {"blockers": ["preserve-original"], "warnings": []}
                with patch.object(daily, "now_kst", return_value=datetime(2026, 11, day, 6, 30, tzinfo=KST)), patch.object(daily, "choose_approved_new_single", side_effect=depleted), patch.object(daily, "run_step") as run:
                    daily.record_single_cover_readiness(report)
                self.assertEqual(f"2026-11-{expected:02d}T09:00:00+09:00", report["single_cover_readiness"]["next_publish_at"])
                self.assertEqual(f"2026-11-{expected:02d}T06:20:00+09:00", report["single_cover_readiness"]["prepare_before"])
                self.assertEqual(["preserve-original"], report["blockers"])
                self.assertEqual(["aether_upcoming_single_cover_not_ready"], report["warnings"])
                run.assert_not_called()

    def test_unknown_failure_is_unavailable_not_empty_inventory_or_success(self):
        report = {}
        with patch.object(daily, "choose_approved_new_single", side_effect=OSError("private fixture data")):
            daily.record_single_cover_readiness(report)
        details = report["single_cover_readiness"]
        self.assertEqual("unavailable", details["status"])
        self.assertIsNone(details["ready_count"])
        self.assertIsNone(details["selected"])
        self.assertFalse(details["scan_complete"])
        self.assertNotIn("private fixture data", json.dumps(report))

    def test_cover_blocked_slot_does_not_invoke_new_lyria_or_uploader(self):
        report = {"blockers": [], "steps": []}
        request = {"title": "Fresh Ridge", "approval_granted": False}
        def depleted(*, diagnostics):
            diagnostics.update(status="blocked", next_cover_request=request)
        with patch.object(daily, "now_kst", return_value=datetime(2026, 11, 14, 6, 30, tzinfo=KST)), patch.object(daily, "check_new_single_inputs", return_value={}), patch.object(daily, "choose_approved_new_single", side_effect=depleted), patch.object(daily, "run_step", return_value=(0, '{"status":"already_public"}', "")) as run:
            daily.run_single_slot(report, {"status": "idle"})
        self.assertEqual(len(daily.BACKLOG), run.call_count)
        self.assertTrue(all("backlog-worker" in c.args[2] for c in run.call_args_list))
        self.assertEqual(request, report["single_slot"]["next_cover_request"])
        self.assertEqual("cover_selection", report["single_slot"]["stage"])
        for flag in ("created_new_job", "generation_attempted", "upload_attempted"):
            self.assertFalse(report["single_slot"][flag])
        self.assertEqual(["aether_lyria_approved_cover_unavailable"], report["blockers"])

    def test_daily_main_wires_advisory_after_due_music_not_as_replacement(self):
        order = []
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            state = Path(temporary)
            for name, value in (("STATE", state), ("RESULT", state / "result.json"), ("LOCK", state / "worker.lock")):
                stack.enter_context(patch.object(daily, name, value))
            stack.enter_context(patch.object(sys, "argv", ["aether_daily_local.py"]))
            stack.enter_context(patch.object(daily, "now_kst", return_value=datetime(2026, 11, 13, 6, 30, tzinfo=KST)))
            stack.enter_context(patch.object(daily, "repo_sync", return_value=True))
            stack.enter_context(patch.object(daily, "save"))
            stack.enter_context(patch.object(daily, "run_reconcile", return_value={"status": "idle"}))
            stack.enter_context(patch.object(daily, "run_single_slot", side_effect=lambda *a: order.append("single")))
            stack.enter_context(patch.object(daily, "record_single_cover_readiness", side_effect=lambda *a: order.append("cover_advisory")))
            for name in ("run_sleep_slot", "run_compilation_slot", "run_youtube_reports", "publish_local_ops_sources"):
                stack.enter_context(patch.object(daily, name))
            stack.enter_context(patch.object(daily, "run_hosted_ops_workflows", return_value=False))
            stack.enter_context(patch.object(daily, "run_step", return_value=(0, "", "")))
            self.assertEqual(0, daily.main())
        self.assertEqual(["single", "cover_advisory"], order)


if __name__ == "__main__":
    unittest.main()
