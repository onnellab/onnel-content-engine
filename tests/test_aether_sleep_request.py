"""Offline fictional pricing and GUI fixtures. No network, paid calls or uploads."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_sleep_request as request
import aether_sleep_guard as guard
import aether_sleep_contract as contract
import aether_paid_guard as paid
import aether_daily_local as daily
from short_video_credentials import CredentialError

NOW = datetime(2026, 11, 10, 2, tzinfo=timezone.utc)
SOURCE = {"provider_base_price_usd": "0.08", "proof_sha256": "a" * 64,
          "checked_at": "2026-11-10T00:00:00Z", "expires_at": "2026-11-11T00:00:00Z"}


class SleepRequest(unittest.TestCase):
    def test_private_immutable_exact_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp).resolve() / "requests" / "request.json"
            with patch.object(request, "request_path", return_value=path):
                request.record_request(now=NOW)
                original = path.read_bytes()
                self.assertEqual(0o700, path.parent.stat().st_mode & 0o777)
                self.assertEqual(0o600, path.stat().st_mode & 0o777)
                request.record_request(now=NOW)
                self.assertEqual(original, path.read_bytes())
                self.assertFalse(request.pending_request(now=NOW + timedelta(days=3)))
                for service, expected in ((request.SERVICE, True), ("other", False)):
                    with patch.dict(os.environ, {"XPC_SERVICE_NAME": service}):
                        self.assertEqual(expected, request.gui_requested(now=NOW))
                data = json.loads(original)
                data["maximum_requests"] = 4
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(CredentialError, "request_changed"):
                    request.pending_request(now=NOW)

    def test_estimate_honest_scope_hash_and_allocation(self):
        with patch.object(request, "gui_requested", return_value=True), patch.object(paid, "load_paid_proof", return_value=SOURCE):
            estimate = request.load_cost_estimate(request.PROJECT, now=NOW)
            self.assertEqual(Decimal("0.088"), Decimal(estimate["estimated_per_request_usd"]))
            self.assertEqual(Decimal("0.264"), Decimal(estimate["estimated_pilot_total_usd"]))
            self.assertEqual("0.50", estimate["approved_total_cap_usd"])
            self.assertFalse(estimate["gross_cost_verified"])
            self.assertFalse(estimate["actual_account_tax_fx_and_fees_verified"])
            self.assertIsNone(estimate["final_billed_cost_usd"])
            guard.require_remaining_budget([], estimate)
            self.assertLessEqual(Decimal(estimate["all_in_reserved_usd"]) * 3, Decimal(".50"))
            self.assertEqual(3, len(estimate["request_binding"]["concepts"]))
            with self.assertRaises(CredentialError):
                request.load_cost_estimate("wrong", now=NOW)
            with self.assertRaisesRegex(CredentialError, "estimate_changed"):
                request.load_cost_estimate(request.PROJECT, expected_sha256="b" * 64, now=NOW)
            with patch.object(paid, "load_paid_proof", return_value={**SOURCE, "proof_sha256": "c" * 64}):
                with self.assertRaisesRegex(CredentialError, "estimate_changed"):
                    request.load_cost_estimate(request.PROJECT, expected_sha256=estimate["proof_sha256"], now=NOW)

    def test_strict_validator_not_bypassed(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(guard, "PROOF_PATH", Path(temp) / "missing"):
            with patch.object(request, "gui_requested", return_value=True):
                with self.assertRaisesRegex(CredentialError, "account_all_in_cost_unverified"):
                    guard.load_all_in_proof(request.PROJECT)
            with patch.object(request, "gui_requested", return_value=False), patch.object(request, "load_cost_estimate") as estimate:
                with self.assertRaises(CredentialError):
                    guard.load_cost_authorization(request.PROJECT)
                estimate.assert_not_called()

    def test_settled_fantasy_same_day_only_and_unsettled_or_sleep_rejected(self):
        import aether_single as single
        import aether_sleep_worker as worker
        from short_video_pipeline import atomic_json, VideoError
        cases = [
            ("published", "new_lyria", None),
            ("blocked", "new_lyria", "existing_job_unsettled"),
            ("published", contract.SOURCE_KIND, "slot_already_used"),
        ]
        for status, kind, error in cases:
            with self.subTest(status=status, kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                q = single.SingleQueue(root)
                old = {"id": "b" * 24, "slot": contract.PROPOSED_SLOTS[0],
                       "status": status, "source_kind": kind, "thumbnail_status": "set",
                       "upload": {"video_id": "fixture"}}
                atomic_json(q.state_path, {"schema_version": 1, "jobs": {old["id"]: old}})
                with patch.object(single, "SingleQueue", return_value=q), \
                     patch.object(q, "_read", return_value={"schema_version": 1, "jobs": {old["id"]: old}}), \
                     patch.object(contract, "require_activation"), \
                     patch.object(request, "gui_requested", return_value=True), \
                     patch.object(worker, "require_window", return_value="public"), \
                     patch("lyria_config.load_settings", return_value={"enabled": True, "project_id": request.PROJECT}), \
                     patch.object(guard, "load_cost_authorization", return_value={}), \
                     patch.object(guard, "require_affordable_pilot"), patch.object(single, "approved_cover"), \
                     patch.object(worker, "run_locked", return_value={"status": "sleep_source_pending_review"}) as run:
                    kwargs = dict(root=root, concept_id=contract.CONCEPTS[0][0],
                                  slot=contract.PROPOSED_SLOTS[0], execute=True)
                    if error:
                        with self.assertRaisesRegex(VideoError, error):
                            worker.worker(**kwargs)
                        run.assert_not_called()
                    else:
                        self.assertEqual("sleep_source_pending_review", worker.worker(**kwargs)["status"])
                        run.assert_called_once()

    def test_default_off_and_exact_gui_only(self):
        with patch.dict(os.environ, {"AETHER_SLEEP_PILOT_ENABLED": "0"}):
            for allowed in (False, True):
                with patch.object(request, "gui_requested", return_value=allowed):
                    self.assertEqual(allowed, contract.runtime_enabled())

    def test_default_gui_routes_sleep_without_fantasy(self):
        for service, count in ((request.SERVICE, 1), ("other-service", 0)):
            with tempfile.TemporaryDirectory() as temp:
                state = Path(temp)
                result = state / "result.json"
                original = {"kind": "onnellab_aether_local_daily_result", "mode": "daily",
                            "local_date": "2026-11-10", "state": "complete"}
                result.write_text(json.dumps(original))
                with patch.object(daily, "STATE", state), patch.object(daily, "RESULT", result), \
                     patch.object(daily, "LOCK", state / "lock"), patch.object(daily, "now_kst", return_value=NOW), \
                     patch.object(daily, "repo_sync", return_value=True), patch.object(daily, "run_sleep_slot") as sleep, \
                     patch.object(daily, "run_today_single_slot") as fantasy, \
                     patch("aether_single_today.pending_request", return_value=False), \
                     patch.object(request, "pending_request", return_value=True), \
                     patch.dict(os.environ, {"XPC_SERVICE_NAME": service}), patch.object(sys, "argv", ["daily"]):
                    self.assertEqual(0, daily.main())
                self.assertEqual(count, sleep.call_count)
                fantasy.assert_not_called()
                self.assertEqual(original, json.loads(result.read_text()))


if __name__ == "__main__":
    unittest.main()
