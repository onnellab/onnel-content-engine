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

    def test_refreshed_provider_evidence_uses_current_time(self):
        import aether_single as single
        from contextlib import nullcontext
        from unittest.mock import Mock

        refreshed_at = NOW + timedelta(seconds=6)
        def estimate(project, *, now):
            self.assertEqual(request.PROJECT, project)
            if now < refreshed_at:
                raise CredentialError("aether_lyria_cost_proof_expired")
            return {"checked_at": refreshed_at.isoformat()}

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            queue = Mock(root=root)
            queue.lock.return_value = nullcontext()
            queue._read.return_value = {"jobs": {}}
            report = {"blockers": []}
            with patch.object(contract, "runtime_enabled", return_value=True), \
                 patch.object(request, "gui_requested", return_value=True), \
                 patch.object(guard, "ROOT", root), \
                 patch.object(single, "SingleQueue", return_value=queue), \
                 patch.object(daily, "check_new_single_inputs", return_value={}) as refresh, \
                 patch.object(daily, "now_kst", return_value=refreshed_at), \
                 patch.object(request, "load_cost_estimate", side_effect=estimate), \
                 patch.object(daily, "run_owner_sleep_step", return_value=(0, '{"status":"sleep_source_pending_review"}', '')) as run:
                daily.run_sleep_slot(report, NOW)
            refresh.assert_called_once_with(refresh_sources=True)
            run.assert_called_once()
            self.assertEqual([], report["blockers"])
            self.assertEqual(refreshed_at.isoformat(), report["sleep_cost_estimate"]["checked_at"])

    def test_gui_sleep_stays_in_owner_without_subprocess_or_environment_change(self):
        import aether_sleep_worker as worker
        import subprocess
        import signal
        for allowed in (False, True):
            report = {"steps": []}
            before = dict(os.environ)
            with patch.object(request, "gui_requested", return_value=allowed), \
                 patch.object(daily, "save"), patch.object(subprocess, "run") as child, \
                 patch.object(signal, "getitimer", return_value=(0.0, 0.0)), \
                 patch.object(signal, "setitimer") as timer, patch.object(signal, "signal") as handler, \
                 patch.object(worker, "worker", return_value={"status": "sleep_source_pending_review"}) as run:
                code, output, _ = daily.run_owner_sleep_step(report, contract.CONCEPTS[0][0], contract.PROPOSED_SLOTS[0])
            self.assertEqual(0 if allowed else 2, code)
            self.assertEqual(before, dict(os.environ))
            child.assert_not_called()
            self.assertEqual(int(allowed), run.call_count)
            if allowed:
                run.assert_called_once_with(concept_id=contract.CONCEPTS[0][0], slot=contract.PROPOSED_SLOTS[0], execute=True, publish=True)
                self.assertEqual([((signal.ITIMER_REAL, 3600),), ((signal.ITIMER_REAL, 0),)], timer.call_args_list)
                self.assertEqual(2, handler.call_count)
            else:
                self.assertEqual("sleep_gui_owner_required", json.loads(output)["error"])
                timer.assert_not_called()
                handler.assert_not_called()
            self.assertNotIn("active_step", report)

    def test_gui_sleep_timeout_restores_handler_without_retry(self):
        import aether_sleep_worker as worker
        import signal
        previous = signal.getsignal(signal.SIGALRM)
        report = {"steps": []}
        with patch.object(request, "gui_requested", return_value=True), patch.object(daily, "save"), \
             patch.object(signal, "getitimer", return_value=(0.0, 0.0)), \
             patch.object(signal, "setitimer") as timer, patch.object(signal, "signal") as handler, \
             patch.object(worker, "worker", side_effect=daily.SleepOwnerDeadline()) as run:
            code, _, error = daily.run_owner_sleep_step(report, contract.CONCEPTS[0][0], contract.PROPOSED_SLOTS[0])
        self.assertEqual((124, "local_worker_timeout"), (code, error))
        run.assert_called_once()
        handler.assert_called_with(signal.SIGALRM, previous)
        timer.assert_called_with(signal.ITIMER_REAL, 0)

    def test_gui_existing_deadline_is_preserved_and_worker_not_called(self):
        import aether_sleep_worker as worker
        import signal
        with patch.object(request, "gui_requested", return_value=True), patch.object(daily, "save"), \
             patch.object(signal, "getitimer", return_value=(30.0, 0.0)), \
             patch.object(signal, "setitimer") as timer, patch.object(signal, "signal") as handler, \
             patch.object(worker, "worker") as run:
            code, output, _ = daily.run_owner_sleep_step({"steps": []}, contract.CONCEPTS[0][0], contract.PROPOSED_SLOTS[0])
        self.assertEqual(2, code)
        self.assertEqual("sleep_owner_deadline_already_active", json.loads(output)["error"])
        run.assert_not_called()
        timer.assert_not_called()
        handler.assert_not_called()

    def test_gui_request_expiry_never_falls_back_to_subprocess(self):
        import aether_single as single
        import aether_sleep_worker as worker
        from contextlib import nullcontext
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            queue = Mock(root=root)
            queue.lock.return_value = nullcontext()
            queue._read.return_value = {"jobs": {}}
            report = {"steps": [], "blockers": []}
            with patch.object(contract, "runtime_enabled", return_value=True), \
                 patch.object(request, "gui_requested", side_effect=[True, False]), \
                 patch.object(guard, "ROOT", root), patch.object(single, "SingleQueue", return_value=queue), \
                 patch.object(daily, "check_new_single_inputs", return_value={}), \
                 patch.object(request, "load_cost_estimate", return_value={}), \
                 patch.object(daily, "save"), patch.object(daily, "run_step") as subprocess_step, \
                 patch.object(worker, "worker") as run:
                daily.run_sleep_slot(report, NOW)
            self.assertEqual(["sleep_gui_owner_required"], report["blockers"])
            subprocess_step.assert_not_called()
            run.assert_not_called()

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
