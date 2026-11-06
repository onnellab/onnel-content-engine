"""Recorded 2026-11-07 failure regressions; all workflow calls are mocked."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_daily_local as daily

WORKFLOW = "Refresh AI Operations Sources"
KEY = "20261107T062921-ai_operations-033c5d6467cc"
RUN_ID = "42297127692"
INCIDENT = {
    "id": int(RUN_ID),
    "name": f"Daily AI operations [{KEY}]",
    "display_title": f"Daily AI operations [{KEY}]",
    "workflow_id": 362359045,
    "path": ".github/workflows/refresh-ai-operations.yml",
    "event": "workflow_dispatch", "head_branch": "main",
    "created_at": "2026-11-06T21:29:23Z",
    "status": "completed", "conclusion": "cancelled",
}


def report():
    return {
        "steps": [], "blockers": [], "warnings": [],
        "single_slot": {"video_id": "Qcm9voxLvQA", "generation_count": 1},
        "hosted_workflows": {"ai_operations": {
            "workflow": WORKFLOW, "run_id": RUN_ID, "dispatch_key": KEY,
        }},
    }


class HostedRunIdentityRegression(unittest.TestCase):
    def watch(self, observed):
        state = report()
        before = copy.deepcopy(state["single_slot"])
        with patch.object(daily, "run_step", side_effect=[
            (1, "", "watch returned nonzero"),
            (0, json.dumps(observed), ""),
        ]) as run:
            result = daily.watch_hosted_run(
                state, label="ai_operations", run_id=RUN_ID, workflow=WORKFLOW,
                max_polls=1,
            )
        self.assertEqual(2, run.call_count)
        self.assertEqual(before, state["single_slot"])
        argv = run.call_args.args[2]
        self.assertEqual(["gh", "api", "-X", "GET"], argv[:4])
        self.assertIn(f"actions/runs/{RUN_ID}", argv[4])
        self.assertNotIn("workflow", argv)
        return result

    def test_recorded_cancelled_daily_name_is_not_an_identity_mismatch(self):
        result = self.watch(INCIDENT)
        self.assertEqual("failed", result["status"])
        self.assertEqual("cancelled", result["observed_conclusion"])
        self.assertNotIn("verification_error", result)

    def test_dynamic_and_static_name_variants_identify_the_same_run(self):
        for name in (WORKFLOW, INCIDENT["name"]):
            with self.subTest(name=name):
                result = self.watch({**INCIDENT, "name": name, "conclusion": "success"})
                self.assertEqual("success", result["status"])

    def test_fixed_name_cannot_hide_wrong_path_or_dispatch_key(self):
        for changes in (
            {"path": ".github/workflows/sync-store-reviews.yml"},
            {"path": None}, {"display_title": f"Daily AI operations [{KEY}-other]"},
            {"display_title": WORKFLOW}, {"event": "push"},
            {"head_branch": "another"}, {"id": int(RUN_ID) + 1},
        ):
            with self.subTest(changes=changes):
                result = self.watch({**INCIDENT, "name": WORKFLOW, **changes})
                self.assertEqual("unverified", result["status"])
                self.assertEqual("run_identity_mismatch", result["verification_error"])

    def test_ambiguous_dispatch_accepts_dynamic_api_name_without_reposting(self):
        state = report()
        calls = []

        def fake_step(saved, name, argv, **kwargs):
            calls.append((name, argv))
            if name == "dispatch_ai_operations":
                return 1, "", "HTTP 503"
            if name.startswith("reconcile_dispatch_ai_operations_"):
                key = saved["hosted_workflows"]["ai_operations"]["dispatch_key"]
                row = {**INCIDENT, "name": f"Daily AI operations [{key}]",
                       "display_title": f"Daily AI operations [{key}]",
                       "created_at": saved["hosted_workflows"]["ai_operations"]["dispatch_started_at"]}
                return 0, json.dumps({"workflow_runs": [row]}), ""
            self.fail(f"unexpected operation: {name}")

        with patch.object(daily, "run_step", side_effect=fake_step), patch.object(daily.time, "sleep"):
            result = daily.dispatch_hosted_workflow(state, label="ai_operations", workflow=WORKFLOW)
        self.assertEqual(RUN_ID, result["run_id"])
        self.assertEqual("dispatched", result["status"])
        self.assertEqual(1, sum(name == "dispatch_ai_operations" for name, _ in calls))
        for name, argv in calls[1:]:
            self.assertEqual(["gh", "api", "-X", "GET"], argv[:4])

    def test_ambiguous_dispatch_never_adopts_old_or_duplicate_candidates(self):
        for mode in ("old", "other_path", "other_key", "duplicate"):
            state = report()

            def fake_step(saved, name, argv, **kwargs):
                if name == "dispatch_ai_operations":
                    return 1, "", "HTTP 503"
                key = saved["hosted_workflows"]["ai_operations"]["dispatch_key"]
                row = {**INCIDENT, "name": f"Daily AI operations [{key}]",
                       "display_title": f"Daily AI operations [{key}]",
                       "created_at": saved["hosted_workflows"]["ai_operations"]["dispatch_started_at"]}
                if mode == "old":
                    row["created_at"] = "2020-01-01T00:00:00Z"
                elif mode == "other_path":
                    row["path"] = ".github/workflows/other.yml"
                elif mode == "other_key":
                    row["display_title"] = "Daily AI operations [not-this-dispatch]"
                rows = [row, {**row, "id": int(RUN_ID) + 1}] if mode == "duplicate" else [row]
                return 0, json.dumps({"workflow_runs": rows}), ""

            with self.subTest(mode=mode), patch.object(daily, "run_step", side_effect=fake_step) as run, \
                 patch.object(daily.time, "sleep"):
                result = daily.dispatch_hosted_workflow(state, label="ai_operations", workflow=WORKFLOW)
            self.assertEqual("dispatch_unverified", result["status"])
            self.assertEqual("", result["run_id"])
            self.assertEqual(1, sum(x.args[1] == "dispatch_ai_operations" for x in run.call_args_list))

    def test_confirmed_cancel_stops_next_sources_with_exact_reason(self):
        state = report()
        calls = []

        def fake_step(saved, name, argv, **kwargs):
            calls.append(name)
            if name.startswith("dispatch_"):
                return 0, f"https://github.com/onnellab/onnel-content-engine/actions/runs/{RUN_ID}", ""
            if name == "watch_app_operational_status":
                return 0, "", ""
            if name == "watch_ai_operations":
                return 1, "", "cancelled"
            if name == "verify_ai_operations_run_1":
                key = saved["hosted_workflows"]["ai_operations"]["dispatch_key"]
                return 0, json.dumps({**INCIDENT, "display_title": f"Daily AI operations [{key}]"}), ""
            self.fail(f"downstream work must remain stopped: {name}")

        with patch.object(daily, "run_step", side_effect=fake_step):
            self.assertFalse(daily.run_hosted_ops_workflows(state))
        self.assertEqual(["ai_operations_workflow_cancelled"], state["blockers"])
        self.assertEqual("cancelled", state["hosted_workflows"]["ai_operations"]["observed_conclusion"])
        self.assertNotIn("dispatch_store_reviews", calls)
        self.assertEqual("Qcm9voxLvQA", state["single_slot"]["video_id"])
        self.assertEqual(1, state["single_slot"]["generation_count"])


if __name__ == "__main__":
    unittest.main()
