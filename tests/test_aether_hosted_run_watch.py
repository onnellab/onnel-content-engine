"""Fail-closed same-run workflow verification. No real API, shell or production."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_daily_local as daily


RUN_ID = "38469852598"
WORKFLOW = "Sync app operational status"


def response(*, run_id=RUN_ID, workflow=WORKFLOW, status="completed",
             conclusion="success", event="workflow_dispatch", branch="main"):
    return json.dumps({
        "id": int(run_id), "name": workflow, "status": status,
        "conclusion": conclusion, "event": event, "head_branch": branch,
    })


class SameRunVerification(unittest.TestCase):
    def setUp(self):
        self.report = {"steps": [], "blockers": [], "warnings": []}

    def watch(self, *, max_polls=5):
        return daily.watch_hosted_run(
            self.report, label="app_operational_status",
            run_id=RUN_ID, workflow=WORKFLOW, max_polls=max_polls,
        )

    def test_successful_watch_does_not_query_api_or_repeat_dispatch(self):
        with patch.object(daily, "run_step", return_value=(0, "", "")) as run:
            result = self.watch()
        self.assertEqual("success", result["status"])
        self.assertEqual("gh_run_watch_exit_status", result["verification_source"])
        self.assertEqual(1, run.call_count)
        self.assertEqual("watch_app_operational_status", run.call_args.args[1])
        self.assertEqual("gh", run.call_args.args[2][0])
        self.assertEqual("watch", run.call_args.args[2][2])

    def test_502_recovered_by_polling_only_original_run_id(self):
        events = [
            (1, "", "failed to get jobs HTTP 502"),
            (0, response(status="in_progress", conclusion=None), ""),
            (1, "", "HTTP 502"),
            (0, response(), ""),
        ]
        with patch.object(daily, "run_step", side_effect=events) as run, \
             patch.object(daily.time, "sleep") as sleeper:
            result = self.watch(max_polls=5)
        self.assertEqual("success", result["status"])
        self.assertEqual("same_run_api", result["verification_source"])
        self.assertEqual("success", result["observed_conclusion"])
        self.assertEqual(1, result["watch_exit_code"])
        self.assertEqual(
            ["workflow_watch_error_recovered:app_operational_status"],
            self.report["warnings"],
        )
        self.assertEqual(4, run.call_count)
        sleeper.assert_any_call(daily.WORKFLOW_RECHECK_INTERVAL_SECONDS)
        self.assertEqual(2, sleeper.call_count)
        for item in run.call_args_list[1:]:
            args = item.args[2]
            self.assertEqual(["gh", "api", "-X", "GET"], args[:4])
            self.assertIn(f"actions/runs/{RUN_ID}", args[4])
            self.assertNotIn("/jobs", args[4])
            self.assertNotIn("workflow", args)

    def test_verified_run_failure_is_not_recovered(self):
        with patch.object(daily, "run_step", side_effect=[
            (1, "", "HTTP 502"),
            (0, response(conclusion="failure"), ""),
        ]):
            result = self.watch()
        self.assertEqual("failed", result["status"])
        self.assertEqual("failure", result["observed_conclusion"])
        self.assertEqual([], self.report["warnings"])

    def test_cancelled_run_is_not_a_success(self):
        with patch.object(daily, "run_step", side_effect=[
            (1, "", "watch failure"),
            (0, response(conclusion="cancelled"), ""),
        ]):
            result = self.watch()
        self.assertEqual("failed", result["status"])

    def test_run_identity_and_branch_are_required(self):
        cases = [
            ("wrong_run_id", response(run_id="38469852599")),
            ("wrong_workflow", response(workflow="Deploy Ops Dashboard")),
            ("wrong_event", response(event="push")),
            ("wrong_branch", response(branch="other")),
        ]
        for label, value in cases:
            with self.subTest(label=label), patch.object(daily, "run_step", side_effect=[
                (1, "", "HTTP 502"), (0, value, ""),
            ]) as run:
                result = self.watch()
                self.assertEqual("unverified", result["status"])
                self.assertEqual("run_identity_mismatch", result["verification_error"])
                self.assertEqual(2, run.call_count)

    def test_api_unavailable_blocks_without_false_failed_status(self):
        with patch.object(daily, "run_step", side_effect=[
            (1, "", "HTTP 502"),
            *[(1, "", "HTTP 502")] * daily.WORKFLOW_RECHECK_MAX_API_ERRORS,
        ]) as run, patch.object(daily.time, "sleep"):
            result = self.watch(max_polls=10)
        self.assertEqual("unverified", result["status"])
        self.assertEqual("run_api_unavailable", result["verification_error"])
        self.assertEqual(1 + daily.WORKFLOW_RECHECK_MAX_API_ERRORS, run.call_count)

    def test_never_infer_success_from_in_progress_before_deadline(self):
        with patch.object(daily, "run_step", side_effect=[
            (1, "", "HTTP 502"),
            (0, response(status="in_progress", conclusion=None), ""),
            (0, response(status="queued", conclusion=None), ""),
        ]), patch.object(daily.time, "sleep"):
            result = self.watch(max_polls=2)
        self.assertEqual("unverified", result["status"])
        self.assertEqual("run_completion_not_observed", result["verification_error"])

    def test_completed_with_missing_conclusion_is_unverified(self):
        with patch.object(daily, "run_step", side_effect=[
            (1, "", "HTTP 502"),
            (0, response(conclusion=None), ""),
        ]):
            result = self.watch()
        self.assertEqual("unverified", result["status"])
        self.assertEqual("unknown_run_conclusion", result["verification_error"])


class HostedOpsIntegration(unittest.TestCase):
    def setUp(self):
        self.report = {"steps": [], "warnings": [], "blockers": []}

    def test_502_fallback_continues_canonical_order_without_duplicate_dispatch(self):
        ids = {
            "app_operational_status": RUN_ID,
            "ai_operations": "38469978478",
            "store_reviews": "38470090637",
        }
        dispatched = []

        def fake_step(report, name, argv, **kwargs):
            if name.startswith("dispatch_"):
                key = name.removeprefix("dispatch_")
                dispatched.append(key)
                return 0, f"https://github.com/onnellab/onnel-content-engine/actions/runs/{ids[key]}", ""
            if name == "watch_app_operational_status":
                return 1, "", "HTTP 502 /jobs"
            if name == "verify_app_operational_status_run_1":
                return 0, response(run_id=RUN_ID), ""
            if name.startswith("watch_"):
                return 0, "", ""
            if name == "hosted_ops_local_status":
                return 0, "", ""
            if name == "hosted_ops_fetch":
                return 0, "", ""
            if name == "hosted_ops_divergence":
                return 0, "0 0", ""
            self.fail(f"unexpected work: {name}")
        with patch.object(daily, "run_step", side_effect=fake_step):
            okay = daily.run_hosted_ops_workflows(self.report)

        self.assertTrue(okay)
        self.assertEqual(list(ids), dispatched)
        self.assertEqual([], self.report["blockers"])
        self.assertEqual("success", self.report["hosted_workflows"]["app_operational_status"]["status"])
        self.assertEqual("same_run_api", self.report["hosted_workflows"]["app_operational_status"]["verification_source"])

    def test_unverified_first_run_stops_following_workflows(self):
        calls = []

        def fake_step(report, name, argv, **kwargs):
            calls.append(name)
            if name == "dispatch_app_operational_status":
                return 0, f"https://github.com/onnellab/onnel-content-engine/actions/runs/{RUN_ID}", ""
            if name == "watch_app_operational_status":
                return 1, "", "HTTP 502"
            if name.startswith("verify_app_operational_status"):
                return 1, "", "HTTP 502"
            self.fail(f"unwanted workflow: {name}")
        with patch.object(daily, "run_step", side_effect=fake_step), \
             patch.object(daily.time, "sleep"):
            okay = daily.run_hosted_ops_workflows(self.report)
        self.assertFalse(okay)
        self.assertEqual(["app_operational_status_workflow_verification_unavailable"],
                         self.report["blockers"])
        self.assertEqual("unverified", self.report["hosted_workflows"]["app_operational_status"]["status"])
        self.assertFalse(any("dispatch_ai_operations" in name or "dispatch_store_reviews" in name for name in calls))

    def test_verified_failure_stops_other_workflows(self):
        def fake_step(report, name, argv, **kwargs):
            if name == "dispatch_app_operational_status":
                return 0, f"https://github.com/onnellab/onnel-content-engine/actions/runs/{RUN_ID}", ""
            if name == "watch_app_operational_status":
                return 1, "", "HTTP 502"
            if name == "verify_app_operational_status_run_1":
                return 0, response(conclusion="failure"), ""
            self.fail(f"unexpected workflow: {name}")
        with patch.object(daily, "run_step", side_effect=fake_step):
            okay = daily.run_hosted_ops_workflows(self.report)
        self.assertFalse(okay)
        self.assertEqual(["app_operational_status_workflow_failed"],
                         self.report["blockers"])


class OpsDeployIntegration(unittest.TestCase):
    def test_502_recovered_ops_deployment_permits_git_refresh(self):
        report = {"steps": [], "warnings": [], "blockers": []}
        actions = []
        run_id = "38470327575"

        def fake_step(report, name, argv, **kwargs):
            actions.append(name)
            if name == "dispatch_ops_dashboard":
                return 0, f"https://github.com/onnellab/onnel-content-engine/actions/runs/{run_id}", ""
            if name == "watch_ops_dashboard":
                return 1, "", "HTTP 502"
            if name == "verify_ops_dashboard_run_1":
                return 0, response(run_id=run_id, workflow="Deploy Ops Dashboard"), ""
            if name == "ops_dashboard_divergence":
                return 0, "0 0", ""
            if name == "ops_dashboard_fetch":
                return 0, "", ""
            self.fail(f"unexpected work: {name}")
        with patch.object(daily, "run_step", side_effect=fake_step):
            daily.run_ops_dashboard_deploy(report)
        self.assertEqual([], report["blockers"])
        self.assertEqual("success", report["hosted_workflows"]["ops_dashboard"]["status"])
        self.assertIn("ops_dashboard_fetch", actions)
        self.assertEqual(1, actions.count("dispatch_ops_dashboard"))

    def test_unverified_ops_deploy_keeps_blocker_and_does_not_claim_failure(self):
        report = {"steps": [], "warnings": [], "blockers": []}
        run_id = "38470327575"
        names = []

        def fake_step(report, name, argv, **kwargs):
            names.append(name)
            if name == "dispatch_ops_dashboard":
                return 0, f"https://github.com/onnellab/onnel-content-engine/actions/runs/{run_id}", ""
            if name == "watch_ops_dashboard":
                return 1, "", "HTTP 502"
            if name.startswith("verify_ops_dashboard_run_"):
                return 1, "", "HTTP 502"
            self.fail(f"unexpected operation: {name}")
        with patch.object(daily, "run_step", side_effect=fake_step), \
             patch.object(daily.time, "sleep"):
            daily.run_ops_dashboard_deploy(report)
        self.assertEqual(["ops_dashboard_workflow_verification_unavailable"], report["blockers"])
        self.assertEqual("unverified", report["hosted_workflows"]["ops_dashboard"]["status"])
        self.assertNotIn("ops_dashboard_fetch", names)


if __name__ == "__main__":
    unittest.main()
