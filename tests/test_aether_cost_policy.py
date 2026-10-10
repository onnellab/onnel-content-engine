"""No actual paid transport, credentials, generation or upload in unit tests."""
from contextlib import ExitStack
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_audio_review
import aether_cover
import aether_cost_policy
import aether_daily_local
import aether_single
import lyria_generate
from short_video_credentials import CredentialError
from short_video_pipeline import VideoError, atomic_json, file_hash
import test_aether_single as fixtures


class PaidApiPolicyTests(unittest.TestCase):
    def test_other_paid_providers_remain_blocked_before_credentials_or_transport(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary)
            forbidden = []
            for module in (aether_cover, aether_audio_review):
                for name in ("access_token", "load_settings"):
                    forbidden.append(stack.enter_context(patch.object(module, name, side_effect=AssertionError("side effect"))))
            send = Mock(side_effect=AssertionError("transport"))
            calls = [
                lambda: aether_cover.generate_cover("T", "S", "quiet_road", root / "cover", execute=True, send=send, token="fixture"),
                lambda: aether_cover._request("project", "prompt", "fixture", send=send),
                lambda: aether_audio_review.review_audio(root / "missing.wav", "T", "S", "quiet_road", token="fixture", send=send),
                lambda: aether_cost_policy.require_paid_api_allowed(),
                lambda: aether_cost_policy.require_paid_api_allowed(purpose="gemini_audio_review", model="gemini-2.5-flash", candidate_count=1, estimated_cost_usd=0.08),
            ]
            for call in calls:
                with self.subTest(call=call), self.assertRaisesRegex(CredentialError, "aether_paid_api_disabled"):
                    call()
            self.assertEqual([], list(root.iterdir()))
            send.assert_not_called()
            for method in forbidden:
                method.assert_not_called()

    def test_only_one_lyria_3_pro_candidate_is_authorized_at_eight_cents(self):
        arguments = dict(purpose="lyria_3_pro_single", model="lyria-3-pro-preview",
                         candidate_count=1, estimated_cost_usd=0.08)
        self.assertIsNone(aether_cost_policy.require_paid_api_allowed(**arguments))
        for changes, message in (
            ({"model": "gemini-2.5-flash"}, "aether_paid_api_disabled"),
            ({"model": "lyria-3-clip-preview"}, "aether_paid_api_disabled"),
            ({"candidate_count": 2}, "aether_lyria_candidate_limit"),
            ({"estimated_cost_usd": 0.16}, "aether_lyria_spend_limit"),
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(CredentialError, message):
                aether_cost_policy.require_paid_api_allowed(**{**arguments, **changes})

    def test_daily_exhaustion_without_approved_cover_never_spends(self):
        report = {"blockers": [], "steps": []}
        now = datetime(2026, 10, 10, 6, 20, tzinfo=ZoneInfo("Asia/Seoul"))
        with patch.object(aether_daily_local, "now_kst", return_value=now), \
             patch.object(aether_daily_local, "run_step", return_value=(0, json.dumps({"status": "already_public"}), "")) as run, \
             patch.object(aether_daily_local, "choose_approved_new_single", return_value=None) as choose:
            aether_daily_local.run_single_slot(report, {"status": "idle"})
        choose.assert_called_once_with()
        self.assertEqual(len(aether_daily_local.BACKLOG), run.call_count)
        self.assertTrue(all("backlog-worker" in call.args[2] for call in run.call_args_list))
        self.assertEqual("aether_lyria_approved_cover_unavailable", report["single_slot"]["error"])
        self.assertEqual(0.0, report["single_slot"]["spent_usd"])

    def test_legacy_policies_unchanged_and_import_has_truthful_provider(self):
        self.assertEqual(aether_single.POLICY, aether_single.policy_for({}))
        old = {**aether_single.POLICY, "version": 2, "kind": "catalog_backlog_single", "music_provider": "canonical_wav_master"}
        self.assertEqual(old, aether_single.policy_for({"source_kind": "backlog_wav"}))
        new = aether_single.policy_for({"source_kind": "backlog_wav", "cover": {"source_kind": "existing_approved_cover"}})
        self.assertEqual("owner_approved_existing_cover", new["cover_provider"])

    def test_unfinished_reconcile_requires_cover_before_any_paid_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with patch.object(aether_single, "approved_cover", side_effect=VideoError("aether_single_cover_approval_missing")) as preflight, \
                 patch.object(lyria_generate, "access_token", side_effect=AssertionError("credentials")):
                with self.assertRaisesRegex(VideoError, "cover_approval_missing"):
                    aether_single.worker(root, slot="2099-10-10", title="A New Amber Crossing", style="Warm melodic fantasy crossing", lane="skybound_flight", execute=True)
                preflight.assert_called_once()
            state = json.loads((root / "queue.json").read_text())
            job = next(iter(state["jobs"].values()))
            job["publish_requested"] = True
            atomic_json(root / "queue.json", state)
            with patch.object(aether_single, "approved_cover", side_effect=VideoError("aether_single_cover_approval_missing")), \
                 patch.object(aether_single, "publish_slot_stale", return_value=False), \
                 patch.object(lyria_generate, "access_token", side_effect=AssertionError("credentials")):
                with self.assertRaisesRegex(VideoError, "cover_approval_missing"):
                    aether_single.worker(root, execute=True, publish=True, existing_only=True, api_factory=fixtures.Provider)
            self.assertEqual(1, len(json.loads((root / "queue.json").read_text())["jobs"]))

    def test_recovered_candidates_require_offline_review_without_paid_api(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with patch.object(aether_single, "approved_cover", side_effect=VideoError("aether_single_cover_approval_missing")):
                with self.assertRaisesRegex(VideoError, "cover_approval_missing"):
                    aether_single.worker(root, slot="2099-10-10", title="A New Amber Crossing", style="Warm melodic fantasy crossing", lane="skybound_flight", execute=True)
            state = json.loads((root / "queue.json").read_text())
            job = next(iter(state["jobs"].values()))
            folder = root / "jobs" / job["id"] / "lyria" / "run1"
            folder.mkdir(parents=True)
            audio = folder / "candidate.mp3"
            audio.write_bytes(b"x" * 4096)
            atomic_json(folder / "manifest.json", {"state": "generated", "candidates": [{"index": 1, "file": str(audio), "sha256": file_hash(audio)}]})
            with patch.object(aether_single, "audio_duration", return_value=184), \
                 patch.object(aether_single, "review_audio", return_value={
                     "accepted": False, "decision": "reject", "weighted_score": 0,
                     "reason_codes": ["audio_clipping"]}) as local_review, \
                 patch.object(aether_audio_review, "access_token", side_effect=AssertionError("credentials")):
                with self.assertRaisesRegex(Exception, "aether_single_no_accepted_candidate"):
                    aether_single.worker(root, execute=True, slot="2099-10-10")
                local_review.assert_called_once_with(audio)

    def test_uploaded_reconcile_never_regenerates_missing_sources(self):
        fixture = fixtures.SingleTests()
        api = fixtures.Provider()
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(aether_single, "publish_slot_stale", return_value=False), \
             patch.object(aether_single, "audio_duration", return_value=138), \
             patch.object(aether_single, "review_audio", side_effect=lambda path, **_: {
                 "accepted": True, "state": "accepted", "source_sha256": file_hash(path)}), \
             patch.object(aether_single, "find_existing_public_video", return_value=None), \
             patch.object(aether_single, "validate_output", return_value=138):
            root = Path(temporary).resolve()
            source = root / "master.wav"
            source.write_bytes(b"RIFF" + b"x" * 4096)
            first = aether_single.backlog_worker(root / "queue", slot="2099-10-10", title="Beyond the Road of Falling Petals", source_wav=source, execute=True, publish=True, api_factory=lambda: api, cover_generator=fixture.fake_cover, renderer=fixture.fake_renderer)
            state_path = root / "queue" / "queue.json"
            state = json.loads(state_path.read_text())
            job = state["jobs"][first["job_id"]]
            saved_approval, saved_result = dict(job["approval"]), dict(job["result"])
            job["music"] = None
            job["cover"] = None
            atomic_json(state_path, state)
            never = Mock(side_effect=AssertionError("production"))
            second = aether_single.worker(root / "queue", execute=True, publish=True, existing_only=True, api_factory=lambda: api, music_generator=never, cover_generator=never, renderer=never)
            self.assertEqual(first["video_id"], second["video_id"])
            self.assertEqual(1, api.inserts)
            never.assert_not_called()
            after = json.loads(state_path.read_text())["jobs"][first["job_id"]]
            self.assertEqual(saved_approval, after["approval"])
            self.assertEqual(saved_result, after["result"])
            (root / "queue" / "jobs" / first["job_id"] / "video.mp4").write_bytes(b"corrupt")
            with self.assertRaisesRegex(Exception, "render_integrity"):
                aether_single.worker(root / "queue", execute=True, publish=True, existing_only=True, api_factory=lambda: api, music_generator=never, cover_generator=never, renderer=never)
            self.assertEqual(1, api.inserts)


if __name__ == "__main__":
    unittest.main()
