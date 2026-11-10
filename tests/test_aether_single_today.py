"""Fictional offline fixtures; no live account, paid call, render or upload."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_daily_local as daily
import aether_single as single
import aether_single_today as today
import lyria_generate as lyria
from short_video_credentials import CredentialError
from short_video_pipeline import VideoError, digest, atomic_json
import test_aether_paid_boundary as paid_fixtures
import test_aether_single as media_fixtures

NOW = datetime(2026, 11, 10, 2, tzinfo=timezone.utc)
PROOF = {"proof_sha256": "a" * 64, "estimated_total_usd": "0.088", "cost_basis": "official_provider_base_plus_assumed_korea_vat"}

@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary).resolve()
        with patch.object(paid_fixtures, "NOW", NOW), paid_fixtures.fixture_environment(base, project_id=today.PROJECT):
            root = base / "aether-inn" / "singles"
            q = single.SingleQueue(root)
            with patch.object(today, "ROOT", root), patch.object(today, "datetime", wraps=datetime) as clock, \
                 patch.object(today, "load_cost_estimate", return_value=PROOF):
                clock.now.return_value = NOW
                yield q

def create_job(q):
    job = {"id": today.job_id(), "slot": today.SLOT, "title": today.TITLE,
           "style": today.canonical_style(), "lane": today.LANE, "status": "planned",
           "music": None, "cover": None, "result": None, "publish_requested": True,
           "upload_eligible": False, "error": None}
    job["same_day_release"] = today.scope_for(job)
    job["brief"] = single.brief_for(job)
    job["payload_hash"] = digest(job["brief"])
    (q.root / "jobs" / job["id"]).mkdir(mode=0o700)
    atomic_json(q.state_path, {"schema_version": 1, "jobs": {job["id"]: job}})
    return job

class Contract(unittest.TestCase):
    def test_exact_date_title_style_and_lane(self):
        args = (today.SLOT, today.TITLE, today.canonical_style(), today.LANE)
        today.require_target(*args, now=NOW)
        for index in range(4):
            bad = list(args); bad[index] = "other"
            with self.subTest(index=index), self.assertRaises(CredentialError):
                today.require_target(*bad, now=NOW)
        for clock in (NOW - timedelta(days=1), NOW + timedelta(days=1), NOW.replace(tzinfo=None)):
            with self.subTest(clock=clock), self.assertRaises(CredentialError):
                today.require_target(*args, now=clock)

    def test_estimate_is_explicit_and_rejects_price_increase(self):
        import aether_paid_guard as paid
        source = {"provider_base_price_usd": "0.08", "proof_sha256": "b" * 64,
                  "checked_at": "2026-11-10T00:00:00Z", "expires_at": "2026-11-11T00:00:00Z"}
        with patch.object(paid, "load_paid_proof", return_value=source):
            estimate = today.load_cost_estimate()
            self.assertEqual(Decimal("0.088"), Decimal(estimate["estimated_total_usd"]))
            self.assertEqual("0.10", estimate["approved_all_in_cap_usd"])
            self.assertFalse(estimate["actual_account_tax_fx_and_fees_verified"])
            self.assertFalse(estimate["gross_cost_verified"])
            self.assertIsNone(estimate["final_billed_cost_usd"])
            with self.assertRaisesRegex(CredentialError, "cost_estimate_changed"):
                today.load_cost_estimate(expected_sha256="c" * 64)
        with patch.object(paid, "load_paid_proof", return_value={**source, "provider_base_price_usd": "0.09"}):
            with self.assertRaisesRegex(CredentialError, "budget_exceeded"):
                today.load_cost_estimate()

    def test_generation_binding_and_immutable_single_claim(self):
        with fixture() as q:
            job = create_job(q)
            scope = job["same_day_release"]
            prompt = lyria.build_aether_prompt(today.TITLE, today.canonical_style())
            output = q.root / "jobs" / job["id"] / "lyria"
            today.require_generation(scope, today.SLOT, today.PROJECT, prompt, output_root=output, now=NOW)
            for project, text, root in (("wrong", prompt, output), (today.PROJECT, "wrong", output), (today.PROJECT, prompt, output.parent)):
                with self.subTest(project=project, root=root), self.assertRaises(CredentialError):
                    today.require_generation(scope, today.SLOT, project, text, output_root=root, now=NOW)
            today.claim_once(scope, output)
            with self.assertRaisesRegex(CredentialError, "paid_retry_forbidden"):
                today.claim_once(scope, output)

    def test_paid_adapter_one_request_even_after_success_or_uncertainty(self):
        for uncertain in (False, True):
            with self.subTest(uncertain=uncertain), fixture() as q:
                job = create_job(q)
                kwargs = {"execute": True, "slot": today.SLOT,
                          "same_day_release": job["same_day_release"],
                          "output_root": q.root / "jobs" / job["id"] / "lyria"}
                effect = TimeoutError() if uncertain else lambda *a, **k: paid_fixtures.response_fixture()
                with patch.object(lyria, "access_token", return_value="fixture"), patch.object(lyria, "urlopen", side_effect=effect) as wire:
                    if uncertain:
                        with self.assertRaisesRegex(CredentialError, "network_error"):
                            lyria.generate(today.TITLE, today.canonical_style(), **kwargs)
                    else:
                        result = lyria.generate(today.TITLE, today.canonical_style(), **kwargs)
                        self.assertEqual("generated", result["state"])
                        self.assertEqual(job["same_day_release"], result["same_day_release"])
                    with self.assertRaises(CredentialError):
                        lyria.generate(today.TITLE, today.canonical_style(), **kwargs)
                    wire.assert_called_once()

    def test_proof_change_stops_before_provider_post(self):
        with fixture() as q:
            job = create_job(q)
            with patch.object(today, "load_cost_estimate", side_effect=CredentialError("proof_changed")), \
                 patch.object(lyria, "urlopen") as wire:
                with self.assertRaisesRegex(CredentialError, "proof_changed"):
                    lyria.generate(today.TITLE, today.canonical_style(), execute=True, slot=today.SLOT,
                                   same_day_release=job["same_day_release"],
                                   output_root=q.root / "jobs" / job["id"] / "lyria")
                wire.assert_not_called()

    def test_owner_request_is_private_exact_and_date_limited(self):
        with fixture() as q:
            path = today.request_path()
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.parent.chmod(0o700)
            first = today.record_request(now=NOW)
            original = path.read_bytes()
            self.assertEqual("requested", first["status"])
            self.assertTrue(today.pending_request(now=NOW))
            self.assertFalse(today.pending_request(now=NOW + timedelta(days=1)))
            self.assertEqual("already_requested", today.record_request(now=NOW)["status"])
            self.assertEqual(original, path.read_bytes())
            changed = json.loads(original); changed["title"] = "other"
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(CredentialError, "request_changed"):
                today.pending_request(now=NOW)

    def test_only_registered_owner_consumes_default_invocation(self):
        for service, calls in (("com.onnellab.aether-daily-local", 1), ("other-service", 0)):
            with self.subTest(service=service), fixture() as q:
                state = today.request_path().parent
                state.mkdir(mode=0o700, parents=True, exist_ok=True)
                today.record_request(now=NOW)
                result = state / "result.json"
                original = {"kind": "onnellab_aether_local_daily_result", "mode": "daily",
                            "local_date": today.SLOT, "state": "complete"}
                atomic_json(result, original)
                with patch.object(daily, "STATE", state), patch.object(daily, "RESULT", result), \
                     patch.object(daily, "LOCK", state / "worker.lock"), \
                     patch.object(daily, "now_kst", return_value=NOW), \
                     patch.object(daily, "repo_sync", return_value=True), \
                     patch.object(daily, "run_today_single_slot") as single_slot, \
                     patch.object(daily, "run_sleep_slot") as sleep_slot, \
                     patch.dict(os.environ, {"XPC_SERVICE_NAME": service}), \
                     patch.object(sys, "argv", ["aether_daily_local.py"]):
                    self.assertEqual(0, daily.main())
                self.assertEqual(calls, single_slot.call_count)
                sleep_slot.assert_not_called()
                self.assertEqual(original, json.loads(result.read_text()))

    def test_request_creates_private_child_without_changing_report_directory(self):
        with fixture() as q:
            path = today.request_path()
            reports = path.parent.parent
            reports.mkdir(parents=True, exist_ok=True)
            reports.chmod(0o755)
            self.assertFalse(path.parent.exists())
            today.record_request(now=NOW)
            self.assertEqual(0o755, reports.stat().st_mode & 0o777)
            self.assertEqual(0o700, path.parent.stat().st_mode & 0o777)
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            self.assertTrue(today.pending_request(now=NOW))

class Worker(unittest.TestCase):
    def test_missing_all_in_receipt_does_not_consume_job_or_touch_provider(self):
        with fixture() as q, patch.object(today, "load_cost_estimate", side_effect=CredentialError("unverified")), \
             patch.object(single, "YouTube") as youtube:
            before = q.state_path.read_bytes() if q.state_path.exists() else None
            with self.assertRaisesRegex(CredentialError, "unverified"):
                single.worker(q.root, slot=today.SLOT, title=today.TITLE,
                              style=today.canonical_style(), lane=today.LANE,
                              execute=True, publish=True, same_day_release=True)
            self.assertEqual(before, q.state_path.read_bytes() if q.state_path.exists() else None)
            youtube.assert_not_called()

    def test_publishes_exact_new_job_once_and_reconciles_same_id(self):
        with fixture() as q:
            provider = media_fixtures.Provider()
            media = media_fixtures.SingleTests()
            calls = []
            def music(title, style, **kwargs):
                calls.append(kwargs.pop("same_day_release"))
                return media.fake_music(title, style, **kwargs)
            def select(result, prior, **kwargs):
                row = result["candidates"][0]
                return {"path": row["file"], "sha256": row["sha256"], "duration_seconds": 184,
                        "review": {"accepted": True}}
            def thumbnail(q, state, job, api):
                job["thumbnail_status"] = "set"
                atomic_json(q.state_path, state)
            with patch.object(single, "select_candidate", side_effect=select), \
                 patch.object(single.SingleQueue, "_render"), patch.object(single, "thumbnail", side_effect=thumbnail):
                args = {"root": q.root, "slot": today.SLOT, "title": today.TITLE,
                        "style": today.canonical_style(), "lane": today.LANE,
                        "execute": True, "publish": True, "same_day_release": True,
                        "api_factory": lambda: provider, "music_generator": music,
                        "cover_generator": media.fake_cover, "renderer": media.fake_renderer}
                first, second = single.worker(**args), single.worker(**args)
            self.assertTrue(first["publication_complete"])
            self.assertEqual(first["video_id"], second["video_id"])
            self.assertEqual(1, len(calls))
            self.assertEqual(1, provider.inserts)
            self.assertEqual("public", provider.body["status"]["privacyStatus"])
            self.assertNotIn("publishAt", provider.body["status"])

    def test_daily_missing_proof_stops_before_worker(self):
        report = {"steps": [], "blockers": []}
        with fixture() as q, patch.object(single, "SingleQueue", return_value=q), \
             patch.object(today, "load_cost_estimate", side_effect=CredentialError("account_all_in_unverified")), \
             patch.object(daily, "check_new_single_inputs", return_value={}), \
             patch.object(daily, "run_step") as run:
            daily.run_today_single_slot(report)
        self.assertEqual(["account_all_in_unverified"], report["blockers"])
        self.assertFalse(report["single_slot"]["created_new_job"])
        run.assert_not_called()

    def test_coordinator_resume_skips_spend_and_remote_duplicate_gates(self):
        with fixture() as q:
            job = create_job(q)
            job["upload"] = {"video_id": "existing-fixture-id"}
            atomic_json(q.state_path, {"schema_version": 1, "jobs": {job["id"]: job}})
            report = {"steps": [], "blockers": []}
            with patch.object(single, "SingleQueue", return_value=q), \
                 patch.object(today, "load_cost_estimate", side_effect=CredentialError("expired")) as cost, \
                 patch.object(daily, "check_new_single_inputs") as sources, \
                 patch.object(single, "require_no_owned_title_match") as inventory, \
                 patch.object(daily, "run_step", return_value=(0, json.dumps({"status": "published", "video_id": "existing-fixture-id"}), "")) as worker, \
                 patch.object(daily, "sync_playlists_after_upload"):
                daily.run_today_single_slot(report)
            cost.assert_not_called()
            sources.assert_not_called()
            inventory.assert_not_called()
            worker.assert_called_once()
            self.assertEqual("existing-fixture-id", report["single_slot"]["video_id"])
            self.assertEqual([], report["blockers"])

if __name__ == "__main__":
    unittest.main()
