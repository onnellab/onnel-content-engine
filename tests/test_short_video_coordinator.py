import copy
import base64
import json
import io
import subprocess
from datetime import datetime, timezone
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from short_video_coordinator import CASConflict, CoordinationError, Coordinator, GitHubLedger, eligible_apps, next_slot, plan

CHANNEL = "UC" + "a" * 22
NOW = datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc)
SLOT = "2026-10-05T09:00:00+09:00"
HASH = "a" * 64
CONFIG = {"schema_version": 1, "enabled": True, "repository": "onnellab/onnel-content-engine", "branch": "shorts-coordination-state", "path": "shorts/ledger.json", "channel_id": CHANNEL, "owner_id": "windows-n", "legacy_writer_fencing": {"confirmed": True, "evidence": "operator-confirmed migration record"}}
APPS = [{"app_id": "APP-0001", "scenario_id": "one"}, {"app_id": "APP-0002", "scenario_id": "two"}]


class MemoryStore:
    def __init__(self):
        self.data = {"schema_version": 1, "slots": {}}
        self.revision = 0
        self.writes = 0
        self.race = None

    def read(self):
        return copy.deepcopy(self.data), str(self.revision)

    def compare_and_swap(self, expected, data):
        if self.race:
            race, self.race = self.race, None
            race()
        if str(self.revision) != expected:
            raise CASConflict("changed")
        self.data = copy.deepcopy(data)
        self.revision += 1
        self.writes += 1


class CoordinatorTest(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.coordinator = Coordinator(self.store, CONFIG, clock=lambda: NOW)

    def receipt(self):
        return {"video_id": "abcdefghijk", "posted_url": "https://www.youtube.com/shorts/abcdefghijk", "channel_id": CHANNEL, "privacy_status": "public", "upload_status": "processed", "processing_status": "succeeded", "verified_at": NOW.isoformat(), "published_at": NOW.isoformat()}

    def test_unfenced_legacy_writer_blocks_claim_without_any_write(self):
        config = copy.deepcopy(CONFIG)
        config["legacy_writer_fencing"]["confirmed"] = False
        with self.assertRaisesRegex(CoordinationError, "legacy_writer_not_fenced"):
            Coordinator(self.store, config, clock=lambda: NOW).claim(SLOT, APPS[0], HASH)
        self.assertEqual(self.store.writes, 0)

    def test_cas_race_cannot_claim_same_channel_slot_twice(self):
        config = dict(CONFIG, owner_id="other-cooperating-host")
        other = Coordinator(self.store, config, clock=lambda: NOW)
        self.store.race = lambda: other.claim(SLOT, APPS[1], HASH)
        with self.assertRaisesRegex(CoordinationError, "slot_owned"):
            self.coordinator.claim(SLOT, APPS[0], HASH)
        self.assertEqual(len(self.store.data["slots"]), 1)
        self.assertEqual(self.store.writes, 1)

    def test_same_owner_is_idempotent_but_payload_is_immutable(self):
        self.coordinator.claim(SLOT, APPS[0], HASH)
        self.coordinator.claim(SLOT, APPS[0], HASH)
        self.assertEqual(self.store.writes, 1)
        with self.assertRaisesRegex(CoordinationError, "immutable_payload"):
            self.coordinator.claim(SLOT, APPS[0], "b" * 64)

    def test_same_host_different_local_queue_nonce_cannot_share_a_claim(self):
        self.coordinator.claim(SLOT, APPS[0], HASH)
        another_root = Coordinator(self.store, CONFIG, clock=lambda: NOW)
        with self.assertRaisesRegex(CoordinationError, "slot_owned"):
            another_root.claim(SLOT, APPS[0], HASH)
        with self.assertRaisesRegex(CoordinationError, "slot_owned"):
            another_root.mark_upload_started(SLOT, HASH)
        recovered = Coordinator(self.store, CONFIG, clock=lambda: NOW, claim_token=self.coordinator.claim_token)
        recovered.claim(SLOT, APPS[0], HASH)
        self.assertEqual(self.store.writes, 1)

    def test_ambiguous_upload_never_becomes_new_claim_and_blocks_other_slots(self):
        self.coordinator.claim(SLOT, APPS[0], HASH)
        self.coordinator.mark_upload_started(SLOT, HASH)
        self.coordinator.mark_reconcile_required(SLOT, HASH)
        with self.assertRaisesRegex(CoordinationError, "reconcile_required"):
            self.coordinator.claim(SLOT, APPS[0], HASH)
        later = Coordinator(self.store, CONFIG, clock=lambda: datetime(2026, 10, 7, 0, 0, tzinfo=timezone.utc))
        with self.assertRaisesRegex(CoordinationError, "channel_has_unresolved_slot"):
            later.claim("2026-10-07T09:00:00+09:00", APPS[1], HASH)

    def test_complete_requires_real_permalink_matching_provider_identity(self):
        self.coordinator.claim(SLOT, APPS[0], HASH)
        self.coordinator.mark_upload_started(SLOT, HASH)
        for update in ({"posted_url": "https://www.youtube.com/@onnellab"}, {"channel_id": "UC" + "b" * 22}, {"privacy_status": "private"}, {"video_id": "xxxxxxxxxxx"}):
            with self.subTest(update=update), self.assertRaises(CoordinationError):
                self.coordinator.complete(SLOT, HASH, dict(self.receipt(), **update))
        self.coordinator.complete(SLOT, HASH, self.receipt())
        writes = self.store.writes
        self.coordinator.complete(SLOT, HASH, self.receipt())
        self.assertEqual(writes, self.store.writes)
        changed = dict(self.receipt(), video_id="xxxxxxxxxxx", posted_url="https://youtu.be/xxxxxxxxxxx")
        with self.assertRaisesRegex(CoordinationError, "receipt_conflict"):
            self.coordinator.complete(SLOT, HASH, changed)

    def test_rotation_uses_completed_shared_receipts_not_claims(self):
        self.coordinator.claim(SLOT, APPS[0], HASH)
        blocked = plan(CONFIG, self.store.data, APPS, NOW)
        self.assertIn("channel_has_unresolved_slot", blocked["blockers"])
        self.coordinator.mark_upload_started(SLOT, HASH)
        self.coordinator.complete(SLOT, HASH, self.receipt())
        result = plan(CONFIG, self.store.data, APPS, datetime(2026, 10, 7, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(result["selected_app"]["app_id"], "APP-0002")

    def test_mwf_nine_kst_is_fixed_and_future_slots_cannot_be_claimed(self):
        self.assertEqual(next_slot(datetime(2026, 10, 4, 0, 0, tzinfo=timezone.utc)), SLOT)
        self.assertEqual(next_slot(NOW), SLOT)
        self.assertEqual(next_slot(datetime(2026, 10, 6, 0, 0, tzinfo=timezone.utc)), "2026-10-07T09:00:00+09:00")
        with self.assertRaisesRegex(CoordinationError, "slot_not_due"):
            self.coordinator.claim("2026-10-07T09:00:00+09:00", APPS[0], HASH)
        with self.assertRaisesRegex(CoordinationError, "timezone_aware_clock_required"):
            next_slot(datetime(2026, 10, 5, 9, 0))

    def test_non_state_branch_is_rejected(self):
        with self.assertRaisesRegex(CoordinationError, "dedicated_state_branch_required"):
            Coordinator(self.store, dict(CONFIG, branch="main"), clock=lambda: NOW)

    def test_github_transport_reads_state_branch_and_writes_with_exact_sha(self):
        calls = []
        sha = "f" * 40
        def run(args, **kwargs):
            calls.append((args, kwargs))
            payload = {"sha": sha, "content": base64.b64encode(json.dumps(self.store.data).encode()).decode()}
            return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
        store = GitHubLedger(CONFIG, run=run)
        ledger, revision = store.read()
        self.assertEqual(revision, sha)
        self.assertIn("?ref=shorts-coordination-state", calls[0][0][-1])
        store.compare_and_swap(revision, ledger)
        sent = json.loads(calls[1][1]["input"])
        self.assertEqual(sent["sha"], sha)
        self.assertEqual(sent["branch"], "shorts-coordination-state")
        self.assertEqual(json.loads(base64.b64decode(sent["content"])), ledger)
        self.assertEqual(calls[1][0][-2:], ["--input", "-"])

    def test_missing_or_contended_ledger_does_not_become_empty_state(self):
        for status, expected in ((404, CoordinationError), (409, CASConflict)):
            with self.subTest(status=status):
                store = GitHubLedger(CONFIG, run=lambda args, **kw: subprocess.CompletedProcess(args, 1, "", f"HTTP {status}"))
                with self.assertRaises(expected):
                    store.read()

    def test_disabled_configuration_cannot_mutate_and_schedule_is_not_activated(self):
        with self.assertRaisesRegex(CoordinationError, "coordinator_disabled"):
            Coordinator(self.store, dict(CONFIG, enabled=False), clock=lambda: NOW).claim(SLOT, APPS[0], HASH)
        self.assertEqual(self.store.writes, 0)

    def test_lost_upload_intent_ack_never_allows_another_claim(self):
        self.coordinator.claim(SLOT, APPS[0], HASH)
        original = self.store.compare_and_swap
        def lost_ack(expected, ledger):
            original(expected, ledger)
            raise CoordinationError("shared_ledger_request_failed")
        self.store.compare_and_swap = lost_ack
        with self.assertRaisesRegex(CoordinationError, "request_failed"):
            self.coordinator.mark_upload_started(SLOT, HASH)
        self.assertEqual(next(iter(self.store.data["slots"].values()))["status"], "uploading")
        with self.assertRaisesRegex(CoordinationError, "reconcile_required"):
            self.coordinator.claim(SLOT, APPS[0], HASH)

    def test_rotation_requires_positive_store_snapshot_and_reports_missing_coverage(self):
        registry = "app_id,app_name,status,content_eligible,platforms,app_store_url,play_store_url\nAPP-0001,Quivra,released,true,android,,https://play.google.com/store/apps/details?id=one\nAPP-0008,Papira,released,true,ios|android,https://apps.apple.com/app/id1,https://play.google.com/store/apps/details?id=eight\nAPP-0007,Melivra,released,true,android,,https://play.google.com/store/apps/details?id=seven\n"
        stores = "app_id,platform,store_url,status,version\nAPP-0001,android,https://play.google.com/store/apps/details?id=one,unchanged,1.0\nAPP-0008,ios,https://apps.apple.com/app/id1,updated,2.0\nAPP-0008,android,https://play.google.com/store/apps/details?id=eight,manual_check,\nAPP-0007,android,https://play.google.com/store/apps/details?id=seven,unchanged,1.0\n"
        scenarios = {"scenarios": [{"app_id": app, "scenario_id": app, "platforms": ["android_emulator"], "production_eligible": True} for app in ("APP-0001", "APP-0008")]}
        sources = {"apps_registry.csv": registry, "store_versions.csv": stores, "video_recording_scenarios.json": json.dumps(scenarios)}
        def open_fixture(path, *args, **kwargs):
            return io.StringIO(sources[path.name])
        with patch.object(Path, "open", open_fixture):
            apps, coverage = eligible_apps(Path("fixture"))
        self.assertEqual([app["app_id"] for app in apps], ["APP-0001"])
        papira = next(row for row in coverage if row["app_id"] == "APP-0008")
        self.assertEqual(papira["released_platforms"], ["ios"])
        self.assertIn("no_released_host_platform_store_evidence", papira["blockers"])
        self.assertIn("recording_scenario_missing", next(row for row in coverage if row["app_id"] == "APP-0007")["blockers"])


if __name__ == "__main__":
    unittest.main()
